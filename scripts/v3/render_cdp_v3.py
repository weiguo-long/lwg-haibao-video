# -*- coding: utf-8 -*-
"""
v3「字幕即页脚」成片渲染器：CDP 确定性逐帧 + ffmpeg image2pipe。

帧源 = animation-v3/preview.html?capture=1（与用户确认的动画预览同一个文件，
不是另做一份 render.html），因此预览里看到的画面 = 成片画面。
每帧按 frame/fps 调 window.__seekTo(t)，再 Page.captureScreenshot 取 JPEG；
画面静止时复用上一帧，入场 / 字幕淡入 / 字幕换句 / 切场时才真正截图。

与旧 render_cdp.py 的两处关键差异：
1) state_key 增加「字幕淡入期」——否则字幕切换后 0.18s 的淡入会被冻结在
   第一帧（约 30% 不透明度），整句字幕都以半透明显示。
2) 固定设备视口后重算 buildPlans()，保证入场排序与 1080x1440 布局一致。

用法: python3 render_cdp_v3.py [输出.mp4]
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.dirname(HERE)
VOICE_DIR = os.path.join(OUT_DIR, "voice-animation")
FRAME_SRC = os.path.join(HERE, "preview.html")
AUDIO = os.path.join(VOICE_DIR, "voiceover-full.mp3")
TIMELINE = json.load(open(os.path.join(VOICE_DIR, "timeline.json"), encoding="utf-8"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH, HEIGHT = 1080, 1440
FPS = TIMELINE["fps"]
TOTAL = TIMELINE["totalFrames"]
if len(sys.argv) > 2 and sys.argv[2].isdigit():
    TOTAL = min(TOTAL, int(sys.argv[2]))   # 冒烟测试用：只渲前 N 帧
SUB_FADE = 0.18          # 与 preview.html 的 SUB_FADE 一致
ENTER_WINDOW = 2.0       # 长于最长入场（约 1.735s）

OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(OUT_DIR, "成片.mp4")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def ffmpeg_bin():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        path = shutil.which("ffmpeg")
        if not path:
            raise RuntimeError("找不到 ffmpeg")
        return path


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60,
                                              suppress_origin=True)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        ident = self.n
        self.ws.send(json.dumps({"id": ident, "method": method,
                                 "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == ident:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def eval(self, expr):
        r = self.call("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True,
                       "awaitPromise": False})
        return r.get("result", {}).get("value")


def state_key(t, frame):
    """画面状态；相同状态复用上一帧 JPEG。
    必须把「入场」和「字幕淡入」都算作逐帧变化，否则动画会被冻结。"""
    idx = 0
    for i, s in enumerate(TIMELINE["scenes"]):
        if t >= s["start"]:
            idx = i
    scene = TIMELINE["scenes"][idx]
    sub, sub_start = "", None
    for c in scene.get("subtitles", []):
        if c["start"] <= t < c["end"]:
            sub = c.get("id", str(c["start"]))
            sub_start = c["start"]
            break
    entering = idx > 0 and (t - scene["start"]) < ENTER_WINDOW
    fading = sub_start is not None and (t - sub_start) < SUB_FADE
    return (idx, sub, frame if (entering or fading) else -1)


def main():
    port = free_port()
    url = "file://" + urllib.parse.quote(FRAME_SRC) + "?capture=1"
    chrome = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", "--force-device-scale-factor=1",
        "--disable-background-timer-throttling", "--no-first-run",
        "--remote-allow-origins=*",
        "--remote-debugging-port=%d" % port,
        "--user-data-dir=/tmp/chrome-v3-render-%d" % port,
        "--window-size=%d,%d" % (WIDTH, HEIGHT),
        url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/json" % port, timeout=2) as r:
                    pages = json.load(r)
                for p in pages:
                    if p.get("type") == "page" and "preview.html" in p.get("url", ""):
                        ws_url = p["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
            except Exception:
                time.sleep(0.4)
        if not ws_url:
            raise RuntimeError("Chrome DevTools 未就绪")

        c = CDP(ws_url)
        c.call("Page.enable")
        c.call("Runtime.enable")
        # 不固定视口会得到 1080x(1440-一截) 的拉伸帧
        c.call("Emulation.setDeviceMetricsOverride", {
            "width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1,
            "mobile": False,
        })
        for _ in range(80):
            if c.eval("window.__ready === true"):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("帧源未就绪")
        # 固定视口后重算入场排序，保证与验收帧一致
        c.eval("buildPlans()")
        print("帧源就绪 | 视口 %dx%d | 入场单元: %s" %
              (WIDTH, HEIGHT, c.eval("document.body.dataset.units")), flush=True)

        cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
               "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "mjpeg",
               "-i", "pipe:0", "-i", AUDIO,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", OUT]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        last_key, last_jpg, shots = None, None, 0
        t0 = time.time()
        try:
            for frame in range(TOTAL):
                t = frame / FPS
                key = state_key(t, frame)
                c.eval("window.__seekTo(%.6f)" % t)
                if key != last_key:
                    r = c.call("Page.captureScreenshot", {
                        "format": "jpeg", "quality": 90,
                        "captureBeyondViewport": False, "fromSurface": True})
                    last_jpg = base64.b64decode(r["data"])
                    last_key = key
                    shots += 1
                enc.stdin.write(last_jpg)
                if frame % 600 == 0:
                    print("  %4d/%d 帧 | 截图 %d | %.0fs" %
                          (frame, TOTAL, shots, time.time() - t0), flush=True)
        finally:
            enc.stdin.close()
            err = enc.stderr.read().decode("utf-8", "replace")
            code = enc.wait()
            c.ws.close()
        if code != 0:
            raise RuntimeError("ffmpeg 失败(%d): %s" % (code, err[-2000:]))
        print("完成: %s | %d 帧 / %d 次截图 | %.1fs | %.1f MB" %
              (OUT, TOTAL, shots, time.time() - t0,
               os.path.getsize(OUT) / 1024 / 1024), flush=True)
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except Exception:
            chrome.kill()


if __name__ == "__main__":
    main()

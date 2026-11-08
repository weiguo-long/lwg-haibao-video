# -*- coding: utf-8 -*-
"""
确定性逐帧渲染器（Remotion 之外的等价渲染链路，也是成片兜底）。

帧源 = remotion/public/render.html，与用户确认的 preview.html 共用 DOM/CSS/timeline。
用 Chrome DevTools Protocol 保持单个浏览器实例，按 frame/fps 调用 __seekTo(t) 后截帧；
画面静止时复用上一帧（只有字幕切换、场景切换、入场动画期间才真正截图），
再把 JPEG 流通过管道交给 ffmpeg 编码 H.264 + AAC。

用法: python3 render_cdp.py [输出.mp4]
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.dirname(HERE)
FRAME_SRC = os.path.join(PAGES, "remotion", "public", "render.html")
AUDIO = os.path.join(HERE, "voiceover-full.mp3")
TIMELINE = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333
WIDTH = TIMELINE.get("width", 1080)
HEIGHT = TIMELINE.get("height", 1440)
FPS = TIMELINE["fps"]
TOTAL = TIMELINE["totalFrames"]
ENTER = TIMELINE.get("enterAnimation", {})
# 入场期结束后画面静止，可复用上一帧
ENTER_WINDOW = ((ENTER.get("maxGroups", 18) - 1) * ENTER.get("step", 0.075)
                + ENTER.get("duration", 0.46) + 0.3)

OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(PAGES, "成片.mp4")


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=45,
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
    """返回画面状态；相同状态直接复用上一帧，避免 6113 次重复截图。"""
    idx = 0
    for i, s in enumerate(TIMELINE["scenes"]):
        if t >= s["start"]:
            idx = i
    sub = ""
    for c in TIMELINE["scenes"][idx].get("subtitles", []):
        if c["start"] <= t < c["end"]:
            sub = c["id"]
            break
    # 入场期间每帧都在变化；窗口结束后所有页都已铺完
    entering = idx > 0 and (t - TIMELINE["scenes"][idx]["start"]) < ENTER_WINDOW
    return (idx, sub, frame if entering else -1)


def main():
    profile = "/tmp/chrome-price-render-%d" % int(time.time())
    chrome = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--hide-scrollbars", "--force-device-scale-factor=1",
        "--disable-background-timer-throttling", "--no-first-run",
        "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=" + profile,
        "--window-size=%d,%d" % (WIDTH, HEIGHT),
        "file://" + FRAME_SRC,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(120):
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/json" % PORT, timeout=2) as r:
                pages = json.load(r)
            for p in pages:
                if p.get("type") == "page" and "render.html" in p.get("url", ""):
                    ws_url = p["webSocketDebuggerUrl"]
                    break
            if ws_url:
                break
        except Exception:
            time.sleep(0.4)
    if not ws_url:
        chrome.terminate()
        raise RuntimeError("Chrome DevTools 未就绪")

    c = CDP(ws_url)
    c.call("Page.enable")
    c.call("Runtime.enable")
    c.call("Emulation.setDeviceMetricsOverride", {
        "width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1,
        "mobile": False,
    })
    for _ in range(60):
        if c.eval("window.__frameReady === true"):
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("帧源未就绪")
    print("帧源就绪 | 入场单元:", c.eval("window.__units"), flush=True)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
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
            c.eval("window.__seekTo(% .6f)" % t)
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
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except Exception:
            chrome.kill()
    if code != 0:
        raise RuntimeError("ffmpeg 失败(%d): %s" % (code, err[-2000:]))
    print("完成: %s | %d 帧 / %d 次截图 | %.1fs | %.1f MB" %
          (OUT, TOTAL, shots, time.time() - t0,
           os.path.getsize(OUT) / 1024 / 1024), flush=True)


if __name__ == "__main__":
    main()

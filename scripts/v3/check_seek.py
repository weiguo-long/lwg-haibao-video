# -*- coding: utf-8 -*-
"""验证 preview.html 的确定性帧接口 window.__seekTo(t)：
同一 t 反复 seek 得到同一画面，且场景 / 字幕 / 入场状态完全由 t 决定。
这是后续逐帧出片（CDP captureScreenshot + ffmpeg）能不能直接复用预览页的门槛检查。
"""
import base64
import json
import os
import socket
import subprocess
import time
import urllib.parse

import requests
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    port = free_port()
    url = "file://" + urllib.parse.quote(os.path.join(HERE, "preview.html")) + "?capture=1"
    proc = subprocess.Popen([
        CHROME, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--remote-allow-origins=*",
        "--remote-debugging-port=%d" % port,
        "--user-data-dir=/tmp/wb-v3-cdp-%d" % port,
        "--window-size=900,1200", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        pages = None
        target = None
        for _ in range(80):
            try:
                pages = requests.get("http://127.0.0.1:%d/json" % port, timeout=1).json()
                cand = [p for p in pages
                        if p.get("type") == "page" and "preview.html" in p.get("url", "")]
                if cand:
                    target = cand[0]
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not target:
            print("targets:", [(p.get("type"), p.get("url")) for p in (pages or [])])
            raise RuntimeError("preview.html target not found")
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20)
        seq = [0]

        def ev(expr):
            seq[0] += 1
            ws.send(json.dumps({
                "id": seq[0], "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True},
            }))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == seq[0]:
                    res = msg["result"]["result"]
                    if "exceptionDetails" in msg.get("result", {}):
                        raise RuntimeError(str(msg["result"]["exceptionDetails"]))
                    return res.get("value")

        def state(t):
            ev("window.__seekTo(%f)" % t)
            return ev("""(()=>{
              const a=document.querySelector('.scene.active');
              const l=a?a.querySelector('.subline'):null;
              return JSON.stringify({scene:a?a.id:'',sub:l?l.textContent:'',
                subOpacity:l?l.style.opacity:'',active:document.querySelectorAll('.scene.active').length,
                chapter:document.getElementById('chapter').textContent});
            })()""")

        for _ in range(60):
            if ev("typeof window.__seekTo") == "function":
                break
            time.sleep(0.25)
        else:
            print("DIAG", ev("JSON.stringify({ready:document.readyState,title:document.title,"
                             "units:document.body.dataset.units,"
                             "scenes:document.querySelectorAll('.scene').length,"
                             "tl:typeof TIMELINE,seek:typeof window.__seekTo})"))
            raise RuntimeError("__seekTo never became available")
        print("__ready =", ev("window.__ready"), "| __seekTo =", ev("typeof window.__seekTo"))
        print("入场单元数 =", ev("document.body.dataset.units"))

        probe = """(()=>{let s='';document.querySelectorAll('.scene').forEach(x=>{
          s+=(x.classList.contains('active')?'A':'-')});return s})()"""
        # 期望值从 timeline 动态推导，换项目不用改这里的硬编码文本
        TL = json.load(open(os.path.join(os.path.dirname(HERE),
                                        "voice-animation", "timeline.json"),
                            encoding="utf-8"))
        checks = []
        for i, s in enumerate(TL["scenes"], 1):
            t = s["start"] + min(2.0, (s["end"] - s["start"]) / 3)
            want = next((c["text"] for c in s["subtitles"]
                         if c["start"] <= t < c["end"]), "")
            if want:
                checks.append((t, "s%d" % i, want))
        ok = True
        for t, want_scene, want_sub in checks:
            a = json.loads(state(t))
            b = json.loads(state(t))  # 同一 t 再 seek 一次，应完全一致
            same = (a == b)
            good = (a["scene"] == want_scene and a["sub"] == want_sub
                    and a["active"] == 1 and same)
            ok &= good
            print("t=%7.2f  %-3s sub=%-24s active=%d repeat=%s  %s"
                  % (t, a["scene"], a["sub"][:24], a["active"], same,
                     "OK" if good else "FAIL"))
        # 句间空档：文字必须保留（占位不塌），只是 opacity 归零
        blank_t = TL["scenes"][0]["end"] + 0.40
        blank = json.loads(state(blank_t))
        good_blank = (blank["scene"] == "s1" and len(blank["sub"]) > 0
                      and blank["subOpacity"] == "0")
        ok &= good_blank
        print("句间空档 t=%.2f: sub=%-20s opacity=%s  %s" %
              (blank_t, blank["sub"][:20], blank["subOpacity"],
               "OK" if good_blank else "FAIL"))
        # 入场态也必须是 t 的纯函数
        e1 = ev("window.__seekTo(8.60);" + probe)
        ev("window.__seekTo(10.50)")
        e2 = ev("window.__seekTo(8.60);" + probe)
        print("入场景状态可复现:", e1 == e2, e1)
        ok &= (e1 == e2)

        # 出片前必须固定视口尺寸：headless 默认 viewport 高比 --window-size 少一截，
        # 不固定会得到 900x1057 的拉伸帧。
        seq[0] += 1
        ws.send(json.dumps({
            "id": seq[0], "method": "Emulation.setDeviceMetricsOverride",
            "params": {"width": 900, "height": 1200, "deviceScaleFactor": 1, "mobile": False},
        }))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == seq[0]:
                break
        # 与 preview.html?capture=1&t=<同一时间> 的截图逐像素比对，应完全一致
        ev("buildPlans();window.__seekTo(%.6f)" % checks[0][0])
        seq[0] += 1
        ws.send(json.dumps({
            "id": seq[0], "method": "Page.captureScreenshot",
            "params": {"format": "png", "captureBeyondViewport": False},
        }))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == seq[0]:
                data = base64.b64decode(msg["result"]["data"])
                break
        os.makedirs(os.path.join(HERE, "frames"), exist_ok=True)
        shot = os.path.join(HERE, "frames", "cdp-seek.png")
        open(shot, "wb").write(data)
        print("CDP 帧:", shot, len(data), "bytes")
        print("RESULT:", "PASS" if ok else "FAIL")
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()

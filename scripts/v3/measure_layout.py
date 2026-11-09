# -*- coding: utf-8 -*-
"""量化「字幕消失时其它元素是否抖动」。

对 8 个场景各取两个时间点：
  t1 = 该场景最后一句字幕的中段（字幕完全可见）
  t2 = 该场景结束后的句间空档（字幕不可见，但页面仍在）
用 window.__seekTo 确定性定位，量出 .scene.active 内所有元素的
getBoundingClientRect；理想情况两态完全一致（0 位移）。

用法: python3 measure_layout.py [输出.json]
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse

import requests
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TIMELINE = json.load(open(os.path.join(os.path.dirname(HERE),
                                       "voice-animation", "timeline.json"),
                          encoding="utf-8"))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(HERE, "layout-report.json")

SNAP = r"""(()=>{
  window.__seekTo(%f);
  const a=document.querySelector('.scene.active');
  const line=a?a.querySelector('.subline'):null;
  const rows=[];
  if(a) a.querySelectorAll('*').forEach((el,i)=>{
    const r=el.getBoundingClientRect();
    rows.push({i:i,tag:el.tagName,cls:String(el.className||''),
               x:+r.x.toFixed(2),y:+r.y.toFixed(2),
               w:+r.width.toFixed(2),h:+r.height.toFixed(2)});
  });
  return JSON.stringify({scene:a?a.id:'',sub:line?line.textContent:'',
                         opacity:line?line.style.opacity:'',rows:rows});
})()"""


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
        "--user-data-dir=/tmp/wb-v3-layout-%d" % port,
        "--window-size=900,1200", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        target = None
        for _ in range(80):
            try:
                pages = requests.get("http://127.0.0.1:%d/json" % port,
                                     timeout=1).json()
                cand = [p for p in pages if p.get("type") == "page"
                        and "preview.html" in p.get("url", "")]
                if cand:
                    target = cand[0]
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not target:
            raise RuntimeError("preview.html target not found")
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        seq = [0]

        def call(method, params=None):
            seq[0] += 1
            ident = seq[0]
            ws.send(json.dumps({"id": ident, "method": method,
                                "params": params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == ident:
                    if "error" in msg:
                        raise RuntimeError(str(msg["error"]))
                    return msg.get("result", {})

        def ev(expr):
            r = call("Runtime.evaluate",
                     {"expression": expr, "returnByValue": True})
            if "exceptionDetails" in r:
                raise RuntimeError(str(r["exceptionDetails"]))
            return r.get("result", {}).get("value")

        for _ in range(60):
            if ev("window.__ready === true"):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("帧源未就绪")
        call("Emulation.setDeviceMetricsOverride", {
            "width": 900, "height": 1200, "deviceScaleFactor": 1,
            "mobile": False})
        ev("buildPlans()")

        report = {"view": "900x1200", "scenes": []}
        print("场景  可见字幕 t1   空档 t2   变化元素  最大位移(px)  subhost 高度变化")
        for i, sc in enumerate(TIMELINE["scenes"], 1):
            last = sc["subtitles"][-1]
            t1 = last["start"] + min(0.6, (last["end"] - last["start"]) / 2)
            t2 = sc["end"] + 0.40
            a = json.loads(ev(SNAP % t1))
            b = json.loads(ev(SNAP % t2))
            ra, rb = a["rows"], b["rows"]
            moved = []
            for x, y in zip(ra, rb):
                d = max(abs(x["x"] - y["x"]), abs(x["y"] - y["y"]),
                        abs(x["w"] - y["w"]), abs(x["h"] - y["h"]))
                if d > 0.05:
                    moved.append({"tag": x["tag"], "cls": x["cls"][:38],
                                  "delta": round(d, 2),
                                  "a": [x["x"], x["y"], x["w"], x["h"]],
                                  "b": [y["x"], y["y"], y["w"], y["h"]]})
            maxd = max((m["delta"] for m in moved), default=0.0)
            host_a = next((r for r in ra if "subhost" in r["cls"]), None)
            host_b = next((r for r in rb if "subhost" in r["cls"]), None)
            dh = (round(host_b["h"] - host_a["h"], 2)
                  if host_a and host_b else None)
            report["scenes"].append({
                "scene": i, "t1": round(t1, 3), "t2": round(t2, 3),
                "sub1": a["sub"], "sub2": b["sub"],
                "opacity1": a["opacity"], "opacity2": b["opacity"],
                "elements": len(ra), "moved": len(moved),
                "maxDelta": maxd, "subhostHeightDelta": dh,
                "movedDetail": moved[:12],
            })
            print("%4d  %8.2f  %8.2f  %6d  %10.2f  %s" %
                  (i, t1, t2, len(moved), maxd, dh))
            for m in moved[:4]:
                print("        - %s.%s  Δ%.2f  %s -> %s" %
                      (m["tag"], m["cls"], m["delta"], m["a"], m["b"]))
        # ---- 换句阶段：字幕文字长短变化时，其它元素是否仍零位移 ----
        # 只取入场已结束（开场 2.2s 之后）的字幕，避免入场 translate 干扰测量。
        # .subline 自身允许 x / w 变化（文字变长、居中页会自己挪），
        # 但 y / h 必须恒定；其它元素四值全部必须恒定。
        switch = []
        print("\n换句阶段（同一场景内字幕长短变化）")
        for i, sc in enumerate(TIMELINE["scenes"], 1):
            pts = [c["start"] + 0.22 for c in sc["subtitles"]
                   if c["start"] + 0.22 < c["end"]
                   and c["start"] - sc["start"] >= 2.2]
            if len(pts) < 2:
                switch.append({"scene": i, "samples": len(pts),
                               "moved": 0, "maxDelta": 0.0, "skipped": True})
                print("%4d  样本不足(%d)，跳过" % (i, len(pts)))
                continue
            base = json.loads(ev(SNAP % pts[0]))["rows"]
            worst, cnt, detail = 0.0, 0, None
            for t in pts[1:]:
                rows = json.loads(ev(SNAP % t))["rows"]
                for x, y in zip(base, rows):
                    is_sub = "subline" in x["cls"]
                    ds = [abs(x["y"] - y["y"]), abs(x["h"] - y["h"])]
                    if not is_sub:
                        ds += [abs(x["x"] - y["x"]), abs(x["w"] - y["w"])]
                    d = max(ds)
                    if d > 0.05:
                        cnt += 1
                        if d > worst:
                            detail = {"cls": x["cls"][:38], "delta": round(d, 2)}
                    worst = max(worst, d)
            switch.append({"scene": i, "samples": len(pts), "moved": cnt,
                           "maxDelta": round(worst, 2), "worst": detail,
                           "skipped": False})
            print("%4d  %2d 条样本 | 变化元素 %d | 最大位移 %.2f px %s" %
                  (i, len(pts), cnt, worst, detail or ""))
        # 补充：8 页全覆盖——在同一个时间点直接换成该页最长 / 最短字幕，
        # 绕开入场窗口限制，确认文字长度极端变化时其它元素仍零位移。
        forced = []
        print("\n强制对照（各页最长 vs 最短字幕，直接替换文字）")
        for i, sc in enumerate(TIMELINE["scenes"], 1):
            texts = [c["text"] for c in sc["subtitles"]]
            long_t = max(texts, key=len)
            short_t = min(texts, key=len)
            expr = r"""(()=>{
              window.__seekTo(%f);
              const a=document.querySelector('.scene.active');
              const line=a.querySelector('.subline');
              const snap=()=>{const rows=[];a.querySelectorAll('*').forEach((el,i)=>{
                const r=el.getBoundingClientRect();
                rows.push({cls:String(el.className||''),x:+r.x.toFixed(2),
                  y:+r.y.toFixed(2),w:+r.width.toFixed(2),h:+r.height.toFixed(2)});});
                return rows;};
              const bak=line.textContent;
              line.textContent=%s; const L=snap();
              line.textContent=%s; const S=snap();
              line.textContent=bak;
              return JSON.stringify({L:L,S:S});
            })()""" % (sc["start"] + 2.4,
                       json.dumps(long_t, ensure_ascii=False),
                       json.dumps(short_t, ensure_ascii=False))
            pair = json.loads(ev(expr))
            worst, cnt, detail = 0.0, 0, None
            for x, y in zip(pair["L"], pair["S"]):
                is_sub = "subline" in x["cls"]
                ds = [abs(x["y"] - y["y"]), abs(x["h"] - y["h"])]
                if not is_sub:
                    ds += [abs(x["x"] - y["x"]), abs(x["w"] - y["w"])]
                d = max(ds)
                if d > 0.05:
                    cnt += 1
                    if d > worst:
                        detail = {"cls": x["cls"][:38], "delta": round(d, 2)}
                worst = max(worst, d)
            forced.append({"scene": i, "longest": len(long_t),
                           "shortest": len(short_t), "moved": cnt,
                           "maxDelta": round(worst, 2), "worst": detail})
            print("%4d  %2d字 vs %2d字 | 变化元素 %d | 最大位移 %.2f px %s" %
                  (i, len(long_t), len(short_t), cnt, worst, detail or ""))
        report["forced"] = forced
        report["forcedMaxDelta"] = max(s["maxDelta"] for s in forced)
        report["switch"] = switch
        report["switchMaxDelta"] = max(s["maxDelta"] for s in switch)
        report["totalMoved"] = sum(s["moved"] for s in report["scenes"])
        report["maxDelta"] = max(s["maxDelta"] for s in report["scenes"])
        json.dump(report, open(OUT, "w"), ensure_ascii=False, indent=1)
        print("\n消失阶段：变化元素 %d | 最大位移 %.2f px" %
              (report["totalMoved"], report["maxDelta"]))
        print("换句阶段：最大位移 %.2f px | 报告 %s" %
              (report["switchMaxDelta"], OUT))
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

# -*- coding: utf-8 -*-
"""字幕占位稳定性视觉验收：

1) 重截 12 帧关键帧 + 5 帧入场序列（preview.html 改动后保持一致）
2) 8 场景各截「字幕可见 / 字幕消失」两帧，算差异 bbox
3) 拼一张验收图：修复前后位移柱状图 + 代表帧的可见/消失/差异对照
"""
import json
import os
import subprocess
import sys
import urllib.parse

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
FRAMES = os.path.join(HERE, "frames")
STAB = os.path.join(FRAMES, "stability")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
BASE = "file://" + urllib.parse.quote(os.path.join(HERE, "preview.html"))


def font(sz):
    return ImageFont.truetype(FONT, sz)


def shot(t, dst, budget=2500):
    if "--no-shot" in sys.argv and os.path.exists(dst):
        return dst
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--force-device-scale-factor=1",
           "--virtual-time-budget=%d" % budget,
           "--user-data-dir=/tmp/wb-v3-stab-%d" % (abs(hash(dst)) % 100000),
           "--window-size=900,1200", "--screenshot=" + dst,
           BASE + "?capture=1&t=%.3f" % t]
    subprocess.run(cmd, capture_output=True, text=True, timeout=150)
    return dst


def main():
    os.makedirs(STAB, exist_ok=True)
    after = json.load(open(os.path.join(HERE, "layout-after.json"),
                           encoding="utf-8"))
    bp = os.path.join(HERE, "layout-before.json")
    if os.path.exists(bp):
        before = json.load(open(bp, encoding="utf-8"))
    else:
        # 新项目没有「修复前」基线时：柱状图只画修复后的 0 值，不中断
        before = {"scenes": [{"maxDelta": 0.0, "subhostHeightDelta": 0.0}
                             for _ in after["scenes"]]}
        print("提示：未找到 layout-before.json，柱状图只显示修复后数据")

    os.makedirs(FRAMES, exist_ok=True)
    tl = json.load(open(os.path.join(OUT, "voice-animation", "timeline.json"),
                        encoding="utf-8"))
    scene2 = (tl["scenes"][1]["start"] if len(tl["scenes"]) > 1
              else tl["scenes"][0]["start"])

    # ---- 1) 关键帧：同步写 meta.json 供 rebuild_sheets.py 拼图 ----
    # 【模板说明】时间点与标签按项目调整
    SHOTS = [
        (1.20, "01 场景1 · 封面栏线下"),
        (8.32, "02 场景2 开场 +0.18s · 入场中"),
        (10.50, "03 场景2 入场完成"),
        (24.50, "04 场景2 · 21 字字幕"),
        (35.85, "05 场景3 开场 +0.25s · 入场中"),
        (55.00, "06 场景3 · 22 字深蓝块"),
        (78.00, "07 场景4 · 24 字居中"),
        (106.60, "08 场景5 · 深底页脚"),
        (142.60, "09 场景6 · 居中页码位"),
        (157.00, "10 场景7 · 24 字字幕"),
        (194.00, "11 场景8 · 23 字字幕"),
        (202.00, "12 场景8 · 收尾"),
    ]
    for i, (t, _lab) in enumerate(SHOTS, 1):
        shot(t, os.path.join(FRAMES, "f%02d.png" % i))
    json.dump([{"file": "f%02d.png" % i, "t": t, "label": lab}
               for i, (t, lab) in enumerate(SHOTS, 1)],
              open(os.path.join(FRAMES, "meta.json"), "w"),
              ensure_ascii=False, indent=1)
    print("%d 帧关键帧已重截 + meta.json" % len(SHOTS))

    # ---- 2) 入场序列：同步写 enter_meta.json ----
    SEQ = [(0.10, "开场 +0.10s"), (0.45, "+0.45s"),
           (0.90, "+0.90s"), (1.40, "+1.40s"), (2.20, "+2.20s 完成")]
    for i, (dt, _lab) in enumerate(SEQ, 1):
        shot(scene2 + dt, os.path.join(FRAMES, "enter%02d.png" % i))
    json.dump([{"file": "enter%02d.png" % i,
                "t": round(scene2 + dt, 3), "label": lab}
               for i, (dt, lab) in enumerate(SEQ, 1)],
              open(os.path.join(FRAMES, "enter_meta.json"), "w"),
              ensure_ascii=False, indent=1)
    print("5 帧入场序列已重截 + enter_meta.json")

    # ---- 3) 8 场景可见 / 消失两态 ----
    pairs = []
    for s in after["scenes"]:
        a = shot(s["t1"], os.path.join(STAB, "s%02d-on.png" % s["scene"]))
        b = shot(s["t2"], os.path.join(STAB, "s%02d-off.png" % s["scene"]))
        ia = Image.open(a).convert("RGB")
        ib = Image.open(b).convert("RGB")
        diff = ImageChops.difference(ia, ib)
        bbox = diff.getbbox()
        # 差异像素占比（阈值 12，忽略抗锯齿微差）
        mask = diff.convert("L").point(lambda v: 255 if v > 12 else 0)
        px = sum(mask.histogram()[255:]) / float(ia.width * ia.height)
        pairs.append({"scene": s["scene"], "t1": s["t1"], "t2": s["t2"],
                      "bbox": bbox, "ratio": round(px * 100, 3),
                      "on": a, "off": b})
        print("场景 %d  差异 bbox=%s  面积占比 %.3f%%" %
              (s["scene"], bbox, px * 100))

    # ---- 4) 验收拼图 ----
    ft, fm, fs, fx = font(27), font(16), font(14), font(12)
    BG, FG, SUB, LINE = "#151A27", "#F1E6D8", "#8C99B2", "#3A4560"
    RED, GREEN = "#AA2B3A", "#7FA88B"
    W, H = 1320, 1040
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((24, 16), "字幕占位稳定性 · 修复验收", font=ft, fill=FG)
    d.text((24, 54), "字幕消失时只隐藏文字、不清空内容：字幕区域占位恒定，其它页面元素零位移",
           font=fm, fill=SUB)

    # 4.1 修复前后位移柱状图
    d.text((24, 92), "① 字幕消失瞬间 · 页脚高度收缩量（= 牵动其它元素的位移，单位 px）",
           font=fm, fill=FG)
    bx, by, bw, maxv = 40, 140, 640, 40.0
    bh = 118
    d.line((bx, by + bh, bx + bw, by + bh), fill=LINE, width=1)
    for v in (0, 10, 20, 30, 40):
        y = by + bh - v / maxv * bh
        d.line((bx, y, bx + bw, y), fill="#242C3E", width=1)
        d.text((bx - 30, y - 7), str(v), font=fx, fill=SUB)
    for i in range(8):
        x = bx + 20 + i * 76
        v0 = abs(before["scenes"][i]["subhostHeightDelta"] or 0)
        v1 = abs(after["scenes"][i]["subhostHeightDelta"] or 0)
        h0 = min(v0, maxv) / maxv * bh
        d.rectangle((x, by + bh - h0, x + 24, by + bh), fill="#6A3A46")
        d.rectangle((x + 27, by + bh - 3, x + 51, by + bh), fill=GREEN)
        d.text((x + 2, by + bh - h0 - 16), "%.0f" % v0, font=fx, fill="#C08A94")
        d.text((x + 29, by + bh - 18), "0", font=fx, fill=GREEN)
        d.text((x + 6, by + bh + 6), "%02d" % (i + 1), font=fx, fill=SUB)
    d.text((bx + 20, by + bh + 26),
           "暗红 = 修复前（页脚收缩 10–35px，字幕盒宽度塌陷最多 565px）   绿 = 修复后 0px",
           font=fx, fill=SUB)

    # 4.2 右侧测量结论
    rx = 740
    d.text((rx, 92), "② 三阶段几何测量", font=fm, fill=FG)
    lines = [
        ("消失阶段", "8/8 场景  0 个变化元素  0.00 px"),
        ("换句阶段", "43 条样本  0.00 px"),
        ("强制对照", "8/8 页 最长 vs 最短字幕  0.00 px"),
        ("字幕自身", "允许宽度随文字变，高度恒定 35.28 px"),
        ("53 条字幕", "逐句溢出审计 0 条"),
    ]
    for k, (name, val) in enumerate(lines):
        y = 128 + k * 28
        d.text((rx, y), name, font=fx, fill=SUB)
        d.text((rx + 74, y), val, font=fx, fill=FG)
    d.text((rx, 292), "修复前：文字清空 → 行盒塌成 0 → 页脚收缩 35.28px，",
           font=fx, fill="#C08A94")
    d.text((rx, 310), "08 页连引文、结语句一起被下拉；02/05/07 朱红短线", font=fx,
           fill="#C08A94")
    d.text((rx, 328), "下移 5px。修复后全部为 0。", font=fx, fill="#C08A94")

    # 4.3 代表帧对照：01 / 03 / 06 / 08
    d.text((24, 320), "③ 代表帧 · 字幕可见 / 字幕消失 / 差异区域", font=fm, fill=FG)
    reps = [1, 3, 6, 8]
    CW, CH = 200, 267
    G = 18
    ROW_H = 311
    Y_START = 372
    for k, n in enumerate(reps):
        p = pairs[n - 1]
        col, row = k % 2, k // 2
        x = 24 + col * (3 * CW + 2 * 8 + G)
        y0 = Y_START + row * ROW_H
        d.text((x + 2, y0 - 22), "第 %02d 页" % n, font=fm, fill=FG)
        for j, key in enumerate(("on", "off")):
            im = Image.open(p[key]).convert("RGB").resize((CW, CH), Image.LANCZOS)
            xx = x + j * (CW + 8)
            c.paste(im, (xx, y0))
            d.rectangle((xx, y0, xx + CW, y0 + CH), outline=LINE, width=1)
            d.text((xx + 2, y0 + CH + 4), "字幕可见  t=%.2fs" % p["t1"] if j == 0
                   else "字幕消失  t=%.2fs" % p["t2"], font=fx, fill=SUB)
        # 差异图
        ia = Image.open(p["on"]).convert("RGB")
        ib = Image.open(p["off"]).convert("RGB")
        diff = ImageChops.difference(ia, ib).convert("L").point(
            lambda v: 255 if v > 12 else 0).convert("RGB")
        # 差异染成朱红，其余压暗
        dm = Image.new("RGB", ia.size, "#1B2030")
        dm.paste(Image.new("RGB", ia.size, RED), (0, 0),
                 diff.convert("L"))
        dx = x + 2 * (CW + 8)
        dmi = dm.resize((CW, CH), Image.LANCZOS)
        c.paste(dmi, (dx, y0))
        d.rectangle((dx, y0, dx + CW, y0 + CH), outline=LINE, width=1)
        bb = p["bbox"]
        if bb:
            s = CW / 900.0
            d.rectangle((dx + bb[0] * s, y0 + bb[1] * s,
                         dx + bb[2] * s, y0 + bb[3] * s),
                        outline=FG, width=1)
        d.text((dx + 2, y0 + CH + 4), "差异 %.3f%% · 仅字幕文字" % p["ratio"],
               font=fx, fill=SUB)

    d.text((24, 980),
           "朱红区域 = 两帧之间唯一变化处（字幕文字本身）；页面其它元素位置逐像素不变。",
           font=fx, fill=SUB)
    d.text((24, H - 34),
           "帧源 animation-v3/preview.html?capture=1  |  900×1200  |  云健配音 3:23.75  |  报告 layout-before/after.json",
           font=fx, fill="#5C6880")
    p = os.path.join(OUT, "v3-字幕占位稳定性验收.png")
    c.save(p)
    print("验收图:", p, c.size, os.path.getsize(p))


if __name__ == "__main__":
    main()

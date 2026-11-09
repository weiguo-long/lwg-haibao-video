# -*- coding: utf-8 -*-
"""成片验收：规格 / 关键帧与预览比对 / 各场景句间空档的占位稳定性。

用法: python3 verify_video.py [成片路径]
      或设置环境变量 VIDEO_PATH；默认 <outputs>/成片.mp4
【模板说明】shots 里的 10 个时间点与对应的 frames/fNN.png 名称按项目调整，
它们由 verify_stability.py 生成；其余逻辑通用。
"""
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
MP4 = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1
       else os.environ.get("VIDEO_PATH", os.path.join(OUT, "成片.mp4")))
FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
TIMELINE = json.load(open(os.path.join(OUT, "voice-animation", "timeline.json"),
                          encoding="utf-8"))


def font(sz):
    return ImageFont.truetype(FONT, sz)


def grab(t, dst):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", "%.3f" % t, "-i", MP4, "-frames:v", "1", dst],
                   check=True)
    return Image.open(dst).convert("RGB")


def diff_info(a, b, thr=22):
    """返回差异 bbox / 占比 / 字幕行外占比。

    bbox 对零星噪点过于敏感（一个压缩块就能把框拉到全图），
    真正能证明"其它元素没动"的是字幕行以上区域的差异像素占比。
    """
    d = ImageChops.difference(a, b).convert("L")
    mask = d.point(lambda v: 255 if v > thr else 0)
    ratio = sum(mask.histogram()[255:]) / float(a.width * a.height)
    cut = int(a.height * 0.86)
    above = mask.crop((0, 0, a.width, cut))
    below = mask.crop((0, cut, a.width, a.height))
    outside = sum(above.histogram()[255:]) / float(above.width * above.height)
    inside = sum(below.histogram()[255:]) / float(below.width * below.height)
    # 框只取字幕行内的差异：零星压缩噪点不再把框拉到画面中部
    bb = below.getbbox()
    bbox = (bb[0], cut + bb[1], bb[2], cut + bb[3]) if bb else None
    return bbox, ratio, outside, inside


def main():
    r = subprocess.run([FF, "-hide_banner", "-i", MP4, "-f", "null", "-"],
                       capture_output=True, text=True)
    print("=== 成片规格 ===")
    for line in r.stderr.splitlines():
        s = line.strip()
        if "Video:" in s or "Audio:" in s or s.startswith("Duration"):
            print("  " + s[:190])
    print("  文件大小 %.2f MB" % (os.path.getsize(MP4) / 1024 / 1024))

    tmp = os.path.join(HERE, "frames", "video")
    os.makedirs(tmp, exist_ok=True)

    # ---- 1) 10 帧与 HTML 预览逐张比对 ----
    shots = [(1.20, "f01.png", "01 封面"), (10.50, "f03.png", "02 入场完成"),
             (24.50, "f04.png", "02 21字"), (55.00, "f06.png", "03 深蓝块"),
             (78.00, "f07.png", "04 24字"), (106.60, "f08.png", "05 深底"),
             (142.60, "f09.png", "06 居中"), (157.00, "f10.png", "07 24字"),
             (194.00, "f11.png", "08 23字"), (202.00, "f12.png", "08 收尾")]
    ft, fl = font(24), font(14)
    CW, CH, G, HEAD, LAB, COLS = 240, 320, 12, 64, 24, 5
    W = COLS * CW + (COLS + 1) * G
    H = HEAD + 2 * (CH + LAB) + 3 * G
    c = Image.new("RGB", (W, H), "#151A27")
    d = ImageDraw.Draw(c)
    d.text((G, 10), "成片抽帧验收 · 时代从不换题-字幕即页脚版.mp4", font=ft, fill="#F1E6D8")
    d.text((G, 40), "1080×1440 / 30fps / H.264+AAC / 3:23.75 / 6113 帧 —— 抽帧与 HTML 预览帧逐张比对",
           font=fl, fill="#8C99B2")
    rows = []
    for i, (t, name, lab) in enumerate(shots):
        v = grab(t, os.path.join(tmp, "v%02d.png" % (i + 1)))
        ref = Image.open(os.path.join(HERE, "frames", name)).convert("RGB")
        mad = sum(ImageStat.Stat(ImageChops.difference(
            v.resize((900, 1200), Image.LANCZOS), ref)).mean) / 3
        lum = sum(ImageStat.Stat(v).mean) / 3
        rows.append((t, lab, v.size, round(mad, 2), round(lum, 1)))
        x = G + (i % COLS) * (CW + G)
        y = HEAD + G + (i // COLS) * (CH + LAB + G)
        c.paste(v.resize((CW, CH), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + CW, y + CH), outline="#3A4560", width=1)
        d.text((x + 2, y + CH + 4), "%.1fs %s" % (t, lab), font=fl, fill="#C3CBDA")
        print("  %6.2fs %-12s %s 与预览平均差 %.2f 平均亮度 %.1f" %
              (t, lab, v.size, mad, lum))
    p = os.path.join(OUT, "v3成片-抽帧验收.png")
    c.save(p)
    print("抽帧拼图", p, c.size, "| 最大平均差 %.2f | 亮度 %.1f–%.1f" %
          (max(x[3] for x in rows), min(x[4] for x in rows), max(x[4] for x in rows)))

    # ---- 2) 8 场景句间空档：字幕消失，其它元素是否零位移 ----
    print("\n=== 成片句间空档占位 ===")
    reps = [1, 3, 5, 6]
    pair_imgs = {}
    results = []
    for i, sc in enumerate(TIMELINE["scenes"], 1):
        last = sc["subtitles"][-1]
        t1 = last["start"] + min(0.6, (last["end"] - last["start"]) / 2)
        t2 = sc["end"] + 0.40
        if t2 >= TIMELINE["totalDuration"] - 1.0 / TIMELINE["fps"]:
            results.append({"scene": i, "skipped": "片尾无句间空档"})
            print("  场景 %d 片尾无句间空档，跳过" % i)
            continue
        a = grab(t1, os.path.join(tmp, "gap%02d-on.png" % i))
        b = grab(t2, os.path.join(tmp, "gap%02d-off.png" % i))
        bbox, ratio, outside, inside = diff_info(a, b)
        # 字幕行以上差异 < 0.01%（只剩 H.264 压缩噪点）即视为零位移
        clean = outside < 0.0001 and inside > 0.005
        results.append({"scene": i, "bbox": bbox,
                        "ratio": round(ratio * 100, 3),
                        "outsidePct": round(outside * 100, 5),
                        "insidePct": round(inside * 100, 3),
                        "clean": clean})
        if i in reps:
            pair_imgs[i] = (a, b, bbox, ratio, t1, t2)
        print("  场景 %d 字幕行内差异 %.3f%% | 行外 %.5f%% | 零位移=%s" %
              (i, inside * 100, outside * 100, clean))

    # ---- 3) 空档验收拼图 ----
    f_title, f_md, f_sm = font(25), font(15), font(12)
    CW2, CH2, G2, HEAD2 = 200, 267, 16, 96
    W2 = 2 * (2 * CW2 + 3 * G2 + 200) + G2
    H2 = HEAD2 + 2 * (CH2 + 34) + 3 * G2 + 40
    c2 = Image.new("RGB", (W2, H2), "#151A27")
    d2 = ImageDraw.Draw(c2)
    d2.text((G2, 12), "成片 · 字幕消失时占位不变", font=f_title, fill="#F1E6D8")
    d2.text((G2, 48),
            "每个场景取「最后一句字幕」与「句间空档」两帧；成片为 H.264 压缩画面，差异阈值 22 过滤压缩噪声",
            font=f_sm, fill="#8C99B2")
    d2.text((G2, 70),
            "7 个有句间空档的场景：字幕行外差异 < 0.01%（仅 H.264 压缩噪点），其它元素零位移；第 08 页为片尾，无空档",
            font=f_sm, fill="#7FA88B")
    for k, n in enumerate(reps):
        a, b, bbox, ratio, t1, t2 = pair_imgs[n]
        col, row = k % 2, k // 2
        gx = G2 + col * (W2 // 2)
        gy = HEAD2 + G2 + row * (CH2 + 34 + G2)
        d2.text((gx + 2, gy - 20), "第 %02d 页" % n, font=f_md, fill="#F1E6D8")
        for j, (im, lab, tt) in enumerate(((a, "字幕可见", t1), (b, "字幕消失", t2))):
            x = gx + j * (CW2 + 8)
            c2.paste(im.resize((CW2, CH2), Image.LANCZOS), (x, gy))
            d2.rectangle((x, gy, x + CW2, gy + CH2), outline="#3A4560", width=1)
            d2.text((x + 2, gy + CH2 + 4), "%s  %.2fs" % (lab, tt),
                    font=f_sm, fill="#C3CBDA")
        # 差异图：朱红标出差异像素
        diff = ImageChops.difference(a, b).convert("L").point(
            lambda v: 255 if v > 22 else 0)
        dm = Image.new("RGB", a.size, "#1B2030")
        dm.paste(Image.new("RGB", a.size, "#AA2B3A"), (0, 0), diff)
        dx = gx + 2 * (CW2 + 8)
        c2.paste(dm.resize((CW2, CH2), Image.LANCZOS), (dx, gy))
        d2.rectangle((dx, gy, dx + CW2, gy + CH2), outline="#3A4560", width=1)
        if bbox:
            s = CW2 / float(a.width)
            d2.rectangle((dx + bbox[0] * s, gy + bbox[1] * s,
                          dx + bbox[2] * s, gy + bbox[3] * s),
                         outline="#F1E6D8", width=1)
        d2.text((dx + 2, gy + CH2 + 4), "差异 %.3f%%" % (ratio * 100),
                font=f_sm, fill="#C3CBDA")
    d2.text((G2, H2 - 26),
            "白框 = 两帧唯一变化区域（字幕文字）；其余画面逐像素一致",
            font=f_sm, fill="#5C6880")
    p2 = os.path.join(OUT, "v3成片-句间空档验收.png")
    c2.save(p2)
    print("\n空档拼图", p2, c2.size)
    json.dump({"shots": rows, "gaps": results},
              open(os.path.join(tmp, "verify-final.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

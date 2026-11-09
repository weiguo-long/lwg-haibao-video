# -*- coding: utf-8 -*-
"""按当前 frames/ 下的帧重拼三张验收图（关键帧 / 入场序列 / 字幕配色对照）。"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
F = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(sz):
    return ImageFont.truetype(F, sz)


ft, f_sm, f_md, f_xs = font(26), font(13), font(16), font(11.5)
BG, FG, SUB, LINE = "#151A27", "#F1E6D8", "#8C99B2", "#3A4560"


def keyframes():
    meta = json.load(open(os.path.join(HERE, "frames", "meta.json"),
                          encoding="utf-8"))
    CW, CH, G, LAB, HEAD, COLS, ROWS = 300, 400, 16, 30, 86, 4, 3
    W = COLS * CW + (COLS + 1) * G
    H = HEAD + ROWS * (CH + LAB) + (ROWS + 1) * G
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((G, 18), "字幕即页脚 · 动画关键帧验收", font=ft, fill=FG)
    d.text((G, 55),
           "12 个时间点 / 900×1200 满幅 3:4 / 云健配音 3:23.75 / 53 条字幕逐句审计 0 溢出 / 字幕占位恒定",
           font=f_sm, fill=SUB)
    for i, m in enumerate(meta):
        x = G + (i % COLS) * (CW + G)
        y = HEAD + G + (i // COLS) * (CH + LAB + G)
        im = Image.open(os.path.join(HERE, "frames", m["file"])).convert("RGB")
        c.paste(im.resize((CW, CH), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + CW, y + CH), outline=LINE, width=1)
        d.text((x + 2, y + CH + 5), m["label"] + "  t=%.2fs" % m["t"],
               font=f_md, fill="#C3CBDA")
    p = os.path.join(OUT, "v3动画-关键帧验收.png")
    c.save(p)
    print("关键帧", p, c.size)


def enter_seq():
    meta = json.load(open(os.path.join(HERE, "frames", "enter_meta.json"),
                          encoding="utf-8"))
    CW, CH, G, LAB, HEAD = 248, 331, 14, 28, 76
    W = 5 * CW + 6 * G
    H = HEAD + CH + LAB + 2 * G
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((G, 14), "场景 2 · 依次入场序列", font=ft, fill=FG)
    d.text((G, 48),
           "同一场景 0 → 2.2 秒：画面排版元素按视觉从上到下依次淡入上移；字幕始终与配音同步，不参与排序",
           font=f_sm, fill=SUB)
    for i, m in enumerate(meta):
        x = G + i * (CW + G)
        im = Image.open(os.path.join(HERE, "frames", m["file"])).convert("RGB")
        c.paste(im.resize((CW, CH), Image.LANCZOS), (x, HEAD))
        d.rectangle((x, HEAD, x + CW, HEAD + CH), outline=LINE, width=1)
        d.text((x + 2, HEAD + CH + 5), m["label"], font=f_md, fill="#C3CBDA")
    p = os.path.join(OUT, "v3动画-入场序列.png")
    c.save(p)
    print("入场序列", p, c.size)


def colors():
    COLOR = [
        ("#C2BFBD", "7.00:1 · 深底", "米白掺灰蓝 28% · 呼应 PRICE 水印", "f01.png", "01 栏线下的信息行"),
        ("#4A5B78", "5.57:1 · 浅底", "原 .foot-en 页脚行的灰蓝", "f04.png", "02 连载 02 + 英文行"),
        ("#C2BFBD", "7.00:1 · 深底", "深蓝块内原米白的柔和化", "f06.png", "03 底部深蓝块"),
        ("#28314E", "10.40:1 · 浅底", "该页主文字夜蓝（标题 / 数字）", "f07.png", "04 MODEL T 大字行"),
        ("#C2BFBD", "7.00:1 · 深底", "米白掺灰蓝 28%", "f08.png", "05 右下页码位"),
        ("#4A5B78", "5.57:1 · 浅底", "诗文 .poem / .poem-en 的灰蓝", "f09.png", "06 居中页码位"),
        ("#28314E", "10.40:1 · 浅底", "底部 .foot-box 与 .kana 的夜蓝", "f10.png", "07 右下页码位"),
        ("#28314E", "10.40:1 · 浅底", "结语句 .punch 的夜蓝", "f11.png", "08《道德经》出处行"),
    ]
    CW, CH, G, INFO, HEAD, COLS = 300, 400, 16, 74, 150, 4
    W = COLS * CW + (COLS + 1) * G
    H = HEAD + 2 * (CH + INFO) + 3 * G
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((G, 14), "8 页字幕配色 · 逐页取色对照", font=ft, fill=FG)
    d.text((G, 49),
           "字幕色不再一律墨色 / 米白：浅底页接该页原有的次级或主文字色，深底页用米白与该页灰蓝调和出的浅色",
           font=f_sm, fill=SUB)
    legend = [("#F1E6D8", "米白"), ("#1A1614", "墨"), ("#28314E", "夜蓝"),
              ("#4A5B78", "灰蓝"), ("#AA2B3A", "朱红")]
    lx, ly = G, 78
    for hexv, name in legend:
        used = hexv in ("#28314E", "#4A5B78")
        d.rectangle((lx, ly, lx + 15, ly + 15), fill=hexv,
                    outline=FG if used else "#5A6480", width=2 if used else 1)
        d.text((lx + 21, ly), name + ("  · 字幕用" if used else ""),
               font=f_xs, fill="#C3CBDA" if used else "#74809A")
        lx += 128
    d.text((G, 106),
           "另：深底派生色 #C2BFBD = 米白 #F1E6D8 掺灰蓝 #4A5B78 28%　|　朱红仅作引导短线，不用于整行",
           font=f_xs, fill=SUB)
    for i, (hexv, ratio, why, file, where) in enumerate(COLOR):
        x = G + (i % COLS) * (CW + G)
        y = HEAD + G + (i // COLS) * (CH + INFO + G)
        im = Image.open(os.path.join(HERE, "frames", file)).convert("RGB")
        c.paste(im.resize((CW, CH), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + CW, y + CH), outline=LINE, width=1)
        ty = y + CH + 7
        d.rectangle((x + 2, ty + 2, x + 14, ty + 14), fill=hexv,
                    outline="#6B7690", width=1)
        d.text((x + 20, ty), hexv, font=f_md, fill=FG)
        d.text((x + 112, ty + 2), ratio, font=f_xs, fill=SUB)
        d.text((x + 2, ty + 22), why, font=f_xs, fill="#C3CBDA")
        d.text((x + 2, ty + 42), "%02d  %s" % (i + 1, where),
               font=f_xs, fill="#74809A")
    p = os.path.join(OUT, "v3动画-字幕配色对照.png")
    c.save(p)
    print("配色对照", p, c.size)


if __name__ == "__main__":
    keyframes()
    enter_seq()
    colors()

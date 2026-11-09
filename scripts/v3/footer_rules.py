# -*- coding: utf-8 -*-
"""
「字幕即页脚」版式效果图（静态设计稿；不生成动画 / 视频 / 时间轴）。

设计前提：字幕不是页面做完后再找地方塞的元素，而是**一开始就把页脚与页码
那一块留给它**。做法是把每页原有的页脚信息 / 页码元素整个替换成字幕，
沿用该位置原有的栏线、栅格、色块、对齐与字号层级；不新增字幕层、
不把原页脚上移、不压缩画面。

产出：outputs/字幕即页脚-设计效果图.html
      URL 加 #P1 … #P8 可看单页 900x1200 全尺寸

【模板说明】
- 复制到 <workspace>/outputs/animation-v3/ 下，与 build_preview_v3.py 同目录；
  OUT 会自动推导为 <workspace>/outputs/。
- FILES / SUBS / WHERE / RULES 全是项目专属示例值。换新项目时必须：
  1) 改 FILES 为实际海报文件名；
  2) 逐页检查原页脚 / 页码元素的实际 HTML，重写 RULES[n]["find"]（必须唯一命中）；
  3) 保留原元素 class，只加 subhost / subline，继承该位置的定位与栅格；
  4) SUBS 用每页最长的一条字幕，展示最挤状态。
- 本文件可直接运行出静态效果图；被 build_preview_v3.py 导入时不会执行 main()。
  规则细节见 references/05-subtitle-as-footer.md。
"""
import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)

FILES = {
    1: "01-cover-the-price.html",
    2: "02-cheap-seats.html",
    3: "03-the-only-variable.html",
    4: "04-model-t.html",
    5: "05-ideal-x.html",
    6: "06-the-demand-never-changed.html",
    7: "07-ask-the-price.html",
    8: "08-the-wide-road.html",
}

# 每页取该场景最长的一条字幕，效果图直接展示最挤的状态
SUBS = {
    1: "时代从不换题，它只是不停降价",
    2: "等一个词热到你都听说了，便宜的位置，早没了",
    3: "是原本根本用不起的人，全进来了，用量一下炸开",
    4: "一九一三年，他把流水线搬进高地公园工厂，装一辆车",
    5: "一九五六年四月二十六号，一艘叫理想X的旧油轮",
    6: "一个把车价降到三成，一个把运价降到三十六分之一",
    7: "换张纸，写一件身边人人都想要，却因为贵、或者麻烦",
    8: "别找没人做过的事，找人人都想做，只是还嫌贵的事",
}

# 原位置 -> 字幕位的替换说明（展板标注用）
WHERE = {
    1: "栏线下的信息行 + 页码 01 / 08",
    2: "连载 02 + OLD NEEDS, NEW PRICES",
    3: "底部深蓝结语句色块",
    4: "MODEL T 描边大字行",
    5: "右下角页码 05 / 08",
    6: "居中页码 06 / 08",
    7: "右下角页码 07 / 08",
    8: "《道德经》出处行 + 08 / 08",
}

LINE = "font-size:2.8cqw;font-weight:600;letter-spacing:.02em;line-height:1.4;white-space:nowrap"

# 每页：把原页脚 / 页码元素整体替换成字幕，并只做「这个位置本来就该长这样」的样式定义
RULES = {
    1: dict(
        find=r'<div class="foot">.*?</div>',
        html='<div class="foot subhost"><p class="subline">{sub}</p></div>',
        css="""#c{n} .foot.subhost{{opacity:1;color:#F1E6D8;align-items:center;padding-top:2.6cqw}}
#c{n} .foot.subhost .subline{{""" + LINE + ";color:#F1E6D8}}",
    ),
    2: dict(
        find=r'<div class="foot">.*?</div>',
        html='<div class="foot subhost"><span class="submark" aria-hidden="true"></span><p class="subline">{sub}</p></div>',
        css="""#c{n} .foot.subhost{{justify-content:flex-start;align-items:center;gap:1.4cqw;color:#1A1614}}
#c{n} .foot.subhost .submark{{flex:none;width:.7cqw;height:2.8cqw;background:#AA2B3A}}
#c{n} .foot.subhost .subline{{""" + LINE + ";color:#1A1614}}",
    ),
    3: dict(
        find=r'<div class="conclusion">.*?</div>',
        html='<div class="conclusion subhost"><p class="subline">{sub}</p></div>',
        css="""#c{n} .conclusion.subhost{{padding:3cqw 3.2cqw 3.2cqw;color:#F1E6D8}}
#c{n} .conclusion.subhost .subline{{""" + LINE + ";color:#F1E6D8}}",
    ),
    4: dict(
        find=r'<div class="bottom-en"[^>]*>.*?</div>',
        html='<div class="bottom-en subhost"><p class="subline">{sub}</p></div>',
        css="""#c{n} .bottom-en.subhost{{left:8%;right:8%;bottom:4%;font-family:inherit;font-size:2.8cqw;font-weight:600;letter-spacing:.02em;line-height:1.4;color:#1A1614;-webkit-text-stroke:0;text-align:center;pointer-events:auto}}
#c{n} .bottom-en.subhost .subline{{white-space:nowrap}}""",
    ),
    5: dict(
        find=r'<span class="pg">\s*05\s*/\s*08\s*</span>',
        html='<p class="pg subhost"><span class="submark" aria-hidden="true"></span><span class="subline">{sub}</span></p>',
        css="""#c{n} .pg.subhost{{left:8%;right:8%;bottom:3.4%;display:flex;align-items:center;gap:1.2cqw;opacity:1;color:#F1E6D8}}
#c{n} .pg.subhost .submark{{flex:none;width:.7cqw;height:2.8cqw;background:#AA2B3A}}
#c{n} .pg.subhost .subline{{""" + LINE + ";color:#F1E6D8}}",
    ),
    6: dict(
        find=r'<span class="pg">\s*06\s*/\s*08\s*</span>',
        html='<p class="pg subhost"><span class="subline">{sub}</span></p>',
        css="""#c{n} .pg.subhost{{bottom:6.5%;font-family:inherit;font-size:2.8cqw;font-weight:600;letter-spacing:.02em;line-height:1.4;color:#1A1614;opacity:1}}
#c{n} .pg.subhost .subline{{white-space:nowrap}}""",
    ),
    7: dict(
        find=r'<span class="pg">\s*07\s*/\s*08\s*</span>',
        html='<div class="pg subhost"><span class="submark" aria-hidden="true"></span><span class="subline">{sub}</span></div>',
        css="""#c{n} .pg.subhost{{left:8%;right:8%;bottom:3.2%;display:flex;align-items:center;gap:1.2cqw;opacity:1;color:#1A1614}}
#c{n} .pg.subhost .submark{{flex:none;width:.7cqw;height:2.8cqw;background:#AA2B3A}}
#c{n} .pg.subhost .subline{{""" + LINE + ";color:#1A1614}}",
    ),
    8: dict(
        find=r'<p class="src">.*?</p>',
        html='<p class="src subhost"><span class="subline">{sub}</span></p>',
        css="""#c{n} .src.subhost{{margin-top:2.8cqw;font-size:2.8cqw;font-weight:600;letter-spacing:.02em;line-height:1.4;color:#1A1614;opacity:1}}
#c{n} .src.subhost .subline{{white-space:nowrap}}""",
    ),
}


def read_page(n):
    src = open(os.path.join(OUT, FILES[n]), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    stage = re.search(r'<main class="stage">(.*?)</main>', src, re.S).group(1).strip()
    return css, stage


def strip_page_numbers(stage):
    stage = re.sub(r'<span class="(?:pg|page)">\s*\d{2}\s*/\s*08\s*</span>', "", stage)
    stage = re.sub(r"<b>\s*\d{2}\s*/\s*08\s*</b>", "", stage)
    stage = re.sub(r"\s*/\s*08", "", stage)
    stage = re.sub(r"[\u3000\s]+</p>", "</p>", stage)
    return stage


def scoped(cid, css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = sel.strip(), body.strip()
        if not sel or sel in ("*", "html,body", "html", "body"):
            continue
        if sel == ":root":
            out.append("#%s{%s}" % (cid, body))
            continue
        parts = ["#%s %s" % (cid, p.strip()) for p in sel.split(",")]
        out.append(", ".join(parts) + "{" + body + "}")
    out.append(
        "#%s .stage{position:absolute;inset:0;width:100%%;height:100%%;"
        "aspect-ratio:auto;box-shadow:none}" % cid
    )
    return "\n".join(out)


def build_card(n):
    cid = "cP%d" % n
    css, stage = read_page(n)
    rule = RULES[n]
    repl = rule["html"].replace("{sub}", html.escape(SUBS[n]))
    stage, cnt = re.subn(rule["find"], repl, stage, flags=re.S)
    if cnt != 1:
        raise RuntimeError("page %d footer replace count=%d" % (n, cnt))
    stage = strip_page_numbers(stage)
    extra = (rule["css"].replace("{n}", "P%d" % n)
             .replace("{{", "{").replace("}}", "}"))
    tone = "dark" if n in (1, 5) else "light"
    card = """<div class="cell" id="cardP%d">
      <div class="card %s" id="%s"><main class="stage">%s</main></div>
      <div class="cap"><b>%02d</b><span>原 %s → 字幕</span></div>
    </div>""" % (n, tone, cid, stage, n, html.escape(WHERE[n]))
    return scoped(cid, css) + "\n" + extra, card


TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>字幕即页脚 · 8 页版式设计效果图</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23AA2B3A'/%3E%3C/svg%3E">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#F1E6D8;--ink:#1A1614;--navy:#28314E;--red:#AA2B3A}
html,body{margin:0}
body{width:1360px;background:#151A27;color:var(--paper);font-family:"PingFang SC","Hiragino Sans GB","Source Han Sans SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased;padding:34px 40px 28px}
header{border-bottom:1px solid rgba(241,230,216,.16);padding-bottom:20px}
.eyebrow{font-size:12px;letter-spacing:.22em;color:#8C99B2;margin-bottom:11px}
header h1{font-size:29px;font-weight:800;letter-spacing:.02em}
header h1 em{font-style:normal;color:var(--red)}
.lede{margin-top:9px;font-size:13.5px;line-height:1.8;color:#AEB8CC;max-width:1080px}
.logic{margin:18px 0 6px;background:#1C2334;border:1px solid rgba(241,230,216,.1);border-radius:10px;padding:15px 18px}
.logic h2{font-size:12px;letter-spacing:.18em;color:#8C99B2;font-weight:500;margin-bottom:10px}
.logic p{font-size:13px;line-height:1.9;color:#C3CBDA}
.logic del{color:#8C99B2;text-decoration-color:#AA2B3A;text-decoration-thickness:1px}
.logic b{color:#F1E6D8;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(4,300px);gap:18px 20px;margin-top:20px}
.cell{min-width:0}
.card{width:300px;height:400px;position:relative;overflow:hidden;container-type:inline-size;box-shadow:0 9px 26px rgba(0,0,0,.5)}
.card.light{color:#1A1614}
.card.dark{color:#F1E6D8}
.cap{display:flex;align-items:baseline;gap:8px;margin-top:8px;font-size:11px;line-height:1.5;color:#8C99B2}
.cap b{font-family:"Helvetica Neue",Arial,sans-serif;font-size:11px;color:#AA2B3A;flex:none}
footer{margin-top:22px;border-top:1px solid rgba(241,230,216,.16);padding-top:15px;display:flex;gap:24px}
.spec{flex:1;font-size:12px;line-height:2.05;color:#9DA9C0}
.spec b{color:#F1E6D8;font-weight:500}
.spec .k{display:inline-block;width:72px;color:#74809A}
.note{width:420px;flex:none;font-size:11.5px;line-height:1.85;color:#8C99B2}
.note b{color:#C3CBDA;font-weight:500}
body.single{width:900px;height:1200px;padding:0;background:#151A27}
body.single header,body.single .logic,body.single footer{display:none}
body.single .grid{display:block;margin:0}
body.single .cell:not(.focus){display:none}
body.single .cell.focus{margin:0}
body.single .card{width:900px;height:1200px;box-shadow:none}
body.single .cap{display:none}
__SCOPED_CSS__
</style>
</head>
<body>
<header>
  <div class="eyebrow">版式重做 · 8 页设计效果图 / 本轮未生成动画与视频</div>
  <h1>字幕<em>就是页脚</em></h1>
  <p class="lede">不是页面做完再给字幕找位置，而是从一开始就把页脚和页码那一块留给字幕：取消原有的页脚信息与页码，字幕继承该位置原有的栏线、栅格、色块、对齐和字号层级。八页各不相同，字幕跟着各自的版式走，画面全部满幅 3:4。</p>
</header>

<div class="logic">
  <h2>被取消的东西 / 让出来的位置</h2>
  <p><del>页码 NN / 08、VOL 页序</del>　<del>连载标签、OLD NEEDS, NEW PRICES</del>　<del>老需求 · 数量级 · 谁用得起</del>　<del>MODEL T 描边大字</del>　<del>《道德经》出处行</del>　<del>底部深蓝结语句块</del><br>
  → <b>这些位置现在只放一行字幕</b>：2.8cqw / 字重 600 / 单行不折行；浅底页墨色字、深底页米白字；朱红只在个别页作一根引导短线。没有新增字幕层，没有上移任何元素，没有缩放画面。</p>
</div>

<div class="grid">__CARDS__</div>

<footer>
  <div class="spec">
    <div><span class="k">配色</span><b>C-01 纸红复古</b>　米白 #F1E6D8 / 墨 #1A1614 / 夜蓝 #28314E / 朱红 #AA2B3A / 灰蓝 #4A5B78</div>
    <div><span class="k">字幕位</span>各页原页脚 / 页码位，bottom 3.2%–7% 不等，随该页版式</div>
    <div><span class="k">字号</span>2.8cqw / 字重 600 / 单行不折行 / 字距 .02em；24 字 ≈ 67cqw，版心 ≥ 77cqw</div>
    <div><span class="k">页码</span>全部取消；VOL 只保留期号，不再带 / 08</div>
    <div><span class="k">未动</span>8 页源文件、timeline.json、配音、动画预览、成片、技能包</div>
  </div>
  <div class="note">
    <b>每页展示的都是该场景最长的一条字幕</b>（14–24 字），直接看最挤的状态。字幕在一页内换句时位置不动，只有文字变；切场时字幕随整页一起换，跟着该页页脚的位置走。<br><br>
    03 页字幕落在原有深蓝色块内，06 页落在原居中页码位，04 页落在原底部大字行——同一套字号规则，三种不同的页脚形态。<br><br>
    <b>待确认 · 内容近重复</b>：01 / 06 / 07 / 08 页的字幕与该页主文案同源（海报本就是拿配音文案排的），会出现上下两句几乎相同，08 页最明显。这是文案层面的事，不是版式问题，效果图保留原状未改内容；铺开 8 页前需定：换字幕、弱化页面重复文字，还是接受。
  </div>
</footer>

<script>
const k = location.hash.slice(1);
if (/^P[1-8]$/.test(k)) {
  document.body.classList.add('single');
  const el = document.getElementById('card' + k);
  if (el) el.classList.add('focus');
}
</script>
</body>
</html>
"""


def main():
    css_all, cards = [], []
    for n in range(1, 9):
        css, card = build_card(n)
        css_all.append(css)
        cards.append(card)
    out = TPL.replace("__SCOPED_CSS__", "\n".join(css_all)).replace("__CARDS__", "\n".join(cards))
    path = os.path.join(OUT, "字幕即页脚-设计效果图.html")
    open(path, "w", encoding="utf-8").write(out)
    print("written:", path, len(out), "chars")


if __name__ == "__main__":
    main()

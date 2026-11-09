# -*- coding: utf-8 -*-
"""
「字幕即页脚」v3 HTML 动画预览（只出预览，不渲染视频 / 不更新技能）

与 v2 的根本差别：没有独立字幕条，画面也不再缩放让位。
字幕位 = 每页原本留给页脚与页码的那个元素，整个替换成字幕宿主，
沿用该位置原有的栏线、栅格、色块、对齐与字号层级。

版式规则直接复用 design-preview/build_effect_v3.py 的 RULES / scoped / strip_page_numbers，
保证动画与已确认的 8 页设计效果图是同一套版式，不产生漂移。

- 8 页 = 8 场景，时长沿用 voice-animation/timeline.json（云健配音）
- 字幕在各自页脚里逐句切换，画面满幅 3:4
- 除第 1 场景外，其它场景开始时画面排版元素依次入场；
  字幕是与配音同步的活文字，不参与排序（否则会迟到约 1.3s），改为切句 0.18s 淡入
- 入场与字幕淡入都由播放时间 t 确定性驱动，不用 WAAPI / CSS animation，可直接搬进逐帧渲染
- 句间 / 场景末尾：字幕只隐藏（opacity:0）不清空，字幕区域占位恒定，其它元素零位移
- 音频 base64 内嵌，单文件离线可播；?t= 可定位，?capture=1 隐藏 UI 作为帧源
"""
import base64
import html as htmlmod
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
VOICE_DIR = os.path.join(OUT, "voice-animation")

# ---- 逐页字幕色：取该页配色里已经存在的文字色，不再一律墨色 / 米白 ----
# C-01 色板：米白 #F1E6D8 / 墨 #1A1614 / 夜蓝 #28314E / 朱红 #AA2B3A / 灰蓝 #4A5B78
# 浅底页：接该页原有的次级或主文字色；深底页：米白与该页灰蓝按 28% 调和，
# 得到 #C2BFBD（在 #28314E 上 7.00:1），明显区别于纯白，又落在页面自身的色彩层级里。
# 朱红仍只作引导短线，不用于整行（色板规则：朱红占比 ≤5%）。
SUB_COLORS = {
    1: ("#C2BFBD", "深底｜米白掺 --mid 灰蓝 28%（呼应竖排 PRICE 水印）"),
    2: ("#4A5B78", "浅底｜原 .foot-en 页脚英文行的 --steel 灰蓝"),
    3: ("#C2BFBD", "深蓝块｜同深底，块内原文字 --paper 的柔和化"),
    4: ("#28314E", "浅底｜该页主文字 --navy（标题/数字/结语句）"),
    5: ("#C2BFBD", "深底｜米白掺 --steel 灰蓝 28%"),
    6: ("#4A5B78", "浅底｜诗文 .poem / .poem-en 的 --steel 灰蓝"),
    7: ("#28314E", "浅底｜底部 .foot-box 与 .kana 的 --navy 夜蓝"),
    8: ("#28314E", "浅底｜.punch 结语句的 --navy（与上方灰蓝引文分层）"),
}
# v3 规则里给字幕宿主写死的基础色，按页替换成上面的取色
BASE_COLORS = {
    1: "#F1E6D8", 2: "#1A1614", 3: "#F1E6D8", 4: "#1A1614",
    5: "#F1E6D8", 6: "#1A1614", 7: "#1A1614", 8: "#1A1614",
}

# 版式唯一来源：同目录的 footer_rules.py（项目专属，换项目必须改写 RULES）。
# 两个脚本都放在 outputs/animation-v3/，OUT 会推导为 outputs/。
sys.path.insert(0, HERE)
from footer_rules import (  # noqa: E402
    FILES,
    RULES,
    read_page,
    scoped,
    strip_page_numbers,
)

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>时代从不换题 · 配音动画预览 v3（字幕即页脚）</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23AA2B3A'/%3E%3C/svg%3E">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:#0B0E17;color:#F1E6D8;font-family:"PingFang SC","Hiragino Sans GB","Source Han Sans SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased;display:flex;flex-direction:column;align-items:center;overflow:hidden}
.toolbar{width:100%;height:56px;flex:none;display:flex;align-items:center;gap:12px;padding:0 18px;background:#121724;border-bottom:1px solid #232A3B}
.brand{font-size:13px;font-weight:700;letter-spacing:.04em;white-space:nowrap}
.brand em{color:#AA2B3A;font-style:normal}
button{background:#1D2537;color:#F1E6D8;border:1px solid #33405C;border-radius:6px;padding:7px 11px;font-size:12px;cursor:pointer;font-family:inherit;white-space:nowrap}
button:hover{background:#28314E}
button:disabled{opacity:.38;cursor:default}
button:disabled:hover{background:#1D2537}
button.on{background:#AA2B3A;border-color:#AA2B3A}
#play{font-weight:700;min-width:66px}
#time{font-family:"Helvetica Neue",Arial,sans-serif;font-size:12px;letter-spacing:.05em;color:#9AA6BF;white-space:nowrap}
#seek{flex:1;min-width:90px;accent-color:#AA2B3A;height:4px;cursor:pointer}
#chapters{display:flex;gap:4px;flex:none}
.ch{width:24px;height:24px;padding:0;border-radius:4px;font-size:11px;display:flex;align-items:center;justify-content:center;font-family:"Helvetica Neue",Arial,sans-serif}
.ch.active{background:#AA2B3A;border-color:#AA2B3A}
#chapter{font-family:"Helvetica Neue",Arial,sans-serif;font-size:12px;color:#9AA6BF;min-width:52px;text-align:center}
.viewport{flex:1;width:100%;min-height:0;display:flex;align-items:center;justify-content:center;padding:12px}
/* 画面满幅 3:4：没有字幕带、没有 poster 缩放 */
#stageFrame{position:relative;width:min(92vw,calc((100vh - 132px)*0.75));aspect-ratio:3/4;overflow:hidden;container-type:inline-size;box-shadow:0 18px 55px rgba(0,0,0,.55)}
.scene{position:absolute;inset:0;display:none;overflow:hidden}
.scene.active{display:block}
body.immersive .toolbar,body.immersive .hint{display:none}
body.immersive #stageFrame{width:min(96vw,calc((100vh - 28px)*0.75))}
/* 帧源模式：窗口本身就是 3:4，UI 全隐藏，舞台铺满窗口 */
body.capture .toolbar,body.capture .hint{display:none}
body.capture .viewport{padding:0;flex:none;height:100vh}
body.capture #stageFrame{width:100vw;height:100vh;aspect-ratio:auto;box-shadow:none}
.hint{flex:none;padding:0 0 9px;font-size:11px;letter-spacing:.06em;color:#6F7B96}
__SCOPED_CSS__
</style>
</head>
<body>
  <div class="toolbar">
    <span class="brand">时代从不换题 <em>·</em> 字幕即页脚 v3</span>
    <button id="play">播放</button>
    <span id="time"><span id="cur">0:00</span> / <span id="total">0:00</span></span>
    <input id="seek" type="range" min="0" max="1" step="0.01" value="0">
    <span id="chapter">01 / 08</span>
    <div id="chapters"></div>
    <button id="mute">静音</button>
    <button id="reenter">重播入场</button>
    <button id="immersive">沉浸</button>
  </div>

  <div class="viewport">
    <div id="stageFrame">__SCENES_HTML__</div>
  </div>

  <p class="hint">字幕长在各页页脚里 · 点击播放试听 · 空格暂停 · ← → 快退快进 5 秒 · 数字 1–8 跳场景 · R 重播入场 · I 隐藏控制条</p>
<pre id="auditResult" style="display:none"></pre>
<script>
const AUDIO_B64 = "__AUDIO_B64__";
const TIMELINE = __TIMELINE_JSON__;
const $ = id => document.getElementById(id);
const SUBS = [];
TIMELINE.scenes.forEach((s,si) => (s.subtitles||[]).forEach(c =>
  SUBS.push({s:c.start, e:c.end, text:c.text, scene:si+1})));

let audio=null;
let playing=false, offset=0, activeIdx=-1, muted=false, lastT=null;
let duration=TIMELINE.totalDuration;
const q=new URLSearchParams(location.search);
/* 全部由播放时间 t 决定，可逐帧复现、可直接搬进 Remotion / CDP 出片 */
const ENTER_DUR=0.46, ENTER_STEP=0.075, ENTER_LIFT=16, ENTER_GROUPS=18;
const SUB_FADE=0.18;
/* 字幕不可见时的兜底占位文字：静态 HTML 已填首句，这里只防被外部清空。
   占位必须始终存在，否则行盒塌陷会牵动同页其它元素。 */
const SUB_PLACEHOLDER=TIMELINE.scenes.map(s=>
  (s.subtitles&&s.subtitles.length)?s.subtitles[0].text:'\u3000');
const ENTER_PLAN={}, ENTER_EPOCH={};

function fmt(t){ t=Math.max(0,Math.floor(t)); return Math.floor(t/60)+':'+String(t%60).padStart(2,'0'); }
function now(){ return audio && !audio.paused ? audio.currentTime : offset; }

function ensureAudio(){
  if(audio) return;
  const bin=atob(AUDIO_B64);
  const bytes=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
  audio=new Audio(URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'})));
  audio.preload='auto';
  audio.muted=muted;
  audio.addEventListener('loadedmetadata',()=>{
    duration=audio.duration||TIMELINE.totalDuration;
    $('seek').max=duration.toFixed(2);
    $('total').textContent=fmt(duration);
  });
  audio.addEventListener('ended',()=>{
    playing=false; offset=duration;
    $('play').textContent='播放'; render(duration);
  });
}

function toggle(){
  ensureAudio();
  if(playing){
    offset=audio.currentTime;
    audio.pause();
    playing=false;
    $('play').textContent='播放'; render(offset);
  }else{
    if(offset>=duration) offset=0;
    if(audio.readyState>=1){ try{ audio.currentTime=offset; }catch(e){} }
    const p=audio.play();
    if(p&&p.catch) p.catch(()=>{});
    playing=true;
    $('play').textContent='暂停';
  }
}

function seek(t){
  ensureAudio();
  t=Math.max(0,Math.min(duration,t));
  offset=t;
  if(audio.readyState>=1){ try{ audio.currentTime=t; }catch(e){} }
  render(t);
}

/* 收集画面排版单元。字幕宿主是与配音同步的活文字，不进排序、不下钻：
   否则它在视觉最底部会排到最后一组，迟到约 1.3 秒，配音已开口而字幕还没出现。 */
function collectUnits(stage){
  const out=[];
  function walk(el){
    if(el.classList && el.classList.contains('subhost')) return;
    if(el.tagName && el.tagName.toLowerCase()==='svg'){ out.push(el); return; }
    const kids=el.children?Array.from(el.children):[];
    const ownText=el.childNodes?Array.from(el.childNodes).some(
      n=>n.nodeType===3 && n.nodeValue.trim().length):false;
    if(ownText || kids.length===0){ out.push(el); return; }
    kids.forEach(walk);
  }
  Array.from(stage.children).forEach(walk);
  return out;
}

function easeOut(p){ return 1-Math.pow(1-p,3); }

function makePlan(n){
  const root=$('s'+n), stage=root?root.querySelector('.stage'):null;
  if(!stage) return null;
  const units=collectUnits(stage);
  units.sort((a,b)=>{
    const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
    if(Math.abs(ra.top-rb.top)>12) return ra.top-rb.top;
    return ra.left-rb.left;
  });
  const groups=Math.min(units.length,ENTER_GROUPS);
  return {
    units:units.map((el,i)=>{
      const o=parseFloat(getComputedStyle(el).opacity);
      return {el:el,o:isNaN(o)?1:o,
              d:Math.floor(i*groups/Math.max(1,units.length))*ENTER_STEP};
    }),
    total:(groups-1)*ENTER_STEP+ENTER_DUR,
    done:false
  };
}

function buildPlans(){
  const scenes=Array.from(document.querySelectorAll('.scene'));
  scenes.forEach(s=>{s.style.display='block';});
  for(let n=2;n<=TIMELINE.scenes.length;n++) ENTER_PLAN[n]=makePlan(n);
  scenes.forEach(s=>{s.style.removeProperty('display');});
  document.body.dataset.units=Object.keys(ENTER_PLAN)
    .map(n=>n+':'+ENTER_PLAN[n].units.length).join(',');
}

function clearPlan(plan){
  if(!plan) return;
  plan.units.forEach(u=>{u.el.style.removeProperty('opacity');u.el.style.removeProperty('translate');});
  plan.done=false;
}

function applyEnter(t,idx){
  const n=idx+1, plan=ENTER_PLAN[n];
  if(!plan) return;
  const epoch=(ENTER_EPOCH[n]!==undefined)?ENTER_EPOCH[n]:TIMELINE.scenes[idx].start;
  const e=t-epoch;
  if(e>plan.total+0.02){
    if(!plan.done){ clearPlan(plan); plan.done=true; }
    return;
  }
  plan.done=false;
  plan.units.forEach(u=>{
    let p=(e-u.d)/ENTER_DUR;
    p=p<0?0:(p>1?1:p);
    if(p>=1){ u.el.style.removeProperty('opacity'); u.el.style.removeProperty('translate'); return; }
    const k=easeOut(p);
    u.el.style.opacity=(u.o*k).toFixed(3);
    u.el.style.setProperty('translate','0 '+((1-k)*ENTER_LIFT).toFixed(2)+'px');
  });
}

function replayEnter(){
  const n=activeIdx+1;
  if(n===1 || !ENTER_PLAN[n]) return;
  ENTER_EPOCH[n]=now();
  if(!playing) toggle();
  render(now());
}

/* 字幕只写当前场景自己页脚里的 .subline；淡入按 t - 字幕起点确定性计算。
   关键：句间 / 场景末尾字幕不可见时，只把 opacity 归零，绝不清空文字。
   文字一旦清空，行盒会塌成 0，页脚高度随之收缩，flex / 文档流里
   上方元素被整体下拉（实测最多 35.28px），成片里就是一次可见抖动。
   保留文字 = 字幕区域占位恒定；消失只是看不见，不是不存在。 */
function applySubtitle(t,idx,sub){
  const root=$('s'+(idx+1));
  const line=root?root.querySelector('.subline'):null;
  if(!line) return;
  if(sub){
    if(line.textContent!==sub.text) line.textContent=sub.text;
    const p=Math.max(0,Math.min(1,(t-sub.s)/SUB_FADE));
    line.style.opacity = p<1 ? (0.30+0.70*p).toFixed(3) : '1';
  }else{
    if(!line.textContent) line.textContent=SUB_PLACEHOLDER[idx];
    line.style.opacity='0';
  }
}

function render(t){
  let idx=0;
  for(let i=0;i<TIMELINE.scenes.length;i++) if(t>=TIMELINE.scenes[i].start) idx=i;
  if(idx!==activeIdx){
    if(activeIdx>=0){
      $('s'+(activeIdx+1)).classList.remove('active');
      clearPlan(ENTER_PLAN[activeIdx+1]);
    }
    activeIdx=idx;
    $('s'+(idx+1)).classList.add('active');
    document.querySelectorAll('.ch').forEach((el,i)=>el.classList.toggle('active',i===idx));
    $('reenter').disabled=(idx===0);
  }
  applyEnter(t,idx);
  let sub=null;
  for(let i=0;i<SUBS.length;i++){
    if(t>=SUBS[i].s && t<SUBS[i].e){ sub=SUBS[i]; break; }
  }
  applySubtitle(t,idx,sub);
  $('cur').textContent=fmt(t);
  $('seek').value=t;
  $('chapter').textContent=String(idx+1).padStart(2,'0')+' / 08';
}

function loop(){ if(playing) render(now()); requestAnimationFrame(loop); }

function buildChapters(){
  TIMELINE.scenes.forEach((s,i)=>{
    const b=document.createElement('button');
    b.className='ch'; b.textContent=String(i+1).padStart(2,'0');
    b.title='跳到 '+fmt(s.start);
    b.onclick=()=>seek(s.start);
    $('chapters').appendChild(b);
  });
}

/* 逐句宽度审计：?audit=1 时把 53 条字幕逐条塞进各自页脚，量出是否溢出画面 */
function audit(){
  const scenes=Array.from(document.querySelectorAll('.scene'));
  scenes.forEach(s=>{s.style.display='block';});
  const frame=$('stageFrame').getBoundingClientRect();
  const rows=[];
  TIMELINE.scenes.forEach((s,si)=>{
    const root=$('s'+(si+1)), line=root.querySelector('.subline');
    (s.subtitles||[]).forEach(c=>{
      line.textContent=c.text;
      const r=line.getBoundingClientRect();
      // block 型 .subline 盒宽不含 nowrap 溢出文字，用 scrollWidth 补判
      const spill=(line.clientWidth>0 && line.scrollWidth>line.clientWidth+1);
      rows.push({scene:si+1,n:c.text.length,text:c.text,
                 left:+(r.left-frame.left).toFixed(1),
                 right:+(r.right-frame.left).toFixed(1),
                 w:+r.width.toFixed(1),
                 cw:line.clientWidth,sw:line.scrollWidth,
                 overflow:(spill || r.left-frame.left < 4 || r.right-frame.left > frame.width-4)});
    });
  });
  scenes.forEach(s=>{s.style.removeProperty('display');});
  const bad=rows.filter(r=>r.overflow);
  const out={frameWidth:+frame.width.toFixed(1),total:rows.length,overflow:bad.length,bad:bad};
  $('auditResult').textContent=JSON.stringify(out);
  $('auditResult').style.display='block';
  document.title='AUDIT '+JSON.stringify(out);
}

$('play').onclick=toggle;
$('mute').onclick=()=>{
  muted=!muted;
  if(audio) audio.muted=muted;
  $('mute').textContent=muted?'取消静音':'静音';
  $('mute').classList.toggle('on',muted);
};
$('reenter').onclick=replayEnter;
$('immersive').onclick=()=>document.body.classList.toggle('immersive');
$('seek').addEventListener('input',e=>seek(parseFloat(e.target.value)));
document.addEventListener('keydown',e=>{
  if(e.code==='Space'){ e.preventDefault(); toggle(); }
  else if(e.code==='ArrowRight') seek(now()+5);
  else if(e.code==='ArrowLeft') seek(now()-5);
  else if(/^Digit[1-8]$/.test(e.code)) seek(TIMELINE.scenes[Number(e.code.slice(5))-1].start);
  else if(e.key==='r'||e.key==='R') replayEnter();
  else if(e.key==='i'||e.key==='I') document.body.classList.toggle('immersive');
});

$('total').textContent=fmt(TIMELINE.totalDuration);
$('seek').max=TIMELINE.totalDuration.toFixed(2);
if(q.get('capture')==='1') document.body.classList.add('capture');
buildChapters();
buildPlans();
render(0);
loop();
if(q.get('audit')==='1') audit();
const st=parseFloat(q.get('t'));
if(!isNaN(st)){ offset=Math.min(duration,st); render(offset); }
if(q.get('autoplay')==='1') toggle();

/* 帧源接口：给后续逐帧出片用，确定性、不推进音频 */
window.__seekTo=function(t){
  if(lastT!==null && Math.abs(lastT-t)<0.0005) return;
  lastT=t; offset=t; render(t);
};
window.__ready=true;
</script>
</body>
</html>
'''


def stage_bg(css):
    """读出该页 .stage 的实际底色，作为 .scene 的兜底背景。"""
    root = re.search(r":root\s*\{([^}]*)\}", css, re.S)
    variables = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", root.group(1))) if root else {}
    rule = re.search(r"\.stage\s*\{([^}]*)\}", css, re.S)
    if not rule:
        return "#F1E6D8"
    m = re.search(r"background\s*:\s*([^;]+);", rule.group(1))
    if not m:
        return "#F1E6D8"
    value = m.group(1).strip()
    var = re.match(r"var\((--[\w-]+)(?:,\s*([^)]+))?\)", value)
    if var:
        return variables.get(var.group(1), (var.group(2) or "#F1E6D8")).strip()
    return value


def build_scene(n, first_sub):
    cid = "s%d" % n
    css, stage = read_page(n)
    rule = RULES[n]
    repl = rule["html"].replace("{sub}", htmlmod.escape(first_sub))
    stage, cnt = re.subn(rule["find"], repl, stage, flags=re.S)
    if cnt != 1:
        raise RuntimeError("page %d footer replace count=%d" % (n, cnt))
    stage = strip_page_numbers(stage)
    # 效果图的 css 模板用 #c{n} 作前缀，动画场景根是 #sN
    extra = (rule["css"].replace("#c{n}", "#s%d" % n)
             .replace("{{", "{").replace("}}", "}"))
    # 只覆盖颜色，版式结构一字不动；subhost 与 subline 两处 color 一并替换
    old, new = BASE_COLORS[n], SUB_COLORS[n][0]
    extra, cnt = re.subn(r"(?<!-)color\s*:\s*%s" % re.escape(old),
                         "color:%s" % new, extra)
    if cnt == 0:
        raise RuntimeError("scene %d: no subtitle color to replace" % n)
    scoped_css = scoped(cid, css) + "\n" + extra
    scene_html = ('<section class="scene" id="s%d" style="background:%s">'
                  '<main class="stage">%s</main></section>'
                  % (n, stage_bg(css), stage))
    return scoped_css, scene_html


def main():
    with open(os.path.join(VOICE_DIR, "timeline.json"), encoding="utf-8") as f:
        timeline = json.load(f)
    with open(os.path.join(VOICE_DIR, "voiceover-full.mp3"), "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    css_blocks, scenes_html = [], []
    for i, scene in enumerate(timeline["scenes"], start=1):
        subs = scene.get("subtitles") or []
        first = subs[0]["text"] if subs else ""
        css, html = build_scene(i, first)
        css_blocks.append("/* ---- scene %d ---- */\n%s" % (i, css))
        scenes_html.append(html)

    slim = {k: v for k, v in timeline.items() if k != "scenes"}
    slim["scenes"] = [
        {k: v for k, v in s.items() if k not in ("words", "script")}
        for s in timeline["scenes"]
    ]
    out_html = (TEMPLATE
                .replace("__SCOPED_CSS__", "\n".join(css_blocks))
                .replace("__SCENES_HTML__", "\n".join(scenes_html))
                .replace("__TIMELINE_JSON__", json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
                .replace("__AUDIO_B64__", b64))
    path = os.path.join(HERE, "preview.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print("preview.html: %.0f KB | %d scenes | %d subtitles | voice %s | %.2fs"
          % (os.path.getsize(path) / 1024, len(scenes_html),
             sum(len(s["subtitles"]) for s in timeline["scenes"]),
             timeline["voice"], timeline["totalDuration"]))


if __name__ == "__main__":
    main()

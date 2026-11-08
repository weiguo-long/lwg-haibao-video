# -*- coding: utf-8 -*-
"""
把已确认的海报页搬进一个 HTML 时间轴预览（v2，通用模板）：
- 每页 = 一个 scene，显示时长由该段配音决定（含场景间静音）
- 底部固定深色字幕条，按短句级时间轴显示配音文字；画面元素不进入字幕区
- 画面文字保持海报原样，不做卡点高亮；去掉所有页码
- 除封面外逐元素依次入场，由播放时间 t 确定性驱动
- 音频内嵌为 base64，单文件离线可播
海报文件与场景从 timeline.json 的 scenes[].source 读取；标题从 project.json 读取。
确认后再用 timeline.json 搭 Remotion 工程渲染 MP4。
"""
import base64
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.dirname(HERE)


def project_title():
    p = os.path.join(HERE, "project.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return html.escape(json.load(f).get("title", "配音动画"))
    return "配音动画"

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · 配音动画预览</title>
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
#stageFrame{--sub:11.5%;--s:.885;position:relative;width:min(92vw,calc((100vh - 132px)*0.75));aspect-ratio:3/4;overflow:hidden;container-type:inline-size;box-shadow:0 18px 55px rgba(0,0,0,.55)}
/* 切场不做整体交叉淡化，动效交给场景内元素依次入场 */
.scene{position:absolute;inset:0;display:none}
.scene.active{display:block}
/* 海报安全区：等比缩放到字幕条上方，任何出血元素都被裁在这里 */
.poster-zone{position:absolute;left:0;right:0;top:0;height:calc(100% - var(--sub));overflow:hidden}
.poster-scale{position:absolute;top:0;left:50%;margin-left:-50%;width:100%;height:calc(100% / var(--s));transform:scale(var(--s));transform-origin:top center}
/* 底部字幕：配色中的墨色作底、米白作字、朱红作唯一点缀 */
#subbar{position:absolute;left:0;right:0;bottom:0;height:var(--sub);z-index:9;background:#1A1614;border-top:1px solid rgba(241,230,216,.16);display:flex;align-items:center;justify-content:center;padding:0 5%}
#submark{position:absolute;left:0;top:24%;bottom:24%;width:.6%;background:#AA2B3A}
#subtext{max-width:92%;color:#F1E6D8;font-size:3.05cqw;font-weight:600;letter-spacing:.035em;line-height:1.5;text-align:center;text-wrap:balance}
.hint{flex:none;padding:0 0 9px;font-size:11px;letter-spacing:.06em;color:#6F7B96}
body.immersive .toolbar,body.immersive .hint{display:none}
body.immersive #stageFrame{width:min(96vw,calc((100vh - 28px)*0.75))}
body.snapshot .scene{transition:none}
__SCOPED_CSS__
</style>
</head>
<body>
  <div class="toolbar">
    <span class="brand">__TITLE__ <em>·</em> 配音动画</span>
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
    <div id="stageFrame">
__SCENES_HTML__
      <div id="subbar"><span id="submark"></span><div id="subtext"></div></div>
    </div>
  </div>

  <p class="hint">点击播放试听 · 空格暂停 · ← → 快退快进 5 秒 · 数字 1–8 跳场景 · R 键重播入场 · I 键隐藏控制条</p>

<script>
const AUDIO_B64 = "__AUDIO_B64__";
const TIMELINE = __TIMELINE_JSON__;
const $ = id => document.getElementById(id);
const SUBS = [];
TIMELINE.scenes.forEach((s,si) => (s.subtitles||[]).forEach(c =>
  SUBS.push({s:c.start, e:c.end, text:c.text, k:si+'-'+c.id})));

let audio=null;
let playing=false, offset=0, activeIdx=-1, muted=false, lastSubKey='__init__';
let duration=TIMELINE.totalDuration;
const q=new URLSearchParams(location.search);
/* 入场动画完全由播放时间 t 决定，不依赖浏览器动画时钟：可逐帧复现、可直接搬进 Remotion */
const ENTER_DUR=0.46, ENTER_STEP=0.075, ENTER_LIFT=16, ENTER_GROUPS=18;
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
  document.body.dataset.step='audio-created';
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
    if(audio.readyState>=1){
      try{ audio.currentTime=offset; }catch(e){}
    }
    const p=audio.play();
    if(p&&p.catch) p.catch(e=>{document.body.dataset.step='play-rejected:'+e.message;});
    playing=true;
    $('play').textContent='暂停';
    document.body.dataset.step='playing';
  }
}

function seek(t){
  ensureAudio();
  t=Math.max(0,Math.min(duration,t));
  offset=t;
  if(audio.readyState>=1){
    try{ audio.currentTime=t; }catch(e){}
  }
  render(t);
}

/* 收集场景里的视觉单元：含自身文字的块整体算一个，纯容器继续下钻，SVG 整体算一个 */
function collectUnits(stage){
  const out=[];
  function walk(el){
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

/* 依次入场：按视觉位置从上到下排序，分成最多 18 组，每组间隔 75ms */
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
  scenes.forEach(s=>{s.style.display='block';});   // 临时展开以便量出视觉位置
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
  const key=sub?sub.k:'';
  if(key!==lastSubKey){
    lastSubKey=key;
    const el=$('subtext');
    el.textContent=sub?sub.text:'';
    if(sub && el.animate && !document.body.classList.contains('snapshot')){
      el.animate([{opacity:0,transform:'translateY(5px)'},{opacity:1,transform:'none'}],
                 {duration:200,easing:'ease-out'});
    }
  }
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
buildChapters();
buildPlans();
render(0);
loop();
const st=parseFloat(q.get('t'));
if(!isNaN(st)){
  offset=Math.min(duration,st);
  document.body.classList.add('snapshot');
  render(offset);
}
if(q.get('autoplay')==='1') toggle();
</script>
</body>
</html>
'''


def extract_stage(path, total):
    """取海报主画面；总页数由 timeline 推出，清掉三种形态的页码。"""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'<main class="stage">(.*?)</main>', src, re.S)
    if not m:
        raise RuntimeError("stage not found: " + path)
    stage = m.group(1).strip()
    tok = r"\d{1,3}\s*/\s*0?%d\b" % total
    # 右下角 NN / 总页数、藏在落款里的 <b>NN / 总页数</b>、VOL. 01 / 总页数 的页序
    stage = re.sub(r'<span class="(?:pg|page)">\s*' + tok + r'\s*</span>', '', stage)
    stage = re.sub(r'<b>\s*' + tok + r'\s*</b>', '', stage)
    stage = re.sub(r'\s*/\s*0?%d\b' % total, '', stage)
    stage = re.sub(r'[\u3000\s]+</p>', '</p>', stage)
    return stage


def stage_bg(css):
    """读出该页 .stage 的实际底色，用于填满缩放后两侧的留白。"""
    root = re.search(r':root\s*\{([^}]*)\}', css, re.S)
    variables = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+)', root.group(1))) if root else {}
    rule = re.search(r'\.stage\s*\{([^}]*)\}', css, re.S)
    if not rule:
        return '#F1E6D8'
    m = re.search(r'background\s*:\s*([^;]+);', rule.group(1))
    if not m:
        return '#F1E6D8'
    value = m.group(1).strip()
    var = re.match(r'var\((--[\w-]+)(?:,\s*([^)]+))?\)', value)
    if var:
        return variables.get(var.group(1), (var.group(2) or '#F1E6D8')).strip()
    return value


def scoped_css(n, css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    rules = re.findall(r'([^{}]+)\{([^{}]*)\}', css)
    out = []
    for sel, body in rules:
        sel, body = sel.strip(), body.strip()
        if not sel:
            continue
        if sel in ('*', 'html,body', 'html', 'body'):
            continue
        if sel == ':root':
            out.append('#s%d{%s}' % (n, body))
            continue
        if sel == '.stage':
            body = re.sub(r'width:min\([^;]*\);', 'width:100%;', body)
            body = re.sub(r'aspect-ratio:[^;]*;', 'height:100%;', body)
            # 海报自带的投影会落在缩放后的左右留白上，预览里由 stageFrame 统一提供
            body = re.sub(r'box-shadow:[^;}]*;?', '', body)
        parts = ['#s%d %s' % (n, p.strip()) for p in sel.split(',')]
        out.append(', '.join(parts) + '{' + body + '}')
    return '\n'.join(out)


def extract_css(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'<style>(.*?)</style>', src, re.S)
    return m.group(1) if m else ''


def main():
    with open(os.path.join(HERE, 'timeline.json'), encoding='utf-8') as f:
        timeline = json.load(f)
    total = len(timeline['scenes'])
    with open(os.path.join(HERE, 'voiceover-full.mp3'), 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')

    scenes_html, css_blocks = [], []
    for i, scene in enumerate(timeline['scenes'], start=1):
        path = os.path.join(PAGES, scene['source'])
        css = extract_css(path)
        scenes_html.append(
            '      <section class="scene" id="s%d">\n'
            '        <div class="poster-zone" style="background:%s">\n'
            '          <div class="poster-scale"><div class="stage">%s</div></div>\n'
            '        </div>\n'
            '      </section>'
            % (i, stage_bg(css), extract_stage(path, total))
        )
        css_blocks.append('/* ---- scene %d ---- */\n%s' % (i, scoped_css(i, css)))

    slim = {k: v for k, v in timeline.items() if k != 'scenes'}
    slim['scenes'] = [
        {k: v for k, v in s.items() if k not in ('words', 'script')}
        for s in timeline['scenes']
    ]
    html = (TEMPLATE
            .replace('__TITLE__', project_title())
            .replace('__SCOPED_CSS__', '\n'.join(css_blocks))
            .replace('__SCENES_HTML__', '\n'.join(scenes_html))
            .replace('__TIMELINE_JSON__', json.dumps(slim, ensure_ascii=False, separators=(',', ':')))
            .replace('__AUDIO_B64__', b64))
    out = os.path.join(HERE, 'preview.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('preview.html: %.0f KB | %d scenes | %d subtitles | voice %s' %
          (os.path.getsize(out) / 1024, len(scenes_html),
           sum(len(s['subtitles']) for s in timeline['scenes']), timeline['voice']))


if __name__ == '__main__':
    main()

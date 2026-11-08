# -*- coding: utf-8 -*-
"""
生成 Remotion 用的「纯帧源」页面 render.html（通用模板）。

与 preview.html 共用同一批海报 DOM / scoped CSS / timeline.json 渲染逻辑，
只剥掉播放器 UI 与音频，暴露 window.__seekTo(t)，由 Remotion 或 CDP 按 frame/fps 同步驱动。
因此成片画面与用户确认的 HTML 预览像素级一致。

同时把 timeline.json / voiceover-full.mp3 同步到 public/，
并按 timeline 的 fps / 尺寸 / totalFrames 生成 src/config.ts（若 src/ 存在）。
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_preview import extract_stage, extract_css, scoped_css, stage_bg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.dirname(HERE)
OUT = os.path.join(PAGES, "remotion", "public", "render.html")

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Price Story · frame source</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%;overflow:hidden;background:#1A1614}
body{font-family:"PingFang SC","Hiragino Sans GB","Source Han Sans SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased}
#stageFrame{--sub:11.5%;--s:.885;position:relative;width:100%;height:100%;overflow:hidden;container-type:inline-size}
.scene{position:absolute;inset:0;display:none}
.scene.active{display:block}
.poster-zone{position:absolute;left:0;right:0;top:0;height:calc(100% - var(--sub));overflow:hidden}
.poster-scale{position:absolute;top:0;left:50%;margin-left:-50%;width:100%;height:calc(100% / var(--s));transform:scale(var(--s));transform-origin:top center}
#subbar{position:absolute;left:0;right:0;bottom:0;height:var(--sub);z-index:9;background:#1A1614;border-top:1px solid rgba(241,230,216,.16);display:flex;align-items:center;justify-content:center;padding:0 5%}
#submark{position:absolute;left:0;top:24%;bottom:24%;width:.6%;background:#AA2B3A}
#subtext{max-width:92%;color:#F1E6D8;font-size:3.05cqw;font-weight:600;letter-spacing:.035em;line-height:1.5;text-align:center;text-wrap:balance}
__SCOPED_CSS__
</style>
</head>
<body>
<div id="stageFrame">
__SCENES_HTML__
  <div id="subbar"><span id="submark"></span><div id="subtext"></div></div>
</div>
<script>
const TIMELINE = __TIMELINE_JSON__;
const $ = id => document.getElementById(id);
const SUBS = [];
TIMELINE.scenes.forEach((s,si) => (s.subtitles||[]).forEach(c =>
  SUBS.push({s:c.start, e:c.end, text:c.text, k:si+'-'+c.id})));

const ENTER_DUR=0.46, ENTER_STEP=0.075, ENTER_LIFT=16, ENTER_GROUPS=18;
const ENTER_PLAN={};
let activeIdx=-1, lastSubKey='__init__', lastT=null;

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
  window.__units=Object.keys(ENTER_PLAN).map(n=>n+':'+ENTER_PLAN[n].units.length).join(',');
}
function clearPlan(plan){
  if(!plan) return;
  plan.units.forEach(u=>{u.el.style.removeProperty('opacity');u.el.style.removeProperty('translate');});
  plan.done=false;
}
function applyEnter(t,idx){
  const n=idx+1, plan=ENTER_PLAN[n];
  if(!plan) return;
  const e=t-TIMELINE.scenes[idx].start;
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
  }
  applyEnter(t,idx);
  let sub=null;
  for(let i=0;i<SUBS.length;i++){
    if(t>=SUBS[i].s && t<SUBS[i].e){ sub=SUBS[i]; break; }
  }
  const key=sub?sub.k:'';
  if(key!==lastSubKey){
    lastSubKey=key;
    $('subtext').textContent=sub?sub.text:'';
  }
}
window.__seekTo=function(t){
  if(lastT!==null && Math.abs(lastT-t)<0.0005) return;
  lastT=t;
  render(t);
};
buildPlans();
render(0);
/* 便于单帧截图验收：render.html?t=20 直接停在 20 秒的画面 */
const _q=new URLSearchParams(location.search);
const _st=parseFloat(_q.get('t'));
if(!isNaN(_st)) window.__seekTo(_st);
window.__frameReady=true;
</script>
</body>
</html>
'''


def main():
    with open(os.path.join(HERE, "timeline.json"), encoding="utf-8") as f:
        timeline = json.load(f)
    total = len(timeline["scenes"])

    scenes_html, css_blocks = [], []
    for i, scene in enumerate(timeline["scenes"], start=1):
        path = os.path.join(PAGES, scene["source"])
        css = extract_css(path)
        scenes_html.append(
            '  <section class="scene" id="s%d">\n'
            '    <div class="poster-zone" style="background:%s">\n'
            '      <div class="poster-scale"><div class="stage">%s</div></div>\n'
            '    </div>\n'
            '  </section>'
            % (i, stage_bg(css), extract_stage(path, total))
        )
        css_blocks.append("/* ---- scene %d ---- */\n%s" % (i, scoped_css(i, css)))

    slim = {k: v for k, v in timeline.items() if k != "scenes"}
    slim["scenes"] = [
        {k: v for k, v in s.items() if k not in ("words", "script")}
        for s in timeline["scenes"]
    ]
    html = (TEMPLATE
            .replace("__SCOPED_CSS__", "\n".join(css_blocks))
            .replace("__SCENES_HTML__", "\n".join(scenes_html))
            .replace("__TIMELINE_JSON__",
                     json.dumps(slim, ensure_ascii=False, separators=(",", ":"))))
    pub = os.path.dirname(OUT)
    os.makedirs(pub, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    # 让 Remotion 工程与时间轴自动同步
    shutil.copyfile(os.path.join(HERE, "timeline.json"),
                    os.path.join(pub, "timeline.json"))
    audio = os.path.join(HERE, "voiceover-full.mp3")
    if os.path.exists(audio):
        shutil.copyfile(audio, os.path.join(pub, "voiceover-full.mp3"))
    src_dir = os.path.join(os.path.dirname(pub), "src")
    if os.path.isdir(src_dir):
        config = (
            "// 由 build_render.py 从 timeline.json 自动生成，请勿手改\n"
            "export const FPS = %d;\n"
            "export const WIDTH = %d;\n"
            "export const HEIGHT = %d;\n"
            "export const DURATION_IN_FRAMES = %d;\n"
            % (timeline.get("fps", 30), timeline.get("width", 1080),
               timeline.get("height", 1440), timeline["totalFrames"])
        )
        with open(os.path.join(src_dir, "config.ts"), "w", encoding="utf-8") as f:
            f.write(config)

    print("render.html: %.0f KB | %d scenes | %d subtitles | %s" %
          (os.path.getsize(OUT) / 1024, len(scenes_html),
           sum(len(s["subtitles"]) for s in timeline["scenes"]), OUT))


if __name__ == "__main__":
    main()

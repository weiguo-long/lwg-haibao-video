# 阶段 3–4：HTML 动画、帧源与 MP4 渲染

## 1. 单页时间轴预览的架构

`build_preview.py` 把 N 个海报 HTML 合成一个 `preview.html`：

```
<body>
  <div class="toolbar">播放 / 进度 / 章节 / 静音 / 重播入场 / 沉浸</div>
  <div id="stageFrame">           container-type:inline-size
    <section class="scene" id="s1"> <div class="poster-zone"> <div class="poster-scale"> <div class="stage">…</div>
    … s2…sN
    <div id="subbar"><span id="submark"></span><div id="subtext"></div></div>
  </div>
</body>
```

- **scoped CSS**：把每张海报 `<style>` 里的规则按 `#sN <选择器>` 重写；`:root` 变量改挂到 `#sN`；跳过 `*` / `html,body` 全局规则；`.stage` 的 `width:min(...)` 改 `width:100%`、`aspect-ratio` 改 `height:100%`，并**去掉 `box-shadow`**（否则缩放后落在左右留白形成暗带）。
- **音频内嵌**：`voiceover-full.mp3` base64 写进 `AUDIO_B64`，单文件离线可播；体积约 2 MB。
- **时间轴 slim**：从 `timeline.json` 里剔除 `words` / `script` 再内联，避免预览文件膨胀。
- **snapshot 模式**：`?t=<秒>` 加 `body.snapshot`，禁用切场过渡与字幕淡入，方便截图验收。

## 2. 页码清理

在 `extract_stage()` 里对每张海报的 `<main class="stage">` 内容做正则清理（总页数由 `len(timeline.scenes)` 推出，不要硬编码 08）：

- 删 `<span class="pg|page">NN / 总页数</span>`
- 删藏在落款里的 `<b>NN / 总页数</b>`
- 删 ` / 总页数` 尾缀（`VOL. 01 / 08` → `VOL. 01`，期号保留）
- 清理尾部全角空格

播放器控制条里的 `01 / 08` 是章节指示，不是画面元素，保留。交付前用 `--dump-dom` 在画面区域搜 `/ 08` 确认零残留。

## 3. 字幕条与避让数学

```css
#stageFrame{--sub:11.5%;--s:.885;container-type:inline-size}
.poster-zone{height:calc(100% - var(--sub));overflow:hidden}
.poster-scale{height:calc(100% / var(--s));transform:scale(var(--s));transform-origin:top center}
#subbar{position:absolute;bottom:0;height:var(--sub);z-index:9;background:#1A1614}
#subtext{font-size:3.05cqw;color:#F1E6D8;text-wrap:balance}
```

`--s = 1 - --sub/100`：`poster-scale` 先撑到安全区高度的 `1/0.885` 倍，再等比缩回 `0.885`，视觉高度正好等于安全区。海报因此完整落在字幕条上方，`overflow:hidden` 裁掉出血装饰。左右留白用 `stage_bg()` 从海报 `:root` 变量与 `.stage{background:var(...)}` 解析出的实际底色填充，深底页不会露出黑边。

字幕按 `SUBS[]`（全片绝对时间）切换；切换时用 `lastSubKey` 去重，静音期清空文本只留深色条。`#submark` 是左缘朱红细竖条，唯一装饰。

## 4. 播放链路

用 `<audio>` + `Blob(mp3)` + `currentTime` 驱动，**不要用 Web Audio 的 `decodeAudioData`**（无头 Chrome 下 Promise 不 resolve，播放链路直接挂起）：

```js
audio = new Audio(URL.createObjectURL(new Blob([bytes], {type:'audio/mpeg'})));
function now(){ return audio && !audio.paused ? audio.currentTime : offset; }
```

`render(t)` 由 `requestAnimationFrame(loop)` 在播放时调用；`seek(t)` 直接设 `currentTime` 并 `render(t)`。空格暂停、←→ 快退快进 5 秒、数字 1–N 跳场景、`I` 沉浸模式（隐藏控制条便于录屏）、`R` 重播入场。

## 5. 逐元素依次入场（第 2–N 场景）

**唯一正确做法：由 `t - scene.start` 确定性驱动，每帧直接写 inline 样式。**

```
collectUnits(stage)：
  含自身文本的块 → 整体算 1 个单元（保住标题里朱红 <span> 不被拆散）
  纯容器 → 下钻到子块
  <svg> → 整体算 1 个
排序：getBoundingClientRect().top（容差 12px 视为同行）→ left
groups = min(units.length, 18)
delay(i) = floor(i * groups / units.length) * 0.075
动画：p = clamp((e - delay) / 0.46, 0, 1)，k = 1-(1-p)^3
     opacity = computedOpacity * k
     translate = "0 (1-k)*16px"
e > groups 总时长 → 移除 inline opacity/translate，完全复原
```

要点：

- 用独立 CSS `translate` 属性（`style.setProperty('translate', ...)`），**不覆盖**海报自带的 `rotate(-16deg)` / `translateX(-50%)`。
- 终点 opacity 取各元素原 computed 值，保住 `.deco{opacity:.1}` 等水印层次。
- 切场用 `display:none/block` **硬切**，不做整体交叉淡化，避免两层半透明叠加把动效糊掉。
- 封面静止；`ENTER_EPOCH[n]` 允许「重播入场」把起点重设到当前时间。
- 各页单元数示例 `2:17, 3:13, 4:16, 5:13, 6:7, 7:13, 8:9`，最长入场约 1.66 秒，远短于最短配音段（9.5 秒）。

验收：`?t=8.2 / 8.6 / 9.2 / 10.5 / 20` 逐帧截图，用 PIL 统计海报区域「非纸底像素」，应单调递增后稳定；终态与静态海报完全一致。

## 6. 纯帧源 render.html

`build_render.py` 生成 `remotion/public/render.html`：与 `preview.html` **共用同一批海报 DOM、scoped CSS 与 timeline 渲染逻辑**，只剥掉播放器 UI、音频和字幕淡入动画，暴露：

```js
window.__seekTo(t)   // 相同 t 直接 return；否则 render(t)
window.__frameReady = true
window.__units       // 各场景入场单元数，便于核对
```

附加 `?t=<秒>` 支持，便于单帧截图。同时把 `timeline.json` 复制到 `public/`，并按 `fps / totalFrames / width / height` 生成 `remotion/src/config.ts`，让 Remotion 工程与时间轴自动同步。

**成片与预览像素级一致的关键**：两条链路都消费同一个 `render.html` / 同一份 `timeline.json`，不要在 Remotion 里重写一套 React 版式。

## 7. CDP 确定性逐帧渲染（推荐主链路）

`render_cdp.py`：

1. 启动单个 Chrome：`--headless=new --remote-debugging-port=9333 --window-size=1080,1440 --force-device-scale-factor=1 --hide-scrollbars --no-sandbox`，加载 `file://…/render.html`。
2. 从 `http://127.0.0.1:9333/json` 取 `webSocketDebuggerUrl`；`Emulation.setDeviceMetricsOverride` 强制视口 1080×1440；轮询 `window.__frameReady`。
3. 每帧 `frame ∈ [0, totalFrames)`：`t = frame/fps` → `Runtime.evaluate("window.__seekTo(t)")`。
4. **状态缓存**：`key = (场景 idx, 当前字幕 id, 入场期则该帧号否则 -1)`；key 不变就复用上一帧 JPEG。入场期长度 = `(maxGroups-1)*step + duration + 0.3`。静止期画面完全不变，6113 帧通常只需约 480 次 `Page.captureScreenshot(format=jpeg, quality=90)`。
5. JPEG 字节流写入 ffmpeg stdin：

```
ffmpeg -y -f image2pipe -framerate 30 -vcodec mjpeg -i pipe:0 \
  -i voiceover-full.mp3 \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -shortest -movflags +faststart 成片.mp4
```

实测 3:23.75 / 1080×1440 / 6113 帧约 96 秒完成，成片约 5.4 MB。`-shortest` 让视频对齐音轨；`+faststart` 便于在线播放。

## 8. Remotion 工程（可复现，非必需主链路）

`assets/remotion/` 整目录复制到 `outputs/remotion/`，结构：

```
package.json          render / still / studio 三个脚本
src/index.ts          registerRoot
src/Root.tsx          Composition，常量从 ./config 读取
src/config.ts         由 build_render.py 从 timeline.json 生成
src/PriceStory.tsx    同源 iframe + 每帧同步 seek + <Audio>
public/render.html    帧源（build_render.py 生成）
public/timeline.json  时间轴（build_render.py 复制）
public/voiceover-full.mp3
```

`PriceStory.tsx` 的关键点：

- iframe `src={staticFile('render.html')}`，与父页同源，可直接同步访问 `contentWindow.__seekTo`。
- `useState(() => delayRender(...))` 等 iframe `onLoad` 后 `continueRender(handle)`。
- **首帧时序坑**：单帧渲染时组件只挂载一次，`useLayoutEffect` 首次执行时 iframe 还没加载完，seek 被跳过 → 画面停在初始帧。必须在 `onLoad` 里立即 `seek(tRef.current)`，并在 render 阶段与每次 `useLayoutEffect` 各兜底一次。
- `<Audio src={staticFile('voiceover-full.mp3')} />` 混入音轨。
- 渲染命令加 `--browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` 指向本机 Chrome，避免下载 Headless Shell；`--image-format=jpeg --jpeg-quality=90` 提速。

**性能预期**：iframe 逐帧 seek 全片在本机 concurrency=6 跑 16 分钟未产出；先用 `still --frame=300` 与 `--frames=0-60` 短片验证工程可用，正式成片交给 CDP 链路。两者帧源相同，画面无差异；在交付说明里如实写明用了哪条链路。

## 9. 成片验收命令

```bash
# 规格与音轨
ffmpeg -hide_banner -i 成片.mp4            # Duration / 1080x1440 / 30fps / h264+aac
ffmpeg -i 成片.mp4 -af volumedetect -f null -   # mean_volume 约 -25dB 说明音轨非静音

# 抽 9 帧拼图（1 / 场景2起点+0.2 / 场景2终态 / 各场景中段 / 结尾）
ffmpeg -ss <t> -i 成片.mp4 -frames:v 1 /tmp/chk-<t>.png
```

用图像查看工具逐格核对：场景序号、字幕文字与时间点、入场中间态、底部字幕条、无播放器 UI / 无页码 / 无黑边。

`--dump-dom` 用于核对运行时状态：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --no-sandbox --virtual-time-budget=1500 --dump-dom \
  "file://…/preview.html?t=150" | python3 -c "…抓 #subtext / body.class / data-step…"
```

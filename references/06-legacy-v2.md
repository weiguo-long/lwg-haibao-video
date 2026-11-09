# 历史链路 v2：独立字幕条、避让缩放、Remotion 工程

v3 已默认走「字幕即页脚 + 帧源即预览」，本篇保留 v2 的完整做法。适用场景：用户明确要求画面外有独立字幕条、或需要 Remotion 可复现工程、或复用 `scripts/build_preview.py` / `build_render.py` / `render_cdp.py` 这套已有脚本。

## 1. 结构差异

```
<div id="stageFrame">  --sub:11.5%; --s:.885
  <section class="scene" id="sN">
    <div class="poster-zone"><div class="poster-scale"><main class="stage">…</main></div></div>
  </section>
  <div id="subbar"><span id="submark"></span><div id="subtext"></div></div>
</div>
```

字幕是画面外的通栏 `#subbar`，所有场景共用一条；画面整体等比缩放塞进上方安全区。

## 2. 避让数学

```css
#stageFrame{--sub:11.5%;--s:.885;container-type:inline-size}
.poster-zone{height:calc(100% - var(--sub));overflow:hidden}
.poster-scale{height:calc(100% / var(--s));transform:scale(var(--s));transform-origin:top center}
#subbar{position:absolute;bottom:0;height:var(--sub);z-index:9;background:#1A1614}
#subtext{font-size:3.05cqw;color:#F1E6D8;text-wrap:balance}
```

`--s = 1 - --sub/100`：`poster-scale` 先撑到安全区高度的 `1/0.885` 倍再缩回，视觉高度正好等于安全区；`overflow:hidden` 裁掉出血装饰。左右留白用 `stage_bg()` 从海报 `:root` 变量与 `.stage{background:var(...)}` 解析出的**逐页实际底色**填充，深底页不会露黑边。

字幕按 `SUBS[]`（全片绝对时间）切换，切换时用 `lastSubKey` 去重，静音期清空文本只留深色条。`#submark` 是左缘朱红细竖条，唯一装饰。

> 注意：v2 的「静音期清空文本」在独立通栏字幕条里是安全的（它是绝对定位、固定高度的独立层），**但搬到 v3 页脚里会造成布局塌陷**，见 `05-subtitle-as-footer.md` 第 4 节。

## 3. 纯帧源 render.html

`build_render.py` 生成 `remotion/public/render.html`：与 `preview.html` 共用同一批海报 DOM、scoped CSS 与 timeline 渲染逻辑，只剥掉播放器 UI、音频和字幕淡入，暴露：

```js
window.__seekTo(t)   // 相同 t 直接 return；否则 render(t)
window.__frameReady = true
window.__units       // 各场景入场单元数
```

附加 `?t=<秒>` 单帧截图；同时把 `timeline.json` 复制到 `public/`，按 `fps / totalFrames / width / height` 生成 `remotion/src/config.ts`。**成片与预览像素级一致的关键**：两条链路消费同一个 `render.html` 与同一份 `timeline.json`，不要在 Remotion 里重写一套 React 版式。

## 4. CDP 渲染（v2 版）

`render_cdp.py` 与 v3 主链路相同，差别在：加载 `render.html` 而非 `preview.html?capture=1`；`state_key` 只含 `(场景 idx, 字幕 id, 入场期帧号)`，**没有字幕淡入期**（v2 帧源剥掉了淡入，所以不会冻住；v3 若照搬会整句半透明）。6113 帧约 480 次截图、96 秒。

## 5. Remotion 工程

`assets/remotion/` 整目录复制到 `outputs/remotion/`：

```
package.json          render / still / studio 三个脚本
src/index.ts          registerRoot
src/Root.tsx          Composition，常量从 ./config 读取
src/config.ts         由 build_render.py 从 timeline.json 生成
src/PriceStory.tsx    同源 iframe + 每帧同步 seek + <Audio>
public/render.html    帧源（build_render.py 生成）
public/timeline.json  时间轴
public/voiceover-full.mp3
```

`PriceStory.tsx` 关键点：

- iframe `src={staticFile('render.html')}`，同源可直接访问 `contentWindow.__seekTo`。
- `useState(() => delayRender(...))` 等 iframe `onLoad` 后 `continueRender(handle)`。
- **首帧时序坑**：单帧渲染组件只挂载一次，`useLayoutEffect` 首次执行时 iframe 还没加载完，seek 被跳过 → 画面停在初始帧。必须在 `onLoad` 里立即 `seek(tRef.current)`，并在 render 阶段与每次 `useLayoutEffect` 各兜底一次。
- `<Audio src={staticFile('voiceover-full.mp3')} />` 混入音轨。
- 渲染加 `--browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` 指向本机 Chrome；`--image-format=jpeg --jpeg-quality=90` 提速。

**性能预期**：iframe 逐帧 seek 全片在本机 concurrency=6 跑 16 分钟未产出；用 `still --frame=300` 与 `--frames=0-60` 验证工程可用即可，正式成片交给 CDP。两者帧源相同、画面无差异。

## 6. v2 → v3 迁移清单

| 项 | v2 | v3 |
|---|---|---|
| 字幕层 | 画面外通栏 `#subbar` | 每页自己的 `.subhost > .subline` |
| 画面 | 缩放到 0.885、溢出裁切 | 满幅 3:4，不缩放 |
| 页码 | 动画阶段正则清除 | 静态版式阶段就取消，页脚位改放字幕 |
| 字幕色 | 统一墨底米白字 | 逐页取该页原有文字色 |
| 句间空档 | 清空字幕文字（安全） | **只隐藏不清空**（否则布局塌陷） |
| 帧源 | 另做 `render.html` | 直接 `preview.html?capture=1` |
| 渲染器 | `render_cdp.py` | `render_cdp_v3.py`（+淡入期状态 + 固定视口后 `buildPlans()`） |
| 验收 | 截帧看 | 几何测量 + 像素统计双重 |
| Remotion | 可复现工程 | 不需要 |

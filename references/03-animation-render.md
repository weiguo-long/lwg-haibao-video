# 阶段 3–4（v3）：HTML 动画、帧源即预览、MP4 渲染

v3 相对 v2 的结构性简化：**不再另做一份 `render.html`**。用户确认过的 `preview.html?capture=1` 就是唯一帧源，预览里看到的画面 = 成片画面。字幕即页脚、逐页取色、占位恒定见 `references/05-subtitle-as-footer.md`；v2 的独立字幕条、避让缩放与 Remotion 工程见 `references/06-legacy-v2.md`。

## 1. preview.html 架构

```
<body class="capture?">        ?capture=1 隐藏 toolbar / hint，画面满幅
  <div class="toolbar">播放 / 进度 / 章节 / 静音 / 重播入场 / 沉浸</div>
  <div id="stageFrame">        container-type:inline-size
    <section class="scene" id="s1"><main class="stage">…含 .subhost > .subline…</main></section>
    … s2…sN
  </div>
  <audio> 由 Blob(mp3) 创建，base64 内嵌
</body>
```

- **scoped CSS**：把每张海报 `<style>` 的规则按 `#sN <选择器>` 重写；`:root` 变量改挂到 `#sN`；跳过 `*` / `html,body` 全局规则；`.stage` 的 `width:min(...)` 改 `width:100%`、`aspect-ratio` 改 `height:100%`，并**去掉 `box-shadow`**（否则缩放后落在左右留白形成暗带）。
- **逐页版式规则**：`RULES[n]` 的 CSS 模板用 `#c{n}` 作前缀，生成时替换成 `#sN`，再叠加 `SUB_COLORS[n]` 的颜色覆盖。
- **音频内嵌**：`voiceover-full.mp3` base64 写进 `AUDIO_B64`，单文件离线可播，约 2.2 MB。
- **时间轴 slim**：从 `timeline.json` 剔除 `words` / `script` 再内联，避免预览膨胀。
- **页码清理**：三条正则删 `NN / 总页数`、落款里的 `<b>NN / 总页数</b>`、`VOL. 01 / 08` 尾缀（总页数由 `len(scenes)` 推出，别硬编码 08）。播放器控制条里的 `01 / 08` 是章节指示，保留。

## 2. URL 参数与帧源接口

| 参数 / 接口 | 用途 |
|---|---|
| `?capture=1` | 隐藏播放器 UI，作为 CDP 帧源；不推进音频 |
| `?t=秒` | 确定性定位到某一帧，用于无头截图验收 |
| `?audit=1` | 把全部字幕逐条塞进各自页脚，量 `scrollWidth` / `clientWidth` / 左右边界，结果写进 `<title>AUDIT …</title>`，用 `--dump-dom` 取 |
| `window.__seekTo(t)` | 逐帧渲染入口；相同 `t` 直接 `return`，否则 `render(t)` |
| `window.__ready` | 页面就绪标志，CDP 轮询它 |
| `buildPlans()` | 重算逐元素入场排序；**固定视口后必须重新调用** |

`__seekTo` 必须是 `t` 的纯函数：同一 `t` 反复调用得到同一画面，入场中间态也能复现。`check_seek.py` 验证这一点，并额外检查句间空档「文字保留 + `opacity=0`」。

## 3. 播放链路

用 `<audio>` + `Blob(mp3)` + `currentTime` 驱动，**不要用 Web Audio 的 `decodeAudioData`**（无头 Chrome 下 Promise 不 resolve）：

```js
audio = new Audio(URL.createObjectURL(new Blob([bytes], {type:'audio/mpeg'})));
function now(){ return audio && !audio.paused ? audio.currentTime : offset; }
```

`render(t)` 由 `requestAnimationFrame(loop)` 在播放时调用；`seek(t)` 设 `currentTime` 并 `render(t)`。空格暂停、←→ 跳 5 秒、数字 1–N 跳场景、`R` 重播入场、`I` 隐藏控制条。

## 4. 逐元素依次入场（第 2–N 场景）

**唯一正确做法：由 `t - scene.start` 确定性驱动，每帧直接写 inline 样式。**

```
collectUnits(stage)：
  遇到 .subhost 直接 return（字幕不参与入场，见 05）
  含自身文本的块 → 整体算 1 个单元（保住标题里朱红 <span> 不被拆散）
  纯容器 → 下钻到子块；<svg> → 整体算 1 个
排序：getBoundingClientRect().top（容差 12px 视为同行）→ left
groups = min(units.length, 18)
delay(i) = floor(i * groups / units.length) * 0.075
动画：p = clamp((e - delay) / 0.46, 0, 1)，k = 1-(1-p)^3
     opacity = computedOpacity * k
     translate = "0 (1-k)*16px"
e > 总时长 → 移除 inline opacity/translate，完全复原
```

- 用独立 CSS `translate` 属性，**不覆盖**海报自带的 `rotate(-16deg)` / `translateX(-50%)`。
- 终点 opacity 取各元素原 computed 值，保住 `.deco{opacity:.1}` 等水印层次。
- 切场用 `display:none/block` **硬切**，不做整体交叉淡化。
- 封面静止；`ENTER_EPOCH[n]` 允许「重播入场」把起点重设到当前时间。
- 固定 1080×1440 视口后单元数会变（本项目 `2:15, 3:11, 4:15, 5:13, 6:7, 7:13, 8:8`），最长入场约 1.74 秒。

验收：`?t=8.24 / 8.59 / 9.04 / 9.54 / 10.34` 截 5 帧序列，元素应逐步增多且终态完整；字幕在每一帧都稳定显示在页脚。

## 5. CDP 确定性逐帧渲染

`render_cdp_v3.py`：

1. 启动单个 Chrome：`--headless=new --remote-debugging-port=<随机> --window-size=1080,1440 --force-device-scale-factor=1 --hide-scrollbars --no-sandbox --remote-allow-origins=*`，加载 `file://…/preview.html?capture=1`。
2. 从 `/json` 找 URL 含 `preview.html` 的 page 取 `webSocketDebuggerUrl`；`Emulation.setDeviceMetricsOverride({width:1080,height:1440,deviceScaleFactor:1,mobile:false})` **强制视口**；轮询 `window.__ready`。
3. **固定视口后调 `buildPlans()`** 重算入场排序，否则排序基于默认视口、成片与验收帧不一致。
4. 每帧 `frame ∈ [0, totalFrames)`：`t = frame/fps` → `Runtime.evaluate("window.__seekTo(t)")`。
5. **状态缓存**：

```python
def state_key(t, frame):
    idx = 当前场景
    sub, sub_start = "", None
    for c in scene["subtitles"]:
        if c["start"] <= t < c["end"]:
            sub, sub_start = c.get("id", str(c["start"])), c["start"]
            break
    entering = idx > 0 and (t - scene["start"]) < ENTER_WINDOW   # 2.0s
    fading   = sub_start is not None and (t - sub_start) < SUB_FADE # 0.18s
    return (idx, sub, frame if (entering or fading) else -1)
```

`fading` 这一项**不能省**：否则字幕切换后 0.18s 的淡入会被冻结在第一帧（约 30% 不透明度），整句字幕都半透明。句间空档 `sub=""` 与有字幕时 key 不同，会单独截一帧（此时占位保留、文字隐藏），空档内再复用。

6. JPEG 写 ffmpeg stdin：

```
ffmpeg -y -f image2pipe -framerate 30 -vcodec mjpeg -i pipe:0 \
  -i voiceover-full.mp3 \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -shortest -movflags +faststart 成片.mp4
```

实测 3:23.75 / 1080×1440 / 6113 帧 / 724 次截图 / 约 75 秒 / 5.79 MB。

**先跑冒烟片**：`python3 render_cdp_v3.py /tmp/smoke.mp4 300` 只渲前 300 帧（约 6 秒），覆盖第 1 个句间空档（约 7.39–8.14s）。抽 7.20 / 7.45 / 7.95 / 8.32 四帧，确认字幕淡入正常、空档时其它元素不抖、无拉伸，再跑全片。

## 6. 无头 CDP 视口坑

不固定视口时，headless 默认 viewport 高度比 `--window-size` 少一截（实测 900×1200 会变成 900×1057），截图被拉伸。必须 `Emulation.setDeviceMetricsOverride`，并在其后 `buildPlans()`。`check_seek.py` 会验证 CDP 帧与 `--screenshot` 预览帧**逐像素一致**。

## 7. 成片验收

```bash
python3 verify_video.py
```

- `ffmpeg -hide_banner -i 成片.mp4 -f null -` 读 Duration / 1080×1440 / 30fps / h264+aac；
- 10 个时间点抽帧与 `preview.html` 帧比对，平均像素差应在 1.4–3.3（JPEG 压缩量级），亮度区间 63.6（深底）–220.7（浅底）说明无黑帧；
- 句间空档：字幕行内差异 1.2%–3.8%，**行外 < 0.01%**；用区域统计而非全局 bbox 判定；
- 输出抽帧拼图与空档对照图（可见 / 消失 / 差异）。

## 8. Remotion 的位置

v3 不需要 Remotion。v2 曾以「同源 iframe + 每帧 seek」做可复现工程，但本机 6113 帧并发 16 分钟无产出，只验证了单帧与 0–60 帧短片。保留在 `assets/remotion/` 与 `references/06-legacy-v2.md` 供需要时参考，**正式成片一律用 CDP 链路**，并在交付说明里写明用了哪条链路。

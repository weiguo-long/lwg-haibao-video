# 故障速查：症状 → 原因 → 修法

按现象检索。所有条目均来自实际渲染中踩过并修掉的问题。

## 动画与播放

| 症状 | 原因 | 修法 |
|---|---|---|
| 无头 Chrome 截图里入场动画永远停在第一帧，或 `--virtual-time-budget` 加大也没用 | 虚拟时钟不推进 `document.timeline`，WAAPI / CSS animation 不执行 | 改为由 `t - scene.start` 确定性驱动，每帧直接写 inline `opacity` / `translate` |
| 自动播放验证失败，页面一直显示初始状态 | Web Audio 的 `decodeAudioData` 在无头 Chrome 下 Promise 不 resolve | 用 `<audio>` + `Blob(mp3)` + `currentTime` 驱动；加 `body.dataset.step` 打点定位卡在哪一步 |
| 逐元素入场后标题里的朱红块被单独拆出来闪现 | 单元收集下钻到了含文本元素的子节点 | `collectUnits()` 里「含自身文本 → 整块算 1 个单元」，只有纯容器才下钻 |
| 斜线装饰的旋转角度在入场后丢失 | 动画写了 `style.transform`，覆盖了海报原本的 `rotate(-16deg)` | 用独立 CSS `translate` 属性，不用 `transform`；终点 opacity 取 computed 值保住水印透明度 |
| 切场时两层画面半透明叠加、动效发糊 | 0.3 秒整体交叉淡化与元素入场同时进行 | 改成 `display:none/block` 硬切，动效全部交给元素入场 |
| 拖动进度条后入场动画没有重播 | 动画依赖挂载时的时钟 | 时间驱动天然可 seek；「重播入场」用 `ENTER_EPOCH[n]` 重设起点 |

## 画面与排版

| 症状 | 原因 | 修法 |
|---|---|---|
| 海报缩放后左右留白出现两条灰暗带 | 海报 `.stage` 自带 `box-shadow` 落在缩放后的留白上 | `scoped_css()` 对 `.stage` 规则去掉 `box-shadow`；正则用 `box-shadow:[^;}]*;?`（压缩 CSS 最后一条声明可能无分号） |
| 朱红短线 / 装饰线完全看不见 | 百分比 `height` 在「绝对定位且高度 auto」的父容器内塌成 0 | 装饰线高度一律用 `cqw` |
| `cqw` 单位不生效、字号忽大忽小 | 容器没声明 `container-type:inline-size` | 在 `.stage`（海报）与 `#stageFrame`（预览/帧源）上声明 |
| 元素压到字幕条上、底部文字被裁 | 海报按全高摆放 | 字幕条 `height:var(--sub)=11.5%` 且不透明置顶；`--s = 1 - --sub/100 = .885`，`.poster-zone{overflow:hidden}` 裁出血 |
| 深底页左右出现黑边 | 留白填了统一底色而非该页底色 | `stage_bg()` 从海报 `:root` 变量 + `.stage{background:var(...)}` 解析实际底色，逐页填充 |
| 页码仍残留在画面里 | 除了右下角页码，还有藏在《道德经》落款里的 `<b>08 / 08</b>`、`VOL. 01 / 08` 尾缀 | 三条正则全清（总页数由 `len(scenes)` 推出，别硬编码 08），再用 `--dump-dom` 在画面区验证零残留 |
| 长字幕换成两行或溢出字幕条 | 单条字幕过长 | `subtitleMax=22` 句内合并上限 + 超长硬切 + `text-wrap:balance`；`3.05cqw` 字号在 1080 宽下单行放得下 |
| 深底页 / 朱红实心块上的文字高亮后不可读 | 早期 v1 的卡点高亮用整体透明度，压在色块上变暗红 | v2 已彻底取消卡点高亮；若复用 v1，改成只调字色明暗，并在深底页提亮米白 |

## 配音与时间轴

| 症状 | 原因 | 修法 |
|---|---|---|
| 拿不到词级时间戳 | `edge_tts.Communicate` 没传 `boundary="WordBoundary"` | 必须显式传；`offset/duration` 单位 100ns，除以 `1e7` 得秒 |
| 字幕读起来连成一片、没有停顿 | 切分时把所有标点都删了 | 以句号为硬边界，句内按逗号合并到 ≤22 字，**保留句内标点**，只去句末标点 |
| 字幕时间点倒退或重叠 | 锚点在字符流里 `find` 失配 | 前 3 字锚点 + 比例插值兜底；生成后做单调性修正（推到前一条 +0.35s）并补齐空隙 |
| 音轨时长与 `totalDuration` 差几十毫秒到几百毫秒 | 用 mp3 文件头时长算场景（有编码器延迟） | 先解码成 24kHz mono s16le WAV，用 `getnframes()/SR` 算时长，采样级拼接 |
| 静音期字幕不清空 | 字幕 `end` 覆盖到了下一段起点 | 最后一条字幕 `end = cursor + duration`，不跨过 `gap`；渲染时按绝对时间查找，查不到就清空 |

## 环境与工具

| 症状 | 原因 | 修法 |
|---|---|---|
| 总览拼图里中文标签显示为方块 | `/System/Library/Fonts/PingFang.ttc` 在本机不存在，PIL 回退到默认字体 | 用 `/System/Library/Fonts/STHeiti Medium.ttc`；第二行标签被裁时把画布加高约 70px |
| `timeout: command not found` | macOS 默认无 GNU `timeout` | 用工具调用自身的超时参数，或 `curl --max-time` 等替代 |
| `ps: operation not permitted` | 沙箱限制进程查询 | 不做进程轮询，靠后台任务通知与输出文件判断是否完成 |
| `npm install` 耗时 6 分钟以上 | registry 首次响应约 8.5 秒 | 后台运行，期间并行推进不依赖 npm 的工作；交付时说明 |
| 系统 PATH 里没有 ffmpeg | 本环境由 `imageio_ffmpeg` 提供 | `imageio_ffmpeg.get_ffmpeg_exe()` 取路径；已含 libx264 / aac / libmp3lame |
| 找不到 `html` skill 或 `shot.py` | 环境未安装 | 按 `lwg-haibao-design` 的 baseline + checklist 出稿，用 Chrome 无头截图验收；**不要中断流程**，在交付说明里写明替代方式 |

## Remotion 专项

| 症状 | 原因 | 修法 |
|---|---|---|
| `remotion still` 输出的是第 1 场景初始画面，字幕为空 | 单帧渲染组件只挂载一次，`useLayoutEffect` 首次执行时 iframe 尚未 onLoad，seek 被跳过 | `onLoad` 里立即 `seek(tRef.current)`；render 阶段与每次 `useLayoutEffect` 各兜底一次；`delayRender` 在 seek 之后才 `continueRender` |
| 全片渲染十几分钟无产出 | iframe 逐帧同步 seek + 每帧截图，6113 帧开销大 | 用 `still --frame=300` 与 `--frames=0-60` 验证工程；正式成片交给 CDP 链路；加 `--image-format=jpeg --jpeg-quality=90` 提速 |
| 提示要下载 Chrome Headless Shell | Remotion 默认用自己的浏览器 | 加 `--browser-executable="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`（路径含空格必须加引号） |
| 改了配音但 Remotion 时长没变 | `Root.tsx` 里写了固定常量 | 由 `build_render.py` 从 `timeline.json` 生成 `src/config.ts`，`Root.tsx` 一律从 `./config` 读 |

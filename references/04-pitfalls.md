# 故障速查：症状 → 原因 → 修法

按现象检索。所有条目均来自实际渲染中踩过并修掉的问题。标 `v2` 的只适用于历史独立字幕条链路，标 `v3` 的是当前默认链路。

## 动画与播放

| 症状 | 原因 | 修法 |
|---|---|---|
| 无头 Chrome 截图里入场动画永远停在第一帧，或 `--virtual-time-budget` 加大也没用 | 虚拟时钟不推进 `document.timeline`，WAAPI / CSS animation 不执行 | 改为由 `t - scene.start` 确定性驱动，每帧直接写 inline `opacity` / `translate` |
| 自动播放验证失败，页面一直显示初始状态 | Web Audio 的 `decodeAudioData` 在无头 Chrome 下 Promise 不 resolve | 用 `<audio>` + `Blob(mp3)` + `currentTime` 驱动 |
| 逐元素入场后标题里的朱红块被单独拆出来闪现 | 单元收集下钻到了含文本元素的子节点 | `collectUnits()` 里「含自身文本 → 整块算 1 个单元」，只有纯容器才下钻 |
| 斜线装饰的旋转角度在入场后丢失 | 动画写了 `style.transform`，覆盖了海报原本的 `rotate(-16deg)` | 用独立 CSS `translate` 属性；终点 opacity 取 computed 值保住水印透明度 |
| 切场时两层画面半透明叠加、动效发糊 | 0.3 秒整体交叉淡化与元素入场同时进行 | 改成 `display:none/block` 硬切 |
| 拖动进度条后入场动画没有重播 | 动画依赖挂载时的时钟 | 时间驱动天然可 seek；「重播入场」用 `ENTER_EPOCH[n]` 重设起点 |
| **v3** 字幕在场景开头迟到约 1.3 秒，配音已开口字幕还没出来 | 把 `.subline` 排进了按视觉 top→left 的入场序列，它总在最后 | `collectUnits()` 遇到 `.subhost` 直接 `return`；字幕改为切句时 0.18s 淡入，与配音同步 |

## 字幕占位与配色（v3 重点）

| 症状 | 原因 | 修法 |
|---|---|---|
| **字幕一消失，整页元素往下跳一下** | 句间 / 场景末尾执行 `line.textContent=''`，行盒塌成 0，页脚收缩 10–35px，flex / 文档流把上方元素整组下拉 | 空档只写 `line.style.opacity='0'`，**文字保留**；加 `SUB_PLACEHOLDER` 兜底。实测 8/8 页受影响，08 页连引文与结语句都被下拉 35.28px |
| 字幕颜色非黑即白，和页面像两套系统 | 把原页脚元素换成字幕时顺手把颜色刷成统一墨色 / 米白，抹掉了该位置本来的 `.foot-en` 灰蓝、`.src` 灰蓝、`.foot-box` 夜蓝 | 逐页 `SUB_COLORS` 映射，只覆盖颜色声明不动结构；深底页用米白掺灰蓝 28% 的 `#C2BFBD` 而非纯白 |
| 设计效果图里方案 A / B 渲染成同一个样子 | 方案标记写在卡片自身，样式却用了后代选择器 `.planA .card .subfoot` | 改成 `.card.planA .subfoot` |
| 深底页方案 A 出现浅底浅字，看不清 | 封面页自己定义了 `--ink: #F1E6D8`，覆盖了展板全局的墨色变量 | 展板配色一律用字面色值，不用会被页面 `:root` 污染的 CSS 变量 |
| 字幕上沿与原页脚文字几乎贴在一起 | 让位距离 3.6cqw 时净距只有约 8px | 调到 4.6cqw；按 900×1200 实算净距（A 约 17px、B 约 23px）再定 |
| 24 字最长字幕折行或溢出 | 字号 / 版心宽度不匹配 | `2.8cqw` + `white-space:nowrap`；版心可用 707px，24 字约 617px，余量 90px；逐句 `?audit=1` 量 `scrollWidth` |
| 字幕与页面主文案上下两句几乎重复 | 海报本就是拿配音文案排的 | 文案层面问题，不是版式问题；列「换字幕 / 删弱页面句 / 接受」三选一交回用户，**不要擅自改稿** |

## 画面与排版

| 症状 | 原因 | 修法 |
|---|---|---|
| 海报缩放后左右留白出现两条灰暗带 | 海报 `.stage` 自带 `box-shadow` 落在缩放后的留白上 | `scoped_css()` 对 `.stage` 规则去掉 `box-shadow`；正则用 `box-shadow:[^;}]*;?` |
| 朱红短线 / 装饰线完全看不见 | 百分比 `height` 在「绝对定位且高度 auto」的父容器内塌成 0 | 装饰线高度一律用 `cqw` |
| `cqw` 单位不生效、字号忽大忽小 | 容器没声明 `container-type:inline-size` | 在 `.stage`（海报）与 `#stageFrame`（预览）上声明 |
| **v2** 元素压到字幕条上、底部文字被裁 | 海报按全高摆放 | 字幕条 `height:var(--sub)=11.5%` 且不透明置顶；`--s = 1 - --sub/100 = .885`；`.poster-zone{overflow:hidden}` |
| **v2** 深底页左右出现黑边 | 留白填了统一底色而非该页底色 | `stage_bg()` 逐页从 `:root` + `.stage{background:var(...)}` 解析实际底色 |
| 页码仍残留在画面里 | 除了右下角页码，还有藏在落款里的 `<b>08 / 08</b>`、`VOL. 01 / 08` 尾缀 | 三条正则全清（总页数由 `len(scenes)` 推出），再用 `--dump-dom` 验证零残留 |
| 深底页 / 朱红块上的文字高亮后不可读 | v1 的卡点高亮用整体透明度 | 已彻底取消卡点高亮；若复用 v1，只调字色明暗 |

## CDP 渲染与验收

| 症状 | 原因 | 修法 |
|---|---|---|
| 成片里整句字幕冻在约 30% 半透明 | `state_key` 没把字幕 0.18s 淡入算作画面变化，淡入期复用了第一帧 | `fading = sub_start is not None and (t-sub_start) < SUB_FADE`，淡入期 key 带帧号，逐帧截图 |
| CDP 截图是 900×1057 的拉伸帧 | headless 默认 viewport 高度比 `--window-size` 少一截 | `Emulation.setDeviceMetricsOverride(1080,1440,1,false)`；**固定视口后调 `buildPlans()`** 重算入场排序 |
| CDP 连上的是初始空白页 | 端口起来时目标页还没加载 | 轮询 `/json` 找 URL 含 `preview.html` 的 page，再轮询 `window.__ready === true` |
| 成片与预览帧不一致 | 另做了 `render.html`，两份版式逻辑漂移 | v3 **帧源即预览**：CDP 直接加载 `preview.html?capture=1` |
| 句间空档的几何验收判定失败，但肉眼看没抖 | 用全局 `diff.getbbox()` 判定，一个 H.264 压缩噪点就把框拉到全图中部 | 改用区域统计：字幕行以上差异像素占比 < 0.01%；画框时只取字幕行内的 bbox |
| 第 8 场景验收报 `FileNotFoundError` | 片尾没有句间空档，`t2 = scene.end + 0.4` 超出成片时长，ffmpeg 抽不到帧 | 判断 `t2 >= totalDuration - 1/fps` 时跳过并标注「片尾无空档」 |
| 冒烟片字幕停在半透明 | 旧渲染器状态缓存漏了淡入期 | 先渲 300 帧冒烟片，抽淡入起 / 中 / 末 / 稳定四帧确认 0.30 → 1.0，再跑全片 |

## 配音与时间轴

| 症状 | 原因 | 修法 |
|---|---|---|
| 拿不到词级时间戳 | `edge_tts.Communicate` 没传 `boundary="WordBoundary"` | 必须显式传；`offset/duration` 单位 100ns，除以 `1e7` 得秒 |
| 字幕读起来连成一片、没有停顿 | 切分时把所有标点都删了 | 以句号为硬边界，句内按逗号合并到 ≤22 字，**保留句内标点**，只去句末标点 |
| 字幕时间点倒退或重叠 | 锚点在字符流里 `find` 失配 | 前 3 字锚点 + 比例插值兜底；单调性修正（推到前一条 +0.35s）并补齐空隙 |
| 音轨时长与 `totalDuration` 差几十到几百毫秒 | 用 mp3 文件头时长算场景（有编码器延迟） | 先解码成 24kHz mono s16le WAV，用 `getnframes()/SR` 算时长，采样级拼接 |
| **v2** 静音期字幕不清空 | 字幕 `end` 覆盖到下一段起点 | 最后一条 `end = cursor + duration`，不跨过 `gap`；渲染时按绝对时间查找，查不到就清空。**v3 改为只隐藏不清空** |

## 环境与工具

| 症状 | 原因 | 修法 |
|---|---|---|
| 总览拼图里中文标签显示为方块 | `/System/Library/Fonts/PingFang.ttc` 在本机不存在 | 用 `/System/Library/Fonts/STHeiti Medium.ttc`；第二行标签被裁时把画布加高约 70px |
| `timeout: command not found` | macOS 默认无 GNU `timeout` | 用工具调用自身的超时参数 |
| `ps: operation not permitted` | 沙箱限制进程查询 | 不做进程轮询，靠后台任务通知与输出文件判断 |
| 系统 PATH 里没有 ffmpeg | 本环境由 `imageio_ffmpeg` 提供 | `imageio_ffmpeg.get_ffmpeg_exe()` 取路径 |
| 找不到 `html` skill 或 `shot.py` | 环境未安装 | 按 `lwg-haibao-design` 的 baseline + checklist 出稿，用 Chrome 无头截图验收；**不要中断流程** |

## Remotion 专项（v2）

| 症状 | 原因 | 修法 |
|---|---|---|
| `remotion still` 输出第 1 场景初始画面 | `useLayoutEffect` 首次执行时 iframe 尚未 onLoad，seek 被跳过 | `onLoad` 里立即 `seek(tRef.current)`；`delayRender` 在 seek 之后才 `continueRender` |
| 全片渲染十几分钟无产出 | iframe 逐帧同步 seek + 每帧截图，6113 帧开销大 | 用 `still --frame=300` 与 `--frames=0-60` 验证工程；正式成片交给 CDP |
| 改了配音但 Remotion 时长没变 | `Root.tsx` 里写了固定常量 | 由 `build_render.py` 从 `timeline.json` 生成 `src/config.ts` |

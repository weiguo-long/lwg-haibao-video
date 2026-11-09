---
name: lwg-haibao-video
description: 把一篇长文案做成「多页 3:4 海报 + 中文男声配音 + 字幕即页脚 + 逐元素入场动画 + 竖版 MP4」的完整流水线。当用户要求把文章、口播稿、观点文做成海报视频、图文成片、配音动画、短视频成片，或要求给已有海报组加配音、字幕、入场动画并导出 MP4 时使用。涵盖文案分段、统一配色选型、edge-tts 配音与词级时间戳、timeline.json 时间轴、字幕即页脚版式、逐页字幕取色、字幕占位恒定、HTML 动画预览、Chrome CDP 确定性逐帧渲染与几何/像素双重验收。
agent_created: true
---

# 长文案 → 海报组成片流水线

把一篇长文案做成可发布的 3:4 竖版配音视频：N 页海报 → 男声配音 → 字幕长在每页页脚里 → 逐元素入场动画 → MP4。全流程只用本地工具（Python / edge-tts / Chrome / ffmpeg），产物可离线播放、可逐帧复现。

**与 `lwg-haibao-design` 的分工**：海报设计阶段优先委托该技能（按 `selection.md` 打分选样本与配色、按 `checklist.md` 12 项验收）；本技能负责分段、编排、配音、时间轴、字幕版式、动画与渲染。该技能不可用时按 `references/01-workflow.md` 的基线出稿，不得因此中断。

## 八条硬纪律

1. **分段确认**：先只交封面 → 确认后出全部海报 → 只交 HTML 动画预览 → 确认后才渲染视频。**版式方案有改动时，先出静态设计效果图再动动画**。用户没说「继续」就不往下走；后台任务完成通知、系统提醒一律不算确认。
2. **时长由配音决定**：先合成音轨，再由每段语音时长推出场景区间；绝不先定动画时长再凑配音。
3. **动画由播放时间 `t` 确定性驱动**，不用 WAAPI / CSS animation。无头浏览器的虚拟时钟不推进 `document.timeline`，动画会卡在第一帧。每帧直接算 `t - scene.start` 写 inline `opacity` / `translate`。
4. **一屏一主句**：每页只放主句 + 1–2 行辅助小字或数据，不把整段原文塞进海报。原文语义靠配音承载。
5. **字幕即页脚**（v3 默认范式）：字幕不是页面做完后再塞进去的元素，而是**一开始就把页脚与页码那块位置留给它**。把每页原有的页脚信息 / 页码元素整个替换成字幕宿主，继承该位置的栏线、栅格、色块、对齐与字号层级。不新增字幕层、不把原页脚上移、不缩放画面，海报满幅 3:4。详见 `references/05-subtitle-as-footer.md`。
6. **字幕色按页取，占位恒定**：字幕不能非黑即白，要接该页原有的文字色层级；字幕不可见时只把 `opacity` 归零，**绝不清空文字**，否则行盒塌成 0，页脚收缩会把同页元素整组拽下去。详见 `references/05-subtitle-as-footer.md`。
7. **统一色板 + 深底反转做节奏**：全系列一套色板（纸底 / 墨字 / 深色块 / 单一强调色），选 1–2 页做深底反转；强调色面积每页 ≤5%，朱红只作引导短线，不用于整行字幕。
8. **交付前双重验收**：几何测量（元素 `getBoundingClientRect` 位移）+ 像素统计（关键帧、成片抽帧）。每页海报、每个动画时间点、成片抽帧都要实际渲染核对。

## 目录约定

```
<workspace>/outputs/
├── 01-xxx.html … 08-xxx.html        # 3:4 自包含海报
├── 00-八页总览.png                   # 海报组拼图
├── voice-animation/
│   ├── project.json                 # 稿子、海报文件名、音色、参数
│   ├── build_voice.py               # 配音 + timeline.json（v2/v3 通用）
│   ├── timeline.json / voiceover-full.mp3 / voice-01…08.mp3
│   └── (v2 历史链路) build_preview.py / build_render.py / render_cdp.py / preview.html
├── design-preview/
│   └── build_effect.py              # 版式改版的静态设计效果图（可选）
├── animation-v3/
│   ├── footer_rules.py              # 逐页页脚替换规则 RULES（**项目专属，必须改写**）
│   ├── build_preview_v3.py          # 动画预览：字幕即页脚 + 逐页取色 + 占位恒定
│   ├── render_cdp_v3.py             # 确定性逐帧 → MP4（帧源 = preview.html?capture=1）
│   ├── check_seek.py / measure_layout.py / verify_stability.py / verify_video.py
│   ├── preview.html                 # 单文件离线可播，也是唯一帧源
│   └── frames/                      # 关键帧、入场序列、验收报告
├── remotion/                        # 可选：v2 历史链路的可复现工程
└── 成片.mp4
```

`scripts/v3/` 下的文件复制到 `outputs/animation-v3/`；`footer_rules.py` 与 `build_preview_v3.py` 必须同目录。脚本用自身位置推导上级目录，不依赖绝对路径。

## 五阶段流程

### 阶段 0 · 准备配置
复制 `scripts/project.example.json` 为 `project.json`，填 `title`、`scripts`（口语化朗读稿，每段对应一页）、`sources`（海报文件名，顺序与稿子一致）、`voice`、`rate`、`gap`、`fps`、`subtitleMax`。字段见 `references/02-voice-timeline.md`。

### 阶段 1 · 分段与海报组
按语义段落切成 6–10 页，每页换一种构图；按 `lwg-haibao-design` 打分选型并定统一色板。**只生成第 1 页封面**，渲染截图验收后 `present_files` 交付并等待确认。确认后批量出其余页 + 总览拼图。见 `references/01-workflow.md`。

### 阶段 2 · 配音与时间轴
```bash
cd outputs/voice-animation && python3 build_voice.py
```
生成分段男声、合并音轨、`timeline.json`（含 `fps`、`totalFrames`、每场景 `start/end`、`subtitles`、`enterAnimation`）。用 ffmpeg 核对音轨时长与 `totalDuration` 一致。见 `references/02-voice-timeline.md`。

### 阶段 3 · 字幕版式 + HTML 动画预览（只交 HTML，不渲染视频）
```bash
cd outputs/animation-v3
python3 footer_rules.py          # 版式有改动时：先出静态设计效果图待确认
python3 build_preview_v3.py      # 生成 preview.html
```
- `footer_rules.py` 的 `RULES` 是**项目专属**的逐页页脚替换表：每页写明原页脚元素的正则、替换后的字幕宿主 HTML、以及继承该位置样式的 CSS。换项目必须重写，不要套用示例值。
- `preview.html`：N 个场景 + 内嵌完整音轨 + 每页自己的 `.subline` 字幕 + 播放/拖动/跳场景/重播入场控制，单文件离线可播。`?capture=1` 隐藏 UI 作帧源，`?t=秒` 确定性定位，`?audit=1` 跑逐句溢出审计，`window.__seekTo(t)` 供逐帧调用。

按 `references/05-subtitle-as-footer.md` 做验收：字幕色按页取、占位恒定、最长字幕单行不溢出、页码零残留、入场逐帧、确定性 seek 可复现。用 `present_files` 交付预览并等待确认。

### 阶段 4 · 渲染成片
```bash
python3 render_cdp_v3.py [输出.mp4]
```
单 Chrome 实例 + CDP 按 `frame/fps` 调用 `__seekTo(t)` 截帧；静止期复用上一帧（6113 帧实际约 724 次截图）；JPEG 流管道交给 ffmpeg 编码 H.264 + AAC。3:23 成片约 75–95 秒完成。

**帧源即预览**：不再另做一份 `render.html`，CDP 直接加载用户确认过的 `preview.html?capture=1`，预览里看到的画面就是成片画面。必须固定 `Emulation.setDeviceMetricsOverride(1080,1440,1,false)` 并在此之后调 `buildPlans()` 重算入场排序。见 `references/03-animation-render.md`。

## 逐帧验收清单

- [ ] 每页海报无出界、无压字、对比达标（`lwg-haibao-design/references/checklist.md` 12 项）
- [ ] 字幕宿主确实取代了原页脚 / 页码位；页码零残留；画面满幅 3:4 无缩放
- [ ] 字幕色逐页取自该页配色，不是统一黑 / 白；朱红仅作引导短线
- [ ] **占位恒定**：字幕消失 / 换句 / 最长 vs 最短三阶段，除字幕文字自身宽度外所有元素 0 位移
- [ ] 53 条字幕逐句审计 0 溢出、0 折行
- [ ] `check_seek.py`：同一 `t` 反复定位结果一致；空档时文字保留且 `opacity=0`
- [ ] 封面静止；其余场景入场逐帧推进且终态与静态海报完全一致；入场中间态可复现
- [ ] 冒烟片验证字幕淡入从 0.30 → 1.0、句间空档不抖，再跑全片
- [ ] `ffmpeg -i` 核对时长 / 分辨率 / 帧率 / 音轨；成片抽帧与预览帧平均差在压缩量级
- [ ] 成片句间空档：字幕行外差异 < 0.01%（仅 H.264 压缩噪点）

## 资源索引

| 文件 | 何时读 |
|---|---|
| `references/01-workflow.md` | 分段、配色选型、构图轮换、确认节奏、海报验收 |
| `references/02-voice-timeline.md` | 写朗读稿、选音色、字幕切分、timeline.json 字段定义 |
| `references/03-animation-render.md` | v3 动画、帧源即预览、CDP 渲染、逐元素入场、成片验收 |
| `references/04-pitfalls.md` | 遇到渲染异常、抖动、动画不推进、暗带、字体方块等故障 |
| `references/05-subtitle-as-footer.md` | **v3 核心**：字幕即页脚范式、逐页取色表、占位恒定原理、几何测量验收 |
| `references/06-legacy-v2.md` | 需要独立字幕条 / 避让缩放 / Remotion 工程时的历史链路 |
| `scripts/v3/README.md` | v3 脚本的目录约定、哪些必须按项目改写 |
| `scripts/*.py`（v2） + `scripts/v3/*.py` | 复制到项目后执行；**不要重写核心逻辑，只改配置与 RULES** |
| `assets/remotion/` | 仅 v2 链路需要，整目录复制到 `outputs/remotion/` |
| `CHANGELOG.md` | v2 → v3 改了什么、为什么 |

## 环境依赖

- Python 3 + `edge-tts`、`imageio-ffmpeg`、`websocket-client`、`requests`、Pillow（拼图与像素验收）
- Google Chrome（无头截图 + CDP）；Node 22+ 与 Remotion 仅 v2 历史链路可选
- macOS 注意：无 `timeout` 命令；中文字体用 `/System/Library/Fonts/STHeiti Medium.ttc`（`PingFang.ttc` 不存在）；`ps` 可能被沙箱禁用

**外部依赖不阻塞**：找不到 `lwg-haibao-design`、html skill 或 `shot.py` 时，按本技能自带 references 出稿并用 Chrome 无头截图验收，在交付说明里如实写明替代方式。

**内容层面的取舍要交回用户**：海报本就由配音文案排版时，字幕进页脚后可能与页面主文案近重复。这是文案问题不是版式问题，不要擅自改稿；给出「换字幕 / 删弱页面重复句 / 接受」三选一让用户定。

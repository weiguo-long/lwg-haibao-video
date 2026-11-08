---
name: lwg-haibao-video
description: 把一篇长文案做成「多页 3:4 海报 + 中文男声配音 + 底部字幕 + 逐元素入场动画 + 竖版 MP4」的完整流水线。当用户要求把文章、口播稿、观点文做成海报视频、图文成片、配音动画、短视频成片，或要求给已有海报组加配音、字幕、入场动画并导出 MP4 时使用。涵盖文案分段、统一配色选型、edge-tts 配音与词级时间戳、timeline.json 时间轴、HTML 动画预览、Chrome CDP 确定性逐帧渲染、Remotion 工程模板与逐帧验收。
agent_created: true
---

# 长文案 → 海报组成片流水线

把一篇长文案做成可发布的 3:4 竖版配音视频：N 页海报 → 男声配音 → 底部字幕 → 逐元素入场动画 → MP4。全流程只用本地工具（Python / edge-tts / Chrome / ffmpeg），产物可离线播放、可逐帧复现。

**与 `lwg-haibao-design` 的分工**：海报设计阶段优先委托该技能（按 `selection.md` 打分选样本与配色、按 `checklist.md` 12 项验收）；本技能负责分段、编排、配音、时间轴、动画与渲染。该技能不可用时按 `references/01-workflow.md` 的基线出稿，不得因此中断。

## 七条硬纪律

1. **三段确认**：先只交封面 → 确认后出全部海报 → 再只交 HTML 动画预览 → 确认后才渲染视频。用户没说「继续」就不往下走。
2. **时长由配音决定**：先合成音轨，再由每段语音时长推出场景区间；绝不先定动画时长再凑配音。
3. **动画由播放时间 `t` 确定性驱动**，不用 WAAPI / CSS animation。无头浏览器的虚拟时钟不推进 document.timeline，动画会卡在第一帧，既无法截图验收也无法在 Remotion 复现。每帧直接算 `t - scene.start` 写 inline `opacity` / `translate`。
4. **一屏一主句**：每页只放主句 + 1–2 行辅助小字或数据，不把整段原文塞进海报。原文语义靠配音承载。
5. **字幕区是禁区**：底部字幕条固定 11.5% 高且不透明，海报整体等比缩放 0.885 放进上方安全区、溢出裁切，任何画面元素不得进入字幕区。
6. **统一色板 + 深底反转做节奏**：全系列一套色板（纸底 / 墨字 / 深色块 / 单一强调色），选 1–2 页做深底反转；强调色面积每页 ≤5%。
7. **交付前逐帧截图验收**：每页海报、每个动画时间点、成片抽帧都要实际渲染核对；用像素统计确认入场终态稳定、无元素丢失。

## 目录约定

```
<workspace>/outputs/
├── 01-xxx.html … 08-xxx.html        # 3:4 自包含海报
├── 00-八页总览.png                   # 海报组拼图
├── voice-animation/
│   ├── project.json                 # 本项目的稿子、海报文件名、音色、参数
│   ├── build_voice.py               # 配音 + timeline.json
│   ├── build_preview.py             # HTML 动画预览（音频 base64 内嵌）
│   ├── build_render.py              # 纯帧源 render.html + Remotion 配置
│   ├── render_cdp.py                # 确定性逐帧 → MP4
│   ├── timeline.json / voiceover-full.mp3 / voice-01…08.mp3
│   └── preview.html / 00-字幕动画总览.png
├── remotion/                        # 可选：可复现工程（资产模板复制而来）
└── 成片.mp4
```

把 `scripts/` 下的文件复制到 `outputs/voice-animation/`，把 `assets/remotion/` 复制到 `outputs/remotion/`。脚本用自身位置推导上级目录，不依赖绝对路径；海报文件名由 `project.json` 的 `sources` 指定。

## 五阶段流程

### 阶段 0 · 准备配置
复制 `scripts/project.example.json` 为 `project.json`，填 `title`、`scripts`（口语化朗读稿，每段对应一页）、`sources`（海报文件名，顺序与稿子一致）、`voice`、`rate`、`gap`、`fps`、`subtitleMax`。详细字段见 `references/02-voice-timeline.md`。

### 阶段 1 · 分段与海报组
按语义段落切成 6–10 页，每页换一种构图；按 `lwg-haibao-design` 打分选型并定统一色板。**只生成第 1 页封面**，渲染截图验收后 `present_files` 交付并等待确认。确认后批量出其余页 + 总览拼图。具体分段法、构图轮换与验收口径见 `references/01-workflow.md`。

### 阶段 2 · 配音与时间轴
```bash
cd outputs/voice-animation && python3 build_voice.py
```
生成分段男声、合并音轨、`timeline.json`（含 `fps`、`totalFrames`、每场景 `start/end/startFrame/durationInFrames`、`subtitles`、`enterAnimation`、`subtitleStyle`）。用 ffmpeg 核对音轨时长与 `totalDuration` 一致。配音文本口语化、数字汉字化、字幕切分与时间轴 schema 见 `references/02-voice-timeline.md`。

### 阶段 3 · HTML 动画预览（只交 HTML，不渲染视频）
```bash
python3 build_preview.py && python3 build_render.py
```
- `preview.html`：8 场景 + 内嵌完整音轨 + 底部字幕 + 播放/拖动/跳场景/重播入场控制，单文件离线可播。
- `remotion/public/render.html`：剥掉播放器 UI 与音频的纯帧源，暴露 `window.__seekTo(t)`，支持 `?t=秒` 单帧截图。

按 `references/03-animation-render.md` 做截图验收：页码零残留、字幕同步、避让、入场逐帧、播放链路。用 `present_files` 交付预览并等待确认。

### 阶段 4 · 渲染成片
```bash
python3 render_cdp.py [输出.mp4]
```
单 Chrome 实例 + CDP 按 `frame/fps` 调用 `__seekTo(t)` 截帧；静止期复用上一帧（6113 帧通常只需约 480 次截图）；JPEG 流管道交给 ffmpeg 编码 H.264 + AAC。3:23 成片约 90–120 秒完成。

Remotion 工程位于 `outputs/remotion/`，`npm run render` 可完整复现（先 `npm install`）。本机 iframe 逐帧 seek 全片很慢时，以 CDP 链路输出正式成片，两者帧源相同、画面无差异。工程结构与首帧时序坑见 `references/03-animation-render.md`。

## 逐帧验收清单

- [ ] 每页海报无出界、无压字、对比达标（按 `lwg-haibao-design/references/checklist.md` 12 项）
- [ ] 画面内页码零残留；字幕条内文字单行不溢出
- [ ] 场景切换时字幕清空、静音期不残留
- [ ] 封面静止；其余场景入场逐帧推进且终态与静态海报完全一致
- [ ] 8 页终态总览逐页确认无元素缺失或半透明
- [ ] `ffmpeg -i` 核对时长 / 分辨率 / 帧率 / 音轨；`volumedetect` 确认音轨非静音
- [ ] 成片抽 9 个时间点拼图核对场景、字幕、入场中间态与结尾

## 资源索引

| 文件 | 何时读 |
|---|---|
| `references/01-workflow.md` | 分段、配色选型、构图轮换、三段确认节奏、海报验收 |
| `references/02-voice-timeline.md` | 写朗读稿、选音色、字幕切分、timeline.json 字段定义 |
| `references/03-animation-render.md` | 搭 HTML 动画、字幕避让、逐元素入场、帧源、CDP 渲染、Remotion 工程 |
| `references/04-pitfalls.md` | 遇到渲染异常、动画不推进、暗带、字体方块等故障时 |
| `scripts/*.py` | 直接复制到项目后执行，按 `project.json` 配置；不要重写 |
| `assets/remotion/` | 需要 Remotion 工程时整目录复制，`build_render.py` 会同步配置 |

## 环境依赖

- Python 3 + `edge-tts`、`imageio-ffmpeg`、`websocket-client`、Pillow（拼图）
- Google Chrome（无头截图 + CDP）、Node 22+（Remotion 可选）
- macOS 注意：无 `timeout` 命令；中文字体用 `/System/Library/Fonts/STHeiti Medium.ttc`（`PingFang.ttc` 不存在）；`ps` 可能被沙箱禁用

**外部依赖不阻塞**：找不到 `lwg-haibao-design`、html skill 或 `shot.py` 时，按本技能自带 references 出稿并用 Chrome 无头截图验收，在交付说明里如实写明替代方式。

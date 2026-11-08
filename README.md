# lwg-haibao-video

WorkBuddy 技能。把一篇长文案做成「多页 3:4 海报 + 中文男声配音 + 底部字幕 + 逐元素入场动画 + 竖版 MP4」的完整流水线：文案分段 → 统一配色海报组 → edge-tts 配音与词级时间戳 → `timeline.json` 时间轴 → HTML 动画预览 → Chrome CDP/Remotion 逐帧渲染 → MP4 成片。

使用时机：用户要求把文章、口播稿、观点文做成海报视频、图文成片、配音动画、短视频成片，或要求给已有海报组加配音、字幕、入场动画并导出 MP4。

**与 `lwg-haibao-design` 的分工**：海报设计阶段优先委托该技能（打分选样本与配色、12 项清单验收）；本技能负责分段、编排、配音、时间轴、动画与渲染。该技能不可用时按 `references/01-workflow.md` 的基线出稿，不中断流程。

## 安装到 WorkBuddy

本仓库以「一个仓库 = 一个技能」组织，根目录即技能本体（`SKILL.md` + `references/` + `scripts/` + `assets/`），没有同名嵌套层。

**方式 A｜上传技能包**：把本仓库目录打包成 zip（zip 内以含 `SKILL.md` 的目录为根），在 WorkBuddy 走「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」导入。
> GitHub 的 "Download ZIP" 会自动加一层 `lwg-haibao-video-main/`，请以真正含 `SKILL.md` 的那一层为准。

**方式 B｜本机直接复制**：把仓库目录复制到 `~/.workbuddy/skills/lwg-haibao-video/`（用户级，所有项目可用）。

## 目录

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 技能入口：七条硬纪律 + 五阶段流程 + 验收清单 |
| `references/01-workflow.md` | 分段骨架、构图轮换、C-01 色板五角色、三段确认话术、单页 `cqw` 规范 |
| `references/02-voice-timeline.md` | 音色对照、朗读稿去 AI 味、字幕切分、词级时间戳锚点、`timeline.json` 全字段 schema |
| `references/03-animation-render.md` | scoped CSS、页码清理、字幕避让数学、逐元素入场、播放链路、帧源与 CDP/Remotion 渲染 |
| `references/04-pitfalls.md` | 20 条「症状 → 原因 → 修法」速查 |
| `scripts/project.example.json` | 项目配置模板（稿子、海报文件名、音色、fps、尺寸、字幕与入场参数） |
| `scripts/build_voice.py` | 配音 + 采样级拼接 + 字幕时间轴 |
| `scripts/build_preview.py` | 自包含 HTML 动画预览（音频 base64 内嵌） |
| `scripts/build_render.py` | 纯帧源 `render.html` + Remotion 配置同步 |
| `scripts/render_cdp.py` | 确定性逐帧截图 → ffmpeg 编码 MP4 |
| `assets/remotion/` | Remotion 工程模板（`src/`、`package.json`） |

## 环境依赖

- Python 3 + `edge-tts` + `websocket-client` + `imageio-ffmpeg`（ffmpeg 二进制）
- Google Chrome / Chromium（无头截图与 CDP）
- 可选：Node.js 22 + Remotion（复现工程）；不装也能用 `render_cdp.py` 出片
- 可选：Pillow（拼总览图、像素级验收）

脚本只用自身位置推导目录，不依赖绝对路径；海报文件名与朗读稿全部由 `project.json` 驱动。

## 标准流程

```bash
# 0. 把 scripts/ 复制到 <workspace>/outputs/voice-animation/，assets/remotion/ 复制到 outputs/remotion/
cp scripts/project.example.json outputs/voice-animation/project.json   # 填稿子、sources、voice
# 1. 先只出封面，确认后出全部海报
# 2. 配音与时间轴
cd outputs/voice-animation && python3 build_voice.py
# 3. 只交 HTML 预览，确认后再渲染
python3 build_preview.py && python3 build_render.py
# 4. 出片
python3 render_cdp.py ../成片.mp4
```

**三段确认**是硬纪律：封面 → 全部海报 → HTML 动画预览 → 才渲染视频。时长一律由配音决定，动画必须由播放时间 `t` 确定性驱动，字幕区是禁区。

## 说明

- GitHub 更新后，WorkBuddy 中已安装的技能不会自动刷新，需要重新导入一次。
- 本技能由一次完整实拍项目沉淀：8 页 3:4 海报、云健男声 3:23.75、53 条字幕、6113 帧 1080×1440 MP4，全流程逐帧截图验收通过。

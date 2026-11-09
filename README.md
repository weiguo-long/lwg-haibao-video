# lwg-haibao-video

WorkBuddy 技能。把一篇长文案做成「多页 3:4 海报 + 中文男声配音 + **字幕即页脚** + 逐元素入场动画 + 竖版 MP4」的完整流水线：文案分段 → 统一配色海报组 → edge-tts 配音与词级时间戳 → `timeline.json` → 字幕版式效果图 → HTML 动画预览 → Chrome CDP 确定性逐帧渲染 → MP4 成片。

使用时机：用户要求把文章、口播稿、观点文做成海报视频、图文成片、配音动画、短视频成片，或要求给已有海报组加配音、字幕、入场动画并导出 MP4。

**当前默认 v3**：字幕不是画面外的独立字幕条，而是把每页原本留给页脚 / 页码的位置整个换成字幕，画面满幅 3:4；字幕色逐页取自该页配色；字幕消失时只隐藏不清空，占位恒定。v2 的独立字幕条、避让缩放与 Remotion 工程保留为历史链路（`references/06-legacy-v2.md`）。

**与 `lwg-haibao-design` 的分工**：海报设计阶段优先委托该技能（打分选样本与配色、12 项清单验收）；本技能负责分段、编排、配音、时间轴、字幕版式、动画与渲染。该技能不可用时按 `references/01-workflow.md` 的基线出稿，不中断流程。

## 安装到 WorkBuddy

本仓库以「一个仓库 = 一个技能」组织，根目录即技能本体（`SKILL.md` + `references/` + `scripts/` + `assets/`），没有同名嵌套层。

**方式 A｜上传技能包**：把本仓库目录打包成 zip（zip 内以含 `SKILL.md` 的目录为根），在 WorkBuddy 走「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」导入。
> GitHub 的 "Download ZIP" 会自动加一层 `lwg-haibao-video-main/`，请以真正含 `SKILL.md` 的那一层为准。

**方式 B｜本机直接复制**：把仓库目录复制到 `~/.workbuddy/skills/lwg-haibao-video/`（用户级，所有项目可用）。

## 目录

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 技能入口：八条硬纪律 + 五阶段流程 + 验收清单 |
| `references/01-workflow.md` | 分段骨架、构图轮换、C-01 色板、确认节奏、单页 `cqw` 规范 |
| `references/02-voice-timeline.md` | 音色、朗读稿去 AI 味、字幕切分、词级时间戳、`timeline.json` schema |
| `references/03-animation-render.md` | v3 动画、帧源即预览、CDP 渲染、逐元素入场、成片验收 |
| `references/04-pitfalls.md` | 40+ 条「症状 → 原因 → 修法」速查 |
| `references/05-subtitle-as-footer.md` | **v3 核心**：逐页替换规则、逐页取色表、占位恒定原理、几何测量验收 |
| `references/06-legacy-v2.md` | v2 历史链路：字幕条避让数学、纯帧源、Remotion 工程、迁移清单 |
| `scripts/project.example.json` | 项目配置模板（含 v3 的 `subtitleMode` / `perSceneColors` 等） |
| `scripts/build_voice.py` | 配音 + 采样级拼接 + 字幕时间轴（v2/v3 通用） |
| `scripts/build_preview.py` / `build_render.py` / `render_cdp.py` | v2 历史链路脚本 |
| `scripts/v3/` | **v3 主链路**：版式规则、动画预览、CDP 渲染、几何 / 像素验收脚本 |
| `assets/remotion/` | 仅 v2 链路需要的 Remotion 工程模板 |
| `CHANGELOG.md` | v2 → v3 变更记录与取舍 |

## 环境依赖

- Python 3 + `edge-tts` + `websocket-client` + `requests` + `imageio-ffmpeg` + Pillow
- Google Chrome / Chromium（无头截图与 CDP）
- 可选：Node.js 22 + Remotion（仅 v2 复现工程）；不装也能用 v3 的 `render_cdp_v3.py` 出片

脚本只用自身位置推导目录，不依赖绝对路径；海报文件名与朗读稿全部由 `project.json` 驱动，`footer_rules.py` 的逐页 `RULES` 是项目专属、必须按新项目页脚改写。

## 标准流程

```bash
# 0. scripts/ → outputs/voice-animation/，scripts/v3/ → outputs/animation-v3/
cp scripts/project.example.json outputs/voice-animation/project.json   # 填稿子、sources、voice
# 1. 先只出封面，确认后出全部海报
# 2. 配音与时间轴（v2/v3 通用，改版式不用重跑）
cd outputs/voice-animation && python3 build_voice.py
# 3. 版式有改动：先出静态效果图待确认；再只交 HTML 动画预览
cd ../animation-v3
python3 footer_rules.py && python3 build_preview_v3.py
python3 check_seek.py && python3 measure_layout.py layout-after.json
# 4. 确认后出片
python3 render_cdp_v3.py /tmp/smoke.mp4 300      # 先冒烟
python3 render_cdp_v3.py ../成片.mp4
python3 verify_video.py
```

**确认节奏**是硬纪律：封面 → 全部海报 →（版式改版时）静态效果图 → HTML 动画预览 → 才渲染视频；成片效果可行后再决定是否更新技能。时长一律由配音决定，动画必须由播放时间 `t` 确定性驱动，**字幕不可见时只隐藏不清空**。

## 说明

- GitHub 更新后，WorkBuddy 中已安装的技能不会自动刷新，需要重新导入一次。
- 本技能由一次完整实拍项目沉淀：8 页 3:4 海报、云健男声 3:23.75、53 条字幕、6113 帧 1080×1440 MP4；v3 又补了逐页配色、字幕占位恒定与几何 / 像素双重验收，全流程逐帧截图核对通过。
- 已知取舍：海报由配音文案排版时，字幕进页脚后会与页面主文案近重复（08 页最明显）。这是文案问题，交回用户决定，不擅自改稿。

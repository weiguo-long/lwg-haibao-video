# scripts/v3 · 字幕即页脚主链路

把本目录**整目录复制**到 `<workspace>/outputs/animation-v3/`。脚本用自身位置推导目录：

```
outputs/
├── 01-xxx.html … 08-xxx.html       ← 海报源文件
├── voice-animation/
│   ├── timeline.json               ← 由 build_voice.py 生成，v2/v3 通用
│   └── voiceover-full.mp3
└── animation-v3/                   ← 本目录
    ├── frames/                     ← 各脚本自动创建
    └── …
```

## 脚本职责与执行顺序

| 顺序 | 脚本 | 作用 |
|---|---|---|
| 1 | `footer_rules.py` | 逐页页脚替换规则 `RULES`；**可直接运行**出静态设计效果图 `outputs/字幕即页脚-设计效果图.html`（`#P1`… 看单页）。同时被下一步导入 |
| 2 | `build_preview_v3.py` | 生成 `preview.html`（音频 base64 内嵌、可播放可拖动、`?capture=1` 作帧源、`?t=` 定位、`?audit=1` 审计、`window.__seekTo`） |
| 3 | `check_seek.py` | 确定性验证：同一 `t` 可复现、入场态可复现、句间空档文字保留且 `opacity=0`、固定视口后 CDP 帧与预览帧逐像素一致 |
| 4 | `measure_layout.py` | 三阶段几何测量（字幕消失 / 换句 / 最长 vs 最短），输出 `layout-after.json`；修复前可先跑一份存为 `layout-before.json` 做对照 |
| 5 | `verify_stability.py` | 重截 12 关键帧 + 5 入场序列 + 8 场景可见/消失帧，出位移柱状图与帧对照图；`--no-shot` 可复用已有帧只重排 |
| 6 | `rebuild_sheets.py` | 重拼关键帧 / 入场序列 / 配色对照三张验收图 |
| 7 | `render_cdp_v3.py` | 冒烟 `python3 render_cdp_v3.py /tmp/smoke.mp4 300`，全片 `python3 render_cdp_v3.py ../成片.mp4` |
| 8 | `verify_video.py` | 成片规格、抽帧与预览比对、句间空档区域统计，出两张验收图；可传成片路径或设 `VIDEO_PATH` |

```bash
python3 footer_rules.py                  # 版式有改动时先给用户确认效果图
python3 build_preview_v3.py
python3 check_seek.py
python3 measure_layout.py layout-after.json
python3 verify_stability.py
python3 rebuild_sheets.py
python3 render_cdp_v3.py /tmp/smoke.mp4 300   # 必做：验证淡入与空档不抖
python3 render_cdp_v3.py ../成片.mp4
python3 verify_video.py ../成片.mp4
```

## 换新项目时必须改的地方

1. **`footer_rules.py` 的 `FILES` / `SUBS` / `WHERE` / `RULES`**：全项目专属。逐页检查原页脚 / 页码元素的实际 HTML，重写 `RULES[n]["find"]`（`re.subn` 必须唯一命中一次），保留原 class 只加 `subhost` / `subline`。示例值来自 C-01 纸红复古 8 页海报，不可直接套用。
2. **`build_preview_v3.py` 的 `SUB_COLORS` / `BASE_COLORS`**：按新项目色板与实际文字色重定，逐页取该页已有的颜色；深底页用米白与该页灰蓝调和出的浅色，别用纯白。
3. **`verify_stability.py` 的 `reps` / `SHOTS`**、`rebuild_sheets.py` 的 `COLOR` 表、`verify_video.py` 的 `shots`：验收时间点与配色说明按新项目调整。
4. `project.json` 的 `sources` / `scripts` 必须等长且顺序一致；`subtitleFade` 要与渲染器的 `SUB_FADE` 保持一致。

## 不要改的地方

- `applySubtitle()` 的「空档只隐藏、不清空文字」逻辑 —— 改回清空会造成 8 页布局塌陷与可见抖动。
- `state_key()` 的 `fading` 项 —— 去掉会让整句字幕冻在 30% 半透明。
- `Emulation.setDeviceMetricsOverride` + `buildPlans()` —— 去掉会得到拉伸帧和错乱的入场排序。
- `collectUnits()` 遇到 `.subhost` 直接 `return` —— 否则字幕会迟到约 1.3 秒。

## 依赖

`websocket-client`、`requests`、`imageio-ffmpeg`、Pillow、Google Chrome。`footer_rules.py` / `build_preview_v3.py` / `render_cdp_v3.py` 只用标准库 + ffmpeg；验收脚本才需要第三方包。

规则与原理详见 `references/05-subtitle-as-footer.md`，渲染细节见 `references/03-animation-render.md`。

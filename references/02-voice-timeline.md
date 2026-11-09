# 阶段 2：配音、字幕切分与 timeline.json

## 1. project.json 字段

```json
{
  "title": "时代从不换题",
  "voice": "zh-CN-YunjianNeural",
  "rate": "-5%",
  "gap": 0.75,
  "fps": 30,
  "width": 1080,
  "height": 1440,
  "subtitleMax": 22,
  "subtitleMode": "footer",
  "subtitleFade": 0.18,
  "placeholderPolicy": "hide-only-never-clear",
  "perSceneColors": {
    "1": "#C2BFBD", "2": "#4A5B78", "3": "#C2BFBD", "4": "#28314E",
    "5": "#C2BFBD", "6": "#4A5B78", "7": "#28314E", "8": "#28314E"
  },
  "enterAnimation": {
    "skipFirstScene": true,
    "driver": "t - scene.start",
    "order": "visual top-to-bottom, then left-to-right",
    "duration": 0.46, "step": 0.075, "lift": 16, "maxGroups": 18
  },
  "sources": ["01-cover.html", "..."],
  "scripts": ["第一段口语化朗读稿。", "..."]
}
```

`sources` 与 `scripts` **必须等长且顺序一一对应**；`sources` 是相对 `outputs/` 的海报文件名。`gap` 是场景之间留白，`fps` 决定 `startFrame` / `durationInFrames`。改音色或语速只改 `voice` / `rate` 后重跑 `build_voice.py`，时间轴会自动重算。

v3 新增字段（供动画阶段读取，`build_voice.py` 本身不改）：

- `subtitleMode: "footer"`：字幕长在每页页脚，不用独立字幕条；`"bottom-bar"` 才是 v2 历史链路。
- `subtitleFade: 0.18`：切句淡入秒数，渲染器 `state_key` 必须用同一个值。
- `placeholderPolicy: "hide-only-never-clear"`：**字幕不可见时只隐藏、绝不清空文字**，否则行盒塌陷会牵动同页元素。
- `perSceneColors`：逐页字幕色，取该页配色里已有的文字色；深底页用米白与灰蓝调和出的浅色，不要纯白。详见 `references/05-subtitle-as-footer.md`。

## 2. 音色与语速

| 音色 | 听感 | 适用 |
|---|---|---|
| `zh-CN-YunjianNeural`（云健） | 成熟浑厚男声 | 观点、商业、历史叙事；本项目最终选用 |
| `zh-CN-YunxiNeural`（云希） | 年轻男声，比新闻播报腔自然 | 成长、科技、轻松话题 |
| `zh-CN-XiaoxiaoNeural` | 女声 | 用户明确要女声时 |

`rate=-5%` 语速适中偏从容。调用必须带 `boundary="WordBoundary"`，否则拿不到词级时间戳：

```python
comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
async for chunk in comm.stream():
    if chunk["type"] == "audio": ...
    elif chunk["type"] == "WordBoundary":
        # offset / duration 单位是 100ns，除以 1e7 得秒
```

**音色无法自动试听**：交付时明确请用户戴耳机确认，说明可换音色/调语速且脚本可复跑。

## 3. 去 AI 味落在文本层

不要指望调 TTS 参数解决，改写朗读稿才有效：

- 数字全部汉字化：`1908` → `一九零八年`、`850 美元` → `八百五十美元`、`5.83` → `五点八三`、`1/36` → `三十六分之一`、`T 型车` 保留字母但读法按口语。
- 破折号、引号、括号改成自然停顿（逗号），长句拆成 12–20 字短句。
- 书面连接词删掉或口语化（「此前」可留，「换言之」改「说白了」）。
- 段尾不额外加停顿，靠 `gap` 统一留白。

**字幕文本直接从朗读稿切分**，不要另写一套文案，否则音画不同步。

## 4. 字幕切分规则

`split_subtitles()` 的口径（已验证）：

1. 以 `。！？` 为**硬边界**分句。
2. 句内按 `，、；：` 分成子句，贪心合并到 `core()` 字数 ≤ `subtitleMax`（默认 22 字）。
3. **保留句内标点**（逗号让字幕有呼吸），只去掉句末标点和空格。
4. 超长兜底：按 `subtitleMax` 硬切，避免单行溢出。

踩过的坑：把标点全部删掉会让字幕连成一片、读起来喘不过气。单条 22–24 字在 v3 的 `2.8cqw` / 版心 ≥77cqw 下正好单行（v2 用 `3.05cqw` 通栏）。**v3 必须逐页量**：各页字幕位宽度不同，用 `?audit=1` 把 53 条字幕逐条塞进各自页脚，检查 `scrollWidth` 与左右边界，不能只按最宽的页算。

## 5. 词级时间戳 → 字幕时间点

WordBoundary 给出的是**词**的时间，字幕是**句**。做法：

1. 把每条 WordBoundary 的词拆成字符流 `[(ch, t)]`。
2. 对每条字幕取前 3 个可见字符作锚点，在字符流里从上次位置向后 `find`。
3. 命中取该字符时间 `t - 0.05`，失配时按已用字符比例插值兜底。
4. 每条字幕 `end` = 下一条 `start`；最后一条 `end` = 本场景语音结束。
5. 单调性修正：若 `start[j] <= start[j-1]`，推到 `start[j-1] + 0.35`；并补齐 `end[j-1] < start[j]` 的空隙。

场景起点用 `cursor` 累加：`end = cursor + duration`，下一段 `cursor = end + gap`。

## 6. 采样级拼接（时间轴与音轨严格一致）

```
每段 mp3 → ffmpeg 转 24kHz / mono / pcm_s16le WAV
→ 依次写入主 WAV，段间插 GAP 秒静音（b"\x00\x00" * GAP*SR）
→ libmp3lame 64k 输出 voiceover-full.mp3
```

`duration = wav.getnframes() / SR`，用它算所有 `start/end`。**不要用 mp3 的文件头时长**（有编码器延迟），必须用解码后采样数。

## 7. timeline.json schema

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | int | 2 = 独立字幕条版；**3 = 字幕即页脚版**（v1 卡点高亮版已废弃） |
| `fps` | int | 30；`totalFrames = round(totalDuration * fps)` |
| `voice` / `rate` / `gap` | — | 便于复跑时追溯 |
| `audioFile` | str | `voiceover-full.mp3` |
| `subtitleStyle` | obj | v2 字幕条 `background` / `color` / `position`；v3 仅作兼容占位，实际颜色由 `perSceneColors` 逐页决定 |
| `enterAnimation` | obj | `skipFirstScene`、`duration`、`step`、`lift`、`maxGroups`、`order`、`driver` |
| `totalDuration` / `totalFrames` | number | 全片总时长与总帧数 |
| `scenes[]` | array | 每场景一个对象，见下 |

`scenes[i]`：

| 字段 | 说明 |
|---|---|
| `index` / `id` | 从 1 开始 / `s1`… |
| `source` | 对应海报 HTML 文件名 |
| `start` / `end` / `duration` | 秒，三段小数 |
| `startFrame` / `durationInFrames` | `round(秒 * fps)`，供 Remotion 直接使用 |
| `script` | 该段朗读稿（预览HTML里会被 slim 掉） |
| `words` | 词级时间戳原始数组（预览HTML里会被 slim 掉） |
| `subtitles[]` | `{id, text, start, end}`，`start/end` 为**全片绝对时间** |

下游约定：`build_preview_v3.py`（v3）/ `build_preview.py`（v2）从 `timeline.json` 读 `scenes[].source` 去加载海报；`render_cdp_v3.py` 读 `fps` / `totalFrames` / `subtitles` / `enterAnimation`，并据 `subtitleFade` 决定淡入期状态键。**配音链路 v2/v3 完全通用，改版式不需要重跑 `build_voice.py`**——本轮 v3 全程沿用 11-08 生成的 `timeline.json` 与音轨，时间戳未变。

场景末尾到下一场景起点之间的 `gap`（本项目 0.803s）里没有字幕，这正是 v3 占位恒定要处理的空档，见 `references/05-subtitle-as-footer.md` 第 4 节。

## 8. 校验

```bash
python3 -c "import imageio_ffmpeg,subprocess,json; ff=imageio_ffmpeg.get_ffmpeg_exe(); p=subprocess.run([ff,'-i','voiceover-full.mp3'],capture_output=True,text=True); print([l.strip() for l in p.stderr.splitlines() if 'Duration' in l]); d=json.load(open('timeline.json')); print('timeline:',d['totalDuration'],d['totalFrames'])"
```

音轨 `Duration` 必须等于 `totalDuration`（允许 0.01s 误差）。不一致时先查 WAV 采样率与 `gap` 是否拼接正确，不要靠手改时间轴补。

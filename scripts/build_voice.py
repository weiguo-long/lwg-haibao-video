# -*- coding: utf-8 -*-
"""
生成分段男声配音 + 短句级字幕时间轴 + 合并音轨。
所有项目参数从同目录 project.json 读取；重跑即可换音色 / 语速 / 停顿。
产物：voice-01…NN.mp3、voiceover-full.mp3、timeline.json
"""
import asyncio
import json
import os
import re
import subprocess
import wave

import edge_tts
import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 24000
PUNCT = "，。：；、？！"


def load_config():
    path = os.path.join(HERE, "project.json")
    if not os.path.exists(path):
        raise SystemExit("缺少 project.json：请复制 scripts/project.example.json 到本目录并填写。")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if len(cfg.get("sources", [])) != len(cfg.get("scripts", [])):
        raise SystemExit("project.json 中 sources 与 scripts 数量不一致。")
    if not cfg["sources"]:
        raise SystemExit("project.json 中没有场景。")
    return cfg


CFG = load_config()
TITLE = CFG.get("title", "未命名")
VOICE = CFG.get("voice", "zh-CN-YunjianNeural")
RATE = CFG.get("rate", "-5%")
GAP = float(CFG.get("gap", 0.75))
FPS = int(CFG.get("fps", 30))
WIDTH = int(CFG.get("width", 1080))
HEIGHT = int(CFG.get("height", 1440))
SUB_MAX = int(CFG.get("subtitleMax", 22))
SUBTITLE_STYLE = CFG.get("subtitleStyle", {
    "background": "#1A1614", "color": "#F1E6D8", "position": "bottom"})
ENTER_ANIMATION = CFG.get("enterAnimation", {
    "skipFirstScene": True, "driver": "t - scene.start",
    "order": "visual top-to-bottom, then left-to-right",
    "duration": 0.46, "step": 0.075, "lift": 16, "maxGroups": 18})
SCRIPTS = CFG["scripts"]
SOURCES = CFG["sources"]


async def synth_one(index, text):
    """必须带 boundary='WordBoundary'，否则拿不到词级时间戳。"""
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    audio = bytearray()
    words = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            words.append({
                "t": round(chunk["offset"] / 1e7, 4),
                "d": round(chunk["duration"] / 1e7, 4),
                "w": chunk["text"],
            })
    mp3 = os.path.join(HERE, "voice-%02d.mp3" % index)
    with open(mp3, "wb") as f:
        f.write(audio)
    wav = os.path.join(HERE, "_voice-%02d.wav" % index)
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", mp3,
         "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav],
        check=True,
    )
    with wave.open(wav, "rb") as w:
        frames = w.readframes(w.getnframes())
        duration = w.getnframes() / SR
    os.remove(wav)
    return frames, duration, words


def core(s):
    """只保留可用于对齐的字母数字汉字。"""
    return "".join(ch for ch in s if ch.isalnum())


def split_subtitles(script):
    """以句号为硬边界，句内按逗号合并到 SUB_MAX 字内；句内标点保留，句末标点去掉。"""
    packed = []
    for sent in re.split(r"(?<=[。！？])", script):
        if not sent.strip():
            continue
        buf = ""
        for clause in re.split(r"(?<=[，、；：])", sent.strip()):
            if not clause or not core(clause):
                continue
            if buf and len(core(buf)) + len(core(clause)) > SUB_MAX:
                packed.append(buf)
                buf = clause
            else:
                buf += clause
        if buf:
            packed.append(buf)

    out = []
    for item in packed:
        text = item.replace(" ", "").rstrip("。！？，、；：")
        while len(core(text)) > SUB_MAX + 4:
            out.append(text[:SUB_MAX])
            text = text[SUB_MAX:]
        if core(text):
            out.append(text)
    return out


def locate(chars, anchor, from_idx):
    stream = "".join(c for c, _ in chars)
    pos = stream.find(anchor, from_idx)
    if pos >= 0:
        return chars[pos][1], pos + len(anchor), True
    for i in range(max(0, from_idx), len(chars)):
        if chars[i][0] == anchor[0]:
            return chars[i][1], i + 1, True
    return None, from_idx, False


def subtitle_starts(script, words, duration):
    """用词级时间戳给每条字幕定位；锚点失配时按字符比例平滑兜底。"""
    chars = []
    for item in words:
        for ch in item["w"]:
            if ch.strip():
                chars.append((ch, item["t"]))
    texts = split_subtitles(script)
    total_chars = max(1, len(chars))
    used = 0
    idx = 0
    starts = []
    for text in texts:
        anchor = core(text)[:3] or core(text)
        t, idx, found = locate(chars, anchor, idx)
        if not found or t is None:
            t = duration * min(0.98, used / total_chars)
            idx = min(len(chars), max(idx, int(total_chars * used / total_chars)))
        used += len(core(text))
        starts.append(max(0.0, t - 0.05))
    return texts, starts


def main():
    loop = asyncio.new_event_loop()
    segs = [loop.run_until_complete(synth_one(i + 1, s))
            for i, s in enumerate(SCRIPTS)]

    # 采样级拼接：语音 + 场景间静音，时间轴与音轨严格一致
    silent = b"\x00\x00" * int(GAP * SR)
    master = os.path.join(HERE, "_master.wav")
    with wave.open(master, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for i, (frames, _, _) in enumerate(segs):
            w.writeframes(frames)
            if i < len(segs) - 1:
                w.writeframes(silent)

    full_mp3 = os.path.join(HERE, "voiceover-full.mp3")
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", master,
         "-c:a", "libmp3lame", "-b:a", "64k", full_mp3],
        check=True,
    )
    os.remove(master)

    scenes = []
    cursor = 0.0
    for i, (frames, duration, words) in enumerate(segs):
        texts, starts = subtitle_starts(SCRIPTS[i], words, duration)
        subtitles = []
        for j, text in enumerate(texts):
            subtitles.append({
                "id": "s%d-t%d" % (i + 1, j + 1),
                "text": text,
                "start": round(cursor + max(0.05 if j == 0 else 0.0, starts[j]), 3),
                "end": round(cursor + (starts[j + 1]
                                       if j + 1 < len(starts) else duration), 3),
            })
        # 保证单调不倒退
        for j in range(1, len(subtitles)):
            if subtitles[j]["start"] <= subtitles[j - 1]["start"]:
                subtitles[j]["start"] = round(subtitles[j - 1]["start"] + 0.35, 3)
            if subtitles[j - 1]["end"] < subtitles[j]["start"]:
                subtitles[j - 1]["end"] = subtitles[j]["start"]
        if subtitles:
            subtitles[-1]["end"] = round(cursor + duration, 3)

        end = cursor + duration
        scenes.append({
            "index": i + 1,
            "id": "s%d" % (i + 1),
            "source": SOURCES[i],
            "start": round(cursor, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "startFrame": round(cursor * FPS),
            "durationInFrames": round(duration * FPS),
            "script": SCRIPTS[i],
            "words": words,
            "subtitles": subtitles,
        })
        cursor = end + GAP

    total = round(sum(s["duration"] for s in scenes) + GAP * (len(scenes) - 1), 3)
    timeline = {
        "version": 2,
        "title": TITLE,
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "voice": VOICE,
        "rate": RATE,
        "gap": GAP,
        "audioFile": "voiceover-full.mp3",
        "subtitleStyle": SUBTITLE_STYLE,
        "enterAnimation": ENTER_ANIMATION,
        "totalDuration": total,
        "totalFrames": round(total * FPS),
        "scenes": scenes,
    }
    with open(os.path.join(HERE, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    print("voice: %s | total: %.2fs | mp3: %.0f KB | scenes: %d" %
          (VOICE, total, os.path.getsize(full_mp3) / 1024, len(scenes)))
    for s in scenes:
        print("  %d  %6.2fs -> %6.2fs  (%d subtitles)  %s" %
              (s["index"], s["start"], s["end"], len(s["subtitles"]), s["source"]))


if __name__ == "__main__":
    main()

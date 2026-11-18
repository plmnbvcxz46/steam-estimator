# 讲解视频配音：每镜的旁白交给阿里云百炼 CosyVoice 合成，存下音频和每个字念到的时刻。
# render.mjs 读这些时刻排画面：动作挂在“念到某个词”上，换成真配音画面自动对上。
#
# 用法（仓库根目录，需要环境变量 DASHSCOPE_API_KEY；两个包临时拉，不装进项目环境）：
#   uv run --no-project --with dashscope --with numpy python slides/video/voice.py slides/video/build 1-28
# 产出 build/voice/shotNN.wav 和 shotNN.json。文字和参数都没变的镜不重新合成，只重算时刻；
# 要重配某镜就删掉它的两个文件。重配过的镜必须重录画面。
import difflib
import json
import os
import re
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
MODEL = "cosyvoice-v3-flash"
VOICE = "longyingjing_v3"  # 龙应静
RATE = 1.0    # 语速：试听时选过 1.10，放进画面里偏快
PITCH = 0.93  # 音高：原声偏幼，调低一点
SAMPLE_RATE = 48000


def read_narration():
    """分镜表每行：| 镜 | 秒 | 画面与动效 | 屏幕字 | 配音 / 字幕 |，取镜号和配音。"""
    shots = {}
    for line in (HERE / "storyboard.md").read_text(encoding="utf8").splitlines():
        if not re.match(r"^\| \d+ \| \d+ \|", line):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        shots[int(cells[0])] = cells[4]
    return shots


# ---------- 合成 ----------

def synthesize(text):
    """流式合成一镜，返回 (16 位 PCM, 带时间戳的词)。音频和时间戳必须来自同一次调用。"""
    import dashscope
    from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
    pcm = bytearray()
    tokens = {}
    errors = []

    class Collect(ResultCallback):
        def on_data(self, data):
            pcm.extend(data)

        def on_event(self, message):
            event = json.loads(message) if isinstance(message, str) else message
            sentence = event.get("payload", {}).get("output", {}).get("sentence") or {}
            # 同一个词会先发一个没念完的版本，后面再更新结束时刻，以最后一次为准
            for w in sentence.get("words") or []:
                tokens[(sentence.get("index", 0), w["begin_index"])] = w

        def on_error(self, message):
            errors.append(message)

    synth = SpeechSynthesizer(
        model=MODEL, voice=VOICE, speech_rate=RATE, pitch_rate=PITCH,
        format=AudioFormat.PCM_48000HZ_MONO_16BIT, callback=Collect(),
        additional_params={"word_timestamp_enabled": True},
    )
    synth.streaming_call(text)
    synth.streaming_complete()
    if errors:
        raise RuntimeError(f"合成出错：{errors}")
    words = [[tokens[k]["text"], tokens[k]["begin_time"], tokens[k]["end_time"]] for k in sorted(tokens)]
    return bytes(pcm), words


# ---------- 对时间 ----------

def loudness(samples):
    """每 10 毫秒一格的响度，用来找开口、收声和句间停顿。"""
    hop = SAMPLE_RATE // 100
    frames = samples[: len(samples) // hop * hop].astype(float).reshape(-1, hop)
    return np.sqrt((frames ** 2).mean(axis=1))


def silences(voiced, min_len):
    """连续 min_len 格（每格 10 毫秒）以上的静音段，(起, 止) 秒，不算开头结尾。"""
    out = []
    i = 0
    while i < len(voiced):
        if voiced[i]:
            i += 1
            continue
        j = i
        while j < len(voiced) and not voiced[j]:
            j += 1
        if j - i >= min_len and i > 0 and j < len(voiced):
            out.append((i / 100, j / 100))
        i = j
    return out


def is_han(ch):
    return "一" <= ch <= "鿿"


def align(text, words, samples):
    """算出旁白里每个字开始念的时刻（秒，从音频开头算）；times[len(text)] 是收声的时刻。

    1. 调了音高（或语速）后，返回的时间戳整体比实际音频长一截（音高 0.93 时约 1.13 倍），但比例是固定的：
       用最后一个标点的开始时刻对上实际收声，求出缩放比例。
    2. 时间戳按念出来的字给，数字会变成汉字（39 → 三十九），空格变成“、”，
       所以只拿汉字跟原文按顺序配对；配不上的字（数字、英文、标点）按前后两个配上的字均匀插值。
    """
    voiced = loudness(samples) > 300
    voiced_start = np.argmax(voiced) / 100
    voiced_end = (len(voiced) - np.argmax(voiced[::-1])) / 100
    last = words[-1]
    last_begin = last[1] if last[0] in "，。；、！？" else last[2]
    scale = voiced_end / (last_begin / 1000)

    # 念出来的汉字，每个带 (开始, 结束)。一个词有几个字符就平分它的时长，
    # 字母也占一份（“多k”是一个词，“多”只占前一半），但只留汉字去配对
    spoken = []
    for token, begin, end in words:
        units = [c for c in token if not c.isspace()]
        for k, c in enumerate(units):
            if not is_han(c):
                continue
            b = begin + (end - begin) * k / len(units)
            e = begin + (end - begin) * (k + 1) / len(units)
            spoken.append((c, b / 1000 * scale, e / 1000 * scale))

    han_pos = [i for i, c in enumerate(text) if is_han(c)]
    matcher = difflib.SequenceMatcher(None, [text[i] for i in han_pos], [s[0] for s in spoken], autojunk=False)
    anchors = {}  # 原文位置 → (开始, 结束)
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            anchors[han_pos[a + k]] = spoken[b + k][1:]
    share = len(anchors) / len(han_pos)
    if share < 0.95:
        raise RuntimeError(f"只有 {share:.0%} 的汉字对上了时间戳：{text}")

    times = [None] * (len(text) + 1)
    for i, (b, _) in anchors.items():
        times[i] = b
    times[len(text)] = voiced_end
    # 没配上的一段：从前一个配上的字念完，到后一个配上的字开口，均匀铺开
    i = 0
    while i < len(text):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while times[j] is None:
            j += 1
        prev_end = anchors[i - 1][1] if i > 0 else voiced_start
        nxt = times[j]
        for k in range(i, j):
            times[k] = prev_end + (nxt - prev_end) * (k - i) / (j - i)
        i = j
    for k in range(1, len(times)):
        if times[k] < times[k - 1]:
            raise RuntimeError(f"时刻倒退了：第 {k} 个字，{text}")

    # 自检：句中的逗号、句号之后不远，音频里大多应该真有一段停顿。
    # 时间戳整体比实际声音早 0.1 秒上下，所以停顿允许落在标点时刻之后 0.3 秒内；
    # 有的逗号念得很连贯，只停三四十毫秒甚至不停，所以只要求八成标点对得上
    gaps = silences(voiced, min_len=3)
    marks = [i for i, c in enumerate(text[:-1]) if c in "，。；"]
    hit = [i for i in marks if any(times[i] - 0.1 <= t <= times[i] + 0.3 for t, _ in gaps)]
    if marks and len(hit) < 0.8 * len(marks):
        raise RuntimeError(f"{len(marks)} 个标点只有 {len(hit)} 个附近有停顿，时间可能没对上：{text}")
    return times, float(voiced_start), float(voiced_end), float(scale), f"{len(hit)}/{len(marks)}"


# ---------- 主流程 ----------

def main():
    build = Path(sys.argv[1])
    first, last = map(int, sys.argv[2].split("-"))
    out_dir = build / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)
    params = {"model": MODEL, "voice": VOICE, "rate": RATE, "pitch": PITCH}

    for n, text in read_narration().items():
        if not first <= n <= last:
            continue
        wav_path = out_dir / f"shot{n:02d}.wav"
        json_path = out_dir / f"shot{n:02d}.json"
        old = json.loads(json_path.read_text(encoding="utf8")) if json_path.exists() else None
        if old and wav_path.exists() and old["text"] == text and old["params"] == params:
            words = old["words"]
            with wave.open(str(wav_path)) as w:
                pcm = w.readframes(w.getnframes())
            made = "沿用"
        else:
            pcm, words = synthesize(text)
            with wave.open(str(wav_path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(pcm)
            # 先把原始时间戳存下，下面对时间出错时不用重新合成（花钱）
            json_path.write_text(json.dumps({"text": text, "params": params, "words": words}, ensure_ascii=False), encoding="utf8")
            made = "合成"
        samples = np.frombuffer(pcm, np.int16)
        times, start, end, scale, pauses = align(text, words, samples)
        duration = len(samples) / SAMPLE_RATE
        json_path.write_text(json.dumps({
            "text": text, "params": params, "duration": duration,
            "voiced_start": start, "voiced_end": end, "scale": scale,
            "times": [round(t, 3) for t in times], "words": words,
        }, ensure_ascii=False), encoding="utf8")
        print(f"镜 {n}：{made}，音频 {duration:.2f} 秒，{start:.2f}–{end:.2f} 秒有声，时间戳缩放 {scale:.3f}，标点对上停顿 {pauses}")


if __name__ == "__main__":
    main()

"""音声認識（単語の時刻つき）→ sources/{id}_whisper.json。make.py plan/build の前に使う。
使い方（shadowing/ で）: python3 tools/whisper.py L1-4 L1-5 ...
"""
import json, subprocess, sys
import numpy as np
from pathlib import Path
from faster_whisper import WhisperModel

SRC = Path(__file__).resolve().parent.parent / "sources"
model = WhisperModel("small.en", device="cpu", compute_type="int8")
for i in sys.argv[1:]:
    # 音声は ffmpeg で読む（入っている PyAV が faster-whisper と合わないため）
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC / f"{i}_src.mp4", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    segs, _ = model.transcribe(np.frombuffer(pcm, np.float32), language="en", word_timestamps=True)
    out = [{"s": s.start, "e": s.end, "t": s.text, "w": [[w.start, w.end, w.word] for w in s.words]} for s in segs]
    (SRC / f"{i}_whisper.json").write_text(json.dumps(out, ensure_ascii=False))
    print(i, len(out), flush=True)

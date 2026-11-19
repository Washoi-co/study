"""Business（Startup Dad のショート）と Tech（Code Story）の教材（2026-11-18 kimi）。make.py の時刻合わせ・間詰め・保存をそのまま使う。

使い方（shadowing/ で）:
  python3 tools/biz.py fetch B1-1 T3-2 ...   # 落とす・faster-whisper → sources/{id}_src.mp4, _whisper.json, _draft.json（下書きの行）
  python3 tools/biz.py build B1-1 T3-2 ...   # sources/{id}_plan.json（行・単語・英語のクイズ）から、最初のイントロを切って動画と字幕を作る → data/lessons.json
引数なしなら business_pick.json と tech_pick.json の全部。

pick（sources/business_pick.json・tech_pick.json）の1件:
  {"id": "B1-1", "url": 動画か音声の URL（yt-dlp が読める物）, "title": "...", "speaker": "...", "role": "...",
   "audio_only": true なら音声だけ（サムネイルの静止画＋音声の動画にする）, "episode": 元の回の名前（長い回を切る時）}
  同じ回から何本も切る時は url を同じにしてよい（落とすのと whisper は1回だけ：sources/{key}_src.mp4 を使い回す。key＝"src" に書いた名前）

{id}_plan.json の形（人が書く。英語だけ）:
  {"lines": [{"en": "..."}],            # 話し手のせりふ（本文どおり）。最初の行より前（番組のイントロ・前置き）は切れる
   "from": 秒, "to": 秒,                 # 長い回の中のどこか（whisper の秒。行を探す範囲。5分以内）
   "title_ja": "日本語の題（サムネイル用）", "head": ["見出し1行目", "2行目"], "sub": "小見出し",
   "vocab": [{"en": "...", "ja": "..."}],
   "quiz":  [{"q": "...", "choices": ["..","..","..",".."], "answer": 0, "explain": "..."}]}
"""
import json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make  # noqa: E402

SRC, MEDIA = make.SRC, make.MEDIA
PICK = [p for f in ["business_pick.json", "tech_pick.json"] + sorted(x.name for x in SRC.glob("health_pick*.json")) if (SRC / f).exists() for p in json.load(open(SRC / f))]  # Health は health_pick_a.json など、分けて書いてよい
BY = {p["id"]: p for p in PICK}
CREDIT = {"B": "Clip: Startup Dad podcast with Adam Fishman (youtube.com/@StartupDadPod) — used with permission",
          "T": "Clip: Code Story podcast with Noah Labhart (codestory.co) — used with permission",
          "H": "Clip: Sigma Nutrition Radio with Danny Lennon (sigmanutrition.com) — used with permission"}
CAT = {"B": "business", "T": "tech", "H": "health"}
SOURCE = {"B": "startupdad", "T": "codestory", "H": "sigmanutrition"}


def key(i):
    return BY[i].get("src") or i


def fetch(i):
    p, k = BY[i], key(i)
    src, wj = SRC / f"{k}_src.mp4", SRC / f"{k}_whisper.json"
    if not src.exists():
        if p.get("audio_only"):
            mp3 = SRC / f"{k}_src.mp3"
            if not mp3.exists():
                subprocess.run(["yt-dlp", "-q", "--no-warnings", "-x", "--audio-format", "mp3", "-o", str(SRC / f"{k}_src.%(ext)s"), p["url"]], check=True)
            png = SRC / f"{k}_still.png"; make.still(p.get("episode") or p["title"], png)
            make.ff("-loop", "1", "-framerate", "1", "-i", png, "-i", mp3, "-map", "0:v", "-map", "1:a", "-shortest",
                    "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "1", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", src)
        else:
            subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                            "--merge-output-format", "mp4", "-o", str(src), p["url"]], check=True)
        print(i, "src ok", f"{src.stat().st_size / 1e6:.1f}MB")
    if not wj.exists():
        from faster_whisper import WhisperModel
        import numpy as np
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
        segs, _ = model.transcribe(np.frombuffer(pcm, np.float32), language="en", word_timestamps=True)
        out = [{"s": g.start, "e": g.end, "t": g.text, "w": [[w.start, w.end, w.word] for w in (g.words or [])]} for g in segs]
        wj.write_text(json.dumps(out, ensure_ascii=False))
        print(i, "whisper ok", len(out), "segs")
    segs = json.load(open(wj))
    words = [w for s in segs for w in s["w"]]
    lines, cur = [], []
    for w in words:  # 文の終わりで行を切る（下書き。人が直して plan にする）
        cur.append(w)
        if re.search(r"[.?!]$", w[2].strip()) and len(cur) >= 3:
            lines.append({"start": round(cur[0][0], 2), "end": round(cur[-1][1], 2), "en": "".join(x[2] for x in cur).strip()}); cur = []
    if cur:
        lines.append({"start": round(cur[0][0], 2), "end": round(cur[-1][1], 2), "en": "".join(x[2] for x in cur).strip()})
    (SRC / f"{k}_draft.json").write_text(json.dumps({"key": k, **p, "lines": lines}, ensure_ascii=False, indent=1))


def build(i):
    p, P, k = BY[i], json.load(open(SRC / f"{i}_plan.json")), key(i)
    if k != i:  # 同じ回から切る：元の動画・whisper を自分の id の名前でも読めるように（make.cut／spans が {i}_src.mp4・{i}_whisper.json を読む）
        for ext in ("_src.mp4", "_whisper.json"):
            dst = SRC / f"{i}{ext}"
            if not dst.exists():
                dst.symlink_to(SRC / f"{k}{ext}")
    vertical = not p.get("audio_only") and p["id"][0] == "B"
    make.LESSONS[i] = dict(height=960 if vertical else 720, crf=28)
    segs = json.load(open(SRC / f"{k}_whisper.json"))
    words = [w for s in segs for w in s["w"]]
    lines = [{"en": l["en"].strip()} for l in P["lines"]]
    times = make.align(lines, words, P.get("from", 0), P.get("to", segs[-1]["e"]))
    a = max(times[0][0] - 0.3, 0); b = times[-1][1] + 0.5   # 最初の行の直前から（イントロ・前置きは切る）
    assert b - a <= 330, f"{i}: {b - a:.0f}秒（5分を超えた。plan の行を減らす）"
    c = i[0]
    lesson = dict(id=i, cat=CAT[c], level=None, speaker=p.get("speaker"), role=p.get("role"), title=P.get("title") or p["title"],
                  title_ja=P.get("title_ja"), episode=p.get("episode"),
                  source=SOURCE[c], source_url=p.get("page") or p["url"], video=f"media/{i}.mp4", audio_only=None,
                  subs_en=f"subs/{i}.en.vtt", subs_ja=None, clip_start=round(a, 2), clip_end=round(b, 2),
                  cover_height=0, vertical=vertical, repeat="line", synopsis=None, vocab=P["vocab"], quiz=P["quiz"],
                  lang="en", ja_reviewed=True, ja_unsure=[], credit=CREDIT[c], active=True, start_at=None)
    cues = make.cut(i, lesson, [{"start": s, "end": min(e + 0.15, nxt), "en": l["en"], "ja": ""}  # 次の行と重ねない
                                 for (s, e), l, nxt in zip(times, lines, [t[0] for t in times[1:]] + [1e9])], a, b)
    if p.get("audio_only"):  # 音声だけの回：画面は真っ黒、字幕は真ん中にサムネイルの色で（kimi 2026-11-18）。音はそのまま
        out, tmp = MEDIA / f"{i}.mp4", MEDIA / f"{i}.tmp.mp4"
        make.ff("-f", "lavfi", "-i", "color=c=black:s=1280x720:r=2", "-i", out, "-map", "0:v", "-map", "1:a", "-shortest",
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", tmp)
        tmp.replace(out)
        import thumb
        c = thumb.palette(i)[1]
        lesson.update(screen="black", sub_color=c if isinstance(c, str) else "#%02X%02X%02X" % tuple(c))
    make.save(i, lesson, cues)
    ja = make.SUBS / f"{i}.ja.vtt"
    if ja.exists():
        ja.unlink()  # 日本語字幕は作らない（kimi 2026-11-18）


if __name__ == "__main__":
    cmd, ids = sys.argv[1], sys.argv[2:] or [p["id"] for p in PICK]
    for i in ids:
        {"fetch": fetch, "build": build}[cmd](i)

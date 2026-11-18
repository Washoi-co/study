#!/usr/bin/env python3
"""シャドーイングのサムネイル（1280x720 JPEG）を作る。
  python3 tools/thumb.py            （sources/*_lesson.json の全部）
  python3 tools/thumb.py L1-1 B2-3  （選んだ物だけ）
  python3 tools/thumb.py --new      （まだ thumbs/ に無い物だけ）
→ thumbs/<id>.jpg。そのあと python3 tools/make.py collect で data/lessons.json に "thumb" が入る。

見出し・小見出し：sources/<id>_plan.json の head/sub（B・T）→ 無ければ sources/thumbs_ja.json（L）。
写真：動画からいくつか画面を取り出し、顔（macOS の Vision）が大きく真ん中にある1枚を選んで右に置く。
  選んだ画面は ~/Library/Caches/apush_thumb_picks.json に覚える（選び直す時はその行を消す）。
顔が見つからない物（音声だけ・朗読・NASA の景色）は、写真を使わず文字と波形だけ。
ロゴ・A-PUSH の字は入れない（2026-11-18 kimi）。
色：2026-11-18 kimi「シャドーイングのサムネイルだけ赤・黒・白の決まりの外」。PALETTES から id ごとに決まった1組（隣どうしは別の色）。
"""
import hashlib, json, os, re, subprocess, sys, tempfile
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "sources", ROOT / "thumbs"
W, H = 1280, 720
INK, WHITE = (11, 11, 12), (255, 255, 255)
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
BORDER, RADIUS = 20, 34                     # 色の枠の太さ・中の写真の角の丸み
CACHE = Path.home() / "Library/Caches/apush_thumb_picks.json"

# （枠のグラデーション 左上, 右下, 見出しの箱, 見出しの字）
PALETTES = [
    ("#2B5BFF", "#00C6B5", "#2B5BFF", "#FFFFFF"),   # 青→ティール
    ("#7B2FF7", "#F107A3", "#7B2FF7", "#FFFFFF"),   # 紫→マゼンタ
    ("#B3001B", "#F2B134", "#C8102E", "#FFFFFF"),   # 深い赤→金
    ("#FF6A00", "#FFD200", "#FFD200", "#0B0B0C"),   # オレンジ→黄
    ("#00875A", "#B6E62E", "#00875A", "#FFFFFF"),   # 緑→黄緑
    ("#1D2671", "#C33764", "#C33764", "#FFFFFF"),   # 紺→ローズ
    ("#0F3443", "#34E89E", "#FFD200", "#0B0B0C"),   # 深い緑→ミント、黄の箱
    ("#FF3CAC", "#784BA0", "#FF3CAC", "#FFFFFF"),   # ピンク→紫
    ("#E8321F", "#FF8A00", "#E8321F", "#FFFFFF"),   # 赤→オレンジ
    ("#00B4DB", "#0052D4", "#0052D4", "#FFFFFF"),   # 水色→青
]

FACE_SWIFT = r'''
import Vision
import Foundation
for p in CommandLine.arguments.dropFirst() {
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(url: URL(fileURLWithPath: p)).perform([req])
    print((req.results ?? []).map { r -> String in let b = r.boundingBox
        return String(format: "%.4f,%.4f,%.4f,%.4f", b.minX, 1 - b.maxY, b.width, b.height) }.joined(separator: ";"))
}
'''


def rgb(h):
    return tuple(int(h[k:k + 2], 16) for k in (1, 3, 5))


def palette(i):
    """L1-3 → 1*3+3。同じ課の隣どうしは必ず別の色、課が変わるとずれる"""
    u, n = (list(map(int, re.findall(r"\d+", i))) + [0, 0])[:2]
    return [rgb(c) for c in PALETTES[(u * 3 + n) % len(PALETTES)]]


def face_bin():
    """顔を探す小さな道具（Vision）。初回だけ swiftc で作り、Caches に置く。"""
    b = Path.home() / "Library/Caches" / f"apush_face_{hashlib.md5(FACE_SWIFT.encode()).hexdigest()[:8]}"
    if not b.exists():
        s = Path(tempfile.mkdtemp()) / "face.swift"
        s.write_text(FACE_SWIFT)
        subprocess.run(["swiftc", "-O", str(s), "-o", str(b)], check=True, capture_output=True)
    return str(b)


def faces(paths):
    out = subprocess.run([face_bin(), *map(str, paths)], capture_output=True, text=True).stdout.splitlines()
    return [[tuple(map(float, b.split(","))) for b in line.split(";") if b] for line in out]


def video_of(lesson):
    i = lesson["id"]
    if (ROOT / "media" / f"{i}.mp4").exists():
        return str(ROOT / "media" / f"{i}.mp4")
    v = lesson.get("video") or ""
    if v.startswith("http"):
        return v
    return str(ROOT / v) if v and (ROOT / v).exists() else None


def duration(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True).stdout.strip()
    return float(r) if r else 0


def grab(src, t, path, scale=None):
    vf = ["-vf", f"scale={scale}:-2"] if scale else []
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", *vf, "-y", str(path)],
                   capture_output=True)
    return Path(path).exists() and Path(path).stat().st_size > 0


def pick(src, cover, tmp, n=20):
    """顔が大きく、真ん中寄りで、くっきりした画面を選ぶ。→ [秒, 顔の箱] か None"""
    d = duration(src)
    if d <= 0: return None
    ts = [d * (0.04 + 0.9 * k / (n - 1)) for k in range(n)]
    shots = [(t, tmp / f"c{k}.jpg") for k, t in enumerate(ts) if grab(src, t, tmp / f"c{k}.jpg", 640)]
    best = None
    for (t, p), boxes in zip(shots, faces([p for _, p in shots])):
        boxes = [b for b in boxes if b[2] * b[3] > 0.003 and b[1] + b[3] / 2 < 1 - cover]
        if not boxes: continue
        x, y, w, h = max(boxes, key=lambda b: b[2] * b[3])
        im = Image.open(p)
        sharp = min(1.0, float(np.asarray(ImageOps.grayscale(im).filter(ImageFilter.FIND_EDGES)).mean()) / 12)
        gray = float(np.asarray(im.convert("HSV"))[..., 1].mean()) / 255 < 0.1     # VOA の練習画面（白黒＋字幕）を避ける
        score = (w * h) ** 0.5 * (1.25 - abs(x + w / 2 - 0.5)) * (0.75 if len(boxes) > 2 else 1) * (0.4 + 0.6 * sharp) * (0.2 if gray else 1)
        if not best or score > best[0]:
            best = (score, t, [x, y, w, h])
    return best and list(best[1:])


def cached_pick(i, src, cover, tmp):
    c = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if i in c and c[i]["src"] == src:
        return c[i]["pick"]
    p = pick(src, cover, tmp)
    c = json.loads(CACHE.read_text()) if CACHE.exists() else {}      # 並べて動かした時に他の行を消さない
    c[i] = {"src": src, "pick": p}
    t = CACHE.with_suffix(f".{os.getpid()}")
    t.write_text(json.dumps(c, ensure_ascii=False, indent=0))
    t.replace(CACHE)                                               # 書きかけを読ませない
    return p


def grade(im):
    """色はそのまま、少しだけ締める"""
    im = ImageOps.autocontrast(im, cutoff=0.5)
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.08)).enhance(1.12)


def photo_panel(frame, box, cover):
    """顔を中心に切り抜き、右側の板（幅 pw）にする。縦の動画は右 45%"""
    fw, fh = frame.size
    vertical = fh > fw
    pw = 600 if vertical else 860
    usable = fh * (1 - cover - 0.04) if cover else fh            # 焼き込みの字幕の少し上まで
    top0 = fh * 0.10 if cover else 0                             # 字幕のある VOA は上の 10%（ロゴ）も外す
    if vertical: top0 = fh * 0.19                                # Startup Dad の Shorts は上 19% が番組のロゴ
    x, y, w, h = box
    cx, cy = (x + w / 2) * fw, (y + h / 2) * fh
    ch = min(usable - top0, max(fh * 0.62, h * fh * 3.4))  # 顔が板の高さの 1/3 くらい
    if vertical: ch = min(usable - top0, max(fh * 0.3, min(fh * 0.48, h * fh * 2.1)))   # Shorts：上のロゴ・下の字幕を外して顔の窓だけ（Startup Dad に合わせた値）
    cw = ch * pw / H
    if cw > fw: cw, ch = fw, fw * H / pw
    left = min(max(cx - cw / 2, 0), fw - cw)
    top = min(max(cy - ch * (0.5 if vertical else 0.4), top0), max(usable - ch, top0))
    return grade(frame.crop((int(left), int(top), int(left + cw), int(top + ch))).resize((pw, H), Image.LANCZOS))


def gradient(a, b, size):
    """左上 a → 右下 b"""
    w, h = size
    t = (np.linspace(0, 1, w)[None, :] * w + np.linspace(0, 1, h)[:, None] * h) / (w + h)
    arr = np.array(a)[None, None, :] * (1 - t[..., None]) + np.array(b)[None, None, :] * t[..., None]
    return Image.fromarray(arr.astype(np.uint8))


def dark(pal):
    """写真の左の地：ほぼ黒に枠の色を少し混ぜる"""
    return tuple(int(INK[k] * 0.82 + pal[0][k] * 0.18) for k in range(3))


def base_photo(panel, pal):
    c = Image.new("RGB", (W, H), dark(pal))
    c.paste(panel, (W - panel.width, 0))
    fade = int(panel.width * 0.55)
    g = Image.linear_gradient("L").rotate(-90, expand=True).resize((fade, H))   # 左=255 → 右=0
    c.paste(Image.new("RGB", (fade, H), dark(pal)), (W - panel.width, 0), g)
    return c


def base_audio(seed, pal):
    """写真なし：暗い地に、枠の色のグラデーションの波形"""
    c = Image.new("RGB", (W, H), dark(pal))
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    hs = hashlib.md5(seed.encode()).digest()
    n, x0, gap = 18, 820, 22
    for k in range(n):
        hh = 70 + (hs[k % 16] * (k + 3)) % 330
        x = x0 + k * gap
        d.rounded_rectangle((x, H / 2 - hh / 2, x + 11, H / 2 + hh / 2), 5, fill=255)
    c.paste(gradient(pal[0], pal[1], (W, H)), (0, 0), m)
    return c


def fit(text, size, maxw, path=FONT):
    while size > 20:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= maxw: return f
        size -= 2
    return ImageFont.truetype(path, size)


def text_block(c, head, sub, pal, maxw=640):
    d = ImageDraw.Draw(c)
    padx, pady, gap = 22, 14, 10
    size = min(fit(t, 104, maxw).size for t in head)        # 2行とも同じ大きさ
    hf = ImageFont.truetype(FONT, size)
    sf = fit(sub, 38, maxw - 40) if sub else None
    rows = [(t, hf, pal[2], pal[3], padx, pady) for t in head]
    if sub: rows.append((sub, sf, WHITE, INK, 16, 10))
    heights = [f.getbbox(t)[3] - f.getbbox(t)[1] + 2 * py for t, f, _, _, _, py in rows]
    total = sum(heights) + gap * (len(rows) - 1) + (14 if sub else 0)
    y, x = (H - total) / 2 + 10, 66
    for k, ((t, f, bg, fg, px, py), rh) in enumerate(zip(rows, heights)):
        if sub and k == len(rows) - 1: y += 14                 # 小見出しは少し離す
        l, tp, r, b = f.getbbox(t)
        d.rectangle((x, y, x + (r - l) + 2 * px, y + rh), fill=bg)
        d.text((x + px - l, y + py - tp), t, font=f, fill=fg)
        y += rh + gap


def framed(c, pal):
    """色のグラデーションの枠＋角の丸い中身"""
    out = gradient(pal[0], pal[1], (W, H))
    inner = c.resize((W - 2 * BORDER, H - 2 * BORDER), Image.LANCZOS)
    m = Image.new("L", inner.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, *inner.size), RADIUS, fill=255)
    out.paste(inner, (BORDER, BORDER), m)
    return out


def texts(i):
    """→ (head, sub, t)。t は画面の秒を手で決める時だけ（thumbs_ja.json の "t"）"""
    t = json.loads((SRC / "thumbs_ja.json").read_text()).get(i) or {}
    p = SRC / f"{i}_plan.json"
    pl = json.loads(p.read_text()) if p.exists() else {}
    if pl.get("head"):
        return pl["head"], pl.get("sub", ""), t.get("t")
    return (t["head"], t.get("sub", ""), t.get("t")) if t.get("head") else None


def make(i):
    lesson = json.loads((SRC / f"{i}_lesson.json").read_text())
    tx = texts(i)
    if not tx or not tx[0]:
        return f"{i}: 見出しが無い（plan の head か thumbs_ja.json）"
    pal, cover = palette(i), lesson.get("cover_height") or 0
    src, c, how = video_of(lesson), None, "文字"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if src and tx[2] is not None and grab(src, tx[2], tmp / "m.jpg", 640):   # 手で決めた秒：顔があれば顔、無ければ景色の真ん中
            fs = faces([tmp / "m.jpg"])[0]
            best = [tx[2], list(max(fs, key=lambda b: b[2] * b[3])) if fs else [0.4, 0.25, 0.2, 0.3]]
        else:
            best = cached_pick(i, src, cover, tmp) if src else None
        if best and grab(src, best[0], tmp / "f.jpg"):
            c, how = base_photo(photo_panel(Image.open(tmp / "f.jpg").convert("RGB"), best[1], cover), pal), f"{best[0]:.0f}秒"
    maxw = 640 if c else 720                                   # 写真なしは字を広く
    c = c or base_audio(i, pal)
    text_block(c, tx[0], tx[1], pal, maxw)
    c = framed(c, pal)
    OUT.mkdir(exist_ok=True)
    q = 82
    while True:
        c.save(OUT / f"{i}.jpg", "JPEG", quality=q, optimize=True, progressive=True)
        if (OUT / f"{i}.jpg").stat().st_size < 200_000 or q < 50: break
        q -= 6
    return f"{i}: {how} q{q} {(OUT / f'{i}.jpg').stat().st_size // 1000}KB"


if __name__ == "__main__":
    assert palette("L1-1") != palette("L1-2") and palette("B3-1") == palette("B3-1")
    args = sys.argv[1:]
    all_ids = sorted(p.name[:-12] for p in SRC.glob("*_lesson.json"))
    ids = [i for i in all_ids if not (OUT / f"{i}.jpg").exists()] if args == ["--new"] else args or all_ids
    for i in ids:
        print(make(i), flush=True)

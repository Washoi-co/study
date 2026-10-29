"""教材データを暗号化して data.enc を作る。

  python3 build.py

元データ（公開しない）は ../study-src/ に置く:
  beginner.txt       Beginner PDF を pdftotext -layout したもの
  intermediate.json  Intermediate の文字起こし [{ch,title,ja,items:[[T,S,T訳,S訳],...]}]
  send.json          録音の送り先 {"url": Apps Script の URL, "key": 合い鍵}（任意）。合い鍵そのものは data.enc に入れず、
                     生徒ごとの鍵（録音 rk・管理アプリ tok）を作って、その生徒の keys[会員番号] にだけ入れる
  students.json      生徒ごとのログイン [{"id": "STU005", "name": "T.Y", "pass": "パスワード", "track": "biz"}, ...]
                     track：その生徒の専門（下の TRACKS のキー）。ONにすると話すも単語もその専門になる。無い生徒は普通の教材だけ
  business.json / civil.json  専門の章 [{ch,title,ja,items:[[T,S,T訳,S訳,絵文字],...]}]。その専門の生徒だけが開ける
生徒を足した・パスワードを変えた時は、もう一度これを実行して data.enc を push する。

しくみ: 教材は1つの鍵（データ鍵）で暗号化し、そのデータ鍵を生徒ごとのパスワードで
それぞれ包んで keys[会員番号] に入れる。生徒を消せば、その生徒はもう開けない。
"""
import base64, hashlib, hmac, json, os, re, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SRC = os.path.join(os.path.dirname(__file__), "..", "study-src")
UNITS_B = [(1, 6, "A"), (7, 13, "B"), (14, 20, "C"), (21, 24, "D")]
UNITS_I = [(1, 6, "A"), (7, 12, "B"), (13, 18, "C"), (19, 26, "D")]
UNITS_Z = [(1, 6, "A"), (7, 12, "B"), (13, 18, "C"), (19, 24, "D")]


def unit(n, table):
    return next(u for a, b, u in table if a <= n <= b)


def beginner():
    txt = open(os.path.join(SRC, "beginner.txt"), encoding="utf-8").read()
    chs = []
    for m in re.finditer(r"^\f?Chapter (\d+)\s+Beginner [A-D]\n(.+?)\n(.*?)Native Flow — Beginner", txt, re.M | re.S):
        n, title, body = int(m[1]), m[2].strip(), m[3]
        ts = re.findall(r"T: (.+)", body)
        ss = re.findall(r"S: (.+)", body)
        assert len(ts) == len(ss) == 6, n
        chs.append({"n": n, "u": unit(n, UNITS_B), "title": title,
                    "items": [{"t": t.strip(), "s": s.strip(), "pic": f"img/b/{n}.webp"} for t, s in zip(ts, ss)]})
    assert [c["n"] for c in chs] == list(range(1, 25))
    return chs


def intermediate():
    chs = []
    for c in json.load(open(os.path.join(SRC, "intermediate.json"), encoding="utf-8")):
        n = c["ch"]
        chs.append({"n": n, "u": unit(n, UNITS_I), "title": c["title"], "ja": c["ja"],
                    "items": [{"t": t, "s": s, "tj": tj, "sj": sj, "pic": f"img/i/{n}-{k + 1}.webp"}
                              for k, (t, s, tj, sj) in enumerate(c["items"])]})
    assert [c["n"] for c in chs] == list(range(1, 27))
    return chs


# 専門（生徒ごとにON/OFFするもの）。label＝スイッチの名前、words＝単語コースのグループ（words/courses/index.js の g）
TRACKS = {
    "biz": {"file": "business.json", "name": "Business", "label": "ビジネス英語", "words": "Business"},
    "civ": {"file": "civil.json", "name": "土木", "label": "土木英語", "words": "土木"},
}


def track_level(tid):
    t = TRACKS[tid]
    path = os.path.join(SRC, t["file"])
    if not os.path.exists(path):
        return None
    chs = []
    for c in json.load(open(path, encoding="utf-8")):
        n = c["ch"]
        chs.append({"n": n, "u": unit(n, UNITS_Z), "title": c["title"], "ja": c["ja"],
                    "items": [{"t": t_, "s": s, "tj": tj, "sj": sj, "e": e} for t_, s, tj, sj, e in c["items"]]})
    return {"id": "z", "name": t["name"], "chapters": chs}


def derive(sk, purpose, sid):
    """生徒ごとの鍵：base64url(HMAC-SHA256(合い鍵, "rec|STU005")) の先頭32字。
    rec＝録音の鍵（Reviewing system が同じ式で確かめる）／kanri＝管理アプリに入る鍵（functions/studentToken.js と同じ式）"""
    return base64.urlsafe_b64encode(hmac.new(sk.encode(), (purpose + "|" + sid).encode(), hashlib.sha256).digest()).decode()[:32]


def main():
    if len(sys.argv) != 1:
        sys.exit(__doc__)
    students = json.load(open(os.path.join(SRC, "students.json"), encoding="utf-8"))
    send_path = os.path.join(SRC, "send.json")
    send = json.load(open(send_path)) if os.path.exists(send_path) else None
    sk = str(send.get("key") or "").strip() if send else ""
    data = {
        "send": {"url": send["url"]} if send else None,   # 合い鍵は共通の教材に入れない（生徒ごとの rk を keys[会員番号] に入れる）
        "levels": [{"id": "b", "name": "Beginner", "chapters": beginner()},
                   {"id": "i", "name": "Intermediate", "chapters": intermediate()}],
    }
    b64 = lambda b: base64.b64encode(b).decode()
    dkey, iv = os.urandom(32), os.urandom(12)
    ct = AESGCM(dkey).encrypt(iv, json.dumps(data, ensure_ascii=False).encode(), None)
    # 専門の章は専門ごとに別の鍵で暗号化し、その専門の生徒にだけ鍵を渡す（data.enc の t[専門]）
    out, tkeys = {"i": b64(iv), "c": b64(ct), "t": {}}, {}
    for tid in TRACKS:
        lv = track_level(tid)
        if not lv:
            continue
        tkeys[tid], tiv = os.urandom(32), os.urandom(12)
        out["t"][tid] = {"i": b64(tiv), "c": b64(AESGCM(tkeys[tid]).encrypt(tiv, json.dumps(lv, ensure_ascii=False).encode(), None))}
    keys = {}
    for st in students:
        salt, siv = os.urandom(16), os.urandom(12)
        kek = hashlib.pbkdf2_hmac("sha256", st["pass"].encode(), salt, 200_000, 32)
        sid = st["id"].upper()
        me = {"k": b64(dkey), "name": st["name"]}
        if sk:   # この生徒だけの鍵：rk＝録音、tok＝管理アプリ（他の生徒の分は持たない＝他人のふりができない）
            me["rk"], me["tok"] = derive(sk, "rec", sid), derive(sk, "kanri", sid)
        tid = st.get("track")
        if tid in TRACKS:   # 専門：スイッチの名前・単語のグループ・章の鍵
            me["track"] = {"id": tid, "label": TRACKS[tid]["label"], "words": TRACKS[tid]["words"]}
            if tid in tkeys:
                me["kb"] = b64(tkeys[tid])
        inner = json.dumps(me, ensure_ascii=False).encode()
        keys[sid] = {"s": b64(salt), "i": b64(siv), "c": b64(AESGCM(kek).encrypt(siv, inner, None))}
    json.dump({**out, "keys": keys}, open(os.path.join(os.path.dirname(__file__), "data.enc"), "w"))
    print("data.enc:", sum(len(l["chapters"]) for l in data["levels"]), "chapters, students:", len(keys), ", send:", bool(data["send"]),
          ", tracks:", {tid: ",".join(s["id"] for s in students if s.get("track") == tid) for tid in tkeys})


main()

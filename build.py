"""教材データを暗号化して data.enc を作る。

  python3 build.py

元データ（公開しない）は ../study-src/ に置く:
  beginner.txt       Beginner PDF を pdftotext -layout したもの
  intermediate.json  Intermediate の文字起こし [{ch,title,ja,items:[[T,S,T訳,S訳],...]}]
  send.json          録音の送り先 {"url": Apps Script の URL, "key": 合い鍵}（任意）
  students.json      生徒ごとのログイン [{"id": "STU005", "name": "T.Y", "pass": "パスワード", "biz": true}, ...]
  business.json      ビジネスの章（任意）[{ch,title,ja,items:[[T,S,T訳,S訳,絵文字],...]}]。"biz": true の生徒だけが開ける
生徒を足した・パスワードを変えた時は、もう一度これを実行して data.enc を push する。

しくみ: 教材は1つの鍵（データ鍵）で暗号化し、そのデータ鍵を生徒ごとのパスワードで
それぞれ包んで keys[会員番号] に入れる。生徒を消せば、その生徒はもう開けない。
"""
import base64, hashlib, json, os, re, sys
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


def business():
    path = os.path.join(SRC, "business.json")
    if not os.path.exists(path):
        return None
    chs = []
    for c in json.load(open(path, encoding="utf-8")):
        n = c["ch"]
        chs.append({"n": n, "u": unit(n, UNITS_Z), "title": c["title"], "ja": c["ja"],
                    "items": [{"t": t, "s": s, "tj": tj, "sj": sj, "e": e} for t, s, tj, sj, e in c["items"]]})
    return {"id": "z", "name": "Business", "chapters": chs}


def main():
    if len(sys.argv) != 1:
        sys.exit(__doc__)
    students = json.load(open(os.path.join(SRC, "students.json"), encoding="utf-8"))
    send_path = os.path.join(SRC, "send.json")
    data = {
        "send": json.load(open(send_path)) if os.path.exists(send_path) else None,
        "levels": [{"id": "b", "name": "Beginner", "chapters": beginner()},
                   {"id": "i", "name": "Intermediate", "chapters": intermediate()}],
    }
    b64 = lambda b: base64.b64encode(b).decode()
    dkey, iv = os.urandom(32), os.urandom(12)
    ct = AESGCM(dkey).encrypt(iv, json.dumps(data, ensure_ascii=False).encode(), None)
    # ビジネスの章は別の鍵で暗号化し、"biz": true の生徒にだけその鍵を渡す
    biz, out = business(), {"i": b64(iv), "c": b64(ct)}
    if biz:
        bkey, biv = os.urandom(32), os.urandom(12)
        out["b"] = {"i": b64(biv), "c": b64(AESGCM(bkey).encrypt(biv, json.dumps(biz, ensure_ascii=False).encode(), None))}
    keys = {}
    for st in students:
        salt, siv = os.urandom(16), os.urandom(12)
        kek = hashlib.pbkdf2_hmac("sha256", st["pass"].encode(), salt, 200_000, 32)
        me = {"k": b64(dkey), "name": st["name"]}
        if biz and st.get("biz"):
            me["kb"] = b64(bkey)
        inner = json.dumps(me, ensure_ascii=False).encode()
        keys[st["id"].upper()] = {"s": b64(salt), "i": b64(siv), "c": b64(AESGCM(kek).encrypt(siv, inner, None))}
    json.dump({**out, "keys": keys}, open(os.path.join(os.path.dirname(__file__), "data.enc"), "w"))
    print("data.enc:", sum(len(l["chapters"]) for l in data["levels"]), "chapters, students:", len(keys), ", send:", bool(data["send"]),
          ", business:", f'{len(biz["chapters"])} chapters → ' + ",".join(s["id"] for s in students if s.get("biz")) if biz else "none")


main()

/**
 * 生徒の録音を受け取り、Google ドライブに保存して、このスプレッドシートに1行追加する。
 *
 * 設定:
 *  1. 新しいスプレッドシートを作る →「拡張機能」→「Apps Script」→ このファイルの中身を貼る
 *  2. KEY を好きな文字列に変える（../study-src/send.json の key と同じにする）
 *  3.「デプロイ」→「新しいデプロイ」→ 種類「ウェブアプリ」
 *     実行するユーザー: 自分 ／ アクセスできるユーザー: 全員 → デプロイ → 承認
 *  4. 表示された URL を send.json の url に入れて、build.py をもう一度実行
 */
const KEY = 'ここを変える';
const FOLDER = 'A-PUSH 生徒の録音';
const SHEET = '録音';

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.key !== KEY) return json({ ok: false, error: 'key' });

    const ss = SpreadsheetApp.getActive();
    const sheet = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['日時', '名前', 'レベル', '章', '問題', '練習', '質問 (T)', '答え (S)', '音声', 'メモ']);
      sheet.setFrozenRows(1);
    }

    const stamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd-HHmmss');
    const ext = /mp4|m4a|aac/.test(d.mime) ? 'm4a' : 'webm';
    const name = `${stamp}_${d.name}_${d.level}_Ch${d.ch}-${d.q}.${ext}`;
    const file = folder().createFile(Utilities.newBlob(Utilities.base64Decode(d.data), d.mime, name));

    sheet.appendRow([new Date(), d.name, d.level, d.ch, d.q, d.mode, d.t, d.s].map(safe).concat([file.getUrl(), '']));
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

/** 表に書く文：先頭が = + - @ なら ' を付けて、数式として読ませない（点検 10/29） */
function safe(v) { if (typeof v !== "string") return v; const s = v; return /^[=+\-@\t\r]/.test(s) ? "'" + s : s; }

/** スプレッドシートと同じ場所に録音フォルダを作る（なければ） */
function folder() {
  const parent = DriveApp.getFileById(SpreadsheetApp.getActive().getId()).getParents().next();
  const it = parent.getFoldersByName(FOLDER);
  return it.hasNext() ? it.next() : parent.createFolder(FOLDER);
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

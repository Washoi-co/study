/* 生徒用の単語コース一覧（words/ と、チャンクトレーニングの「単語ミックス」で使う）。
   単語の並びは生徒の記録（何番目の単語か）に使うので、各コースのファイルは後ろに足すだけにする。
   2026-10-17：中学1年レベル（gen1：I・you など）は易しすぎるので一覧から外した。gen1.js は前に使っていた生徒の記録のために残す。 */
window.APW_COURSES = [
  {g:"General", id:"gen2", t:"中学2年レベル"},
  {g:"General", id:"gen3", t:"中学3年レベル"},
  {g:"General", id:"gen4", t:"高校基礎レベル"},
  {g:"TOEIC", id:"toeic700", t:"700点"},
  {g:"TOEIC", id:"toeic800", t:"800点"},
  {g:"TOEIC", id:"toeic900", t:"900点"},
  {g:"IELTS", id:"ielts60", t:"6.0"},
  {g:"IELTS", id:"ielts65", t:"6.5"},
  {g:"IELTS", id:"ielts70", t:"7.0"},
  {g:"IELTS", id:"ielts75", t:"7.5"},
  {g:"IELTS", id:"ielts80", t:"8.0"},
  {g:"IELTS", id:"ielts85", t:"8.5"},
  {g:"TOEFL iBT", id:"toefl60", t:"60点"},
  {g:"TOEFL iBT", id:"toefl70", t:"70点"},
  {g:"TOEFL iBT", id:"toefl80", t:"80点"},
  {g:"TOEFL iBT", id:"toefl90", t:"90点"},
  {g:"TOEFL iBT", id:"toefl100", t:"100点"},
  {g:"TOEFL iBT", id:"toefl110", t:"110点"},
  // 2026-10-18：ビジネス（開ける生徒だけ。words/index.html で絞る）
  {g:"Business", id:"biz1", t:"レベル1"},
  {g:"Business", id:"biz2", t:"レベル2"},
  {g:"Business", id:"biz3", t:"レベル3"},
  {g:"Business", id:"biz4", t:"レベル4"}
];

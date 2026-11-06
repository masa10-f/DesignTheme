# 01 Brown & Orange

茶の帯にクリームの文字を載せ、オレンジを線のアクセントに使う。種色は研究ミーティング用 PPTX テンプレートのテーマ配色（accent1〜3）。

- 種色: ベース = 茶、アクセント = オレンジ、サブ = クリーム
- 正本: [theme.json](theme.json)（色の値はここだけで管理する。この README には hex を書かない）
- 見本スライド: 下の[プレビュー](#プレビュー)。色見本・コントラスト比・種色の判定: リポジトリの [README のテーマ一覧](../../README.md#テーマ一覧)、[dist/01/swatches.svg](../../dist/01/swatches.svg)

## プレビュー

<!-- BEGIN GENERATED: preview -->
<!-- この区間は scripts/build.py が生成する。手で編集しないこと。 -->

見本スライド 5 枚。点線の枠は、その部分に使っている role の名前。色は [theme.json](theme.json) の値そのまま（画像は [dist/01/preview/](../../dist/01/preview/)）。

**表紙** — `on-band`・`band`・`category`・`emphasis`・`accent`・`text`・`text-secondary`

![01 Brown & Orange: 表紙](../../dist/01/preview/1-title.svg)

**セクション扉** — `accent`・`section-label`・`emphasis`・`text-secondary`

![01 Brown & Orange: セクション扉](../../dist/01/preview/2-section.svg)

**本文** — `on-band`・`band`・`category`・`emphasis`・`rule`・`text`・`text-secondary`・`placeholder-bg`・`placeholder-text`・`placeholder-border`

![01 Brown & Orange: 本文](../../dist/01/preview/3-body.svg)

**グラフ** — `text`・`text-secondary`・`chart.series`

![01 Brown & Orange: グラフ](../../dist/01/preview/4-chart.svg)

**役割一覧** — 種色 3 つと全 role の色・palette 名・コントラスト比

![01 Brown & Orange: 役割一覧](../../dist/01/preview/5-roles.svg)

<!-- END GENERATED: preview -->

## 色の使い分け

| 場面 | 使う role | ルール |
|---|---|---|
| スライドの地 | `background` | |
| 本文 | `text` | |
| 参考文献・図キャプション | `text-secondary` | 補足情報だけに使う |
| ヘッダー帯・フッター帯 | `band` | 塗りだけに使う。帯の上の文字は `on-band` |
| 帯の上のタイトル・日付・会議名・ページ番号 | `on-band` | `band` の上でだけ使う（クリーム。白地では見えない） |
| 帯の右上のカテゴリラベル | `category` | `band` の上でだけ使う（茶を明るくした色） |
| 表紙タイトル・セクションタイトル・キーメッセージ・Takeaway | `emphasis` | 強調はこの色で行う |
| 表紙のアクセントライン・セクション扉の縦バー | `accent` | **線・図形専用。小さい文字には使わない**（白地で約 3.7:1）。オレンジの文字は `section-label` を使う |
| セクション扉の「01 / SECTION」 | `section-label` | オレンジを少し暗くした色で、小さい文字の基準 4.5:1 を満たす |
| キーメッセージ下の区切り線 | `rule` | 装飾用。白地ではかなり淡いので、情報を担わせない |
| 図のプレースホルダー | `placeholder-bg` / `placeholder-border` / `placeholder-text` | 仮置き専用。実際の図に差し替える |

## グラフ

- 系列色は `chart.series` の順に使う（matplotlib なら `theme.mplstyle` の色サイクル）。**暫定案・要確認**。
- 1 = 茶、2 = オレンジ（種色）。3〜6 は見分けやすさで選んだ追加色（緑・青・ティール・マゼンタ）。
- サブのクリームは系列に入れていない（線に使える明度まで暗くすると、2 型色覚でオレンジと見分けにくくなる）。
- 3 と 4 は 3 型色覚のシミュレーションで色差が小さめ（ΔE00 約 12）。隣り合わせる場合は線種・マーカーの形でも区別する。
- 軸・目盛りは `text-secondary`、ラベル・タイトルは `text`。

## フォント

欧文 Arial、和文 Meiryo UI。ない環境では欧文 Helvetica、和文 Hiragino Sans / Noto Sans JP の順に代替する。

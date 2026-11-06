# 04 Slate & Teal

スレート（灰みの紺）の帯に明るいシーグリーンの文字を載せ、ティールをアクセントに使う。寒色でまとめた落ち着いた配色。

- 種色: ベース = スレート、アクセント = ティール、サブ = シーグリーン
- 正本: [theme.json](theme.json)（色の値はここだけで管理する。この README には hex を書かない）
- 見本スライド: 下の[プレビュー](#プレビュー)。色見本・コントラスト比・種色の判定: リポジトリの [README のテーマ一覧](../../README.md#テーマ一覧)、[dist/04/swatches.svg](../../dist/04/swatches.svg)

## プレビュー

<!-- BEGIN GENERATED: preview -->
<!-- この区間は scripts/build.py が生成する。手で編集しないこと。 -->

見本スライド 5 枚。点線の枠は、その部分に使っている role の名前。色は [theme.json](theme.json) の値そのまま（画像は [dist/04/preview/](../../dist/04/preview/)）。

**表紙** — `on-band`・`band`・`category`・`emphasis`・`accent`・`text`・`text-secondary`

![04 Slate & Teal: 表紙](../../dist/04/preview/1-title.svg)

**セクション扉** — `accent`・`section-label`・`emphasis`・`text-secondary`

![04 Slate & Teal: セクション扉](../../dist/04/preview/2-section.svg)

**本文** — `on-band`・`band`・`category`・`emphasis`・`rule`・`text`・`text-secondary`・`placeholder-bg`・`placeholder-text`・`placeholder-border`

![04 Slate & Teal: 本文](../../dist/04/preview/3-body.svg)

**グラフ** — `text`・`text-secondary`・`chart.series`

![04 Slate & Teal: グラフ](../../dist/04/preview/4-chart.svg)

**役割一覧** — 種色 3 つと全 role の色・palette 名・コントラスト比

![04 Slate & Teal: 役割一覧](../../dist/04/preview/5-roles.svg)

<!-- END GENERATED: preview -->

## 色の使い分け

| 場面 | 使う role | ルール |
|---|---|---|
| スライドの地 | `background` | |
| 本文 | `text` | |
| 参考文献・図キャプション | `text-secondary` | 補足情報だけに使う |
| ヘッダー帯・フッター帯 | `band` | 塗りだけに使う。帯の上の文字は `on-band` |
| 帯の上のタイトル・日付・会議名・ページ番号 | `on-band` | `band` の上でだけ使う。サブのシーグリーンは帯の上で約 3.0:1 と足りないため、同じ色相で明るくした色 |
| 帯の右上のカテゴリラベル | `category` | `band` の上でだけ使う（スレートを明るくした色） |
| 表紙タイトル・セクションタイトル・キーメッセージ・Takeaway | `emphasis` | 強調はこの色で行う |
| 表紙のアクセントライン・セクション扉の縦バー | `accent` | ティール。白地で約 4.6:1 あり、線・図形にも文字にも使える |
| セクション扉の「01 / SECTION」 | `section-label` | `accent` と同じティール |
| キーメッセージ下の区切り線 | `rule` | シーグリーン。装飾用（白地で約 3.1:1） |
| 図のプレースホルダー | `placeholder-bg` / `placeholder-border` / `placeholder-text` | 仮置き専用。実際の図に差し替える |

## グラフ

- 系列色は `chart.series` の順に使う（matplotlib なら `theme.mplstyle` の色サイクル）。**暫定案・要確認**。
- 1 = スレート、2 = ティール、3 = シーグリーン（種色）。4〜6 は見分けやすさで選んだ追加色（オレンジ・オリーブ・ワイン）。種色がすべて寒色なので、追加色は暖色寄りになる。
- **2 のティールと 3 のシーグリーンは 3 型色覚のシミュレーションで色差が小さい（ΔE00 約 10）。** 同じ図で並べるときは、線種・マーカーの形でも区別する。
- 軸・目盛りは `text-secondary`、ラベル・タイトルは `text`。

## フォント

欧文 Arial、和文 Meiryo UI。ない環境では欧文 Helvetica、和文 Hiragino Sans / Noto Sans JP の順に代替する。

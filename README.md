# design-themes

研究発表スライド、論文・ポスターの図（matplotlib）、LaTeX/Beamer、Web ページで共通に使うデザインテーマ（カラーパレット＋フォント）集。各プロジェクトは **テーマ番号**（例: `02`）を選んで使う。

- **正本は 1 テーマ 1 ファイル**: `themes/<番号>-<slug>/theme.json` だけを手で編集する。CSS・mplstyle・LaTeX などは `scripts/build.py` が `dist/<番号>/` に生成する。
- **番号は永久 ID**: 一度割り当てた番号は振り直さず、再利用もしない。廃止するテーマは削除せず `"status": "deprecated"` にする。
- **生成物もコミットする**: `dist/` はコミット済みなので、ビルドしなくても他のプロジェクトから使える。CI で `dist/` が `theme.json` と一致しているかを検証する。
- **依存は最小限**: Python 3.10 以上の標準ライブラリだけで動く（テストのみ pytest を使う）。

`theme.json` は `palette`（生の色。名前は色の見た目で付ける）と `roles`（意味づけ。`palette` の名前を参照する）に分かれている。スライドもグラフも Web も **`roles` を参照して色を決める**。`roles` のキーは全テーマで共通なので、テーマ番号を差し替えてもコードは壊れない。

## テーマ一覧

<!-- BEGIN GENERATED: themes -->
<!-- この区間は scripts/build.py が themes/*/theme.json から生成する。手で編集しないこと。 -->

| 番号 | 名前 | slug | 状態 | band / emphasis / accent |
|---|---|---|---|---|
| `01` | Brown & Orange | `brown-orange` | active | `#70372C` / `#70372C` / `#DC5F36` |
| `02` | Beige & Navy | `beige-navy` | active | `#DCD5C8` / `#1F1E63` / `#1F1E63` |

### 01 Brown & Orange

![01 Brown & Orange の色見本](dist/01/swatches.svg)

- slug: `brown-orange` / 状態: `active`
- 出典: I-Lab Research Palette（研究ミーティング用PPTXテンプレートの前半）
- フォント: 欧文 Arial（代替: Helvetica, sans-serif）、和文 Meiryo UI（代替: Hiragino Sans, Noto Sans JP, sans-serif）
- 使い方のルール: [themes/01-brown-orange/README.md](themes/01-brown-orange/README.md) ・ 正本: [themes/01-brown-orange/theme.json](themes/01-brown-orange/theme.json) ・ 生成物: [dist/01/](dist/01/)

| role | palette | hex | 使われ方 | 検査 | コントラスト |
|---|---|---|---|---|---|
| `background` | `white` | `#FFFFFF` | スライド背景 | 面 | — |
| `text` | `gray-900` | `#242424` | 本文 | 文字 4.5:1 | 15.52:1 vs `background` ✓ |
| `text-secondary` | `gray-600` | `#666666` | 参考文献、図キャプション | 文字 4.5:1 | 5.74:1 vs `background` ✓ |
| `band` | `brown-700` | `#70372C` | ヘッダー帯・フッター帯の塗り | 面 | — |
| `on-band` | `cream-100` | `#F7E3AF` | 帯の上のスライドタイトル、日付・会議名・ページ番号 | 文字 4.5:1 | 7.29:1 vs `band` ✓ |
| `category` | `taupe-300` | `#C4B2AB` | 帯の右上のカテゴリラベル（BACKGROUND など） | 文字 4.5:1 | 4.53:1 vs `band` ✓ |
| `emphasis` | `brown-700` | `#70372C` | 表紙タイトル、セクションタイトル、キーメッセージ、Takeaway | 文字 4.5:1 | 9.24:1 vs `background` ✓ |
| `accent` | `orange-400` | `#DC5F36` | 表紙のアクセントライン、セクション扉の縦バー | 線・図形 3:1 | 3.66:1 vs `background` ✓ 線・図形 / ⚠ 文字には不可 |
| `section-label` | `orange-400` | `#DC5F36` | セクション扉の「01 / SECTION」 | 文字 4.5:1 | **3.66:1** vs `background` ⚠ 基準未満 |
| `rule` | `cream-100` | `#F7E3AF` | キーメッセージ下の区切り線 | 装飾（対象外） | 1.26:1 vs `background` |
| `placeholder-bg` | `warm-gray-50` | `#F7F7F6` | 図プレースホルダーの塗り | 面 | — |
| `placeholder-border` | `warm-gray-100` | `#E2E1DD` | 図プレースホルダーの枠線 | 装飾（対象外） | 1.22:1 vs `placeholder-bg` |
| `placeholder-text` | `gray-500` | `#777777` | 図プレースホルダーの文字 | 文字 4.5:1 | **4.17:1** vs `placeholder-bg` ⚠ 基準未満 |

**グラフ系列色（`chart.series`）: 暫定案・要確認**

1. `brown-700` `#70372C` — 9.24:1 vs `background` ✓
2. `orange-400` `#DC5F36` — 3.66:1 vs `background` ✓
3. `gray-600` `#666666` — 5.74:1 vs `background` ✓
4. `taupe-300` `#C4B2AB` — **2.03:1** vs `background` ⚠ 基準未満

**コントラスト警告**（元資料の値は変更していない）

- ⚠ `accent`（orange-400 #DC5F36）on `background`（#FFFFFF）= 3.66:1。線・図形の基準 3:1 は満たすが、小さい文字には使えない（4.5:1 未満）
- ⚠ `section-label`（orange-400 #DC5F36）on `background`（#FFFFFF）= 3.66:1。小さい文字の基準 4.5:1 未満
- ⚠ `placeholder-text`（gray-500 #777777）on `placeholder-bg`（#F7F7F6）= 4.17:1。小さい文字の基準 4.5:1 未満
- ⚠ `chart.series[3]`（taupe-300 #C4B2AB）on `background`（#FFFFFF）= 2.03:1。線・図形の基準 3:1 未満（線・マーカーには不向き）

### 02 Beige & Navy

![02 Beige & Navy の色見本](dist/02/swatches.svg)

- slug: `beige-navy` / 状態: `active`
- 出典: I-Lab Research Palette（研究ミーティング用PPTXテンプレートの後半）
- フォント: 欧文 Arial（代替: Helvetica, sans-serif）、和文 Meiryo UI（代替: Hiragino Sans, Noto Sans JP, sans-serif）
- 使い方のルール: [themes/02-beige-navy/README.md](themes/02-beige-navy/README.md) ・ 正本: [themes/02-beige-navy/theme.json](themes/02-beige-navy/theme.json) ・ 生成物: [dist/02/](dist/02/)

| role | palette | hex | 使われ方 | 検査 | コントラスト |
|---|---|---|---|---|---|
| `background` | `white` | `#FFFFFF` | スライド背景 | 面 | — |
| `text` | `gray-900` | `#242424` | 本文 | 文字 4.5:1 | 15.52:1 vs `background` ✓ |
| `text-secondary` | `gray-600` | `#666666` | 参考文献、図キャプション | 文字 4.5:1 | 5.74:1 vs `background` ✓ |
| `band` | `beige-100` | `#DCD5C8` | ヘッダー帯・フッター帯の塗り | 面 | — |
| `on-band` | `navy-800` | `#1F1E63` | 帯の上のスライドタイトル、日付・会議名・ページ番号 | 文字 4.5:1 | 10.10:1 vs `band` ✓ |
| `category` | `warm-gray-500` | `#77736C` | 帯の右上のカテゴリラベル（BACKGROUND など） | 文字 4.5:1 | **3.23:1** vs `band` ⚠ 基準未満 |
| `emphasis` | `navy-800` | `#1F1E63` | 表紙タイトル、セクションタイトル、キーメッセージ、Takeaway | 文字 4.5:1 | 14.74:1 vs `background` ✓ |
| `accent` | `navy-800` | `#1F1E63` | 表紙のアクセントライン、セクション扉の縦バー | 線・図形 3:1 | 14.74:1 vs `background` ✓ |
| `section-label` | `navy-800` | `#1F1E63` | セクション扉の「01 / SECTION」 | 文字 4.5:1 | 14.74:1 vs `background` ✓ |
| `rule` | `beige-100` | `#DCD5C8` | キーメッセージ下の区切り線 | 装飾（対象外） | 1.45:1 vs `background` |
| `placeholder-bg` | `warm-gray-50` | `#F7F7F6` | 図プレースホルダーの塗り | 面 | — |
| `placeholder-border` | `warm-gray-100` | `#E2E1DD` | 図プレースホルダーの枠線 | 装飾（対象外） | 1.22:1 vs `placeholder-bg` |
| `placeholder-text` | `gray-500` | `#777777` | 図プレースホルダーの文字 | 文字 4.5:1 | **4.17:1** vs `placeholder-bg` ⚠ 基準未満 |

**グラフ系列色（`chart.series`）: 暫定案・要確認**

1. `navy-800` `#1F1E63` — 14.74:1 vs `background` ✓
2. `warm-gray-500` `#77736C` — 4.71:1 vs `background` ✓
3. `beige-100` `#DCD5C8` — **1.45:1** vs `background` ⚠ 基準未満

**コントラスト警告**（元資料の値は変更していない）

- ⚠ `category`（warm-gray-500 #77736C）on `band`（#DCD5C8）= 3.23:1。小さい文字の基準 4.5:1 未満
- ⚠ `placeholder-text`（gray-500 #777777）on `placeholder-bg`（#F7F7F6）= 4.17:1。小さい文字の基準 4.5:1 未満
- ⚠ `chart.series[2]`（beige-100 #DCD5C8）on `background`（#FFFFFF）= 1.45:1。線・図形の基準 3:1 未満（線・マーカーには不向き）

<!-- END GENERATED: themes -->

## 使い方

### プロジェクトへの導入（apply.py）

```sh
python scripts/apply.py 02 /path/to/project
```

1. `dist/02/` の中身を `/path/to/project/.design/` にコピーする（以前に apply.py で入れた `.design/` は置き換える）。
2. `/path/to/project/design-theme.toml` を作り、テーマ番号・このリポジトリの URL・コミットハッシュ（とタグ）を記録する。
3. `templates/project-agents-snippet.md` の内容を表示する。プロジェクトの `AGENTS.md` に貼る。

テーマを変えるとき、新しい版を取り込むときも同じコマンドを再実行する。特定の版に固定したい場合は、このリポジトリでそのタグ（またはコミット）をチェックアウトしてから実行する。記録される版は `design-theme.toml` の `commit` / `tag` で確認できる。

### 生成物（`.design/` = `dist/<番号>/` の中身）

| ファイル | 内容 |
|---|---|
| `tokens.css` | `:root` の CSS 変数。roles は `--color-<role>`、系列色は `--chart-series-<n>`、palette は `--palette-<name>`、フォントは `--font-latin` / `--font-east-asian` / `--font-sans` |
| `tokens.json` | roles・palette・系列色を hex に解決した JSON（`roles` と `palette` はそれぞれ名前 → hex のフラットな表） |
| `theme.mplstyle` | matplotlib 用。色サイクルは `chart.series`、文字色は `text`、軸・目盛りは `text-secondary`、フォントは欧文 → 和文の順 |
| `theme_colors.py` | `COLORS`（role → hex）、`CHART_SERIES`、`PALETTE`、`FONT_FAMILY` を持つ Python モジュール |
| `theme-colors.sty` | LaTeX `xcolor` 用。`theme-<role>`、`theme-series-<n>`、`palette-<name>` を定義 |
| `claude-design-system/tokens.json` | Claude のデザインシステム取り込み用（色トークン = roles と系列色、`type.families.sans` = フォント） |
| `swatches.svg` | 役割名と hex を並べた色見本 |

### 使用例

CSS（Web ページ）:

```css
@import url("./.design/tokens.css"); /* 公開ディレクトリに置けない場合はコピーして読む */

body { background: var(--color-background); color: var(--color-text); font-family: var(--font-sans); }
.header { background: var(--color-band); color: var(--color-on-band); }
.key-message { color: var(--color-emphasis); border-bottom: 2px solid var(--color-rule); }
```

matplotlib（論文・ポスターの図）:

```python
import sys
import matplotlib.pyplot as plt

plt.style.use(".design/theme.mplstyle")  # 色サイクル・文字色・軸色・フォント

sys.path.insert(0, ".design")
from theme_colors import COLORS  # 個別の色は role 名で参照する

fig, ax = plt.subplots()
ax.plot([0, 1, 2], [0, 1, 4], label="系列 1")
ax.axhline(1, color=COLORS["accent"], linewidth=1)
```

LaTeX / Beamer:

```latex
\usepackage{theme-colors} % .design/ を TEXINPUTS に追加しておく
\setbeamercolor{normal text}{fg=theme-text, bg=theme-background}
\setbeamercolor{frametitle}{fg=theme-on-band, bg=theme-band}
\setbeamercolor{structure}{fg=theme-emphasis}
\setbeamercolor{alerted text}{fg=theme-emphasis}
```

`TEXINPUTS` は `TEXINPUTS=.design//: latexmk main.tex` のように指定するか、`.latexmkrc` に `ensure_path('TEXINPUTS', './.design//');` と書く。フォントは fontspec 系なら `\setsansfont{\ThemeLatinFont}`、和文は `\ThemeEastAsianFont` を使う。

### 代替手順: git submodule

apply.py を使わず、このリポジトリをサブモジュールとして取り込むこともできる。版はサブモジュールのコミットとして親リポジトリに記録される。

```sh
git submodule add https://github.com/masa10-f/DesignTheme.git vendor/design-themes
git -C vendor/design-themes checkout <タグまたはコミット>
git add .gitmodules vendor/design-themes
```

生成物は `vendor/design-themes/dist/02/theme.mplstyle` のように直接参照する（使っている番号はプロジェクトの AGENTS.md に書いておく）。`.design/` の形にそろえたい場合は、サブモジュール内の apply.py を使ってもよい: `python vendor/design-themes/scripts/apply.py 02 .`

## テーマの編集・追加

作業ルールは [AGENTS.md](AGENTS.md) にまとめてある。要点:

- 編集してよいのは `themes/*/theme.json` と各 README だけ。`dist/` と、この README の「テーマ一覧」は `python scripts/build.py` で再生成する。
- 変更後は `python scripts/check.py && python scripts/build.py` を実行し、差分をコミットする。
- 新しいテーマは次の空き番号で `themes/<番号>-<slug>/` を作る（上のテーマ一覧の最大番号 + 1）。既存の番号は変えない。
- 色の値は推測で作らない。元資料（`sources/` の PPTX など）から取る。PPTX との照合は `python scripts/check.py --pptx sources/<ファイル>.pptx`。
- テスト: `python -m pytest`

### コントラスト検査

`check.py` は WCAG 2.x のコントラスト比を計算する。基準は小さい文字 4.5:1、大きい文字（24px / 18pt 以上）と線・図形 3:1。どの role をどの背景に対して、どの基準で検査するかは [schema/theme.schema.json](schema/theme.schema.json) の各 role の `x-contrast` に書いてある。基準を満たさなくても元資料の値は変えず、`theme.json` の `notes` と、この README のテーマ一覧（自動生成）に警告として載せる。`rule` と `placeholder-border` は装飾として扱い、基準の対象外としている。

## TODO（元資料に定義がない・未確認の項目）

- [ ] `chart.series`（グラフの系列色の順番）は元資料に定義がない。両テーマとも役割色から作った **暫定案・要確認**（`"status": "provisional"`）。確認できたら `"confirmed"` にする。
- [ ] `sources/` に PPTX テンプレートが置かれていないため、PPTX との値の照合は未実施。置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` で照合する。
- [ ] 等幅フォント（コード表示用）は元資料に定義がない。
- [ ] ハイパーリンク色（PPTX の hlink / folHlink = palette の `teal-500` / `plum-500`）は palette にあるが、role は定義していない。Web で使うなら `link` などの role を全テーマ共通で追加するか検討する。
- [ ] グラフのグリッド線などの色は元資料に定義がないため、`theme.mplstyle` では設定していない（matplotlib の既定値のまま）。

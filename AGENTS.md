# AGENTS.md — design-themes で作業するエージェント向けのルール

このリポジトリは、デザインテーマ（カラーパレット＋フォント）をテーマ番号つきでホストする。各プロジェクトは番号（例: `02`）を選んで `scripts/apply.py` で導入する。

## ルール

1. **編集してよいのは `themes/*/theme.json` と各 README だけ。** `dist/` と `README.md` の「テーマ一覧」区間（`<!-- BEGIN GENERATED: themes -->` 〜 `<!-- END GENERATED: themes -->`）は `python scripts/build.py` で再生成する。手で直さない。
2. **変更後は必ず `python scripts/check.py && python scripts/build.py` を実行し、`dist/` と `README.md` を含む差分をコミットする。** CI は `dist/` が `theme.json` と一致しているかを検証する。
3. **新しいテーマは次の空き番号で追加し、既存の番号は変えない。** 番号は永久 ID。振り直し・再利用はしない。廃止するテーマは削除せず `"status": "deprecated"` にする（check.py は欠番をエラーにする）。
4. **色の値を推測で作らない。** 値は元資料（`sources/` の PPTX など）から取る。足りない値があれば作らずに、README の TODO に書いて報告する。
5. 元資料の値がコントラスト基準を満たさなくても、値は変えない。`notes` に、その role 名（または palette 名）をバッククォートで囲んで警告を書く（check.py はその記載を確認する）。

## よく使うコマンド

```sh
python scripts/check.py                                  # 検査（エラーなら終了コード 1。警告は 0）
python scripts/build.py                                  # dist/ と README のテーマ一覧を生成
python scripts/build.py --check                          # 生成結果が最新か確かめる（書き込まない）
python scripts/check.py --pptx sources/<ファイル>.pptx    # PPTX の配色と照合（報告のみ）
python -m pytest                                         # テスト
```

Python 3.10 以上、標準ライブラリのみ（pytest はテスト用）。新しい依存を足さない。

## theme.json の要点

- 形式は [schema/theme.schema.json](schema/theme.schema.json)。`palette`（生の色。見た目で命名: `brown-700` など）と `roles`（意味づけ。palette 名を参照）を分ける。
- `roles` のキー集合は全テーマ共通で、スキーマで固定している。role を追加・削除するときは、スキーマ（`x-contrast` を含む）と全テーマを同時に更新する。
- `pptx_slot` は PPTX テーマ配色（clrScheme）のスロット名。スロット外で直接指定されている色には付けない。
- `chart.series` は palette 名の並び。元資料に定義がない場合は `"status": "provisional"` にし、README に「暫定案・要確認」と書く。
- hex は `#RRGGBB` の大文字。

## 新しいテーマを追加する手順

1. 次の空き番号 `NN` を決め、`themes/NN-<slug>/theme.json` を既存テーマをひな形にして作る（`id` と `slug` はディレクトリ名と一致させる）。
2. `themes/NN-<slug>/README.md` に、どの役割にどの色を使うかのルールを書く。
3. `python scripts/check.py && python scripts/build.py` を実行し、警告があれば `notes` に書く。
4. `python -m pytest` を通してからコミットする。

## 元資料との照合

`sources/` に PPTX テンプレートを置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` を実行する。テーマ配色（`ppt/theme/theme*.xml`）と `pptx_slot` の値、スライドマスター・レイアウト（`ppt/slideMasters/*.xml`、`ppt/slideLayouts/*.xml`）で使われている配色スロットと直接指定色を表示する。食い違いがあっても theme.json は修正せず、報告する。

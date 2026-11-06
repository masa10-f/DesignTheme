# AGENTS.md — design-themes で作業するエージェント向けのルール

このリポジトリは、デザインテーマ（カラーパレット＋フォント）をテーマ番号つきでホストする。各プロジェクトは番号（例: `02`）を選んで `scripts/apply.py` で導入する。

## ルール

1. **編集してよいのは `themes/*/theme.json` と各 README だけ。** `theme.json` は `scripts/derive.py` で作り、必要なら手で直す。`dist/`、`README.md` の「テーマ一覧」区間（`<!-- BEGIN GENERATED: themes -->` 〜 `<!-- END GENERATED: themes -->`）、各テーマ README の「プレビュー」区間（`<!-- BEGIN GENERATED: preview -->` 〜 `<!-- END GENERATED: preview -->`）は `python scripts/build.py` で再生成する。手で直さない。
2. **変更後は必ず `python scripts/check.py && python scripts/build.py` を実行し、`dist/` と `README.md` を含む差分をコミットする。** CI は `dist/` が `theme.json` と一致しているかを検証する。
3. **新しいテーマは次の空き番号で追加し、既存の番号は変えない。** 番号は永久 ID。振り直し・再利用はしない。廃止するテーマは削除せず `"status": "deprecated"` にする（check.py は欠番をエラーにする）。
4. **色の値を推測で作らない。** 人が決めるのは各テーマの種色 3 つ（`seeds`: ベース・アクセント・サブ）だけで、値は元資料（`sources/` の PPTX など）かユーザーの指定から取る。それ以外の色は `scripts/derive.py` が決まった手順で導出し、palette の `derived` に由来を残す（check.py が再計算して一致を確かめる）。導出した色を手で変えるときは `derived` を消し、理由を `note` に書く。手順で決まらない値が必要になったら、作らずに README の TODO に書いて報告する。
5. 種色がコントラスト基準を満たさなくても、種色の値は変えない。文字に使う role には derive.py が同じ色相で明度を変えた色を割り当てる。それでも残る警告は `notes` に、その role 名（または palette 名）をバッククォートで囲んで書く（derive.py が自動で書き、check.py がその記載を確認する）。
6. **このリポジトリは公開されている。** 所属先のテンプレート名・資料名・スロット番号など、外部の人に意味のない内部情報は theme.json・README・テスト・コミットメッセージに書かない。出典は「ユーザー指定」のように一般的に書く。

## よく使うコマンド

```sh
python scripts/derive.py 05 <slug> --name "<表示名>" \
    --base <色名>=#RRGGBB --accent <色名>=#RRGGBB --sub <色名>=#RRGGBB   # 種色から theme.json を作る
python scripts/derive.py 03 --force                      # 既存テーマを、記録済みの種色から作り直す
python scripts/check.py                                  # 検査（エラーなら終了コード 1。警告は 0）
python scripts/build.py                                  # dist/ と README のテーマ一覧を生成
python scripts/build.py --check                          # 生成結果が最新か確かめる（書き込まない）
python scripts/check.py --pptx sources/<ファイル>.pptx    # PPTX の配色と照合（報告のみ）
python -m pytest                                         # テスト
```

Python 3.10 以上、標準ライブラリのみ（pytest はテスト用）。新しい依存を足さない。

## theme.json の要点

- 形式は [schema/theme.schema.json](schema/theme.schema.json)。`seeds`（種色 3 つ。palette 名を参照）、`palette`（生の色）、`roles`（意味づけ。palette 名を参照）を分ける。
- palette 名は `<色名>-<明度>`（明度 = CIE L* を四捨五入した 0〜100。例: `brown-30`）。数字が明度なので、名前の数字の差 50 でほぼ 4.5:1、差 40 で 3:1 以上のコントラストになる。
- `derived` は導出した色の由来（`from` = 種色の palette 名、または `hue` = OKLCH の色相、と `chroma`・`tone`）。手順は README の「配色の作り方」と `scripts/derive.py` の冒頭にある。
- `roles` のキー集合は全テーマ共通で、スキーマで固定している。role を追加・削除するときは、スキーマ（`x-contrast` を含む）と全テーマを同時に更新する。
- `pptx_slot` は PPTX テーマ配色（clrScheme）のスロット名。PPTX から取った種色（と白）にだけ付ける。derive.py で作り直しても、同じ hex の色に引き継がれる。
- `chart.series` は palette 名の並び（derive.py は 6 色を作る）。確認されるまでは `"status": "provisional"` にし、README に「暫定案・要確認」と書く。系列色どうしの色差（CIEDE2000、色覚シミュレーションを含む）が目安 10 未満だと check.py が警告する。
- hex は `#RRGGBB` の大文字。

## 新しいテーマを追加する手順

1. 次の空き番号 `NN` を決め、種色 3 つを用意する（色を推測で決めない。ユーザーに確認する）。
2. `python scripts/derive.py NN <slug> --name "<表示名>" --base … --accent … --sub …` で `themes/NN-<slug>/theme.json` を作る。表示される「種色」の判定（白地・帯の上で文字や線に使えるか）と警告をユーザーに報告する。
3. derive.py が作った `themes/NN-<slug>/README.md` のひな形の TODO を埋め、どの役割にどの色を使うかのルールを書く（hex は書かない。プレビュー区間は残す）。
4. `python scripts/check.py && python scripts/build.py` を実行する。
5. `python -m pytest` を通してからコミットする。

## 元資料との照合

`sources/` に PPTX テンプレートを置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` を実行する。テーマ配色（`ppt/theme/theme*.xml`）と `pptx_slot` の値、スライドマスター・レイアウト（`ppt/slideMasters/*.xml`、`ppt/slideLayouts/*.xml`）で使われている配色スロットと直接指定色を表示する。食い違いがあっても theme.json は修正せず、報告する。

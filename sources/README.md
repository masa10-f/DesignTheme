# sources/

テーマの元資料（PPTX テンプレートなど）を置く場所。値の照合に使う。

- 現在、PPTX は置かれていない。テーマ 01・02 の値は、研究ミーティング用 PPTX テンプレート（スライドマスター 2 つ。前半 = 01、後半 = 02。テーマ配色 "I-Lab Research Palette" は共通）から抽出済みのものを使っている。
- PPTX を置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` で theme.json と照合する。食い違いがあっても theme.json は修正せず、報告する。
- 元資料を公開リポジトリにコミットしてよいかは、資料の扱いに従って判断する。

# sources/

テーマの元資料（PPTX テンプレートなど）を置く場所。値の照合に使う。

- 現在、PPTX は置かれていない。テーマ 01・02 の種色は、研究ミーティング用 PPTX テンプレートのテーマ配色 "I-Lab Research Palette" の accent1〜3（01）と accent4〜6（02）。それ以外の色は scripts/derive.py で導出したもので、PPTX のスライドマスターが直接指定している色（本文 `#242424` など）とは一致しない（照合すると「どのテーマの palette にもありません」と報告される）。
- PPTX を置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` で theme.json と照合する。食い違いがあっても theme.json は修正せず、報告する。
- 元資料を公開リポジトリにコミットしてよいかは、資料の扱いに従って判断する。

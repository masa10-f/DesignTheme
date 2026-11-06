# sources/

テーマの元資料（配色を取った PPTX など）を置く場所。値の照合に使う。

- 現在、元資料は置かれていない。
- PPTX を置いたら `python scripts/check.py --pptx sources/<ファイル>.pptx` で theme.json と照合できる（照合するのは palette に `pptx_slot` を付けた色だけ）。食い違いがあっても theme.json は修正せず、報告する。
- **このリポジトリは公開されている。** 公開してよい資料だけを置き、所属先の資料名・ファイル名など、外部の人に意味のない内部情報は theme.json や README にも書かない。

## デザインテーマ（色・フォント）

このプロジェクトの色とフォントは design-themes リポジトリ（https://github.com/masa10-f/DesignTheme）のテーマを使っている。使っているテーマ番号と版は `design-theme.toml` に記録されている。

- 色とフォントは `.design/` のファイルだけを使う。
  - Web / CSS: `.design/tokens.css`（`var(--color-<role>)`、`var(--font-sans)`）
  - matplotlib: `plt.style.use(".design/theme.mplstyle")`
  - Python: `.design/theme_colors.py` の `COLORS["<role>"]`、`CHART_SERIES`
  - LaTeX / Beamer: `.design/theme-colors.sty` の `theme-<role>`
  - その他: `.design/tokens.json`
- hex（`#70372C` など）を直接書かない。role 名（`background`, `text`, `text-secondary`, `band`, `on-band`, `category`, `emphasis`, `accent`, `section-label`, `rule`, `placeholder-bg`, `placeholder-border`, `placeholder-text`）で参照する。palette 名（`brown-700` など）もテーマごとに違うので使わない。
- グラフの系列色は `.design/theme.mplstyle` の色サイクル（または `CHART_SERIES`）を使う。
- `accent` は線・図形用なので、小さい文字には使わない。テーマごとのコントラスト警告は design-themes の README の「テーマ一覧」を見る。
- テーマを変えるときは `python <design-themes のパス>/scripts/apply.py <番号> <このプロジェクトのパス>` を再実行する。
- `.design/` と `design-theme.toml` は手で編集しない。色を変えたい場合は design-themes 側の `theme.json` を変更してから apply.py を再実行する。

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import build
import themelib as tl
from conftest import REPO, edit_theme, snapshot

THEMES = tl.load_themes(REPO)
FILES = [
    "tokens.css",
    "tokens.json",
    "theme.mplstyle",
    "theme_colors.py",
    "theme-colors.sty",
    "claude-design-system/tokens.json",
    "swatches.svg",
    *[f"preview/{name}.svg" for name, _ in build.PREVIEWS],
]


def test_committed_dist_is_up_to_date():
    assert build.main(["--check"]) == 0


def test_build_is_deterministic(repo_copy: Path):
    shutil.rmtree(repo_copy / "dist")
    assert build.main(["--root", str(repo_copy)]) == 0
    first = snapshot(repo_copy)
    assert build.main(["--root", str(repo_copy)]) == 0
    assert snapshot(repo_copy) == first
    assert first == snapshot(REPO)
    assert build.main(["--root", str(repo_copy), "--check"]) == 0


def test_stale_files_are_detected_and_removed(repo_copy: Path):
    stale = repo_copy / "dist/01/old.css"
    stale.write_text("x", encoding="utf-8")
    assert build.main(["--root", str(repo_copy), "--check"]) == 1
    assert build.main(["--root", str(repo_copy)]) == 0
    assert not stale.exists()


def test_python_cache_in_dist_is_ignored(repo_copy: Path):
    cache = repo_copy / "dist/01/__pycache__/theme_colors.cpython-310.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"x")
    assert build.main(["--root", str(repo_copy), "--check"]) == 0


def test_build_refuses_invalid_themes(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["roles"]["band"].update(color="nope"))
    before = snapshot(repo_copy)
    assert build.main(["--root", str(repo_copy)]) == 1
    assert snapshot(repo_copy) == before


def test_change_in_theme_json_propagates(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["roles"]["emphasis"].update(color="neutral-15"))
    assert build.main(["--root", str(repo_copy), "--check"]) == 1
    assert build.main(["--root", str(repo_copy)]) == 0
    tokens = json.loads((repo_copy / "dist/02/tokens.json").read_text(encoding="utf-8"))
    assert tokens["roles"]["emphasis"] == "#272623"
    assert "--color-emphasis: #272623;" in (repo_copy / "dist/02/tokens.css").read_text(encoding="utf-8")


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_all_outputs_exist(theme: tl.Theme):
    for name in FILES:
        assert (REPO / "dist" / theme.id / name).is_file(), name


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_tokens_json_resolves_roles_and_palette(theme: tl.Theme):
    tokens = json.loads((REPO / "dist" / theme.id / "tokens.json").read_text(encoding="utf-8"))
    assert tokens["id"] == theme.id
    assert tokens["roles"] == {role: theme.data["palette"][spec["color"]]["hex"] for role, spec in theme.roles.items()}
    assert tokens["palette"] == {name: e["hex"] for name, e in theme.data["palette"].items()}
    assert tokens["chart"] == {"status": "provisional", "series": theme.series_hex()}
    assert all(isinstance(v, str) for v in [*tokens["roles"].values(), *tokens["palette"].values()])


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_css_defines_roles_palette_and_fonts(theme: tl.Theme):
    css = (REPO / "dist" / theme.id / "tokens.css").read_text(encoding="utf-8")
    for role, hex_ in theme.role_hex().items():
        assert f"--color-{role}: {hex_};" in css
    for name, hex_ in theme.palette_hex().items():
        assert f"--palette-{name}: {hex_};" in css
    assert '--font-sans: Arial, Helvetica, "Meiryo UI", "Hiragino Sans", "Noto Sans JP", sans-serif;' in css


def test_python_modules_share_role_keys():
    keys = set()
    for theme in THEMES:
        spec = importlib.util.spec_from_file_location(f"theme_colors_{theme.id}", REPO / "dist" / theme.id / "theme_colors.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.THEME_ID == theme.id
        assert module.COLORS == theme.role_hex()
        assert module.CHART_SERIES == theme.series_hex()
        assert module.FONT_FAMILY[0] == "Arial"
        keys.add(tuple(module.COLORS))
    assert len(keys) == 1  # テーマを差し替えてもキーは同じ


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_sty_defines_xcolor_colors(theme: tl.Theme):
    sty = (REPO / "dist" / theme.id / "theme-colors.sty").read_text(encoding="utf-8")
    assert "\\ProvidesPackage{theme-colors}" in sty and "\\RequirePackage{xcolor}" in sty
    for role, hex_ in theme.role_hex().items():
        assert f"\\definecolor{{theme-{role}}}{{HTML}}{{{hex_[1:]}}}" in sty
    assert sty.count("{") == sty.count("}")
    # 版情報は日付で始める（そうしないと Beamer などの版比較で \ifnum エラーになる）
    assert re.search(r"\\ProvidesPackage\{theme-colors\}\[\d{4}/\d{2}/\d{2} ", sty)


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_sty_compiles_with_beamer(theme: tl.Theme, tmp_path: Path):
    if not shutil.which("pdflatex") or not shutil.which("kpsewhich"):
        pytest.skip("pdflatex がない")
    if subprocess.run(["kpsewhich", "beamer.cls"], capture_output=True, text=True).returncode != 0:
        pytest.skip("beamer がない")
    (tmp_path / "main.tex").write_text(
        "\\documentclass{beamer}\n\\usepackage{theme-colors}\n"
        "\\setbeamercolor{frametitle}{fg=theme-on-band, bg=theme-band}\n"
        "\\begin{document}\\begin{frame}{T}\\textcolor{theme-emphasis}{x}\\textcolor{theme-series-1}{y}"
        "\\end{frame}\\end{document}\n",
        encoding="utf-8",
    )
    env = {**os.environ, "TEXINPUTS": f"{REPO / 'dist' / theme.id}//{os.pathsep}"}
    r = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, r.stdout[-2000:]


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_claude_design_system_tokens(theme: tl.Theme):
    doc = json.loads((REPO / "dist" / theme.id / "claude-design-system/tokens.json").read_text(encoding="utf-8"))
    assert doc["name"] == f"{theme.id} {theme.name}"
    assert doc["version"] == 1
    assert doc["color"]["themes"] == [{"id": "light", "name": "Light"}]
    tokens = doc["color"]["tokens"]
    assert all(set(t) == {"name", "value", "usage"} for t in tokens)
    assert {t["name"]: t["value"] for t in tokens if not t["name"].startswith("chart-")} == theme.role_hex()
    assert doc["type"] == {"fonts": [], "families": {"sans": 'Arial, "Meiryo UI", sans-serif'}, "groups": []}
    names = [t["name"] for t in tokens] + list(doc["type"]["families"])
    assert all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", n) for n in names)
    assert len(names) == len(set(names))


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_swatches_svg(theme: tl.Theme):
    path = REPO / "dist" / theme.id / "swatches.svg"
    root = ET.parse(path).getroot()
    assert root.tag.endswith("svg")
    text = path.read_text(encoding="utf-8")
    for role, hex_ in theme.role_hex().items():
        assert f">{role}<" in text and hex_ in text


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_mplstyle_loads_in_matplotlib(theme: tl.Theme):
    matplotlib = pytest.importorskip("matplotlib")
    import warnings

    from matplotlib import rc_params_from_file

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # 未知のキーなどがあれば失敗させる
        rc = rc_params_from_file(str(REPO / "dist" / theme.id / "theme.mplstyle"), use_default_template=False)
    colors = rc["axes.prop_cycle"].by_key()["color"]
    assert ["#" + c.upper().lstrip("#") for c in colors] == theme.series_hex()
    assert rc["text.color"].upper().lstrip("#") == theme.role_hex()["text"][1:]
    assert rc["axes.edgecolor"].upper().lstrip("#") == theme.role_hex()["text-secondary"][1:]
    assert rc["font.family"][:2] == ["Arial", "Helvetica"]
    assert matplotlib is not None


def test_readme_lists_themes_with_swatches_roles_and_warnings():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index(build.README_BEGIN) : readme.index(build.README_END)]
    for theme in THEMES:
        assert f"### {theme.id} {theme.name}" in section
        assert f"dist/{theme.id}/swatches.svg" in section
        for role in theme.roles:
            assert f"| `{role}` |" in section
        for key in tl.SEED_KEYS:
            assert f"| {tl.SEED_JA[key]} | `{theme.seeds[key]}` |" in section
    assert "暫定案・要確認" in section
    assert "`accent`（orange-56 #DC5F36）on `background`（#FFFFFF）= 3.66:1" in section
    assert "`accent`（cool-gray-61 #92929D）on `background`（#FFFFFF）= 3.07:1" in section
    assert "| `section-label` | `orange-49` | `#C84C22` | `orange-56` の色相・明度 49 |" in section
    assert "系列色どうしの最小の色差" in section
    # 種色の基準（すべて満たす）
    assert "| アクセント | `cool-gray-61` | `#92929D` | 60.9 | ✓ 白地で 3:1 以上 |" in section
    assert "| サブ | `sea-green-73` | `#7CC1AB` | 73.1 | ✓ 帯の上で 4.5:1 以上 |" in section


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_preview_slides_label_every_role(theme: tl.Theme):
    labelled = set()
    for name, _ in build.PREVIEWS:
        path = REPO / "dist" / theme.id / "preview" / f"{name}.svg"
        root = ET.parse(path).getroot()
        assert root.get("viewBox") == "0 0 1920 1080"
        text = path.read_text(encoding="utf-8")
        labelled |= {r for r in theme.roles if f">{r}</text>" in text}
        # 描画する文字は英語だけ（和文フォントのない環境でも崩れない）。<title> は表示されない
        drawn = re.sub(r"<title>.*?</title>", "", text)
        assert not re.search(r"[\u3000-\u9fff\uff00-\uffef]", drawn), name
    assert labelled == set(theme.roles)
    roles_slide = (REPO / "dist" / theme.id / "preview/5-roles.svg").read_text(encoding="utf-8")
    for role, hex_ in theme.role_hex().items():
        assert f'fill="{hex_}"' in roles_slide
    for hex_ in theme.series_hex():
        assert f'stroke="{hex_}"' in (REPO / "dist" / theme.id / "preview/4-chart.svg").read_text(encoding="utf-8")


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_theme_readme_shows_previews(theme: tl.Theme):
    readme = (theme.dir / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index(build.PREVIEW_BEGIN) : readme.index(build.PREVIEW_END)]
    for name, _ in build.PREVIEWS:
        assert f"](../../dist/{theme.id}/preview/{name}.svg)" in section
    main = (REPO / "README.md").read_text(encoding="utf-8")
    assert f'<img src="dist/{theme.id}/preview/3-body.svg"' in main


def test_build_requires_preview_markers_in_theme_readme(repo_copy: Path, capsys):
    readme = repo_copy / "themes/03-navy-red/README.md"
    readme.write_text("# 03\n", encoding="utf-8")
    assert build.main(["--root", str(repo_copy)]) == 1
    assert "themes/03-navy-red/README.md" in capsys.readouterr().err
    readme.unlink()
    assert build.main(["--root", str(repo_copy)]) == 1

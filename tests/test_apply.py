from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import apply
import themelib as tl
from conftest import REPO


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in tl.list_files(root)}


def read_toml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        return {m.group(1): m.group(2) for m in re.finditer(r'^(\w+) = "([^"]*)"', text, re.M)}
    return tomllib.loads(text)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "project"
    p.mkdir()
    return p


def test_apply_copies_dist_and_records_version(project: Path, capsys):
    assert apply.main(["02", str(project)]) == 0
    assert tree(project / ".design") == tree(REPO / "dist/02")
    toml = read_toml(project / "design-theme.toml")
    assert toml["theme"] == "02"
    assert toml["slug"] == "beige-navy"
    assert toml["repository"].startswith("https://") or toml["repository"] == "unknown"
    assert toml["commit"]
    out = capsys.readouterr().out
    assert "AGENTS.md に貼って" in out
    assert (REPO / "templates/project-agents-snippet.md").read_text(encoding="utf-8").splitlines()[0] in out


def test_python_cache_is_not_copied(repo_copy: Path, project: Path):
    cache = repo_copy / "dist/01/__pycache__/theme_colors.cpython-310.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"x")
    result = apply.apply("01", project, root=repo_copy)
    assert not (project / ".design/__pycache__").exists()
    assert not any("一致していません" in w for w in result["warnings"])


def test_theme_number_is_normalized(project: Path):
    assert apply.main(["2", str(project)]) == 0
    assert json.loads((project / ".design/tokens.json").read_text(encoding="utf-8"))["id"] == "02"


def test_reapply_switches_theme_and_removes_old_files(project: Path):
    assert apply.main(["01", str(project)]) == 0
    (project / ".design/leftover.txt").write_text("old", encoding="utf-8")
    assert apply.main(["02", str(project)]) == 0
    assert tree(project / ".design") == tree(REPO / "dist/02")
    assert read_toml(project / "design-theme.toml")["theme"] == "02"


def test_refuses_unmanaged_design_dir_unless_forced(project: Path):
    mine = project / ".design/my-notes.md"
    mine.parent.mkdir()
    mine.write_text("keep me", encoding="utf-8")
    assert apply.main(["01", str(project)]) == 1
    assert mine.read_text(encoding="utf-8") == "keep me"
    assert not (project / "design-theme.toml").exists()
    assert apply.main(["01", str(project), "--force"]) == 0
    assert not mine.exists()


def test_unknown_theme_and_missing_project(project: Path, tmp_path: Path, capsys):
    assert apply.main(["99", str(project)]) == 1
    assert "使える番号: 01 (brown-orange), 02 (beige-navy)" in capsys.readouterr().err
    assert apply.main(["01", str(tmp_path / "nope")]) == 1


def test_outside_git_records_unknown_commit(repo_copy: Path, project: Path):
    result = apply.apply("01", project, root=repo_copy)
    toml = read_toml(project / "design-theme.toml")
    assert toml["commit"] == "unknown"
    assert any("コミットを特定できません" in w for w in result["warnings"])


def test_warns_when_dist_is_stale(repo_copy: Path, project: Path):
    css = repo_copy / "dist/01/tokens.css"
    css.write_text(css.read_text(encoding="utf-8") + "/* edited */\n", encoding="utf-8")
    result = apply.apply("01", project, root=repo_copy)
    assert any("dist/01/ が theme.json と一致していません" in w for w in result["warnings"])


@pytest.mark.parametrize(
    "remote, expected",
    [
        ("git@github.com:masa10-f/DesignTheme.git", "https://github.com/masa10-f/DesignTheme"),
        ("https://github.com/masa10-f/DesignTheme.git", "https://github.com/masa10-f/DesignTheme"),
        ("https://user:token@github.com/masa10-f/DesignTheme.git", "https://github.com/masa10-f/DesignTheme"),
        (None, "unknown"),
    ],
)
def test_repository_url_is_normalized(monkeypatch, remote, expected):
    monkeypatch.setattr(apply, "_git", lambda root, *args: remote)
    assert apply.repository_url(REPO) == expected

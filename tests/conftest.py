from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
# dist/*/theme_colors.py を import するテストで、dist/ に __pycache__ を作らない
sys.dont_write_bytecode = True


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """テーマ・スキーマ・生成物・README をコピーした作業用のリポジトリ（git 管理外）。"""
    dst = tmp_path / "repo"
    for name in ("themes", "schema", "templates", "dist"):
        shutil.copytree(REPO / name, dst / name)
    shutil.copy2(REPO / "README.md", dst / "README.md")
    return dst


def edit_theme(root: Path, dirname: str, change: Callable[[dict], None]) -> Path:
    path = root / "themes" / dirname / "theme.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def snapshot(root: Path) -> dict:
    """root 以下の dist/、README.md、各テーマの README.md の内容（build.py が書くもの）。"""
    import themelib

    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in themelib.list_files(root / "dist")}
    files["README.md"] = (root / "README.md").read_bytes()
    for readme in sorted((root / "themes").glob("*/README.md")):
        files[readme.relative_to(root).as_posix()] = readme.read_bytes()
    return files

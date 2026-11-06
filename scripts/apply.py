#!/usr/bin/env python3
"""指定したテーマをプロジェクトに導入する。

使い方:
  python scripts/apply.py 02 /path/to/project

1. dist/02/ の中身を <project>/.design/ にコピーする（以前に apply.py で入れた .design/ は置き換える）
2. <project>/design-theme.toml に、テーマ番号・このリポジトリの URL・コミット（とタグ）を記録する
3. templates/project-agents-snippet.md を表示する（プロジェクトの AGENTS.md に貼る）
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import themelib as tl  # noqa: E402

DESIGN_DIRNAME = ".design"
TOML_NAME = "design-theme.toml"
SNIPPET_RELPATH = Path("templates") / "project-agents-snippet.md"
MANAGED_MARKER = "tokens.json"  # .design/ が apply.py で作られたものかの目印


class ApplyError(Exception):
    pass


def _git(root: Path, *args: str) -> Optional[str]:
    """git の標準出力（失敗時は None）。"""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def repository_url(root: Path) -> str:
    url = _git(root, "remote", "get-url", "origin")
    if not url:
        return "unknown"
    m = re.fullmatch(r"git@([^:]+):(.+?)(?:\.git)?", url)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    m = re.fullmatch(r"(https?://)(?:[^@/]+@)?(.+?)(?:\.git)?", url)  # 認証情報は記録しない
    if m:
        return m.group(1) + m.group(2)
    return url


def version_info(root: Path, paths: List[str]) -> Dict[str, object]:
    commit = _git(root, "rev-parse", "--verify", "HEAD") or "unknown"
    tag = _git(root, "describe", "--tags", "--exact-match", "HEAD") if commit != "unknown" else None
    status = _git(root, "status", "--porcelain", "--", *paths)
    return {"commit": commit, "tag": tag or None, "dirty": bool(status) if status is not None else None}


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_toml(theme: tl.Theme, url: str, version: Dict[str, object]) -> str:
    lines = [
        "# どの design-themes のテーマ・版を使っているかの記録。scripts/apply.py が生成する（手で編集しない）。",
        "# テーマを変えるときは apply.py を再実行する。",
        f"theme = {_toml_str(theme.id)}",
        f"name = {_toml_str(theme.name)}",
        f"slug = {_toml_str(theme.slug)}",
        f"repository = {_toml_str(url)}",
        f"commit = {_toml_str(str(version['commit']))}",
    ]
    if version["tag"]:
        lines.append(f"tag = {_toml_str(str(version['tag']))}")
    if version["dirty"] is not None:
        lines.append(f"dirty = {'true' if version['dirty'] else 'false'}  # true: 未コミットの変更を含む状態から導入した")
    return "\n".join(lines) + "\n"


def stale_dist_files(root: Path, theme_id: str) -> Optional[List[str]]:
    """dist/<id>/ が theme.json から生成される内容と食い違うファイル（生成できない場合は None）。"""
    try:
        outputs = build.render_all(root)
    except build.BuildError:
        return None
    prefix = f"{tl.DIST_DIRNAME}/{theme_id}/"
    expected = {p: c for p, c in outputs.items() if p.startswith(prefix)}
    actual = {p.relative_to(root).as_posix() for p in tl.list_files(root / prefix)}
    stale = [p for p, c in expected.items() if p not in actual or tl.read_text(root / p) != c]
    stale += sorted(actual - set(expected))
    return stale


def apply(theme_id: str, project: Path, root: Path = tl.ROOT, force: bool = False) -> Dict[str, object]:
    """テーマを project に導入し、結果（コピー先・記録内容・警告）を返す。"""
    theme_id = tl.normalize_theme_id(theme_id)
    theme = tl.find_theme(root, theme_id)
    if theme is None:
        known = ", ".join(f"{t.id} ({t.slug})" for t in tl.load_themes(root))
        raise ApplyError(f"テーマ {theme_id} がありません。使える番号: {known}")
    dist_dir = root / tl.DIST_DIRNAME / theme.id
    if not (dist_dir / MANAGED_MARKER).is_file():
        raise ApplyError(f"{dist_dir} がありません。python scripts/build.py を実行してください")
    project = project.resolve()
    if not project.is_dir():
        raise ApplyError(f"プロジェクトのディレクトリがありません: {project}")
    if project == root.resolve():
        raise ApplyError("このリポジトリ自身には導入できません")

    warnings: List[str] = []
    if theme.status == "deprecated":
        warnings.append(f"テーマ {theme.label} は deprecated です。新しいプロジェクトでは別のテーマを選んでください")
    stale = stale_dist_files(root, theme.id)
    if stale is None:
        warnings.append("check.py でエラーが出る状態のため、dist/ が theme.json と一致しているか確認できませんでした")
    elif stale:
        warnings.append(f"dist/{theme.id}/ が theme.json と一致していません（{', '.join(stale)}）。build.py を実行してください")

    design = project / DESIGN_DIRNAME
    if design.exists() or design.is_symlink():
        if not design.is_dir() or design.is_symlink():
            raise ApplyError(f"{design} がディレクトリではありません")
        managed = (design / MANAGED_MARKER).is_file() or not any(design.iterdir())
        if not managed and not force:
            raise ApplyError(
                f"{design} は apply.py で作ったものではないようです。中身を確認し、置き換えてよければ --force を付けて再実行してください"
            )
        shutil.rmtree(design)
    shutil.copytree(dist_dir, design, ignore=shutil.ignore_patterns(*tl.CACHE_PATTERNS))

    rel_paths = [f"{tl.DIST_DIRNAME}/{theme.id}", theme.dir.relative_to(root).as_posix()]
    version = version_info(root, rel_paths)
    if version["commit"] == "unknown":
        warnings.append("このリポジトリのコミットを特定できませんでした（git 管理外、またはコミットがありません）")
    elif version["dirty"]:
        warnings.append("未コミットの変更を含む状態から導入しました。記録したコミットと .design/ の内容が一致しない可能性があります")
    toml_path = project / TOML_NAME
    tl.write_text(toml_path, render_toml(theme, repository_url(root), version))

    return {
        "theme": theme,
        "design_dir": design,
        "files": [p.relative_to(design).as_posix() for p in tl.list_files(design)],
        "toml": toml_path,
        "version": version,
        "warnings": warnings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="テーマをプロジェクトの .design/ に導入する")
    parser.add_argument("theme", help="テーマ番号（例: 02）")
    parser.add_argument("project", type=Path, help="導入先プロジェクトのディレクトリ")
    parser.add_argument("--force", action="store_true", help="apply.py で作ったものではない .design/ も置き換える")
    parser.add_argument("--root", type=Path, default=tl.ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        result = apply(args.theme, args.project, root=root, force=args.force)
    except ApplyError as e:
        print(f"apply: {e}", file=sys.stderr)
        return 1

    theme: tl.Theme = result["theme"]  # type: ignore[assignment]
    version: Dict[str, object] = result["version"]  # type: ignore[assignment]
    print(f"テーマ {theme.label} を {result['design_dir']} に導入しました（{len(result['files'])} ファイル）")
    tag = f"、tag {version['tag']}" if version["tag"] else ""
    print(f"記録: {result['toml']}（commit {str(version['commit'])[:12]}{tag}）")
    for w in result["warnings"]:  # type: ignore[union-attr]
        print(f"警告: {w}", file=sys.stderr)
    snippet = root / SNIPPET_RELPATH
    if snippet.is_file():
        print("\n次の内容をプロジェクトの AGENTS.md に貼ってください（貼り済みなら不要）:\n")
        print("-" * 72)
        print(tl.read_text(snippet).rstrip("\n"))
        print("-" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())

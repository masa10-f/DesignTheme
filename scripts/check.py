#!/usr/bin/env python3
"""themes/*/theme.json を検査する。

エラー（終了コード 1）:
  スキーマ違反、存在しない palette 名の参照、pptx_slot の重複、ディレクトリ名と id/slug の不一致、
  番号の重複・欠番、テーマ間での roles キーの不一致、種色（seeds）の不備、
  導出した色（derived）と hex の不一致
警告（終了コード 0）:
  WCAG コントラスト比の基準未満（小さい文字 4.5:1、線・図形 3:1）、
  系列色どうしの色差が目安未満（色覚シミュレーションを含む）、notes への記載漏れ

使い方:
  python scripts/check.py
  python scripts/check.py --pptx sources/<テンプレート>.pptx   # PPTX の配色と照合（報告のみ）
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import themelib as tl  # noqa: E402


@dataclass(frozen=True)
class Finding:
    level: str  # error / warning / info
    where: str
    message: str


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def run_checks(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    def add(level: str, where: str, message: str) -> None:
        findings.append(Finding(level, where, message))

    schema_path = root / tl.SCHEMA_RELPATH
    try:
        schema = tl.read_json(schema_path)
        specs = tl.role_specs_from_schema(schema)
    except (OSError, ValueError, KeyError, TypeError) as e:
        add("error", _rel(schema_path, root), f"スキーマを読めません: {e}")
        return findings

    dirs = tl.theme_dirs(root)
    if not dirs:
        add("error", tl.THEMES_DIRNAME + "/", "テーマがありません")
        return findings

    dir_ids: Dict[str, List[str]] = {}
    dir_slugs: Dict[str, List[str]] = {}
    schema_valid: List[tl.Theme] = []
    fully_valid: List[tl.Theme] = []

    for d in dirs:
        where = _rel(d, root)
        m = tl.THEME_DIR_RE.match(d.name)
        if not m:
            add("error", where, "ディレクトリ名は <番号>-<slug>（例: 01-brown-orange）にしてください")
            continue
        dir_ids.setdefault(m["id"], []).append(where)
        dir_slugs.setdefault(m["slug"], []).append(where)

        path = d / "theme.json"
        where = _rel(path, root)
        if not path.is_file():
            add("error", _rel(d, root), "theme.json がありません")
            continue
        try:
            data = tl.read_json(path)
        except ValueError as e:
            add("error", where, f"JSON として読めません: {e}")
            continue
        try:
            schema_errors = tl.validate_schema(data, schema)
        except tl.SchemaError as e:
            add("error", _rel(schema_path, root), str(e))
            return findings
        for message in schema_errors:
            add("error", where, f"スキーマ違反: {message}")
        if schema_errors:
            continue

        theme = tl.Theme(path, data)
        schema_valid.append(theme)
        n_errors = len(findings)

        if theme.id != m["id"]:
            add("error", where, f"id {theme.id!r} がディレクトリ名の番号 {m['id']!r} と一致しません")
        if theme.slug != m["slug"]:
            add("error", where, f"slug {theme.slug!r} がディレクトリ名 {m['slug']!r} と一致しません")

        palette = data["palette"]
        for role, spec in theme.roles.items():
            if spec["color"] not in palette:
                add("error", where, f"roles.{role}.color: palette に {spec['color']!r} がありません")
        for i, name in enumerate(theme.series_names):
            if name not in palette:
                add("error", where, f"chart.series[{i}]: palette に {name!r} がありません")

        seeds = data["seeds"]
        seed_names = set(seeds.values())
        for key, name in seeds.items():
            if name not in palette:
                add("error", where, f"seeds.{key}: palette に {name!r} がありません")
            elif "derived" in palette[name]:
                add("error", where, f"seeds.{key}: 種色 {name!r} には derived を付けられません（種色は人が決める値）")
        if len(seed_names) != len(seeds):
            add("error", where, "seeds の 3 色は別々の palette 名にしてください")
        for name, entry in palette.items():
            derived = entry.get("derived")
            if derived is None:
                continue
            if ("from" in derived) == ("hue" in derived):
                add("error", where, f"palette.{name}.derived: from と hue のどちらか一方を指定してください")
            elif "hue" in derived and "chroma" not in derived:
                add("error", where, f"palette.{name}.derived: hue を使うときは chroma も指定してください")
            elif "from" in derived and (derived["from"] not in seed_names or derived["from"] not in palette):
                add("error", where, f"palette.{name}.derived.from: {derived['from']!r} は種色（seeds）ではありません")
            else:
                expected = tl.derived_hex(palette, derived)
                if expected != entry["hex"]:
                    add(
                        "error",
                        where,
                        f"palette.{name}: derived から計算した値 {expected} と hex {entry['hex']} が一致しません"
                        "（値を手で変えたなら derived を消す。種色を変えたなら scripts/derive.py で作り直す）",
                    )

        slot_owner: Dict[str, str] = {}
        for name, entry in palette.items():
            slot = entry.get("pptx_slot")
            if slot is None:
                continue
            if slot in slot_owner:
                add("error", where, f"palette.{name}: pptx_slot {slot!r} が palette.{slot_owner[slot]} と重複しています")
            else:
                slot_owner[slot] = name

        if len(findings) == n_errors:
            fully_valid.append(theme)

    # ---- 番号・slug の重複と欠番
    for theme_id, wheres in sorted(dir_ids.items()):
        if len(wheres) > 1:
            add("error", tl.THEMES_DIRNAME + "/", f"番号 {theme_id} が重複しています: {', '.join(wheres)}")
    for slug, wheres in sorted(dir_slugs.items()):
        if len(wheres) > 1:
            add("error", tl.THEMES_DIRNAME + "/", f"slug {slug!r} が重複しています: {', '.join(wheres)}")
    numbers = sorted({int(i) for i in dir_ids})
    if numbers:
        width = max(len(i) for i in dir_ids)
        missing = [str(n).zfill(width) for n in range(1, numbers[-1] + 1) if n not in numbers]
        if missing:
            add(
                "error",
                tl.THEMES_DIRNAME + "/",
                f"欠番があります: {', '.join(missing)}（テーマは削除せず deprecated にし、新規は次の空き番号で追加する）",
            )

    # ---- roles キーの一致（スキーマと、テーマ間）
    expected_roles = list(specs)
    for theme in schema_valid:
        keys = list(theme.roles)
        if set(keys) != set(expected_roles):
            add(
                "error",
                _rel(theme.path, root),
                f"roles のキーがスキーマと一致しません（不足: {sorted(set(expected_roles) - set(keys))}、"
                f"余分: {sorted(set(keys) - set(expected_roles))}）",
            )
    if schema_valid:
        base = schema_valid[0]
        for theme in schema_valid[1:]:
            if set(theme.roles) != set(base.roles):
                add(
                    "error",
                    _rel(theme.path, root),
                    f"roles のキーが {base.id} と一致しません: {sorted(set(theme.roles) ^ set(base.roles))}",
                )

    # ---- コントラスト
    for theme in fully_valid:
        where = _rel(theme.path, root)
        notes = "\n".join(theme.data["notes"])
        for result in tl.contrast_results(theme, specs):
            if result.is_warning:
                add("warning", where, result.describe())
                if f"`{result.ack_key}`" not in notes:
                    add("warning", where, f"notes に `{result.ack_key}` のコントラスト警告が書かれていません")
            elif result.status == "decorative":
                add("info", where, result.describe())
        for sep in tl.series_separation(theme):
            if sep.is_warning:
                add("warning", where, sep.describe())
                if f"`{sep.ack_key}`" not in notes:
                    add("warning", where, f"notes に `{sep.ack_key}` の色差の警告が書かれていません")
        if theme.chart_status == "provisional":
            add("info", where, "chart.series は暫定案（provisional）です。README に「暫定案・要確認」と明記すること")
        if theme.status == "deprecated":
            add("info", where, "deprecated のテーマです")

    return findings


# --------------------------------------------------------------------------- PPTX との照合

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def read_pptx_colors(path: Path) -> Tuple[List[Tuple[str, str, Dict[str, str]]], Dict[str, Tuple[Set[str], Set[str]]]]:
    """PPTX から（スライドマスターが参照するテーマ配色）と（マスター/レイアウトごとの直接指定色・配色スロット）を読む。"""
    schemes: List[Tuple[str, str, Dict[str, str]]] = []
    usage: Dict[str, Tuple[Set[str], Set[str]]] = {}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        theme_files: List[str] = []
        for name in sorted(names):
            m = re.fullmatch(r"ppt/slideMasters/(slideMaster\d+\.xml)", name)
            if not m:
                continue
            rels = f"ppt/slideMasters/_rels/{m.group(1)}.rels"
            if rels not in names:
                continue
            for rel in ET.fromstring(z.read(rels)).iter(f"{_REL}Relationship"):
                if rel.get("Type", "").endswith("/relationships/theme"):
                    target = posixpath.normpath(posixpath.join("ppt/slideMasters", rel.get("Target", "")))
                    if target not in theme_files:
                        theme_files.append(target)
        if not theme_files:
            theme_files = sorted(n for n in names if re.fullmatch(r"ppt/theme/theme\d+\.xml", n))
        for name in theme_files:
            if name not in names:
                continue
            for scheme in ET.fromstring(z.read(name)).iter(f"{_A}clrScheme"):
                slots: Dict[str, str] = {}
                for child in scheme:
                    slot = child.tag.split("}")[-1]
                    srgb = child.find(f"{_A}srgbClr")
                    system = child.find(f"{_A}sysClr")
                    value = srgb.get("val") if srgb is not None else (system.get("lastClr") if system is not None else None)
                    if value:
                        slots[slot] = "#" + value.upper()
                schemes.append((name, scheme.get("name", ""), slots))
        for name in sorted(names):
            if re.fullmatch(r"ppt/(slideMasters/slideMaster|slideLayouts/slideLayout)\d+\.xml", name):
                root = ET.fromstring(z.read(name))
                literals = {"#" + e.get("val", "").upper() for e in root.iter(f"{_A}srgbClr") if e.get("val")}
                scheme_refs = {e.get("val", "") for e in root.iter(f"{_A}schemeClr") if e.get("val")}
                usage[name] = (literals, scheme_refs)
    return schemes, usage


def compare_pptx(path: Path, root: Path, theme_ids: Optional[List[str]] = None) -> List[Finding]:
    """PPTX の配色と theme.json の pptx_slot を照合する。食い違いは警告として報告するだけで、値は変更しない。"""
    where = _rel(path, root)
    try:
        schemes, usage = read_pptx_colors(path)
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError) as e:
        return [Finding("error", where, f"PPTX を読めません: {e}")]
    findings: List[Finding] = []
    themes = [t for t in tl.load_themes(root) if theme_ids is None or t.id in theme_ids]
    if not schemes:
        findings.append(Finding("warning", where, "テーマ配色（a:clrScheme）が見つかりません"))
    for member, scheme_name, slots in schemes:
        findings.append(
            Finding("info", where, f"{member}: clrScheme {scheme_name!r} = " + ", ".join(f"{k} {v}" for k, v in slots.items()))
        )
        for theme in themes:
            if not any("pptx_slot" in e for e in theme.data["palette"].values()):
                findings.append(Finding("info", where, f"{member} ↔ {theme.label}: pptx_slot がないため照合しない"))
                continue
            mismatches = []
            mapped = set()
            for name, entry in theme.data["palette"].items():
                slot = entry.get("pptx_slot")
                if slot is None:
                    continue
                mapped.add(slot)
                actual = slots.get(slot)
                if actual != entry["hex"]:
                    mismatches.append(f"{slot}: theme.json {name} {entry['hex']} / PPTX {actual or 'なし'}")
            unmapped = sorted(set(slots) - mapped)
            label = f"{member} ↔ {theme.label}"
            if mismatches:
                findings.append(Finding("warning", where, f"{label}: 不一致 " + "; ".join(mismatches)))
            else:
                findings.append(Finding("info", where, f"{label}: pptx_slot はすべて一致"))
            if unmapped:
                findings.append(Finding("info", where, f"{label}: palette に対応のないスロット {unmapped}"))
    known: Dict[str, List[str]] = {}
    for theme in themes:
        for hex_color in theme.palette_hex().values():
            known.setdefault(hex_color, []).append(theme.id)
    for member, (literals, scheme_refs) in sorted(usage.items()):
        if not literals and not scheme_refs:
            continue
        parts = []
        if scheme_refs:
            parts.append("配色スロット " + ", ".join(sorted(scheme_refs)))
        if literals:
            parts.append("直接指定 " + ", ".join(f"{h}（{'/'.join(known.get(h, ['未登録']))}）" for h in sorted(literals)))
        findings.append(Finding("info", where, f"{member}: " + "; ".join(parts)))
        for hex_color in sorted(literals):
            if hex_color not in known:
                findings.append(Finding("warning", where, f"{member}: 直接指定色 {hex_color} はどのテーマの palette にもありません"))
    return findings


# --------------------------------------------------------------------------- CLI

_LABELS = {"error": "ERROR", "warning": "WARN ", "info": "INFO "}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="theme.json を検査する")
    parser.add_argument("--root", type=Path, default=tl.ROOT, help=argparse.SUPPRESS)
    parser.add_argument(
        "--pptx", type=Path, action="append", default=[], metavar="FILE",
        help="PPTX テンプレートの配色と照合する（報告のみ。theme.json は変更しない）",
    )
    parser.add_argument("--theme", action="append", metavar="ID", help="--pptx の照合対象を番号で絞る")
    parser.add_argument("-q", "--quiet", action="store_true", help="INFO を表示しない")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    findings = run_checks(root)
    has_errors = any(f.level == "error" for f in findings)
    theme_ids = [tl.normalize_theme_id(t) for t in args.theme] if args.theme else None
    for pptx in args.pptx:
        if has_errors:
            findings.append(Finding("info", str(pptx), "エラーがあるため PPTX の照合を省略しました"))
            break
        findings.extend(compare_pptx(pptx.resolve(), root, theme_ids))

    for f in findings:
        if args.quiet and f.level == "info":
            continue
        print(f"[{_LABELS[f.level]}] {f.where}: {f.message}")
    n_err = sum(f.level == "error" for f in findings)
    n_warn = sum(f.level == "warning" for f in findings)
    n_themes = len(tl.theme_dirs(root))
    print(f"check: {n_themes} テーマ、エラー {n_err} 件、警告 {n_warn} 件")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

import check
import themelib as tl
from conftest import REPO, edit_theme


def errors(findings):
    return [f for f in findings if f.level == "error"]


def warnings(findings):
    return [f for f in findings if f.level == "warning"]


def test_repository_has_no_errors():
    findings = check.run_checks(REPO)
    assert errors(findings) == []
    assert check.main(["--quiet"]) == 0


def test_contrast_ratio_reference_values():
    assert tl.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert tl.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert tl.contrast_ratio("#77736C", "#DCD5C8") == pytest.approx(3.23, abs=0.01)
    assert tl.contrast_ratio("#DC5F36", "#FFFFFF") == pytest.approx(3.66, abs=0.01)
    # 表示は切り捨て（4.4999 を 4.50 と表示しない）
    assert tl.format_ratio(4.4999) == "4.49:1"


def test_known_contrast_warnings_are_reported():
    messages = [f.where + " " + f.message for f in warnings(check.run_checks(REPO))]

    def has(theme_dir: str, *parts: str) -> bool:
        return any(theme_dir in m and all(p in m for p in parts) for m in messages)

    assert has("02-beige-navy", "`category`", "#77736C", "3.23:1", "4.5:1 未満")
    assert has("01-brown-orange", "`section-label`", "#DC5F36", "3.66:1", "4.5:1 未満")
    assert has("01-brown-orange", "`accent`", "#DC5F36", "3:1 は満たす", "小さい文字には使えない")
    # すべて notes に記載済み
    assert not any("notes に" in m for m in messages)


def test_schema_violation_is_error(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["palette"]["brown-700"].update(hex="#70372c"))
    found = errors(check.run_checks(repo_copy))
    assert any("スキーマ違反" in f.message and "palette.brown-700.hex" in f.message for f in found)


def test_unknown_palette_reference_is_error(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["roles"]["band"].update(color="beige-999"))
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["chart"]["series"].append("no-such-color"))
    messages = [f.message for f in errors(check.run_checks(repo_copy))]
    assert any("roles.band.color" in m and "beige-999" in m for m in messages)
    assert any("chart.series[3]" in m and "no-such-color" in m for m in messages)


def test_roles_key_mismatch_is_error(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["roles"].pop("rule"))
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["roles"].update(extra={"color": "white", "usage": "x"}))
    found = errors(check.run_checks(repo_copy))
    assert any("02-beige-navy" in f.where and "'rule'" in f.message for f in found)
    assert any("01-brown-orange" in f.where and "'extra'" in f.message for f in found)


def test_duplicate_number_is_error(repo_copy: Path):
    shutil.copytree(repo_copy / "themes/02-beige-navy", repo_copy / "themes/02-navy-copy")
    edit_theme(repo_copy, "02-navy-copy", lambda d: d.update(slug="navy-copy"))
    assert any("番号 02 が重複" in f.message for f in errors(check.run_checks(repo_copy)))


def test_gap_in_numbers_is_error(repo_copy: Path):
    (repo_copy / "themes/02-beige-navy").rename(repo_copy / "themes/03-beige-navy")
    edit_theme(repo_copy, "03-beige-navy", lambda d: d.update(id="03"))
    assert any("欠番" in f.message and "02" in f.message for f in errors(check.run_checks(repo_copy)))


def test_directory_name_must_match_id_and_slug(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d.update(id="05", slug="brown"))
    messages = [f.message for f in errors(check.run_checks(repo_copy))]
    assert any("id '05'" in m for m in messages)
    assert any("slug 'brown'" in m for m in messages)


def test_duplicate_pptx_slot_is_error(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["palette"]["taupe-300"].update(pptx_slot="accent1"))
    assert any("pptx_slot 'accent1'" in f.message for f in errors(check.run_checks(repo_copy)))


def test_contrast_warning_must_be_acknowledged_in_notes(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d.update(notes=[]))
    found = warnings(check.run_checks(repo_copy))
    assert any("notes に `category`" in f.message for f in found)
    assert errors(check.run_checks(repo_copy)) == []  # 警告であってエラーではない


def test_validator_refuses_unsupported_keywords():
    with pytest.raises(tl.SchemaError):
        tl.validate_schema(1, {"type": "integer", "maximum": 3})


def test_schema_and_themes_agree_with_jsonschema():
    jsonschema = pytest.importorskip("jsonschema")
    validator = getattr(jsonschema, "Draft202012Validator", None)
    if validator is None:
        pytest.skip("jsonschema が古く、Draft 2020-12 に対応していない")
    schema = json.loads((REPO / "schema/theme.schema.json").read_text(encoding="utf-8"))
    validator.check_schema(schema)
    for path in sorted((REPO / "themes").glob("*/theme.json")):
        validator(schema).validate(json.loads(path.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- PPTX との照合

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
SLOTS = {
    "dk1": "242424", "lt1": "FFFFFF", "dk2": "0E2841", "lt2": "E8E8E8",
    "accent1": "70372C", "accent2": "DC5F36", "accent3": "F7E3AF", "accent4": "DCD5C8",
    "accent5": "A2A2AD", "accent6": "1F1E63", "hlink": "467886", "folHlink": "96607D",
}


def make_pptx(path: Path, slots: dict, literals: list) -> Path:
    def color(slot: str, val: str) -> str:
        if slot in ("dk1", "lt1"):
            return f'<a:{slot}><a:sysClr val="windowText" lastClr="{val}"/></a:{slot}>'
        return f'<a:{slot}><a:srgbClr val="{val}"/></a:{slot}>'

    theme_xml = (
        f'<a:theme xmlns:a="{A}" name="T"><a:themeElements><a:clrScheme name="I-Lab Research Palette">'
        + "".join(color(k, v) for k, v in slots.items())
        + "</a:clrScheme></a:themeElements></a:theme>"
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
        'Target="../theme/theme1.xml"/></Relationships>'
    )
    layout = (
        f'<p:sldLayout xmlns:p="p" xmlns:a="{A}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill>'
        + "".join(f'<a:solidFill><a:srgbClr val="{v}"/></a:solidFill>' for v in literals)
        + "</p:sldLayout>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/theme/theme1.xml", theme_xml)
        z.writestr("ppt/theme/theme2.xml", theme_xml.replace("70372C", "000000"))  # ノートマスター用など（無視される）
        z.writestr("ppt/slideMasters/slideMaster1.xml", f'<p:sldMaster xmlns:p="p" xmlns:a="{A}"/>')
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
    return path


def test_pptx_matching_template_reports_no_mismatch(tmp_path: Path):
    pptx = make_pptx(tmp_path / "t.pptx", SLOTS, ["C4B2AB", "77736C"])
    found = check.compare_pptx(pptx, REPO)
    assert not [f for f in found if f.level in ("error", "warning")]
    assert sum("pptx_slot はすべて一致" in f.message for f in found) == 2


def test_pptx_mismatch_is_reported_without_changing_themes(tmp_path: Path):
    before = {p: p.read_bytes() for p in (REPO / "themes").glob("*/theme.json")}
    pptx = make_pptx(tmp_path / "t.pptx", {**SLOTS, "accent4": "DDD5C8"}, ["123456"])
    found = check.compare_pptx(pptx, REPO)
    messages = [f.message for f in found if f.level == "warning"]
    assert any("accent4" in m and "#DCD5C8" in m and "#DDD5C8" in m for m in messages)
    assert any("#123456" in m for m in messages)
    assert {p: p.read_bytes() for p in before} == before

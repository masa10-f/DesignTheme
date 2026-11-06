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
    assert tl.contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)
    assert tl.contrast_ratio("#DC5F36", "#FFFFFF") == pytest.approx(3.66, abs=0.01)
    # 表示は切り捨て（4.4999 を 4.50 と表示しない）
    assert tl.format_ratio(4.4999) == "4.49:1"


def test_known_contrast_warnings_are_reported():
    messages = [f.where + " " + f.message for f in warnings(check.run_checks(REPO))]

    def has(theme_dir: str, *parts: str) -> bool:
        return any(theme_dir in m and all(p in m for p in parts) for m in messages)

    # 種色のまま使う accent だけが基準に届かない（文字用の role は明度を変えた色で基準を満たす）
    assert has("01-brown-orange", "`accent`", "#DC5F36", "3:1 は満たす", "小さい文字には使えない")
    assert has("02-beige-navy", "`accent`", "#92929D", "3.07:1", "3:1 は満たす")
    assert len(messages) == 2
    # すべて notes に記載済み
    assert not any("notes に" in m for m in messages)


def test_schema_violation_is_error(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["palette"]["brown-30"].update(hex="#70372c"))
    found = errors(check.run_checks(repo_copy))
    assert any("スキーマ違反" in f.message and "palette.brown-30.hex" in f.message for f in found)


def test_unknown_palette_reference_is_error(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["roles"]["band"].update(color="beige-999"))
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["chart"]["series"].append("no-such-color"))
    messages = [f.message for f in errors(check.run_checks(repo_copy))]
    assert any("roles.band.color" in m and "beige-999" in m for m in messages)
    assert any("chart.series[6]" in m and "no-such-color" in m for m in messages)


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
    (repo_copy / "themes/02-beige-navy").rename(repo_copy / "themes/05-beige-navy")
    edit_theme(repo_copy, "05-beige-navy", lambda d: d.update(id="05"))
    assert any("欠番" in f.message and "02" in f.message for f in errors(check.run_checks(repo_copy)))


def test_directory_name_must_match_id_and_slug(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d.update(id="05", slug="brown"))
    messages = [f.message for f in errors(check.run_checks(repo_copy))]
    assert any("id '05'" in m for m in messages)
    assert any("slug 'brown'" in m for m in messages)


def test_duplicate_pptx_slot_is_error(repo_copy: Path):
    def two_slots(d):
        d["palette"]["brown-30"]["pptx_slot"] = "accent1"
        d["palette"]["orange-56"]["pptx_slot"] = "accent1"

    edit_theme(repo_copy, "01-brown-orange", two_slots)
    assert any("pptx_slot 'accent1'" in f.message for f in errors(check.run_checks(repo_copy)))


def test_contrast_warning_must_be_acknowledged_in_notes(repo_copy: Path):
    edit_theme(repo_copy, "02-beige-navy", lambda d: d.update(notes=[]))
    found = warnings(check.run_checks(repo_copy))
    assert any("notes に `accent`" in f.message for f in found)
    assert errors(check.run_checks(repo_copy)) == []  # 警告であってエラーではない


# --------------------------------------------------------------------------- 種色と導出した色


def test_derived_colors_are_recomputed(repo_copy: Path):
    # 導出した色を手で変えると、由来（derived）と一致しなくなる
    edit_theme(repo_copy, "03-navy-red", lambda d: d["palette"]["navy-68"].update(hex="#96A4DB"))
    found = errors(check.run_checks(repo_copy))
    assert any("palette.navy-68" in f.message and "derived から計算した値 #96A4DA" in f.message for f in found)


def test_hand_tuned_color_without_derived_is_accepted(repo_copy: Path):
    def tune(d):
        d["palette"]["navy-68"] = {"hex": "#96A4DB", "note": "手で調整"}

    edit_theme(repo_copy, "03-navy-red", tune)
    assert errors(check.run_checks(repo_copy)) == []


def test_changing_a_seed_invalidates_colors_derived_from_it(repo_copy: Path):
    edit_theme(repo_copy, "04-slate-teal", lambda d: d["palette"]["slate-30"].update(hex="#5E3448"))
    messages = [f.message for f in errors(check.run_checks(repo_copy))]
    assert any("palette.neutral-15" in m for m in messages)
    assert any("palette.slate-73" in m for m in messages)


def test_seed_errors(repo_copy: Path):
    edit_theme(repo_copy, "01-brown-orange", lambda d: d["seeds"].update(sub="no-such"))
    edit_theme(repo_copy, "02-beige-navy", lambda d: d["palette"]["navy-16"].update(derived={"from": "beige-85", "tone": 16}))
    edit_theme(repo_copy, "03-navy-red", lambda d: d["palette"]["navy-68"]["derived"].update(**{"from": "neutral-15"}))
    edit_theme(repo_copy, "04-slate-teal", lambda d: d["palette"]["red-35"]["derived"].pop("chroma"))
    messages = [f.where + " " + f.message for f in errors(check.run_checks(repo_copy))]
    assert any("01-brown-orange" in m and "seeds.sub" in m and "no-such" in m for m in messages)
    assert any("02-beige-navy" in m and "seeds.sub" in m and "derived を付けられません" in m for m in messages)
    assert any("03-navy-red" in m and "palette.navy-68.derived.from" in m and "種色" in m for m in messages)
    assert any("04-slate-teal" in m and "palette.red-35.derived" in m and "chroma" in m for m in messages)


def test_derived_range_is_validated_by_schema(repo_copy: Path):
    edit_theme(repo_copy, "03-navy-red", lambda d: d["palette"]["navy-68"]["derived"].update(tone=101))
    assert any("スキーマ違反" in f.message and "101" in f.message for f in errors(check.run_checks(repo_copy)))


def test_similar_series_colors_are_warned(repo_copy: Path):
    def add_similar(d):
        d["palette"]["near-red"] = {"hex": "#E00010"}
        d["chart"]["series"].append("near-red")

    edit_theme(repo_copy, "03-navy-red", add_similar)
    found = warnings(check.run_checks(repo_copy))
    assert any("`chart.series[1]`" in f.message and "`chart.series[6]`" in f.message and "ΔE00" in f.message for f in found)
    assert any("notes に `near-red` の色差の警告" in f.message for f in found)


def test_validator_refuses_unsupported_keywords():
    with pytest.raises(tl.SchemaError):
        tl.validate_schema(1, {"type": "integer", "exclusiveMaximum": 3})


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
# 照合テスト用の架空のテーマ配色。accent1〜3 をテーマ 03 の種色にしておく
SLOTS = {
    "dk1": "000000", "lt1": "FFFFFF", "dk2": "333333", "lt2": "EEEEEE",
    "accent1": "303967", "accent2": "E60012", "accent3": "FFE200", "accent4": "111111",
    "accent5": "222222", "accent6": "444444", "hlink": "0000FF", "folHlink": "800080",
}
SLOTTED = {"navy-25": "accent1", "red-48": "accent2", "yellow-90": "accent3", "white": "lt1"}


def with_slots(repo: Path) -> Path:
    """テーマ 03 の種色と白に pptx_slot を付ける（公開リポジトリのテーマには付けていない）。"""

    def add(d):
        for name, slot in SLOTTED.items():
            d["palette"][name]["pptx_slot"] = slot

    edit_theme(repo, "03-navy-red", add)
    return repo


def make_pptx(path: Path, slots: dict, literals: list) -> Path:
    def color(slot: str, val: str) -> str:
        if slot in ("dk1", "lt1"):
            return f'<a:{slot}><a:sysClr val="windowText" lastClr="{val}"/></a:{slot}>'
        return f'<a:{slot}><a:srgbClr val="{val}"/></a:{slot}>'

    theme_xml = (
        f'<a:theme xmlns:a="{A}" name="T"><a:themeElements><a:clrScheme name="Test Palette">'
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
        z.writestr("ppt/theme/theme2.xml", theme_xml.replace("303967", "000000"))  # ノートマスター用など（無視される）
        z.writestr("ppt/slideMasters/slideMaster1.xml", f'<p:sldMaster xmlns:p="p" xmlns:a="{A}"/>')
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
    return path


def test_pptx_matching_template_reports_no_mismatch(repo_copy: Path, tmp_path: Path):
    pptx = make_pptx(tmp_path / "t.pptx", SLOTS, ["303967", "5D5E62"])
    found = check.compare_pptx(pptx, with_slots(repo_copy))
    assert not [f for f in found if f.level in ("error", "warning")]
    # pptx_slot を付けたテーマ 03 だけを照合する
    assert sum("pptx_slot はすべて一致" in f.message for f in found) == 1
    assert sum("pptx_slot がないため照合しない" in f.message for f in found) == 3


def test_pptx_mismatch_is_reported_without_changing_themes(repo_copy: Path, tmp_path: Path):
    root = with_slots(repo_copy)
    before = {p: p.read_bytes() for p in (root / "themes").glob("*/theme.json")}
    pptx = make_pptx(tmp_path / "t.pptx", {**SLOTS, "accent2": "E60013"}, ["123456"])
    found = check.compare_pptx(pptx, root)
    messages = [f.message for f in found if f.level == "warning"]
    assert any("accent2" in m and "#E60012" in m and "#E60013" in m for m in messages)
    assert any("#123456" in m for m in messages)
    assert {p: p.read_bytes() for p in before} == before


def test_public_themes_have_no_pptx_slots():
    # 公開リポジトリのテーマには、元資料に固有のスロット番号を残さない
    for path in (REPO / "themes").glob("*/theme.json"):
        assert "pptx_slot" not in path.read_text(encoding="utf-8"), path

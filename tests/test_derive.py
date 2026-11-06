from __future__ import annotations

import json
from pathlib import Path

import pytest

import build
import check
import colorlib as cl
import derive
import themelib as tl
from conftest import REPO, edit_theme

REPO_SEEDS = [
    "#70372C", "#DC5F36", "#F7E3AF", "#DCD5C8", "#A2A2AD", "#1F1E63",
    "#303967", "#E60012", "#FFE200", "#34485E", "#3C7D9B", "#5B9F8A",
]


# --------------------------------------------------------------------------- 色の計算


@pytest.mark.parametrize(
    "lab1, lab2, expected",
    [
        # Sharma, Wu & Dalal (2005) の検証用データから
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ],
)
def test_ciede2000_matches_reference(lab1, lab2, expected):
    assert cl.ciede2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("hex_color", REPO_SEEDS)
def test_oklch_round_trip(hex_color: str):
    _, chroma, hue = cl.oklch(hex_color)
    assert cl.at_tone(hue, chroma, cl.tone(hex_color)) == hex_color


@pytest.mark.parametrize("hue", range(0, 360, 30))
@pytest.mark.parametrize("target", [5, 15, 40, 50, 60, 75, 90, 97])
def test_at_tone_hits_the_target_lightness(hue: int, target: int):
    assert cl.tone(cl.at_tone(float(hue), 0.2, float(target))) == pytest.approx(target, abs=0.5)


def test_tone_difference_bounds_contrast():
    # README の説明: 明度の差 40 で 3:1 以上、差 50 でほぼ 4.5:1（最低 4.48）
    def worst(diff: int) -> float:
        return min(
            (cl.tone_to_luminance(t + diff) + 0.05) / (cl.tone_to_luminance(t) + 0.05)
            for t in [x / 10 for x in range(0, (100 - diff) * 10 + 1)]
        )

    assert worst(40) >= 3.0
    assert worst(50) == pytest.approx(4.48, abs=0.01)


def test_color_vision_simulation():
    for vision in cl.CVD_VISIONS:
        assert cl.delta_e("#FFFFFF", "#FFFFFF", vision) == 0
        assert cl.delta_e("#000000", "#FFFFFF", vision) > 90
    # 赤と緑は 1 型・2 型で近づく
    assert cl.delta_e("#D55E00", "#009E73", "deutan") < cl.delta_e("#D55E00", "#009E73") / 2
    assert cl.min_delta_e("#D55E00", "#009E73")[1] in ("protan", "deutan")


def test_hue_names():
    assert [cl.hue_name(cl.oklch(h)[2]) for h in ["#FF0000", "#FF8000", "#00FF00", "#008080", "#0000FF", "#FF00FF"]] == [
        "red", "orange", "green", "teal", "blue", "magenta",
    ]


# --------------------------------------------------------------------------- derive.py


def run_derive(root: Path, *args: str) -> int:
    return derive.main([*args, "--root", str(root)])


def load(root: Path, dirname: str) -> dict:
    return json.loads((root / "themes" / dirname / "theme.json").read_text(encoding="utf-8"))


def test_derived_theme_passes_check_and_is_reproducible(repo_copy: Path):
    args = ["05", "olive-plum", "--name", "Olive & Plum", "--base", "olive=#3E4F22", "--accent", "plum=#8E4585", "--sub", "sand=#E6D3A3"]
    assert run_derive(repo_copy, *args) == 0
    first = (repo_copy / "themes/05-olive-plum/theme.json").read_bytes()
    findings = check.run_checks(repo_copy)
    assert [f for f in findings if f.level == "error"] == []
    assert not [f for f in findings if f.level == "warning" and "notes に" in f.message]
    # 既存の種色から作り直すと同じ内容になる
    assert run_derive(repo_copy, "05", "--force") == 0
    assert (repo_copy / "themes/05-olive-plum/theme.json").read_bytes() == first
    # README のひな形ができ、build がプレビューを埋める
    readme = repo_copy / "themes/05-olive-plum/README.md"
    assert "BEGIN GENERATED: preview" in readme.read_text(encoding="utf-8")
    assert build.main(["--root", str(repo_copy)]) == 0
    assert "dist/05/preview/3-body.svg" in readme.read_text(encoding="utf-8")
    assert (repo_copy / "dist/05/preview/5-roles.svg").is_file()


@pytest.mark.parametrize(
    "seeds",
    [
        ("#70372C", "#DC5F36", "#F7E3AF"),  # 暗いベース・明るいサブ
        ("#DCD5C8", "#A2A2AD", "#1F1E63"),  # 明るいベース・暗いサブ
        ("#F0E0D0", "#3050A0", "#FFE0E0"),  # ベースもサブも白地で文字に使えない
        ("#000000", "#FFFFFF", "#808080"),  # 無彩色だけ
        ("#0000FF", "#FFFF00", "#00FF00"),  # 原色
    ],
)
def test_derive_satisfies_the_contrast_rules(seeds):
    data, _ = derive.derive_theme(
        "09", "x", "X", {k: derive.Seed(k, f"c{i}", h) for i, (k, h) in enumerate(zip(tl.SEED_KEYS, seeds))}
    )
    theme = tl.Theme(REPO / "themes/09-x/theme.json", data)
    specs = tl.role_specs_from_schema(tl.load_schema(REPO))
    # 種色の値は変えない
    assert [data["palette"][data["seeds"][k]]["hex"] for k in tl.SEED_KEYS] == list(seeds)
    # 種色をそのまま使う accent 以外の文字・線の role は、すべて基準を満たす
    for result in tl.contrast_results(theme, specs):
        if result.subject != "accent" and result.kind != "decorative":
            assert not result.is_warning, result.describe()
    assert len(theme.series_names) == derive.SERIES_COUNT
    assert len(set(theme.series_hex())) == derive.SERIES_COUNT
    # 導出した色は check.py の再計算と一致する
    for entry in data["palette"].values():
        if "derived" in entry:
            assert tl.derived_hex(data["palette"], entry["derived"]) == entry["hex"]
    # 決定的
    again, _ = derive.derive_theme(
        "09", "x", "X", {k: derive.Seed(k, f"c{i}", h) for i, (k, h) in enumerate(zip(tl.SEED_KEYS, seeds))}
    )
    assert again == data


def test_light_seed_is_adjusted_only_where_it_must_carry_text(repo_copy: Path):
    data = load(repo_copy, "01-brown-orange")
    roles = {r: s["color"] for r, s in data["roles"].items()}
    assert roles["accent"] == "orange-56"  # 線・図形は種色のまま
    assert roles["section-label"] == "orange-49"  # 文字は同じ色相で明度を下げる
    assert data["palette"]["orange-49"]["derived"] == {"from": "orange-56", "tone": 49}
    data = load(repo_copy, "02-beige-navy")
    assert data["roles"]["emphasis"]["color"] == "navy-16"  # ベースが白地で使えないのでサブ


def test_rederive_keeps_pptx_slots(repo_copy: Path):
    def add(d):
        d["palette"]["navy-25"]["pptx_slot"] = "accent1"
        d["palette"]["white"]["pptx_slot"] = "lt1"

    edit_theme(repo_copy, "03-navy-red", add)
    assert run_derive(repo_copy, "03", "--force") == 0
    after = load(repo_copy, "03-navy-red")
    assert after["palette"]["navy-25"]["pptx_slot"] == "accent1"
    assert after["palette"]["white"]["pptx_slot"] == "lt1"


def test_committed_themes_are_reproducible(repo_copy: Path):
    # 記録済みの種色から作り直すと、コミット済みの theme.json と同じになる
    for theme_id, dirname in (("01", "01-brown-orange"), ("02", "02-beige-navy"), ("03", "03-navy-red"), ("04", "04-slate-teal")):
        before = (repo_copy / "themes" / dirname / "theme.json").read_bytes()
        assert run_derive(repo_copy, theme_id, "--force") == 0
        assert (repo_copy / "themes" / dirname / "theme.json").read_bytes() == before, dirname


def test_derive_refuses_bad_requests(repo_copy: Path, capsys):
    seeds = ["--base", "a=#111111", "--accent", "b=#222222", "--sub", "c=#EEEEEE"]
    assert run_derive(repo_copy, "01", *seeds) == 1  # 既にある
    assert "--force" in capsys.readouterr().err
    assert run_derive(repo_copy, "01", "other-slug", "--name", "X", *seeds, "--force") == 1  # slug を変えない
    assert "01-brown-orange" in capsys.readouterr().err
    assert run_derive(repo_copy, "05", "x", "--name", "X", "--base", "a=#12345", "--accent", "b=#222222", "--sub", "c=#EEEEEE") == 1
    assert "色名=#RRGGBB" in capsys.readouterr().err
    assert run_derive(repo_copy, "05", "x", *seeds) == 1  # --name がない
    assert not (repo_copy / "themes/05-x").exists()


def test_dry_run_writes_nothing(repo_copy: Path, capsys):
    args = ["05", "x", "--name", "X", "--base", "a=#203040", "--accent", "b=#C04020", "--sub", "c=#E0E0D0", "--dry-run"]
    assert run_derive(repo_copy, *args) == 0
    out = capsys.readouterr().out
    assert "chart.series:" in out and "dry-run" in out
    assert not (repo_copy / "themes/05-x").exists()


def test_dump_theme_round_trips():
    data = load(REPO, "04-slate-teal")
    assert json.loads(derive.dump_theme(data)) == data


# --------------------------------------------------------------------------- 種色の判定と提案


def checks_for(base: str, accent: str, sub: str):
    return {c.key: c for c in tl.seed_checks({"base": "b", "accent": "a", "sub": "s"}, {"base": base, "accent": accent, "sub": sub})}


def test_seed_checks_of_committed_themes():
    expected = {"01": [], "02": [], "03": [], "04": []}
    for theme in tl.load_themes(REPO):
        palette = theme.palette_hex()
        checks = tl.seed_checks(theme.seeds, {k: palette[n] for k, n in theme.seeds.items()})
        assert [c.key for c in checks if not c.ok] == expected[theme.id]
    c = checks_for("#DCD5C8", "#A2A2AD", "#1F1E63")["accent"]
    assert (c.proposal_tone, c.proposal_hex) == (61, "#92929D")
    c = checks_for("#34485E", "#3C7D9B", "#5B9F8A")["sub"]
    assert (c.proposal_tone, c.proposal_hex) == (73, "#7CC1AB")


@pytest.mark.parametrize(
    "seeds",
    [
        ("#7A8B99", "#B5562F", "#DDE6EC"),  # 中間の明度のベース
        ("#2F6F73", "#3A9A9E", "#7CC4B5"),  # 似た色相
        ("#C9B79C", "#C98B2B", "#5A4636"),  # アクセントが淡い
        ("#808080", "#DDDDDD", "#999999"),  # 無彩色
    ],
)
def test_proposals_meet_the_criteria_and_keep_the_hue(seeds):
    checks = checks_for(*seeds)
    hexes = dict(zip(tl.SEED_KEYS, seeds))
    for key, c in checks.items():
        if c.ok:
            continue
        assert c.proposal_hex is not None and c.proposal_ratio >= c.minimum
        hexes[key] = c.proposal_hex
        _, chroma, hue = cl.oklch(seeds[tl.SEED_KEYS.index(key)])
        if chroma > 0.02:  # 無彩色は色相が定まらない
            assert abs((cl.oklch(c.proposal_hex)[2] - hue + 180) % 360 - 180) < 3
    # 提案の 3 色は、すべての基準を満たす
    assert all(c.ok for c in tl.seed_checks({k: k for k in hexes}, hexes))


def test_base_proposal_moves_to_the_side_where_the_sub_is_readable():
    c = checks_for("#7A8B99", "#B5562F", "#DDE6EC")
    assert c["base"].proposal_tone == 37  # 明るいサブが読めるよう、暗い帯にする（明るい側の 72 の方が近いが選ばない）
    assert c["sub"].ok and c["sub"].against == "提案のベース（帯）"


def test_derive_stops_and_proposes_when_seeds_fail(repo_copy: Path, capsys):
    args = ["05", "trial", "--name", "Trial", "--base", "mid=#7A8B99", "--accent", "rust=#B5562F", "--sub", "mist=#DDE6EC"]
    assert run_derive(repo_copy, *args) == 1
    captured = capsys.readouterr()
    assert "--keep-seeds" in captured.err
    assert '--base mid=#495966 --accent rust=#B5562F --sub mist=#DDE6EC' in captured.out
    assert not (repo_copy / "themes/05-trial").exists()
    # 提案の色なら止まらない
    proposed = ["05", "trial", "--name", "Trial", "--base", "mid=#495966", "--accent", "rust=#B5562F", "--sub", "mist=#DDE6EC"]
    assert run_derive(repo_copy, *proposed) == 0
    assert not any(n.startswith("種色の判定") for n in load(repo_copy, "05-trial")["notes"])


def test_keep_seeds_records_the_decision(repo_copy: Path):
    args = ["05", "trial", "--name", "Trial", "--base", "mid=#7A8B99", "--accent", "rust=#B5562F", "--sub", "mist=#DDE6EC"]
    assert run_derive(repo_copy, *args, "--keep-seeds") == 0
    notes = load(repo_copy, "05-trial")["notes"]
    assert any(n.startswith("種色の判定: ベース `mid-57`") and "提案を採らず" in n for n in notes)
    assert [f for f in check.run_checks(repo_copy) if f.level == "error"] == []


def test_on_band_and_category_too_close_is_reported(capsys, repo_copy: Path):
    args = ["05", "trial", "--name", "Trial", "--base", "teal=#2F6F73", "--accent", "aqua=#3A9A9E", "--sub", "mint=#7CC4B5", "--dry-run"]
    assert run_derive(repo_copy, *args) == 0
    assert "`on-band`" in capsys.readouterr().out

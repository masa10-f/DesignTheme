#!/usr/bin/env python3
"""種色 3 つ（ベース・アクセント・サブ）から theme.json を作る。

使い方:
  python scripts/derive.py 03 navy-red --name "Navy & Red" \\
      --base navy=#303967 --accent red=#E60012 --sub yellow=#FFE200
  python scripts/derive.py 01 --force       # 既存の theme.json の種色から作り直す
  python scripts/derive.py ... --dry-run    # 書き込まずに結果だけ表示する

種色はそのまま palette に入れ、値を変えない。それ以外の色は次の手順で機械的に作り、
palette の "derived" に由来（色相・彩度・明度）を残す（check.py が再計算して一致を確かめる）。

1. 明度は CIE L*（0〜100）で扱う。コントラスト比は輝度だけで決まるので、role ごとに必要な明度が決まる。
2. 色相と彩度は OKLCH で種色から取り、明度だけを変える（sRGB に収まらなければ彩度だけ下げる）。
3. role の割り当て（基準はスキーマの x-contrast）:
   - background = 白。text / text-secondary / placeholder-* = ベースの色相をわずかに混ぜたグレー
   - band = ベース。emphasis = ベース → サブの順で白地で基準を満たす種色。なければベースの明度を変えた色
   - on-band = サブ（band の上で基準を満たさなければ、サブの明度を変えた色）
   - category = ベースの明度を変えた色（帯と同じ色相で、帯の上で基準を満たす最も近い明度）
   - accent = アクセント（そのまま）。section-label = アクセント（白地で基準を満たさなければ明度を変えた色）
   - rule = 種色のうち最も明るい色（装飾）
   「明度を変えた色」は、元の種色の明度に最も近く、基準を満たす整数の明度を選ぶ。
4. グラフの系列色（6 色、暫定案）: emphasis に使った種色 → 残りの種色（アクセント、ベース、サブの順）。
   白地で 3:1 未満なら明度を下げて使い、既に選んだ色と見分けにくい（色差 ΔE00 が目安未満）なら外す。
   残りは追加色で埋める。候補（色相 5° 刻み × 明度 35〜60）のうち、色覚シミュレーション（1〜3 型）でも
   既存の色と ΔE00 12 以上離れるものの中で、一般色覚での最小色差が最大のものを順に選ぶ。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import colorlib as cl  # noqa: E402
import themelib as tl  # noqa: E402

WHITE = "#FFFFFF"
NEUTRAL_CHROMA = 0.006  # グレーに混ぜるベースの色の量（OKLCH の彩度）
NEUTRAL_TONES = {"text": 15, "text-secondary": 40, "placeholder-border": 88, "placeholder-bg": 97, "placeholder-text": 40}
SERIES_COUNT = 6
EXTRA_HUE_STEP = 5
EXTRA_TONES = (35, 40, 45, 50, 55, 60)  # 白地で 3:1 以上になる明度
EXTRA_CHROMA_RANGE = (0.10, 0.15)  # 追加色の彩度 = 種色の最大彩度をこの範囲に収めた値
EXTRA_CVD_MIN = 12.0  # 追加色は色覚シミュレーションでもこの色差以上離す（警告の目安 10 に余裕を持たせる）

DEFAULT_TYPOGRAPHY = {
    "latin": "Arial",
    "east_asian": "Meiryo UI",
    "fallbacks": {"latin": ["Helvetica", "sans-serif"], "east_asian": ["Hiragino Sans", "Noto Sans JP", "sans-serif"]},
}
ROLE_USAGE = {
    "background": "スライド背景",
    "text": "本文",
    "text-secondary": "参考文献、図キャプション",
    "band": "ヘッダー帯・フッター帯の塗り",
    "on-band": "帯の上のスライドタイトル、日付・会議名・ページ番号",
    "category": "帯の右上のカテゴリラベル（BACKGROUND など）",
    "emphasis": "表紙タイトル、セクションタイトル、キーメッセージ、Takeaway",
    "accent": "表紙のアクセントライン、セクション扉の縦バー",
    "section-label": "セクション扉の「01 / SECTION」",
    "rule": "キーメッセージ下の区切り線",
    "placeholder-bg": "図プレースホルダーの塗り",
    "placeholder-border": "図プレースホルダーの枠線",
    "placeholder-text": "図プレースホルダーの文字",
}
WORD_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)*$")
HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


class DeriveError(Exception):
    pass


@dataclass(frozen=True)
class Seed:
    key: str  # base / accent / sub
    word: str  # 色名（例: brown）
    hex: str

    @property
    def tone(self) -> float:
        return cl.tone(self.hex)

    @property
    def name(self) -> str:
        return f"{self.word}-{cl.round_half_up(self.tone)}"

    @property
    def label(self) -> str:
        return f"{tl.SEED_JA[self.key]} `{self.name}`"


def parse_seed(key: str, text: str) -> Seed:
    """'brown=#70372C' を読む。"""
    word, sep, hex_part = text.partition("=")
    word = word.strip().lower()
    hex_part = hex_part.strip()
    if not sep or not WORD_RE.match(word) or not HEX_RE.match(hex_part):
        raise DeriveError(f"--{key} は 色名=#RRGGBB の形で指定してください（例: brown=#70372C）: {text!r}")
    return Seed(key, word, "#" + hex_part.lstrip("#").upper())


def seed_word(name: str) -> str:
    """palette 名 'sea-green-61' → 色名 'sea-green'。"""
    m = re.match(r"^(?P<word>.+)-[0-9]+$", name)
    return m["word"] if m else name


# --------------------------------------------------------------------------- 導出


class _Palette:
    def __init__(self) -> None:
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.prefix: Dict[str, str] = {}  # note の前半（色の説明）

    def add(self, name: str, hex_color: str, derived: Optional[Dict[str, Any]], prefix: str) -> str:
        if name in self.entries:
            if self.entries[name]["hex"] != hex_color:
                raise DeriveError(f"palette 名 {name!r} が別の色と重複しました（{self.entries[name]['hex']} / {hex_color}）")
            return name
        entry: Dict[str, Any] = {"hex": hex_color}
        if derived is not None:
            entry["derived"] = derived
        self.entries[name] = entry
        self.prefix[name] = prefix
        return name


def _from_seed(palette: _Palette, seed: Seed, tone: int, reason: str) -> str:
    derived = {"from": seed.name, "tone": tone}
    hex_color = tl.derived_hex(palette.entries, derived)
    return palette.add(f"{seed.word}-{tone}", hex_color, derived, f"{seed.name} の色相で明度 {tone}（{reason}）")


def _nearest_passing_tone(palette: _Palette, seed: Seed, against: str, minimum: float) -> int:
    """seed の色相のまま、against に対して minimum 以上になる、seed の明度に最も近い整数の明度。"""
    t0 = cl.round_half_up(seed.tone)
    for d in range(1, 101):
        for t in (t0 - d, t0 + d):
            if 0 <= t <= 100:
                hex_color = tl.derived_hex(palette.entries, {"from": seed.name, "tone": t})
                if cl.contrast_ratio(hex_color, against) >= minimum:
                    return t
    raise DeriveError(f"{seed.label} の色相では、{against} に対して {minimum}:1 を満たす明度がありません")


def derive_theme(
    theme_id: str,
    slug: str,
    name: str,
    seeds: Dict[str, Seed],
    root: Path = tl.ROOT,
    source: Optional[str] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """theme.json の内容と、標準出力用の報告を返す。"""
    specs = tl.role_specs_from_schema(tl.load_schema(root))

    def minimum(role: str) -> float:
        return tl.THRESHOLDS[specs[role].kind]

    base, accent, sub = seeds["base"], seeds["accent"], seeds["sub"]
    if len({s.name for s in seeds.values()}) != 3:
        raise DeriveError("種色の palette 名（色名-明度）が重複しています。色名を変えてください")
    palette = _Palette()
    for seed in (base, accent, sub):
        palette.add(seed.name, seed.hex, None, f"種色（{tl.SEED_JA[seed.key]}）")
    palette.add("white", WHITE, None, "白（固定）")
    report: List[str] = []
    notes: List[str] = [
        f"種色: ベース `{base.name}`（{base.hex}）、アクセント `{accent.name}`（{accent.hex}）、サブ `{sub.name}`（{sub.hex}）。"
        "それ以外の色は scripts/derive.py が種色から導出した（palette の derived が由来。手順は README「配色の作り方」）。"
    ]

    roles: Dict[str, str] = {}
    neutral: Dict[int, str] = {}
    for tone in sorted(set(NEUTRAL_TONES.values())):
        derived = {"from": base.name, "tone": tone, "chroma": NEUTRAL_CHROMA}
        neutral[tone] = palette.add(
            f"neutral-{tone}", tl.derived_hex(palette.entries, derived), derived, f"ベースの色相をわずかに混ぜたグレー、明度 {tone}"
        )

    roles["background"] = "white"
    roles["text"] = neutral[NEUTRAL_TONES["text"]]
    roles["text-secondary"] = neutral[NEUTRAL_TONES["text-secondary"]]
    roles["band"] = base.name

    # on-band: サブ。帯の上で足りなければサブの明度を変える
    if cl.contrast_ratio(sub.hex, base.hex) >= minimum("on-band"):
        roles["on-band"] = sub.name
    else:
        t = _nearest_passing_tone(palette, sub, base.hex, minimum("on-band"))
        roles["on-band"] = _from_seed(palette, sub, t, "帯の上の文字用")
        notes.append(
            f"`on-band`: サブ `{sub.name}` は `band` に対して {tl.format_ratio(cl.contrast_ratio(sub.hex, base.hex))} のため、"
            f"同じ色相で明度 {t} の `{roles['on-band']}` を使う。"
        )

    # category: 帯と同じ色相で、帯の上で基準を満たす最も近い明度
    t = _nearest_passing_tone(palette, base, base.hex, minimum("category"))
    roles["category"] = _from_seed(palette, base, t, "帯の上のカテゴリラベル用")

    # emphasis: ベース → サブの順で、白地で基準を満たす種色
    emphasis_seed = next((s for s in (base, sub) if cl.contrast_ratio(s.hex, WHITE) >= minimum("emphasis")), None)
    if emphasis_seed is not None:
        roles["emphasis"] = emphasis_seed.name
        if emphasis_seed is not base:
            notes.append(
                f"`emphasis`: ベース `{base.name}` は白地で {tl.format_ratio(cl.contrast_ratio(base.hex, WHITE))} のため、"
                f"サブ `{sub.name}` を使う。"
            )
    else:
        t = _nearest_passing_tone(palette, base, WHITE, minimum("emphasis"))
        roles["emphasis"] = _from_seed(palette, base, t, "白地の強調用")
        notes.append(f"`emphasis`: ベースもサブも白地で基準に届かないため、ベースの色相で明度 {t} の `{roles['emphasis']}` を使う。")

    roles["accent"] = accent.name
    if cl.contrast_ratio(accent.hex, WHITE) >= minimum("section-label"):
        roles["section-label"] = accent.name
    else:
        t = _nearest_passing_tone(palette, accent, WHITE, minimum("section-label"))
        roles["section-label"] = _from_seed(palette, accent, t, "白地の文字用")
        notes.append(
            f"`section-label`: アクセント `{accent.name}` は白地で {tl.format_ratio(cl.contrast_ratio(accent.hex, WHITE))} のため、"
            f"同じ色相で明度 {t} の `{roles['section-label']}` を使う（`accent` は種色のまま）。"
        )
    roles["rule"] = max((base, accent, sub), key=lambda s: s.tone).name
    roles["placeholder-bg"] = neutral[NEUTRAL_TONES["placeholder-bg"]]
    roles["placeholder-border"] = neutral[NEUTRAL_TONES["placeholder-border"]]
    roles["placeholder-text"] = neutral[NEUTRAL_TONES["placeholder-text"]]
    roles = {role: roles[role] for role in specs}  # スキーマの順に並べる

    # ---- グラフの系列色
    primary = emphasis_seed or base
    series: List[str] = []
    skipped: List[str] = []
    for seed in [primary] + [s for s in (accent, base, sub) if s is not primary]:
        if cl.contrast_ratio(seed.hex, WHITE) >= tl.GRAPHIC_MIN:
            candidate, hex_color, how = seed.name, seed.hex, "そのまま"
        else:
            t = _nearest_passing_tone(palette, seed, WHITE, tl.GRAPHIC_MIN)
            derived = {"from": seed.name, "tone": t}
            candidate, hex_color = f"{seed.word}-{t}", tl.derived_hex(palette.entries, derived)
            how = f"白地で 3:1 になるよう明度 {t} にした色"
        chosen_hex = [palette.entries[n]["hex"] for n in series]
        closest = min(((cl.min_delta_e(hex_color, h), n) for h, n in zip(chosen_hex, series)), default=None)
        if closest is not None and closest[0][0] < tl.SERIES_MIN_DE:
            (value, vision), other = closest
            skipped.append(
                f"{seed.label}（{how} `{candidate}` {hex_color}）は `{other}` と見分けにくい"
                f"（{cl.VISION_JA[vision]}で ΔE00 {value:.1f}）ため、系列に入れていない。"
            )
            continue
        if candidate != seed.name:
            _from_seed(palette, seed, t, "グラフの系列色用")
        series.append(candidate)

    chroma = round(min(EXTRA_CHROMA_RANGE[1], max(EXTRA_CHROMA_RANGE[0], max(cl.oklch(s.hex)[1] for s in seeds.values()))), 3)
    candidates = [
        (hue, t, cl.at_tone(float(hue), float(chroma), float(t)))
        for hue in range(0, 360, EXTRA_HUE_STEP)
        for t in EXTRA_TONES
    ]

    def score(hex_color: str, chosen: List[str]) -> Tuple[bool, float]:
        cvd = min(cl.delta_e(hex_color, h, v) for h in chosen for v in cl.CVD_VISIONS)
        normal = min(cl.delta_e(hex_color, h) for h in chosen)
        return (cvd >= EXTRA_CVD_MIN, normal if cvd >= EXTRA_CVD_MIN else cvd)

    while len(series) < SERIES_COUNT:
        chosen = [palette.entries[n]["hex"] for n in series]
        hue, t, hex_color = max(candidates, key=lambda c: (score(c[2], chosen), -c[0], -c[1]))
        derived = {"hue": hue, "chroma": chroma, "tone": t}
        series.append(palette.add(f"{cl.hue_name(hue)}-{t}", hex_color, derived, f"グラフの系列色として追加（色相 {hue}°・明度 {t}）"))

    # ---- palette の並び（種色 → 白 → グレー → 種色から導出 → 追加色）と note
    uses: Dict[str, List[str]] = {}
    for role, n in roles.items():
        uses.setdefault(n, []).append(role)
    for i, n in enumerate(series):
        uses.setdefault(n, []).append(f"chart.series[{i}]")
    slots = _slots_by_hex(existing)
    entries: Dict[str, Dict[str, Any]] = {}
    keep = {s.name for s in seeds.values()}
    for n, entry in palette.entries.items():
        if n not in uses and n not in keep:
            continue
        out: Dict[str, Any] = {"hex": entry["hex"]}
        if entry["hex"] in slots and "derived" not in entry:
            out["pptx_slot"] = slots[entry["hex"]]
        if "derived" in entry:
            out["derived"] = entry["derived"]
        out["note"] = palette.prefix[n] + (f"。{', '.join(uses[n])}" if n in uses else "。どの role にも使っていない")
        entries[n] = out

    data: Dict[str, Any] = {
        "$schema": "../../schema/theme.schema.json",
        "id": theme_id,
        "slug": slug,
        "name": name,
        "status": (existing or {}).get("status", "active"),
        "source": source or (existing or {}).get("source") or "種色はユーザー指定。それ以外は scripts/derive.py で導出",
        "seeds": {key: seeds[key].name for key in tl.SEED_KEYS},
        "palette": entries,
        "roles": {role: {"color": n, "usage": ROLE_USAGE[role]} for role, n in roles.items()},
        "typography": (existing or {}).get("typography", DEFAULT_TYPOGRAPHY),
        "chart": {"status": "provisional", "series": series},
        "notes": notes,
    }

    # ---- 警告を notes に（種色の値は変えない）
    theme = tl.Theme(root / tl.THEMES_DIRNAME / f"{theme_id}-{slug}" / "theme.json", data)
    for result in tl.contrast_results(theme, specs):
        if result.is_warning:
            notes.append(f"コントラスト警告: {result.describe()}。種色の値のまま使う。")
    for sep in tl.series_separation(theme):
        if sep.is_warning:
            notes.append(f"色差の警告: {sep.describe()}。")
    notes.append(
        "chart.series は暫定案（要確認）。種色を先に並べ（白地で 3:1 未満なら明度を下げ、ほかと見分けにくければ外す）、"
        f"残りは見分けやすさで選んだ追加色（彩度 {chroma}）。"
    )
    notes.extend(skipped)
    notes.append("`rule` と `placeholder-border` は装飾として扱い、コントラスト基準の対象外とする。")

    report += _report(theme, seeds, specs)
    return data, report


def _slots_by_hex(existing: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """作り直す前の theme.json にあった pptx_slot（hex が同じ種色・白に引き継ぐ）。"""
    slots: Dict[str, str] = {}
    for entry in ((existing or {}).get("palette") or {}).values():
        if isinstance(entry, dict) and entry.get("pptx_slot") and "derived" not in entry:
            slots[entry["hex"]] = entry["pptx_slot"]
    return slots


def _report(theme: tl.Theme, seeds: Dict[str, Seed], specs: Dict[str, tl.RoleSpec]) -> List[str]:
    band = theme.role_hex()["band"]
    lines = [f"テーマ {theme.id} {theme.name}", "", "種色:"]
    for seed in seeds.values():
        on_white = cl.contrast_ratio(seed.hex, WHITE)
        verdict = "文字・線とも可" if on_white >= tl.TEXT_MIN else ("線・図形のみ可" if on_white >= tl.GRAPHIC_MIN else "文字・線とも不可")
        extra = "" if seed.key == "base" else f"、帯の上 {tl.format_ratio(cl.contrast_ratio(seed.hex, band))}"
        lines.append(f"  {tl.SEED_JA[seed.key]:6} {seed.name:16} {seed.hex}  明度 {seed.tone:5.1f}  白地 {tl.format_ratio(on_white)}（{verdict}）{extra}")
    lines += ["", "roles:"]
    hexes = theme.role_hex()
    for role, spec in theme.roles.items():
        lines.append(f"  {role:18} {spec['color']:16} {hexes[role]}")
    lines += ["", "chart.series:"]
    lines += [f"  {i + 1}. {n:16} {h}" for i, (n, h) in enumerate(zip(theme.series_names, theme.series_hex()))]
    worst = min(tl.series_separation(theme), key=lambda s: s.delta_e, default=None)
    if worst is not None:
        lines.append(f"  最小の色差: ΔE00 {worst.delta_e:.1f}（{cl.VISION_JA[worst.vision]}、{worst.i + 1} と {worst.j + 1}）")
    warnings = [n for n in theme.data["notes"] if n.startswith(("コントラスト警告", "色差の警告"))]
    lines += ["", "警告:"] + ([f"  {w}" for w in warnings] or ["  なし"])
    return lines


# --------------------------------------------------------------------------- 書き出し


def dump_theme(data: Dict[str, Any]) -> str:
    """palette と roles は 1 項目 1 行にして、差分を読みやすくする。"""

    def inline(value: Any) -> str:
        text = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        return "{ " + text[1:-1] + " }" if isinstance(value, dict) and value else text

    lines = ["{"]
    items = list(data.items())
    for idx, (key, value) in enumerate(items):
        comma = "," if idx < len(items) - 1 else ""
        k = json.dumps(key, ensure_ascii=False)
        if key in ("palette", "roles"):
            lines.append(f"  {k}: {{")
            sub = list(value.items())
            for j, (k2, v2) in enumerate(sub):
                lines.append(f"    {json.dumps(k2, ensure_ascii=False)}: {inline(v2)}{',' if j < len(sub) - 1 else ''}")
            lines.append(f"  }}{comma}")
        elif key in ("seeds", "chart"):
            lines.append(f"  {k}: {inline(value)}{comma}")
        else:
            lines.append(f"  {k}: " + json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ") + comma)
    lines.append("}")
    return "\n".join(lines) + "\n"


def readme_skeleton(data: Dict[str, Any]) -> str:
    """新しいテーマの README.md のひな形（プレビュー区間は build.py が埋める）。"""
    seeds = "、".join(f"{tl.SEED_JA[k]} = `{data['seeds'][k]}`" for k in tl.SEED_KEYS)
    return f"""# {data['id']} {data['name']}

TODO: このテーマの説明（どんな場面に向くか）。

- 種色: {seeds}
- 正本: [theme.json](theme.json)（色の値はここだけで管理する。この README には hex を書かない）
- 見本スライド: 下の[プレビュー](#プレビュー)。色見本・コントラスト比・種色の判定: リポジトリの [README のテーマ一覧](../../README.md#テーマ一覧)

## プレビュー

<!-- BEGIN GENERATED: preview -->
<!-- END GENERATED: preview -->

## 色の使い分け

TODO: 既存テーマの README をひな形に、場面ごとに使う role とルールを書く（警告のある role は特に）。

## グラフ

TODO: 系列色の使い方と注意点（見分けにくい組み合わせなど）。
"""


def _theme_dir(root: Path, theme_id: str) -> Optional[Path]:
    for d in tl.theme_dirs(root):
        m = tl.THEME_DIR_RE.match(d.name)
        if m and m["id"] == theme_id:
            return d
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="種色 3 つから theme.json を作る")
    parser.add_argument("id", help="テーマ番号（例: 03）")
    parser.add_argument("slug", nargs="?", help="slug（例: navy-red）。既存テーマを作り直すときは省略できる")
    parser.add_argument("--name", help="表示名（例: 'Navy & Red'）")
    for key in tl.SEED_KEYS:
        parser.add_argument(f"--{key}", metavar="色名=#RRGGBB", help=f"{tl.SEED_JA[key]}カラー")
    parser.add_argument("--source", help="出典（theme.json の source）")
    parser.add_argument("--force", action="store_true", help="既存の theme.json を上書きする")
    parser.add_argument("--dry-run", action="store_true", help="書き込まずに結果だけ表示する")
    parser.add_argument("--root", type=Path, default=tl.ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        theme_id = tl.normalize_theme_id(args.id)
        if not re.fullmatch(r"[0-9]{2,}", theme_id):
            raise DeriveError(f"テーマ番号は数字で指定してください: {args.id!r}")
        current_dir = _theme_dir(root, theme_id)
        existing = tl.read_json(current_dir / "theme.json") if current_dir and (current_dir / "theme.json").is_file() else None
        slug = args.slug or (existing or {}).get("slug")
        if not slug or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
            raise DeriveError("slug を指定してください（例: navy-red）")
        target = root / tl.THEMES_DIRNAME / f"{theme_id}-{slug}" / "theme.json"
        if current_dir is not None and current_dir != target.parent:
            raise DeriveError(f"番号 {theme_id} は {current_dir.name} で使われています（番号と slug は変えない）")
        if existing is not None and not args.force and not args.dry_run:
            raise DeriveError(f"{target.relative_to(root)} は既にあります。作り直すなら --force を付けてください")

        seeds: Dict[str, Seed] = {}
        for key in tl.SEED_KEYS:
            given = getattr(args, key)
            if given:
                seeds[key] = parse_seed(key, given)
            elif existing and "seeds" in existing:
                n = existing["seeds"][key]
                seeds[key] = Seed(key, seed_word(n), existing["palette"][n]["hex"])
            else:
                raise DeriveError(f"--{key} を指定してください（例: --{key} brown=#70372C）")
        name = args.name or (existing or {}).get("name")
        if not name:
            raise DeriveError("--name を指定してください（例: 'Navy & Red'）")

        data, report = derive_theme(theme_id, slug, name, seeds, root, args.source, existing)
    except (DeriveError, OSError, ValueError, KeyError) as e:
        print(f"derive: {e}", file=sys.stderr)
        return 1

    print("\n".join(report))
    if args.dry_run:
        print("\n（--dry-run: 書き込んでいません）")
        return 0
    tl.write_text(target, dump_theme(data))
    print(f"\n書き込みました: {target.relative_to(root).as_posix()}")
    readme = target.parent / "README.md"
    if not readme.exists():
        tl.write_text(readme, readme_skeleton(data))
        print(f"README のひな形を作りました: {readme.relative_to(root).as_posix()}（TODO を埋める）")
    print("次に python scripts/check.py && python scripts/build.py を実行し、テーマの README.md を書く。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

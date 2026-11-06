"""build.py / check.py / apply.py / derive.py が共有する処理（標準ライブラリのみ）。

- テーマの読み込みと、palette / roles / chart.series の hex への解決
- WCAG 2.x のコントラスト比（計算は colorlib）と、系列色どうしの色差
- このリポジトリのスキーマで使う範囲に限った JSON Schema 検証
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import colorlib as cl
from colorlib import contrast_ratio, relative_luminance  # noqa: F401（他のスクリプトから tl.* で使う）

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_RELPATH = Path("schema") / "theme.schema.json"
THEMES_DIRNAME = "themes"
DIST_DIRNAME = "dist"

THEME_DIR_RE = re.compile(r"^(?P<id>[0-9]{2,})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$")

# WCAG 2.x の基準。小さい文字 4.5:1、大きい文字（24px / 18pt 以上）と線・アイコン 3:1。
TEXT_MIN = 4.5
LARGE_MIN = 3.0
GRAPHIC_MIN = 3.0
THRESHOLDS = {"text": TEXT_MIN, "large-text": LARGE_MIN, "graphic": GRAPHIC_MIN}
CONTRAST_KINDS = ("text", "large-text", "graphic", "decorative", "surface")

# 系列色どうしの CIEDE2000 色差がこれ未満（一般色覚または色覚シミュレーションのどれか）なら警告する。
# 線やマーカーのような小さい印では差が見えにくくなるので、余裕を持たせた目安。
SERIES_MIN_DE = 10.0

SEED_KEYS = ("base", "accent", "sub")
SEED_JA = {"base": "ベース", "accent": "アクセント", "sub": "サブ"}

# 種色の基準（docs/color-theory.md）。種色は主な用途で次を満たすこと。満たさなければ代わりの色を提案する。
#   ベース: 帯の地。白か本文色（明度 TEXT_TONE）の文字に対して BAND_MIN 以上（WCAG 1.4.6 の 7:1）。
#           帯には 2 種類の文字（on-band と category）を載せるので、4.5:1 より余裕を持たせる。
#   アクセント: 線・図形。白地で 3:1 以上（WCAG 1.4.11）。
#   サブ: 帯の上の文字。ベースに対して 4.5:1 以上（WCAG 1.4.3）。
BAND_MIN = 7.0
TEXT_TONE = 15
WHITE = "#FFFFFF"

GENERIC_FONT_FAMILIES = frozenset(
    {
        "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
        "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "math", "emoji", "fangsong",
    }
)


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_text(path: Path, text: str) -> None:
    """改行を LF に固定して書く（OS によらず出力を同一にするため）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


# theme_colors.py を import すると隣に __pycache__/ ができる。生成物の比較・コピーでは無視する。
CACHE_PATTERNS = ("__pycache__", "*.pyc")


def list_files(directory: Path) -> List[Path]:
    """directory 以下のファイル（__pycache__ を除く）を並べて返す。"""
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and "__pycache__" not in p.relative_to(directory).parts and p.suffix != ".pyc"
    )


# --------------------------------------------------------------------------- themes


@dataclass(frozen=True)
class Theme:
    path: Path  # themes/<id>-<slug>/theme.json
    data: Dict[str, Any]

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def slug(self) -> str:
        return self.data["slug"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def label(self) -> str:
        return f"{self.id} {self.name}"

    @property
    def roles(self) -> Dict[str, Dict[str, str]]:
        return self.data["roles"]

    @property
    def typography(self) -> Dict[str, Any]:
        return self.data["typography"]

    @property
    def chart_status(self) -> str:
        return self.data["chart"]["status"]

    @property
    def series_names(self) -> List[str]:
        return list(self.data["chart"]["series"])

    @property
    def seeds(self) -> Dict[str, str]:
        """種色の種類（base / accent / sub）→ palette 名。"""
        return dict(self.data["seeds"])

    def palette_hex(self) -> Dict[str, str]:
        return {name: entry["hex"] for name, entry in self.data["palette"].items()}

    def role_hex(self) -> Dict[str, str]:
        palette = self.palette_hex()
        return {role: palette[spec["color"]] for role, spec in self.roles.items()}

    def series_hex(self) -> List[str]:
        palette = self.palette_hex()
        return [palette[name] for name in self.series_names]


def derived_hex(palette: Dict[str, Dict[str, Any]], derived: Dict[str, Any]) -> str:
    """palette の derived（由来）から色を計算する。derive.py と check.py で同じ計算を使う。

    from: 種色の palette 名（色相と、chroma がなければ彩度もその色から取る）。hue: OKLCH の色相（chroma 必須）。
    """
    if "from" in derived:
        _, chroma, hue = cl.oklch(palette[derived["from"]]["hex"])
        chroma = derived.get("chroma", chroma)
    else:
        hue, chroma = derived["hue"], derived["chroma"]
    return cl.at_tone(float(hue), float(chroma), float(derived["tone"]))


def theme_dirs(root: Path) -> List[Path]:
    themes_dir = root / THEMES_DIRNAME
    if not themes_dir.is_dir():
        return []
    return sorted(p for p in themes_dir.iterdir() if p.is_dir())


def load_theme(path: Path) -> Theme:
    return Theme(path=path, data=read_json(path))


def load_themes(root: Path) -> List[Theme]:
    """themes/*/theme.json を番号順に読む。妥当性は check.run_checks で確認しておくこと。"""
    return [load_theme(d / "theme.json") for d in theme_dirs(root) if (d / "theme.json").is_file()]


def find_theme(root: Path, theme_id: str) -> Optional[Theme]:
    for theme in load_themes(root):
        if theme.id == theme_id:
            return theme
    return None


def normalize_theme_id(value: str) -> str:
    """'2' → '02' のように番号を2桁以上にそろえる。"""
    value = value.strip()
    return value.zfill(2) if value.isdigit() else value


# --------------------------------------------------------------------------- role specs


@dataclass(frozen=True)
class RoleSpec:
    role: str
    kind: str  # CONTRAST_KINDS のいずれか
    against: Optional[str]  # 背景になる role（surface のときは None）
    description: str


def load_schema(root: Path) -> Dict[str, Any]:
    return read_json(root / SCHEMA_RELPATH)


def role_specs_from_schema(schema: Dict[str, Any]) -> Dict[str, RoleSpec]:
    """スキーマの roles.properties.*.x-contrast から role ごとの検査方法を読む。"""
    props = schema["properties"]["roles"]["properties"]
    specs: Dict[str, RoleSpec] = {}
    for role, prop in props.items():
        contrast = prop.get("x-contrast")
        if not isinstance(contrast, dict) or contrast.get("kind") not in CONTRAST_KINDS:
            raise ValueError(f"スキーマの roles.{role} に有効な x-contrast.kind がありません")
        kind = contrast["kind"]
        against = contrast.get("against")
        if kind == "surface":
            if against is not None:
                raise ValueError(f"スキーマの roles.{role}: surface に against は指定できません")
        elif against not in props:
            raise ValueError(f"スキーマの roles.{role}: x-contrast.against {against!r} は role ではありません")
        specs[role] = RoleSpec(role, kind, against, prop.get("description", ""))
    return specs


# --------------------------------------------------------------------------- contrast


def format_ratio(ratio: float) -> str:
    """表示用。切り捨てて、表示値が実際の比を上回らないようにする（判定は丸めずに行う）。"""
    return f"{math.floor(ratio * 100) / 100:.2f}:1"


@dataclass(frozen=True)
class ContrastResult:
    subject: str  # 表示名（role 名、または chart.series[i]）
    ack_key: str  # notes でバッククォート付きで言及されるべき名前
    fg_name: str  # palette 名
    fg_hex: str
    against: str  # 背景の role 名
    bg_hex: str
    kind: str  # text / large-text / graphic / decorative
    ratio: float
    allow_graphic_only: bool = True  # 線・図形として可でも、文字には不足な場合に注意を出すか

    @property
    def threshold(self) -> Optional[float]:
        return THRESHOLDS.get(self.kind)

    @property
    def status(self) -> str:
        """pass / fail / graphic-only（線・図形は可、小さい文字は不可） / decorative。"""
        if self.kind == "decorative":
            return "decorative"
        if self.ratio < THRESHOLDS[self.kind]:
            return "fail"
        if self.kind == "graphic" and self.allow_graphic_only and self.ratio < TEXT_MIN:
            return "graphic-only"
        return "pass"

    @property
    def is_warning(self) -> bool:
        return self.status in ("fail", "graphic-only")

    def describe(self) -> str:
        head = (
            f"`{self.subject}`（{self.fg_name} {self.fg_hex}）on `{self.against}`（{self.bg_hex}）"
            f"= {format_ratio(self.ratio)}"
        )
        status = self.status
        if status == "fail" and self.kind == "text":
            return f"{head}。小さい文字の基準 4.5:1 未満"
        if status == "fail" and self.kind == "large-text":
            return f"{head}。大きい文字の基準 3:1 未満"
        if status == "fail":
            return f"{head}。線・図形の基準 3:1 未満（線・マーカーには不向き）"
        if status == "graphic-only":
            return f"{head}。線・図形の基準 3:1 は満たすが、小さい文字には使えない（4.5:1 未満）"
        if status == "decorative":
            return f"{head}。装飾のため基準の対象外"
        return f"{head}。基準を満たす"


def contrast_results(theme: Theme, specs: Dict[str, RoleSpec]) -> List[ContrastResult]:
    """roles と chart.series のコントラストを計算する（theme は検証済みであること）。"""
    roles = theme.roles
    role_hex = theme.role_hex()
    results: List[ContrastResult] = []
    for role in roles:
        spec = specs[role]
        if spec.kind == "surface":
            continue
        assert spec.against is not None
        results.append(
            ContrastResult(
                subject=role,
                ack_key=role,
                fg_name=roles[role]["color"],
                fg_hex=role_hex[role],
                against=spec.against,
                bg_hex=role_hex[spec.against],
                kind=spec.kind,
                ratio=contrast_ratio(role_hex[role], role_hex[spec.against]),
            )
        )
    background = role_hex["background"]
    for i, (name, hex_color) in enumerate(zip(theme.series_names, theme.series_hex())):
        results.append(
            ContrastResult(
                subject=f"chart.series[{i}]",
                ack_key=name,
                fg_name=name,
                fg_hex=hex_color,
                against="background",
                bg_hex=background,
                kind="graphic",
                ratio=contrast_ratio(hex_color, background),
                allow_graphic_only=False,
            )
        )
    return results


@dataclass(frozen=True)
class SeparationResult:
    """系列色 i と j の色差（最も見分けにくい見え方で）。"""

    i: int
    j: int
    name_i: str
    name_j: str
    hex_i: str
    hex_j: str
    delta_e: float
    vision: str

    @property
    def ack_key(self) -> str:
        return self.name_j

    @property
    def is_warning(self) -> bool:
        return self.delta_e < SERIES_MIN_DE

    def describe(self) -> str:
        return (
            f"`chart.series[{self.i}]`（{self.name_i} {self.hex_i}）と `chart.series[{self.j}]`（{self.name_j} {self.hex_j}）"
            f"の色差 ΔE00 = {self.delta_e:.1f}（{cl.VISION_JA[self.vision]}）。目安 {SERIES_MIN_DE:g} 未満で見分けにくい"
        )


def series_separation(theme: Theme) -> List[SeparationResult]:
    """chart.series の全ペアについて、一般色覚と 3 種の色覚シミュレーションのうち最小の色差。"""
    names, hexes = theme.series_names, theme.series_hex()
    out: List[SeparationResult] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            value, vision = cl.min_delta_e(hexes[i], hexes[j])
            out.append(SeparationResult(i, j, names[i], names[j], hexes[i], hexes[j], value, vision))
    return out


@dataclass(frozen=True)
class SeedCheck:
    """種色 1 つの判定と、基準を満たさない場合の提案（同じ色相・彩度で明度だけを変えた色）。"""

    key: str  # base / accent / sub
    name: str
    hex: str
    ratio: float
    minimum: float
    against: str  # 何に対するコントラストか（説明）
    proposal_tone: Optional[int] = None
    proposal_hex: Optional[str] = None
    proposal_ratio: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.ratio >= self.minimum

    def describe(self) -> str:
        head = (
            f"{SEED_JA[self.key]} `{self.name}`（{self.hex}）は{self.against}に対して {format_ratio(self.ratio)}"
            f"（基準 {self.minimum:g}:1 以上）"
        )
        if self.ok:
            return head
        if self.proposal_hex is None:
            return head + "。同じ色相では基準を満たす明度がない"
        return (
            f"{head}。提案: 同じ色相で明度 {self.proposal_tone} の {self.proposal_hex}"
            f"（{format_ratio(self.proposal_ratio or 0)}）"
        )


def _base_ratio(hex_color: str) -> float:
    """帯に載せられる最良の文字（白か、明度 TEXT_TONE の本文色）とのコントラスト。"""
    y = cl.relative_luminance(hex_color)
    y_text = cl.tone_to_luminance(TEXT_TONE)
    on_white = 1.05 / (y + 0.05)
    with_text = (max(y, y_text) + 0.05) / (min(y, y_text) + 0.05)
    return max(on_white, with_text)


def nearest_tone(
    hex_color: str, ok: Callable[[str], bool], prefer: Optional[Callable[[str], bool]] = None
) -> Optional[Tuple[int, str]]:
    """hex_color の色相・彩度のまま、ok を満たす整数の明度のうち、元の明度に最も近いもの（同じ距離なら暗い方）。

    prefer があれば、それも満たす明度を優先する（なければ ok だけで選ぶ）。
    """
    _, chroma, hue = cl.oklch(hex_color)
    t0 = cl.round_half_up(cl.tone(hex_color))
    candidates = []
    for t in range(0, 101):
        candidate = cl.at_tone(hue, chroma, float(t))
        if candidate != hex_color and ok(candidate):
            preferred = prefer(candidate) if prefer is not None else True
            candidates.append((not preferred, abs(t - t0), t, candidate))
    if not candidates:
        return None
    _, _, t, candidate = min(candidates)
    return t, candidate


def seed_checks(names: Dict[str, str], hexes: Dict[str, str]) -> List[SeedCheck]:
    """種色 3 つ（種類 → palette 名 / hex）の判定と提案。

    ベースの提案は、サブが帯の上で読める側（サブが明るければ暗い側）を優先する。
    サブはベースに対して判定する。ベースに提案があるときは、提案のベースに対して判定する。
    """
    sub = hexes["sub"]
    out: List[SeedCheck] = []

    def add(key: str, fn: Callable[[str], float], minimum: float, against: str, prefer=None) -> SeedCheck:
        ratio = fn(hexes[key])
        found = None if ratio >= minimum else nearest_tone(hexes[key], lambda h: fn(h) >= minimum, prefer)
        check = SeedCheck(
            key, names[key], hexes[key], ratio, minimum, against,
            found[0] if found else None, found[1] if found else None, fn(found[1]) if found else None,
        )
        out.append(check)
        return check

    base = add("base", _base_ratio, BAND_MIN, "白か本文色の文字", lambda h: cl.contrast_ratio(sub, h) >= TEXT_MIN)
    add("accent", lambda h: cl.contrast_ratio(h, WHITE), GRAPHIC_MIN, "白地")
    band = base.proposal_hex if not base.ok and base.proposal_hex else base.hex
    add("sub", lambda h: cl.contrast_ratio(h, band), TEXT_MIN, "提案のベース（帯）" if band != base.hex else "ベース（帯）")
    return out


def seed_separation(hexes: Dict[str, str]) -> List[Tuple[str, str, float, str]]:
    """種色どうしの最小の色差（一般色覚と色覚シミュレーション）。(種類, 種類, ΔE00, 見え方)。"""
    out = []
    for i, a in enumerate(SEED_KEYS):
        for b in SEED_KEYS[i + 1 :]:
            value, vision = cl.min_delta_e(hexes[a], hexes[b])
            out.append((a, b, value, vision))
    return out


# --------------------------------------------------------------------------- fonts


def font_stack(typography: Dict[str, Any]) -> List[str]:
    """欧文 → 欧文代替 → 和文 → 和文代替 → 総称ファミリーの順に、重複を除いて並べる。

    欧文を先に置くことで、欧文は Arial、和文は Meiryo UI で表示される。
    """
    names = [
        typography["latin"],
        *typography["fallbacks"]["latin"],
        typography["east_asian"],
        *typography["fallbacks"]["east_asian"],
    ]
    specific: List[str] = []
    generic: List[str] = []
    for name in names:
        bucket = generic if name in GENERIC_FONT_FAMILIES else specific
        if name not in bucket:
            bucket.append(name)
    return specific + generic


def css_font_family(names: List[str]) -> str:
    def quote(name: str) -> str:
        if name in GENERIC_FONT_FAMILIES or re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", name):
            return name
        return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'

    return ", ".join(quote(n) for n in names)


# --------------------------------------------------------------------------- JSON Schema (subset)


class SchemaError(Exception):
    """スキーマ自体が、この検証器の対応範囲外のキーワードを使っている。"""


_SUPPORTED_KEYWORDS = frozenset(
    {
        "$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "examples", "default",
        "type", "enum", "const", "properties", "required", "additionalProperties", "propertyNames",
        "minProperties", "pattern", "minLength", "items", "minItems", "uniqueItems", "minimum", "maximum",
    }
)

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate_schema(instance: Any, schema: Dict[str, Any]) -> List[str]:
    """JSON Schema のうち、このリポジトリで使うキーワードだけを検証する。

    未対応のキーワードがスキーマにあると SchemaError を出す（黙って無視しないため）。
    `x-` で始まるキーワードは注釈として扱い、検証には使わない。
    """
    errors: List[str] = []
    _validate(instance, schema, schema, "$", errors)
    return errors


def _resolve_ref(ref: str, root: Dict[str, Any]) -> Dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix) or ref[len(prefix) :] not in root.get("$defs", {}):
        raise SchemaError(f"解決できない $ref: {ref}")
    return root["$defs"][ref[len(prefix) :]]


def _validate(value: Any, schema: Dict[str, Any], root: Dict[str, Any], path: str, errors: List[str]) -> None:
    unknown = [k for k in schema if k not in _SUPPORTED_KEYWORDS and not k.startswith("x-")]
    if unknown:
        raise SchemaError(f"未対応のスキーマキーワード {unknown} ({path})")

    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), root, path, errors)

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](value) for t in types):
            errors.append(f"{path}: 型は {'/'.join(types)} であるべきです（実際: {type(value).__name__}）")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} は {schema['enum']} のいずれかであるべきです")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: {value!r} は {schema['const']!r} であるべきです")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value!r} は {schema['minimum']} 以上であるべきです")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value!r} は {schema['maximum']} 以下であるべきです")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: 空でない文字列であるべきです")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} はパターン {schema['pattern']} に一致しません")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: 必須のキー {key!r} がありません")
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errors.append(f"{path}: キーが {schema['minProperties']} 個以上必要です")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            child = f"{path}.{key}"
            if "propertyNames" in schema:
                _validate(key, schema["propertyNames"], root, f"{path}（キー {key!r}）", errors)
            if key in props:
                _validate(item, props[key], root, child, errors)
            elif extra is False:
                errors.append(f"{path}: 想定外のキー {key!r} があります")
            elif isinstance(extra, dict):
                _validate(item, extra, root, child, errors)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 要素が {schema['minItems']} 個以上必要です")
        if schema.get("uniqueItems"):
            seen: List[Any] = []
            for item in value:
                if item in seen:
                    errors.append(f"{path}: 要素 {item!r} が重複しています")
                seen.append(item)
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{i}]", errors)


# --------------------------------------------------------------------------- misc


def md_escape(text: str) -> str:
    """Markdown の表のセル用。"""
    return text.replace("|", "\\|").replace("\n", " ")

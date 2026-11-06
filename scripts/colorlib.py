"""色の計算（標準ライブラリのみ）。

- WCAG 2.x の相対輝度とコントラスト比
- 明度（トーン）: WCAG の相対輝度から求めた CIE L*（0 = 黒、100 = 白）。
  コントラスト比は輝度だけで決まるので、トーンの差でおおよその比が分かる
  （差 40 で 3:1 以上、差 50 でほぼ 4.5:1）。
- OKLCH（Björn Ottosson の OKLab の極座標）: 色相と彩度を保ったまま明度だけを変えるのに使う。
- CIELAB（D65）と CIEDE2000 色差: 系列色の見分けやすさの目安。
- 色覚の多様性のシミュレーション: Machado, Oliveira & Fernandes (2009) の行列（程度 1.0）を線形 RGB に掛ける。
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, Tuple

RGB = Tuple[float, float, float]

# --------------------------------------------------------------------------- sRGB


def hex_to_rgb8(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _to_linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(value: float) -> int:
    c = min(1.0, max(0.0, value))
    v = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return int(math.floor(v * 255 + 0.5))


def hex_to_linear(hex_color: str) -> RGB:
    r, g, b = hex_to_rgb8(hex_color)
    return _to_linear(r), _to_linear(g), _to_linear(b)


def linear_to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{_from_linear(c):02X}" for c in rgb)


# --------------------------------------------------------------------------- WCAG


def _luminance_of_linear(rgb: RGB) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def relative_luminance(hex_color: str) -> float:
    return _luminance_of_linear(hex_to_linear(hex_color))


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------- トーン（CIE L*）

_EPSILON = 216 / 24389
_KAPPA = 24389 / 27


def luminance_to_tone(y: float) -> float:
    return 116 * y ** (1 / 3) - 16 if y > _EPSILON else y * _KAPPA


def tone_to_luminance(tone: float) -> float:
    return ((tone + 16) / 116) ** 3 if tone > 8 else tone / _KAPPA


def tone(hex_color: str) -> float:
    """明度（CIE L*、0〜100）。WCAG の相対輝度から求める。"""
    return luminance_to_tone(relative_luminance(hex_color))


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


# --------------------------------------------------------------------------- OKLab / OKLCH


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


def linear_to_oklab(rgb: RGB) -> Tuple[float, float, float]:
    r, g, b = rgb
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b  # noqa: E741
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = _cbrt(l), _cbrt(m), _cbrt(s)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_linear(lab: Tuple[float, float, float]) -> RGB:
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3  # noqa: E741
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def oklch(hex_color: str) -> Tuple[float, float, float]:
    """(L 0〜1, C, 色相 0〜360°)。"""
    L, a, b = linear_to_oklab(hex_to_linear(hex_color))
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _linear_at(ok_l: float, chroma: float, hue: float) -> RGB:
    rad = math.radians(hue)
    return oklab_to_linear((ok_l, chroma * math.cos(rad), chroma * math.sin(rad)))


def _solve_ok_l(chroma: float, hue: float, target_y: float) -> float:
    """色相・彩度を固定して、相対輝度が target_y になる OKLab の L を二分法で求める。"""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _luminance_of_linear(_linear_at(mid, chroma, hue)) < target_y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _in_gamut(rgb: RGB, eps: float = 1e-7) -> bool:
    return all(-eps <= c <= 1 + eps for c in rgb)


@lru_cache(maxsize=None)
def at_tone(hue: float, chroma: float, target_tone: float) -> str:
    """OKLCH の色相 hue・彩度 chroma で、明度（CIE L*）が target_tone になる sRGB 色。

    その明度で sRGB に収まらない彩度なら、収まる最大の彩度まで下げる（色相と明度を優先する）。
    """
    if not 0 <= target_tone <= 100:
        raise ValueError(f"トーンは 0〜100: {target_tone}")
    target_y = tone_to_luminance(target_tone)

    def rgb_for(c: float) -> RGB:
        return _linear_at(_solve_ok_l(c, hue, target_y), c, hue)

    rgb = rgb_for(chroma)
    if not _in_gamut(rgb):
        lo, hi = 0.0, chroma
        for _ in range(50):
            mid = (lo + hi) / 2
            if _in_gamut(rgb_for(mid)):
                lo = mid
            else:
                hi = mid
        rgb = rgb_for(lo)
    return linear_to_hex(rgb)


# --------------------------------------------------------------------------- CIELAB / CIEDE2000

_WHITE_D65 = (0.95047, 1.0, 1.08883)


def linear_to_lab(rgb: RGB) -> Tuple[float, float, float]:
    r, g, b = rgb
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x / _WHITE_D65[0]), f(y / _WHITE_D65[1]), f(z / _WHITE_D65[2])
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def ciede2000(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """CIEDE2000 色差（kL = kC = kH = 1）。Sharma, Wu & Dalal (2005) の式どおり。"""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hue(a: float, b: float) -> float:
        return 0.0 if a == 0 and b == 0 else math.degrees(math.atan2(b, a)) % 360

    h1p, h2p = hue(a1p, b1), hue(a2p, b2)
    d_lp, d_cp = L2 - L1, c2p - c1p
    if c1p * c2p == 0:
        d_hp = 0.0
    else:
        d_hp = h2p - h1p
        if d_hp > 180:
            d_hp -= 360
        elif d_hp < -180:
            d_hp += 360
    d_Hp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(d_hp / 2))
    l_bar, c_barp = (L1 + L2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar = (h1p + h2p + 360) / 2
    else:
        h_bar = (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    d_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_barp ** 7 / (c_barp ** 7 + 25 ** 7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_barp
    s_h = 1 + 0.015 * c_barp * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt(
        (d_lp / s_l) ** 2 + (d_cp / s_c) ** 2 + (d_Hp / s_h) ** 2 + r_t * (d_cp / s_c) * (d_Hp / s_h)
    )


# --------------------------------------------------------------------------- 色覚の多様性

# Machado, Oliveira & Fernandes (2009), severity 1.0。線形 RGB に掛ける。
_CVD_MATRICES: Dict[str, Tuple[RGB, RGB, RGB]] = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}
VISIONS = ("normal", "protan", "deutan", "tritan")
CVD_VISIONS = VISIONS[1:]
VISION_JA = {"normal": "一般色覚", "protan": "1 型色覚", "deutan": "2 型色覚", "tritan": "3 型色覚"}


def simulate_linear(rgb: RGB, vision: str) -> RGB:
    if vision == "normal":
        return rgb
    m = _CVD_MATRICES[vision]
    return tuple(min(1.0, max(0.0, row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2])) for row in m)  # type: ignore[return-value]


@lru_cache(maxsize=None)
def lab_as_seen(hex_color: str, vision: str = "normal") -> Tuple[float, float, float]:
    return linear_to_lab(simulate_linear(hex_to_linear(hex_color), vision))


def delta_e(a: str, b: str, vision: str = "normal") -> float:
    """色 a と b の CIEDE2000 色差（vision の見え方をシミュレーションした上で）。"""
    return ciede2000(lab_as_seen(a, vision), lab_as_seen(b, vision))


def min_delta_e(a: str, b: str, visions: Tuple[str, ...] = VISIONS) -> Tuple[float, str]:
    """visions のうちで最も小さい色差と、その見え方。"""
    return min((delta_e(a, b, v), v) for v in visions)


# --------------------------------------------------------------------------- 色名

# OKLCH の色相（度）の区間 → 名前。palette 名を機械的に付けるときに使う（明度は数字で表す）。
# 目安: 赤 #FF0000 = 29°、橙 #FF8000 = 53°、黄 #FFFF00 = 110°、緑 #00FF00 = 142°、
#       ティール #008080 = 195°、青 #0000FF = 264°、マゼンタ #FF00FF = 328°。
_HUE_NAMES = (
    (0, "rose"), (15, "red"), (40, "orange"), (65, "ochre"), (100, "olive"), (125, "green"),
    (175, "teal"), (220, "blue"), (285, "violet"), (315, "magenta"), (350, "rose"),
)


def hue_name(hue: float) -> str:
    name = _HUE_NAMES[0][1]
    for start, label in _HUE_NAMES:
        if hue % 360 >= start:
            name = label
    return name

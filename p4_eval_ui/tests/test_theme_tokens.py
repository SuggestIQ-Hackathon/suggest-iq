"""The dashboard must follow one theme: all colours come from ui/tokens.py, and the palette must be readable."""
import re
from pathlib import Path

import pytest

from p4_eval_ui.ui import tokens as T

UI = Path(__file__).resolve().parents[1] / "ui"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


def _lum(h):
    r, g, b = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("path", [p for p in sorted(UI.glob("*.py")) if p.name != "tokens.py"], ids=lambda p: p.name)
def test_no_hex_colours_outside_tokens(path):
    stray = HEX.findall(path.read_text())
    assert not stray, f"{path.name} hard-codes colours {stray}; add them to tokens.py or use var(--sd-*)"


def test_text_colours_meet_aa_on_surfaces():
    for fg in (T.INK, T.MUTED, T.BRAND, T.SUCCESS, T.WARNING, T.DANGER, T.INFO):
        for bg in (T.SURFACE, T.BG):
            assert contrast(fg, bg) >= 4.5, f"{fg} on {bg} = {contrast(fg, bg):.2f}"
    assert contrast(T.ON_BRAND, T.BRAND) >= 4.5 and contrast(T.ON_BRAND, T.BRAND_STRONG) >= 4.5


def test_domain_colours_meet_graphics_contrast():
    for name, c in T.DOMAIN_COLOR.items():
        for bg in (T.SURFACE, T.BG):
            assert contrast(c, bg) >= 3.0, f"{name} {c} on {bg} = {contrast(c, bg):.2f}"


def test_domain_colours_are_distinct_and_not_semantic():
    colours = list(T.DOMAIN_COLOR.values())
    assert len(set(colours)) == 4
    assert not set(colours) & {T.SUCCESS, T.WARNING, T.DANGER, T.INFO, T.BRAND}


def test_css_variables_cover_the_tokens():
    css = T.css_vars()
    for var, val in (("--sd-brand", T.BRAND), ("--sd-ink", T.INK), ("--sd-warning", T.WARNING)):
        assert f"{var}:{val}" in css

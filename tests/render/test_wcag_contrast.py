"""#459 / #480: WCAG 2.1 AA contrast guard for both light and dark themes.

The reported issue was visual — multiple text/background pairs on the
emitted site looked low-contrast. Auditing the agent badges revealed
real failures in the light theme:

  agent-cursor:   2.86:1 on light  (FAIL — needs 4.5:1)
  agent-codex:    3.33:1 on light  (FAIL)
  agent-gemini:   4.13:1 on light  (FAIL)
  agent-copilot:  4.49:1 on light  (FAIL — borderline)

The fix darkens those four light-theme text colors. These tests pin
the contrast contract for the surfaces the issue called out, computed
from the colors parsed out of the emitted stylesheet (`llmwiki/render/css.py`)
rather than from copies of them, and without running axe-core in a browser.
axe-core in CI is the right tool for an end-to-end pass; this unit test is
the per-commit guard so a CSS edit can't regress contrast silently.

#480 (merged from the former ``test_chip_contrast``): the yellow chip text
was bumped from ``#b45309`` to ``#92400e`` so it passes 4.5:1 on ``#fef3c7``;
the parametrized freshness-chip check pins that fix for every chip and theme.

# @spec: 414-tests-render-mirror
# #315
"""
from __future__ import annotations

import re

import pytest

from llmwiki.render.css import CSS

# WCAG 2.1 AA threshold for normal text (≥18pt or ≥14pt bold qualifies
# as "large" and only needs 3:1).
AA_NORMAL = 4.5
AA_LARGE = 3.0


# ─── Pure WCAG math, no deps ──────────────────────────────────────────


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rel_lum(rgb: tuple[int, int, int]) -> float:
    def _ch(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)


def _contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    fl, bl = _rel_lum(fg), _rel_lum(bg)
    lo, hi = min(fl, bl), max(fl, bl)
    return (hi + 0.05) / (lo + 0.05)


def _alpha_blend(
    fg_rgba: tuple[int, int, int, float],
    bg_rgb: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Composite an `rgba(...)` color over a solid background — what
    the browser actually renders for an `rgba()` background fill."""
    r, g, b, a = fg_rgba
    br, bg, bb = bg_rgb
    return (
        round(r * a + br * (1 - a)),
        round(g * a + bg * (1 - a)),
        round(b * a + bb * (1 - a)),
    )


# ─── Theme palette pulled from CSS ────────────────────────────────────


def _css_var(theme: str, name: str) -> str:
    """Read a `--var: #hex;` from the appropriate :root block in CSS."""
    if theme == "light":
        # The first :root block is light; second is dark via [data-theme="dark"].
        block_match = re.search(r":root\s*\{(.*?)\}", CSS, re.DOTALL)
    else:
        block_match = re.search(
            r':root\[data-theme="dark"\]\s*\{(.*?)\}', CSS, re.DOTALL
        )
    assert block_match, f"could not find :root block for theme {theme!r}"
    var_match = re.search(rf"{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{3,8}})", block_match.group(1))
    assert var_match, f"variable {name!r} not found in {theme} :root"
    return var_match.group(1)


# ─── Static text-on-bg pairs (the most prominent surfaces) ────────────


PAIRS = [
    # (theme, fg_var, bg_var, threshold, label)
    ("light", "--text", "--bg", AA_NORMAL, "body text on bg"),
    ("light", "--text-secondary", "--bg", AA_NORMAL, "secondary text on bg"),
    ("light", "--text-muted", "--bg", AA_NORMAL, "muted text on bg"),
    ("light", "--text-muted", "--bg-alt", AA_NORMAL, "muted text on bg-alt"),
    ("light", "--accent", "--bg", AA_NORMAL, "accent on bg"),
    ("light", "--accent", "--bg-card", AA_NORMAL, "accent on bg-card"),
    ("dark", "--text", "--bg", AA_NORMAL, "body text on bg"),
    ("dark", "--text-secondary", "--bg", AA_NORMAL, "secondary text on bg"),
    ("dark", "--text-muted", "--bg", AA_NORMAL, "muted text on bg"),
    ("dark", "--text-muted", "--bg-card", AA_NORMAL, "muted text on bg-card"),
    ("dark", "--accent", "--bg", AA_NORMAL, "accent on bg"),
    ("dark", "--accent", "--bg-card", AA_NORMAL, "accent on bg-card"),
]


@pytest.mark.parametrize("theme,fg_var,bg_var,thresh,label", PAIRS)
def test_palette_pair_meets_wcag_aa(
    theme: str, fg_var: str, bg_var: str, thresh: float, label: str
) -> None:
    """Each core text/accent token pair in the emitted theme palette meets its WCAG AA threshold."""
    fg = _hex_to_rgb(_css_var(theme, fg_var))
    bg = _hex_to_rgb(_css_var(theme, bg_var))
    ratio = _contrast(fg, bg)
    assert ratio >= thresh, (
        f"{theme}/{label}: contrast {ratio:.2f}:1 below WCAG AA "
        f"threshold {thresh}:1 ({fg_var} on {bg_var})"
    )


# ─── Live-CSS rule readers ────────────────────────────────────────────

_HEX6 = r"#[0-9a-fA-F]{6}"


def _rule_body(selector: str, theme: str) -> str:
    """Return the declaration block of ``selector`` for ``theme`` as emitted in the live CSS."""
    prefix = r':root\[data-theme="dark"\]\s+' if theme == "dark" else ""
    m = re.search(rf"^{prefix}{re.escape(selector)}\s*\{{([^}}]*)\}}", CSS, re.MULTILINE)
    assert m, f"could not locate {theme} rule for {selector!r} in CSS"
    return m.group(1)


def _declared_hex(selector: str, theme: str, prop: str) -> str:
    m = re.search(rf"(?<![-\w]){prop}\s*:\s*({_HEX6})", _rule_body(selector, theme))
    assert m, f"{theme} {selector}: no hex {prop} declared"
    return m.group(1)


def _declared_rgba(selector: str, theme: str) -> tuple[int, int, int, float]:
    m = re.search(
        r"(?<![-\w])background\s*:\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
        _rule_body(selector, theme),
    )
    assert m, f"{theme} {selector}: no rgba() background declared"
    r, g, b, a = m.groups()
    return int(r), int(g), int(b), float(a)


# ─── Agent badge contrast (alpha-blended bg over page bg) ─────────────

# Each agent badge in CSS has the shape
#   .agent-X { color: #FG; background: rgba(R,G,B,0.1); border-color: ... }
# and sits directly on the page bg (--bg), so the effective bg is the alpha-blend
# of the rgba over the theme's page background. Colours are read from the live CSS.
AGENTS = ["agent-claude", "agent-codex", "agent-copilot", "agent-cursor", "agent-gemini"]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("name", AGENTS)
def test_agent_badge_meets_aa(name: str, theme: str) -> None:
    """Each agent badge's emitted text colour reaches 4.5:1 on its alpha-blended background in both themes."""
    selector = f".{name}"
    fg_hex = _declared_hex(selector, theme, "color")
    page_bg = _hex_to_rgb(_css_var(theme, "--bg"))
    eff_bg = _alpha_blend(_declared_rgba(selector, theme), page_bg)
    ratio = _contrast(_hex_to_rgb(fg_hex), eff_bg)
    assert ratio >= AA_NORMAL, (
        f"{name} ({theme}): contrast {ratio:.2f}:1 < {AA_NORMAL}:1 — "
        f"text {fg_hex} on effective bg rgb{eff_bg}"
    )


# ─── Freshness chip contrast, pinned against the live CSS (#480) ──────


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("name", ["fresh-green", "fresh-yellow", "fresh-red"])
def test_freshness_chip_meets_aa(name: str, theme: str) -> None:
    """Each `.fresh-*` chip's emitted text/background pair reaches 4.5:1 in both themes.

    The yellow chip text was bumped from ``#b45309`` (4.49:1) to ``#92400e`` on ``#fef3c7``;
    this check fails if that — or any other chip — slips back under AA.
    """
    selector = f".{name}"
    fg = _declared_hex(selector, theme, "color")
    bg = _declared_hex(selector, theme, "background")
    ratio = _contrast(_hex_to_rgb(fg), _hex_to_rgb(bg))
    assert ratio >= AA_NORMAL, f"{name} ({theme}): contrast {ratio:.2f}:1 < {AA_NORMAL}:1 (fg={fg}, bg={bg})"


@pytest.mark.parametrize(
    "theme,card_bg",
    [("light", (255, 255, 255)), ("dark", None)],
)
def test_token_ratio_tier_yellow_meets_aa(theme: str, card_bg: tuple[int, int, int] | None) -> None:
    """The token-ratio yellow tier value reaches 4.5:1 on its card background in both themes."""
    fg = _declared_hex(".token-ratio-value.tier-yellow", theme, "color")
    bg = card_bg or _hex_to_rgb(_css_var("dark", "--bg-card"))
    ratio = _contrast(_hex_to_rgb(fg), bg)
    assert ratio >= AA_NORMAL, f".token-ratio-value.tier-yellow ({theme}) contrast {ratio:.2f}:1 (fg={fg})"

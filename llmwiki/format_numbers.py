"""Compact number formatting shared by token / model UI surfaces.

Kept stdlib-only and free of viz/models imports so both sides can use it
without a circular dependency (#58 DRY).
"""

from __future__ import annotations


def format_tokens(n: float) -> str:
    """Format a token count with K/M/B suffix.

    ``format_tokens(1_234_567)`` → ``"1.2M"``. Rounds to 1 decimal place
    for K/M/B ranges and to an integer for values < 1000. Negative
    values and zero return a plain number / ``"0"``.
    """
    n = int(n) if not isinstance(n, int) else n
    if n == 0:
        return "0"
    if abs(n) < 1000:
        return str(n)
    if abs(n) < 1_000_000:
        return f"{n / 1000:.1f}K"
    if abs(n) < 1_000_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1_000_000_000:.1f}B"

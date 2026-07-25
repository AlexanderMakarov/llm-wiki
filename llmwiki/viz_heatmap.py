"""GitLab/GitHub-style activity heatmap (v0.8 — closes #64, #72).

Pure-SVG, stdlib-only, built at static-site-build time. One `render_heatmap`
call returns a self-contained `<svg>` string that can be inlined anywhere —
home page aggregate, per-project page, or dropped into a standalone file for
hotlinking.

Design goals:

* **~18-month rolling window** ending at the build timestamp (extended from
  the original 365-day GitHub window so the SVG fills a normal `.container`
  width without large empty side margins). Empty days render as the lightest
  cell, not omitted — the grid is whole weeks after Sunday alignment.
* **GitHub alignment** — the first column is the Sunday of the week containing
  ``end_date - (WINDOW_DAYS - 1)``, so the grid is always whole weeks with
  the final column holding the week of the end date.
* **Five-level quantile bucketing** — the default color scale matches GitHub's
  original contributions palette but is theme-aware (see `site/style.css`
  `--heatmap-0..4` vars). Quantiles are computed over *non-zero* days only so
  a single dominant zero bucket can't collapse all the activity into one color.
* **Accessible** — root element has `role="img"` + `aria-label` summarising
  the window; every cell has a `<title>` for native browser tooltips.
* **Self-contained** — no external CSS. Colors come from CSS custom properties
  on the containing page, with inline `fill` fallbacks so the SVG still looks
  right when opened directly (no context).

Consumers:

* `build.py` calls `collect_session_counts()` once per build, then passes the
  resulting date→count mapping to `render_heatmap()` for the aggregate home
  page and once more (filtered per project) for each project page.
* Tests in `tests/test_viz_heatmap.py` lock the cell count, window bounds,
  quantile math, and a11y label in place.

Stdlib-only: uses `datetime`, `html`, `typing`, and `collections`.
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Mapping, Optional

# ─── layout constants ─────────────────────────────────────────────────────

# Cell + gap sizes follow GitHub's contribution graph almost exactly. Tweaking
# these is fine for density — the tests don't hardcode pixel values, only the
# structural properties (cell count, row count, etc.).
CELL_SIZE = 11
CELL_GAP = 2
CELL_RADIUS = 2
ROW_COUNT = 7  # Sunday (row 0) through Saturday (row 6)
LEFT_PAD = 28  # room for weekday labels
TOP_PAD = 18  # room for month labels

# Inclusive day count for the rolling window (~18 months). Chosen so the SVG
# width at CELL_SIZE=11 roughly fills a max-width 1080px content column
# (minus container + card padding) instead of floating in empty side space.
WINDOW_DAYS = 525
WINDOW_LABEL = "last 18 months"

# Five-level color scale. These are inline fallbacks for when the SVG is
# opened directly (no page CSS). The *page* CSS overrides via the
# `--heatmap-0..4` custom properties — see `build.py`'s CSS block.
_PALETTE_LIGHT = (
    "#ebedf0",  # 0 — empty / no activity
    "#9be9a8",  # 1
    "#40c463",  # 2
    "#30a14e",  # 3
    "#216e39",  # 4 — max
)

_WEEKDAY_LABELS = ("", "Mon", "", "Wed", "", "Fri", "")
_MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


# ─── data collection ──────────────────────────────────────────────────────


def collect_session_counts(
    entries: Iterable[Mapping[str, object]],
    project_slug: Optional[str] = None,
) -> dict[date, int]:
    """Aggregate session counts by UTC date.

    `entries` is any iterable of frontmatter-ish dicts — each one needs a
    `date` (YYYY-MM-DD string) and, if `project_slug` is given, a `project`
    field. Anything missing either is silently skipped.

    When `project_slug` is supplied, only entries belonging to that project
    are counted, so the same iterable can feed both the aggregate home-page
    heatmap and every per-project heatmap without a second pass over disk.
    """
    counts: Counter[date] = Counter()
    for entry in entries:
        raw_date = entry.get("date")
        if not raw_date:
            continue
        if project_slug is not None and str(entry.get("project", "")) != project_slug:
            continue
        try:
            d = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            continue
        counts[d] += 1
    return dict(counts)


# ─── window + bucketing ───────────────────────────────────────────────────


def window_bounds(end_date: date) -> tuple[date, date]:
    """Return the `(start, end)` inclusive dates for the rolling window.

    `start` is the Sunday of the week containing
    ``end_date - (WINDOW_DAYS - 1)``. This is the GitHub-style alignment
    rule — it guarantees the grid is always whole weeks and the final
    column holds the week of ``end_date``.
    """
    raw_start = end_date - timedelta(days=WINDOW_DAYS - 1)
    # Python's weekday(): Mon=0..Sun=6. We want Sunday=0 offset.
    sunday_offset = (raw_start.weekday() + 1) % 7
    start = raw_start - timedelta(days=sunday_offset)
    return start, end_date


def week_column_count(start: date, end: date) -> int:
    """How many Sunday-start week columns cover ``start..end`` inclusive."""
    days = (end - start).days + 1
    return (days + ROW_COUNT - 1) // ROW_COUNT


def compute_quantile_thresholds(counts: dict[date, int]) -> list[int]:
    """Return the four upper-bound thresholds for levels 1–4.

    Level 0 is always "zero activity". Levels 1–4 are split over the
    *non-zero* days by quantile. Returning ``[t1, t2, t3, t4]`` means:

    * count in ``(0, t1]`` → level 1
    * count in ``(t1, t2]`` → level 2
    * count in ``(t2, t3]`` → level 3
    * count in ``(t3, +inf)`` → level 4

    Quantile-of-nonzero matters (#72): if you split over *all* days, a sparse
    project drowns in zeros and everything non-zero collapses into level 4.
    """
    non_zero = sorted(v for v in counts.values() if v > 0)
    if not non_zero:
        return [1, 2, 3, 4]  # harmless defaults; no days will hit them

    distinct = set(non_zero)
    max_val = non_zero[-1]

    # Edge case: a single distinct non-zero value (e.g. every session day
    # has count 1). We want that value to bucket at LEVEL 4 — it IS the
    # peak — rather than at level 1. Setting t1=t2=t3=0 and t4=max_val
    # makes level_for() return 4 for any positive count, and 0 for zero
    # days. This is what the #72 sparse-data requirement calls out.
    if len(distinct) == 1:
        return [0, 0, 0, max_val]

    n = len(non_zero)

    def at(q: float) -> int:
        # Closest-rank quantile on a non-empty sorted list.
        idx = max(0, min(n - 1, int(round(q * (n - 1)))))
        return non_zero[idx]

    t1 = at(0.25)
    t2 = at(0.50)
    t3 = at(0.75)
    t4 = max_val
    # Ensure strict monotonicity so bucketing is well-defined even when the
    # data is highly clustered (e.g. only two distinct non-zero values).
    if t2 <= t1:
        t2 = t1 + 1
    if t3 <= t2:
        t3 = t2 + 1
    if t4 <= t3:
        t4 = t3 + 1
    return [t1, t2, t3, t4]


def level_for(count: int, thresholds: list[int]) -> int:
    """Map a day's count → a 0..4 bucket via the precomputed thresholds."""
    if count <= 0:
        return 0
    t1, t2, t3, t4 = thresholds
    if count <= t1:
        return 1
    if count <= t2:
        return 2
    if count <= t3:
        return 3
    return 4


# ─── SVG render ───────────────────────────────────────────────────────────


def render_heatmap(
    counts: dict[date, int],
    end_date: Optional[date] = None,
    title_prefix: str = "Activity",
) -> str:
    """Return a self-contained SVG string for the rolling activity heatmap.

    ``counts`` is the output of ``collect_session_counts``. ``end_date``
    defaults to today (UTC). ``title_prefix`` is used in the a11y label and
    in the per-cell tooltips.
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc).date()
    start, end = window_bounds(end_date)
    week_cols = week_column_count(start, end)

    thresholds = compute_quantile_thresholds(counts)

    # SVG outer dimensions
    inner_w = week_cols * (CELL_SIZE + CELL_GAP) - CELL_GAP
    inner_h = ROW_COUNT * (CELL_SIZE + CELL_GAP) - CELL_GAP
    total_w = LEFT_PAD + inner_w + 4
    total_h = TOP_PAD + inner_h + 4

    label = (
        f"{title_prefix} heatmap, "
        f"{start.isoformat()} to {end.isoformat()}"
    )

    parts: list[str] = [
        f'<svg class="heatmap-svg" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w}" height="{total_h}" '
        f'role="img" aria-label="{html.escape(label)}">',
        '<style>',
        '.heatmap-svg text { font: 9px system-ui, -apple-system, sans-serif; fill: var(--text-muted, #64748b); }',
        f'.heatmap-svg .l0 {{ fill: var(--heatmap-0, {_PALETTE_LIGHT[0]}); }}',
        f'.heatmap-svg .l1 {{ fill: var(--heatmap-1, {_PALETTE_LIGHT[1]}); }}',
        f'.heatmap-svg .l2 {{ fill: var(--heatmap-2, {_PALETTE_LIGHT[2]}); }}',
        f'.heatmap-svg .l3 {{ fill: var(--heatmap-3, {_PALETTE_LIGHT[3]}); }}',
        f'.heatmap-svg .l4 {{ fill: var(--heatmap-4, {_PALETTE_LIGHT[4]}); }}',
        '</style>',
    ]

    seen_months: set[tuple[int, int]] = set()
    for col in range(week_cols):
        col_date = start + timedelta(days=col * 7)
        if col_date > end:
            break
        key = (col_date.year, col_date.month)
        if key in seen_months:
            continue
        if col_date.day <= 7:
            x = LEFT_PAD + col * (CELL_SIZE + CELL_GAP)
            parts.append(
                f'<text x="{x}" y="{TOP_PAD - 6}">'
                f'{_MONTH_NAMES[col_date.month - 1]}</text>'
            )
            seen_months.add(key)

    for row, label_text in enumerate(_WEEKDAY_LABELS):
        if not label_text:
            continue
        y = TOP_PAD + row * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 1
        parts.append(f'<text x="0" y="{y}">{label_text}</text>')

    cell_count = 0
    d = start
    col = 0
    while col < week_cols:
        for row in range(ROW_COUNT):
            if d > end:
                d += timedelta(days=1)
                continue
            count = counts.get(d, 0)
            lvl = level_for(count, thresholds)
            x = LEFT_PAD + col * (CELL_SIZE + CELL_GAP)
            y = TOP_PAD + row * (CELL_SIZE + CELL_GAP)
            tip = (
                f"{title_prefix} {d.isoformat()} — "
                f"{count} session{'s' if count != 1 else ''}"
            )
            parts.append(
                f'<rect class="l{lvl}" x="{x}" y="{y}" '
                f'width="{CELL_SIZE}" height="{CELL_SIZE}" '
                f'rx="{CELL_RADIUS}" ry="{CELL_RADIUS}">'
                f'<title>{html.escape(tip)}</title>'
                f'</rect>'
            )
            cell_count += 1
            d += timedelta(days=1)
        col += 1

    parts.append('</svg>')
    return "\n".join(parts)


def render_heatmap_totals(
    counts: dict[date, int],
    *,
    unit: str = "sessions",
) -> str:
    """Muted one-line summary under a heatmap — total + busiest day."""
    total = sum(counts.values())
    if total == 0:
        return f'<p class="heatmap-totals muted">0 {html.escape(unit)}</p>'
    busiest_day, busiest_count = max(counts.items(), key=lambda kv: kv[1])
    return (
        f'<p class="heatmap-totals muted">'
        f'{total} {html.escape(unit)} · busiest {busiest_day.isoformat()}: '
        f'{busiest_count}'
        f'</p>'
    )


def day_int_counts(
    mcp_days: dict[str, dict] | None,
    field: str,
) -> dict[date, int]:
    """Convert ``mcp_days`` day buckets to ``dict[date, int]`` for heatmaps."""
    out: dict[date, int] = {}
    for d, b in (mcp_days or {}).items():
        try:
            out[date.fromisoformat(d)] = int((b or {}).get(field, 0) or 0)
        except ValueError:
            continue
    return {k: v for k, v in out.items() if v}


def mcp_day_has_signal(mcp_days: dict[str, dict] | None, field: str) -> bool:
    """True when any day bucket has a positive value for ``field``."""
    for b in (mcp_days or {}).values():
        if int((b or {}).get(field, 0) or 0) > 0:
            return True
    return False


def activity_heatmap_div(
    label: str, counts: dict[date, int], *, unit: str,
) -> str:
    """One Activity-section heatmap card (label + SVG + totals line)."""
    svg = render_heatmap(counts, title_prefix=label)
    totals = render_heatmap_totals(counts, unit=unit)
    return (
        f'    <div class="activity-heatmap">\n'
        f'      <div class="heatmap-label muted">'
        f'{html.escape(label)} · {WINDOW_LABEL}</div>\n'
        f'      {svg}\n'
        f'      {totals}\n'
        f'    </div>'
    )


def cell_count_for_window(end_date: date) -> int:
    """Compute how many cells `render_heatmap` will emit for a given
    end date. Useful for tests and layout debugging.
    """
    start, end = window_bounds(end_date)
    return (end - start).days + 1

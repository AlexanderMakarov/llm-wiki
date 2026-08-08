"""Shared synthesize CLI reporting helpers (#113).

Presentation only — harvest math and estimate cost math stay elsewhere.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: Clarifying line under the estimate Candidates block: the figure is a
#: snapshot of the wiki before this run writes new source pages.
_PENDING_SOURCES_NOTE = (
    "  note: pending sources are not yet reflected in this figure"
)


def print_candidates_pre_run(backlog: Mapping[str, Any]) -> None:
    """Print the estimate Candidates block labelled as pre-run state.

    Reuses the pre-#113 structure (counts, min-refs, distribution,
    generate-with) but frames the total as current wiki state rather than
    a forecast of what the upcoming synthesize will harvest.
    """
    print()
    if not backlog["broken_targets"]:
        print(
            "Candidates (pre-run state): 0  "
            "(no unresolved wikilinks in wiki/sources/)"
        )
        print(_PENDING_SOURCES_NOTE)
        return

    covered = backlog["covered_links"] / backlog["broken_links"]
    print(
        f"Candidates (pre-run state): {backlog['candidates']} stub(s) at "
        f"--min-refs {backlog['min_refs']}  "
        f"(closes {covered:.0%} of {backlog['broken_links']} broken link(s) "
        f"over {backlog['broken_targets']} target(s))"
    )
    shape = "  ".join(
        f"{n}:{count}" for n, count in sorted(backlog["distribution"].items())
    )
    print(f"  by --min-refs:   {shape}")
    print("  generate with:   llmwiki synth --candidates-only")
    print(_PENDING_SOURCES_NOTE)


def print_source_pages_current_state(
    *,
    pages_on_disk: int,
    sessions: int = 0,
    docs: int = 0,
    stubs: int = 0,
    other: int = 0,
) -> None:
    """Print on-disk wiki/sources/ file counts labelled as current state (#81).

    Same labelling convention as :func:`print_candidates_pre_run`: a snapshot
    of the wiki right now, not a forecast of what this estimate's run will
    write. Counts are ``.md`` files (excluding ``_``-prefixed names), split
    into sessions / docs / stubs (+ other when present) — not unique
    ``source_file`` keys.
    """
    parts = [f"{sessions} sessions", f"{docs} docs", f"{stubs} stubs"]
    if other > 0:
        parts.append(f"{other} other")
    mix = " + ".join(parts)
    print(f"Source pages (current state): {pages_on_disk} on disk ({mix})")


def print_synth_run_start(
    *,
    total: int,
    backend_name: str,
    concurrency: int | None = None,
) -> None:
    """Announce the batch size before the first page result line is printed.

    Gives the operator the scale of the run up front instead of leaving them
    to infer it from result lines as they trickle in. An empty backlog says
    so plainly rather than printing a zero.

    ``concurrency`` — how many pages the run synthesizes at once. Rendered as
    a suffix so result lines arriving out of order read as the run working in
    parallel rather than as a fault. Omitted when the caller leaves it unset.
    """
    if total <= 0:
        print("Nothing to synthesize — every source is already up to date.")
        return
    suffix = f" ({concurrency} at a time)" if concurrency is not None else ""
    print(f"Synthesizing {total} source(s) with {backend_name}{suffix}")


def print_synth_run_summary(
    *,
    synthesized: int,
    duration_s: float,
    tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Print the end-of-run summary after a successful real synthesize.

    Always prints synthesized count and wall-clock duration. Token / cost
    lines appear only when callers pass known values (leave them ``None``
    when unknown — never invent from the estimate rate card).

    Candidates are intentionally **not** printed here: ``run_harvest``
    already reports stubs written + the review command. Repeating a
    Candidates line in this summary duplicated the harvest report (#113
    smoke).
    """
    print()
    print(f"Synthesized: {synthesized}")
    print(f"Duration: {duration_s:.1f}s")
    if tokens is not None:
        print(f"Tokens: {tokens:,}")
    if cost_usd is not None:
        print(f"Cost: ${cost_usd:.4f}")

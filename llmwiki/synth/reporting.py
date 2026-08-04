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

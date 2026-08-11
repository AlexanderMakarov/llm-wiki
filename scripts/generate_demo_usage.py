#!/usr/bin/env python3
"""Generate the demo vault's MCP telemetry fixture.

The Analytics page reports how agents actually consume the wiki: how many
calls each tool served, how much it returned, and what share of calls came
back empty. A fixture with no empty calls reports a zero-hit rate of 0% for
every tool, which reads as "nothing was ever missed" rather than as "there is
no data" — so the demo has to contain realistic misses, not just hits.

Records are written to a per-process JSONL file exactly as the MCP server
writes them, and `daily.json` is then folded from those records by the
product's own rollup rather than maintained separately, so the two cannot
disagree.

Run from the repository root:

    python3 scripts/generate_demo_usage.py --dry-run
    python3 scripts/generate_demo_usage.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Running as `python3 scripts/…` puts scripts/ on sys.path, not the repo root.
sys.path.insert(0, str(REPO_ROOT))
DEMO = REPO_ROOT / "demo"
USAGE = DEMO / "usage"
SERVER_PID = 4242

# Per tool: total calls, how many returned nothing, and a typical response
# size. Zero-hit shares differ by tool on purpose — a broad query misses more
# often than a direct page read, and reporting tools cannot miss at all.
TOOLS: tuple[tuple[str, int, int, int], ...] = (
    ("wiki_query", 26, 6, 4300),
    ("wiki_search", 21, 4, 1900),
    ("wiki_read_page", 16, 2, 3600),
    ("wiki_list_sources", 7, 1, 2400),
    ("wiki_category_browse", 5, 1, 1500),
    ("wiki_dashboard", 4, 0, 900),
    ("wiki_lint", 3, 0, 1200),
)

QUERIES = {
    "wiki_query": [
        "what did I decide about adapter opt-in", "how does incremental synth work",
        "why did the topic graph fall back", "candidate review gate rationale",
        "how are key facts attributed", "what breaks when a page is merged",
        "which adapters are core", "how does search work offline",
    ],
    "wiki_search": [
        "wikilinks resolution", "static site offline", "lint severities",
        "mcp server tools", "project page aggregation", "pagination cursors",
    ],
    "wiki_read_page": [
        "wiki/concepts/WikiLinks.md", "wiki/entities/OpenClaw.md",
        "wiki/projects/llm-wiki.md", "wiki/concepts/StaticSiteGeneration.md",
    ],
    "wiki_list_sources": ["llm-wiki", "trailhead-api", "all"],
    "wiki_category_browse": ["concepts", "entities", "projects"],
    "wiki_dashboard": ["overview"],
    "wiki_lint": ["all rules"],
}

# Misses look different from hits: they are the questions the wiki could not
# answer, which is the signal the Analytics page exists to surface.
MISSES = {
    "wiki_query": [
        "how do I roll back a release", "what is the deploy checklist",
        "who owns the release process", "what is the on-call rotation",
        "how do I rotate credentials", "what is the SLA for sync",
    ],
    "wiki_search": ["kubernetes", "terraform", "oncall runbook", "postgres tuning"],
    "wiki_read_page": ["wiki/concepts/Kubernetes.md", "wiki/entities/Terraform.md"],
    "wiki_list_sources": ["infra"],
    "wiki_category_browse": ["runbooks"],
}

CALLERS = ("llm-wiki", "llm-wiki", "llm-wiki", "trailhead-api", "sensor-mesh", "dotfiles")


def records(today: datetime, days: int) -> list[dict]:
    """Spread calls over the window, weighted toward recent days."""
    out: list[dict] = []
    start = today - timedelta(days=days - 1)
    server_started = (start - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    i = 0
    for tool, calls, zero, size in TOOLS:
        hits_pool = QUERIES[tool]
        miss_pool = MISSES.get(tool, [])
        for n in range(calls):
            # Squaring the position pushes activity toward the recent end of
            # the window rather than spreading it evenly.
            frac = ((n + 1) / calls) ** 0.6
            day = start + timedelta(days=int(frac * (days - 1)))
            ts = day.replace(hour=8 + (i * 3) % 11, minute=(i * 17) % 60, second=(i * 7) % 60)
            is_miss = n < zero and miss_pool
            out.append({
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tool": tool,
                "query": (miss_pool if is_miss else hits_pool)[i % len(miss_pool if is_miss else hits_pool)],
                "hits": 0 if is_miss else 1 + (i * 3) % 6,
                "resp_bytes": 180 if is_miss else size + (i * 37) % 900,
                "duration_ms": 3 + (i * 5) % 26,
                "caller_project": CALLERS[i % len(CALLERS)],
                "caller_source": "client-root",
                "server_pid": SERVER_PID,
                "server_started": server_started,
            })
            i += 1
    out.sort(key=lambda r: r["ts"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=18, help="Window length in days")
    ap.add_argument("--today", help="Anchor date as YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = (datetime.strptime(args.today, "%Y-%m-%d").replace(tzinfo=UTC)
             if args.today else datetime.now(UTC)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = records(today, args.days)
    zero = sum(1 for r in rows if r["hits"] == 0)
    print(f"{len(rows)} records over {args.days} days · {zero} zero-hit ({zero / len(rows):.0%})")
    for tool, calls, z, _ in TOOLS:
        print(f"  {tool:24} {calls:3} calls  {z} zero-hit  {z / calls:5.0%}")

    if args.dry_run:
        print("\ndry run — nothing written")
        return 0

    started = rows[0]["server_started"].replace(":", "-")
    for old in USAGE.glob("mcp-*.jsonl"):
        old.unlink()
    out = USAGE / f"mcp-{SERVER_PID}-{started}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")

    # Fold with the product's own rollup so daily.json cannot drift from the
    # records it summarises.
    from llmwiki.usage import refresh_daily  # noqa: PLC0415 — script-local import

    daily = refresh_daily(DEMO)
    print(f"folded daily.json: {len(daily)} day(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

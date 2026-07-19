# Analytics MCP-usage + raw-docs enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface MCP-usage telemetry (calls, items returned, distinct server processes) and raw-document counts on both the global and per-project Analytics pages, and clarify the existing token/heatmap cards.

**Architecture:** `usage.py` stays pure aggregation and gains new additive fields (`items_returned` per entity-tool, `server_processes` per project). `build.py` computes `combined_totals()` + raw-doc-per-project counts once and threads slices into presentation-only renderers (`viz_tokens`, `changelog_timeline`, `render_analytics`, `render_project_page`). Numbers bake into static HTML at build time.

**Tech Stack:** Python 3.9+ stdlib only (no new deps), pytest. Design spec: `docs/superpowers/specs/2026-07-18-analytics-mcp-usage-design.md`.

## Global Constraints

- **Python floor: 3.9** — no `match`, no PEP 604 `X | Y` in runtime annotations that execute (module uses `from __future__ import annotations`, so annotations are fine as strings).
- **Stdlib only** at runtime. No new dependencies.
- **`raw/` is immutable** — read only.
- **Backward-compat:** new aggregate/rollup fields default to `0` when absent from an old `rollup.json`. Never crash on a legacy rollup.
- **Presentation degrades to empty** on missing data (existing convention: "malformed data → empty card").
- **Tests run with** `env -u LLMWIKI_ROOT python -m pytest` (the env var breaks path resolution in this repo's tests).
- **Metric naming:** the distinct-process metric is **"MCP server processes"** in all UI copy — never call it "sessions".
- **No historical code comments** ("formerly", "replaces X") — describe only the new behavior.
- **Commit messages:** no `Claude-Session`/claude.ai links.

---

## File Structure

- `llmwiki/usage.py` — extend aggregation (Tasks 1–2).
- `llmwiki/raw_docs_site.py` — add `count_docs_by_project` (Task 3).
- `llmwiki/build.py` — wire totals into build, hoist doc scan, update `render_analytics` + `render_project_page` (Tasks 4, 6, 7).
- `llmwiki/viz_tokens.py` — merge token cards, relabel heaviest (Task 5).
- `llmwiki/changelog_timeline.py` — recent-activity breakdown (Task 6).
- `tests/test_mcp_usage.py` — aggregation tests (Tasks 1–2).
- `tests/test_raw_docs_site.py` (create if absent) — doc-count test (Task 3).
- `tests/test_build_analytics.py` (create) — render tests (Tasks 5, 7).
- `tests/test_changelog_timeline.py` (existing or create) — recent-activity test (Task 6).
- `CHANGELOG.md`, `CLAUDE.md` (Log Format note) — Task 8.

---

## Task 1: usage.py — `items_returned` per entity tool

**Files:**
- Modify: `llmwiki/usage.py` (constants near top; `_empty_totals`, `aggregate`, `merge_aggregates`)
- Test: `tests/test_mcp_usage.py`

**Interfaces:**
- Produces: `ENTITY_TOOLS: frozenset[str]`; `is_entity_tool(tool: str) -> bool`. Aggregate dict gains `total_items_returned: int`, `per_tool[tool]["items_returned"]: int`, `per_project[proj]["items_returned"]: int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_usage.py — add
from llmwiki.usage import aggregate, ENTITY_TOOLS, is_entity_tool

def test_items_returned_counts_only_entity_tools():
    records = [
        {"tool": "wiki_search", "hits": 5, "caller_project": "p", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_query", "hits": 3, "caller_project": "p", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_lint", "hits": 9, "caller_project": "p", "server_pid": 1, "server_started": "s1"},   # excluded
        {"tool": "wiki_search", "hits": None, "caller_project": "p", "server_pid": 1, "server_started": "s1"},  # unknown, not counted
        {"tool": "wiki_search", "hits": 0, "caller_project": "p", "server_pid": 1, "server_started": "s1"},  # zero, not counted
    ]
    agg = aggregate(records)
    assert agg["total_items_returned"] == 8            # 5 + 3
    assert agg["per_tool"]["wiki_search"]["items_returned"] == 5
    assert agg["per_tool"]["wiki_query"]["items_returned"] == 3
    assert agg["per_tool"]["wiki_lint"]["items_returned"] == 0
    assert agg["per_project"]["p"]["items_returned"] == 8

def test_entity_tool_classification():
    assert is_entity_tool("wiki_search") is True
    assert is_entity_tool("wiki_dashboard") is False
    assert "wiki_confidence" in ENTITY_TOOLS and "wiki_sync" not in ENTITY_TOOLS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_mcp_usage.py::test_items_returned_counts_only_entity_tools -v`
Expected: FAIL (`ImportError: cannot import name 'ENTITY_TOOLS'`).

- [ ] **Step 3: Implement**

Add near the top of `llmwiki/usage.py` (after `_QUERY_KEYS`):

```python
# Tools whose result is a set of retrievable entities/answers. Only these
# contribute to "items returned" — lint/sync/lifecycle/dashboard perform an
# action or report status rather than returning corpus items.
ENTITY_TOOLS = frozenset({
    "wiki_query", "wiki_search", "wiki_list_sources", "wiki_read_page",
    "wiki_entity_search", "wiki_category_browse", "wiki_export", "wiki_confidence",
})


def is_entity_tool(tool: str) -> bool:
    return tool in ENTITY_TOOLS
```

In `_empty_totals()` add the new keys:

```python
def _empty_totals() -> dict[str, Any]:
    return {
        "total_calls": 0,
        "total_resp_bytes": 0,
        "total_items_returned": 0,
        "total_server_processes": 0,
        "per_tool": {},
        "per_project": {},
    }
```

In `aggregate()`, change the per-tool/per-project seed dicts and add the items logic. Replace the loop body's per_tool/per_project setup with:

```python
        tstat = totals["per_tool"].setdefault(
            tool, {"calls": 0, "zero_hits": 0, "resp_bytes": 0, "items_returned": 0})
        tstat["calls"] += 1
        tstat["resp_bytes"] += resp_bytes
        if hits == 0:
            tstat["zero_hits"] += 1

        pstat = totals["per_project"].setdefault(
            project, {"calls": 0, "resp_bytes": 0, "items_returned": 0, "server_processes": 0})
        pstat["calls"] += 1
        pstat["resp_bytes"] += resp_bytes

        if tool in ENTITY_TOOLS and isinstance(hits, int) and hits > 0:
            tstat["items_returned"] += hits
            pstat["items_returned"] += hits
            totals["total_items_returned"] += hits
```

In `merge_aggregates()`, add the totals and per-entry sums:

```python
    out["total_items_returned"] = (
        a.get("total_items_returned", 0) + b.get("total_items_returned", 0))
```
and in the per_tool loop seed `"items_returned": 0` and add `dst["items_returned"] += stats.get("items_returned", 0)`; in the per_project loop seed `"items_returned": 0, "server_processes": 0` and add `dst["items_returned"] += stats.get("items_returned", 0)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_mcp_usage.py -k "items_returned or entity_tool" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/usage.py tests/test_mcp_usage.py
git commit -m "feat(usage): count items_returned per entity tool (#27)"
```

---

## Task 2: usage.py — `server_processes` per project + rollup/backward-compat

**Files:**
- Modify: `llmwiki/usage.py` (`aggregate`, `merge_aggregates`)
- Test: `tests/test_mcp_usage.py`

**Interfaces:**
- Consumes: Task 1's aggregate shape.
- Produces: `per_project[proj]["server_processes"]: int` (distinct `(server_pid, server_started)`), `total_server_processes: int`. `merge_aggregates`/`combined_totals`/`load_rollup` sum them; missing keys read as 0.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_usage.py — add
from llmwiki.usage import aggregate, merge_aggregates, _empty_totals

def test_server_processes_counts_distinct_pairs():
    records = [
        {"tool": "wiki_search", "caller_project": "a", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_search", "caller_project": "a", "server_pid": 1, "server_started": "s1"},  # same proc
        {"tool": "wiki_query",  "caller_project": "a", "server_pid": 2, "server_started": "s2"},  # 2nd proc
        {"tool": "wiki_query",  "caller_project": "b", "server_pid": 3, "server_started": "s3"},
    ]
    agg = aggregate(records)
    assert agg["per_project"]["a"]["server_processes"] == 2
    assert agg["per_project"]["b"]["server_processes"] == 1
    assert agg["total_server_processes"] == 3

def test_merge_sums_server_processes_and_legacy_rollup_defaults_zero():
    live = aggregate([
        {"tool": "wiki_search", "caller_project": "a", "server_pid": 9, "server_started": "s9"},
    ])
    legacy = {  # old rollup shape: no items_returned / server_processes
        "total_calls": 2, "total_resp_bytes": 0,
        "per_tool": {"wiki_search": {"calls": 2, "zero_hits": 0, "resp_bytes": 0}},
        "per_project": {"a": {"calls": 2, "resp_bytes": 0}},
    }
    merged = merge_aggregates(legacy, live)
    assert merged["per_project"]["a"]["server_processes"] == 1   # 0 (legacy) + 1 (live)
    assert merged["per_project"]["a"]["items_returned"] == 0
    assert merged["total_server_processes"] == 1
    assert merged["total_calls"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_mcp_usage.py -k server_processes -v`
Expected: FAIL (`KeyError: 'server_processes'` or assertion error).

- [ ] **Step 3: Implement**

In `aggregate()`, before the loop add `proc_sets: dict[str, set] = {}`. Inside the loop, after updating `pstat`, add:

```python
        pid = r.get("server_pid")
        started = r.get("server_started")
        if pid is not None and started is not None:
            proc_sets.setdefault(project, set()).add((pid, started))
```

After the loop, before `return _finalize_rates(totals)`:

```python
    for proj, procs in proc_sets.items():
        pstat = totals["per_project"].setdefault(
            proj, {"calls": 0, "resp_bytes": 0, "items_returned": 0, "server_processes": 0})
        pstat["server_processes"] = len(procs)
        totals["total_server_processes"] += len(procs)
```

In `merge_aggregates()` add:

```python
    out["total_server_processes"] = (
        a.get("total_server_processes", 0) + b.get("total_server_processes", 0))
```
and in the per_project loop add `dst["server_processes"] += stats.get("server_processes", 0)` (seed already added in Task 1).

- [ ] **Step 4: Run tests**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_mcp_usage.py -v`
Expected: PASS (all, including existing rollup/compact tests — verifies backward-compat).

- [ ] **Step 5: Commit**

```bash
git add llmwiki/usage.py tests/test_mcp_usage.py
git commit -m "feat(usage): count distinct MCP server processes per project (#27)"
```

---

## Task 3: raw_docs_site — `count_docs_by_project`

**Files:**
- Modify: `llmwiki/raw_docs_site.py`
- Test: `tests/test_raw_docs_site.py` (create if absent)

**Interfaces:**
- Produces: `count_docs_by_project(files: list[RawDocFile]) -> dict[str, int]`. Project = `meta["project"]` if set, else the top folder segment, else the file stem.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_raw_docs_site.py
from pathlib import Path, PurePosixPath
from llmwiki.raw_docs_site import RawDocFile, count_docs_by_project

def _doc(rel, project=None):
    meta = {"project": project} if project else {}
    return RawDocFile(path=Path("/x"), rel=PurePosixPath(rel), meta=meta, body="")

def test_count_docs_by_project_uses_frontmatter_then_folder():
    files = [
        _doc("alpha/a.md", project="proj-x"),
        _doc("alpha/b.md", project="proj-x"),
        _doc("beta/c.md"),                 # no project → folder "beta"
        _doc("solo.md"),                   # no project, no folder → stem "solo"
    ]
    counts = count_docs_by_project(files)
    assert counts == {"proj-x": 2, "beta": 1, "solo": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_raw_docs_site.py -v`
Expected: FAIL (`ImportError: cannot import name 'count_docs_by_project'`).

- [ ] **Step 3: Implement**

Add to `llmwiki/raw_docs_site.py` (after `scan_raw_docs`):

```python
def count_docs_by_project(files: list[RawDocFile]) -> dict[str, int]:
    """Count raw documents per owning project.

    Attribution mirrors ``add_doc``: the ``project`` frontmatter field when
    present, else the top folder segment under ``raw/docs``, else the file
    stem for a bare top-level doc.
    """
    out: dict[str, int] = {}
    for f in files:
        proj = str(f.meta.get("project") or "").strip()
        if not proj:
            proj = f.rel.parts[0] if len(f.rel.parts) > 1 else f.rel.stem
        out[proj] = out.get(proj, 0) + 1
    return out
```

- [ ] **Step 4: Run test**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_raw_docs_site.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/raw_docs_site.py tests/test_raw_docs_site.py
git commit -m "feat(raw-docs): count raw documents per project (#27)"
```

---

## Task 4: build_site — compute totals once, hoist doc scan, thread params

**Files:**
- Modify: `llmwiki/build.py` (`build_site` body around lines 2542–2560; imports)

**Interfaces:**
- Consumes: `usage.combined_totals`, `raw_docs_site.count_docs_by_project`.
- Produces: `usage_totals: dict` and `docs_by_project: dict[str,int]` available before the project-page loop; passes them into `render_project_page(...)` and `render_analytics(...)` (signatures updated in Tasks 5 & 7 — this task threads the values through, defaulting to the new keyword params).

- [ ] **Step 1: Add imports** (top of `build.py`, with the other `from llmwiki...` imports)

```python
from llmwiki.usage import combined_totals as _mcp_combined_totals
```

- [ ] **Step 2: Hoist doc scan + totals above the project loop**

In `build_site`, replace the block starting at `for project, sessions in groups.items():` / `render_project_page(...)` so the doc scan and totals are computed first. The new ordering:

```python
    # Raw-doc tree + MCP usage totals are needed by both the per-project
    # pages and the analytics page, so compute them once up front.
    raw_docs_dir = raw_dir / "docs"
    doc_files = raw_docs_site.scan_raw_docs(raw_docs_dir)
    docs_by_project = raw_docs_site.count_docs_by_project(doc_files)
    usage_totals = _mcp_combined_totals(REPO_ROOT)

    for project, sessions in groups.items():
        render_project_page(
            project, sessions, out_dir,
            usage_totals=usage_totals,
            doc_count=docs_by_project.get(project, 0),
        )
    print(f"  wrote {len(groups)} project pages")

    render_projects_index(groups, out_dir)
    render_sessions_index(sources, groups, out_dir)

    docs_root = raw_docs_site.build_tree(doc_files)
    doc_entries = raw_docs_site.group_documents(doc_files)
    render_index(docs_root, doc_entries, len(doc_files), out_dir)
    render_raw(docs_root, doc_entries, len(doc_files), out_dir)
    render_recent(doc_entries, out_dir)
    render_analytics(
        groups, sources, out_dir, synthesis=synthesis,
        usage_totals=usage_totals,
        docs_by_project=docs_by_project,
    )
```

(Delete the old `raw_docs_dir = ... / doc_files = scan_raw_docs(...)` lines that were at ~2553, now hoisted.)

- [ ] **Step 3: Verify build still runs** (renderers get new kwargs in Tasks 5 & 7; add the kwargs to their signatures with defaults there. To keep this task green in isolation, temporarily nothing else is required — but run the fast import check.)

Run: `env -u LLMWIKI_ROOT python -c "import llmwiki.build"`
Expected: no error.

- [ ] **Step 4: Commit** (after Tasks 5 & 7 land the signatures — see note). For subagent execution, land Task 4 together with Task 5 & 7 signature changes in one review gate to avoid a broken intermediate. Commit:

```bash
git add llmwiki/build.py
git commit -m "feat(build): compute MCP totals + raw-doc counts once, thread to renderers (#27)"
```

> **Sequencing note for the executor:** Tasks 4, 5, 7 touch overlapping call/def sites. Execute them as one unit (add the new keyword params with safe defaults in 5 & 7 first, then the wiring in 4), then run the full suite once at the end of Task 7.

---

## Task 5: Global Analytics page — token card merge, heatmap rename, MCP section

**Files:**
- Modify: `llmwiki/viz_tokens.py` (`render_site_token_stats`)
- Modify: `llmwiki/build.py` (`render_analytics` signature + body)
- Test: `tests/test_build_analytics.py` (create)

**Interfaces:**
- Consumes: `usage_totals` (Task 1–2 shape), `docs_by_project`.
- Produces: `render_analytics(groups, all_sources, out_dir, synthesis=None, usage_totals=None, docs_by_project=None)`; `render_mcp_usage_section(usage_totals, docs_by_project, link_prefix="") -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_analytics.py
from llmwiki.build import render_mcp_usage_section

def test_mcp_section_renders_tools_and_totals():
    totals = {
        "total_calls": 12, "total_items_returned": 40, "total_server_processes": 3,
        "per_tool": {
            "wiki_search": {"calls": 8, "zero_hits": 2, "zero_hit_rate": 0.25, "resp_bytes": 0, "items_returned": 30},
            "wiki_lint":   {"calls": 4, "zero_hits": 0, "zero_hit_rate": 0.0,  "resp_bytes": 0, "items_returned": 0},
        },
        "per_project": {"proj-x": {"calls": 12, "resp_bytes": 0, "items_returned": 40, "server_processes": 3}},
    }
    html_out = render_mcp_usage_section(totals, {"proj-x": 5}, link_prefix="")
    assert "wiki_search" in html_out
    assert "Most MCP-active project" in html_out
    assert "proj-x" in html_out
    assert "40" in html_out            # items returned total
    assert "5" in html_out             # raw docs count

def test_mcp_section_empty_without_data():
    empty = {"total_calls": 0, "total_items_returned": 0, "total_server_processes": 0,
             "per_tool": {}, "per_project": {}}
    assert render_mcp_usage_section(empty, {}, link_prefix="") == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_build_analytics.py -v`
Expected: FAIL (`ImportError: cannot import name 'render_mcp_usage_section'`).

- [ ] **Step 3: Implement**

(a) In `viz_tokens.py::render_site_token_stats`, replace the two separate "Total tokens" and "Average per session" cards with one card, and relabel heaviest. Replace the `parts` seed list:

```python
    parts: list[str] = [
        '<section class="section token-stats-section">',
        '  <div class="container">',
        '    <div class="token-stat-grid">',
        f'      <div class="token-stat"><div class="token-stat-label muted">Tokens</div>'
        f'<div class="token-stat-value">{format_tokens(total)}</div>'
        f'<div class="token-stat-sub muted">{format_tokens(avg)} / session avg</div></div>',
    ]
```
and change the Heaviest label line to:
```python
            f'<div class="token-stat-label muted">Heaviest project (by tokens)</div>'
```

(b) In `build.py`, add `render_mcp_usage_section` (near `render_analytics`):

```python
def render_mcp_usage_section(
    usage_totals: dict[str, Any],
    docs_by_project: dict[str, int],
    link_prefix: str = "",
) -> str:
    """Static "Wiki usage (MCP)" block: per-tool calls/items, totals, the
    most MCP-active project, and the raw-document total. Empty string when
    there is neither telemetry nor any raw document."""
    total_calls = int(usage_totals.get("total_calls", 0) or 0)
    total_docs = sum(docs_by_project.values()) if docs_by_project else 0
    if total_calls == 0 and total_docs == 0:
        return ""

    per_tool = usage_totals.get("per_tool", {})
    rows = []
    for tool, s in sorted(per_tool.items(), key=lambda kv: -kv[1].get("calls", 0)):
        calls = int(s.get("calls", 0) or 0)
        items = int(s.get("items_returned", 0) or 0)
        items_cell = str(items) if is_entity_tool(tool) else "—"
        zhr = float(s.get("zero_hit_rate", 0.0) or 0.0)
        rows.append(
            f'<tr><td>{html.escape(tool)}</td><td>{calls}</td>'
            f'<td>{items_cell}</td><td>{zhr * 100:.0f}%</td></tr>'
        )
    table = (
        '<table class="mcp-usage-table"><thead><tr>'
        '<th>Tool</th><th>Calls</th><th>Items returned</th><th>Zero-hit rate</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    ) if rows else ""

    per_project = usage_totals.get("per_project", {})
    most_active = ""
    if per_project:
        slug, s = max(per_project.items(), key=lambda kv: kv[1].get("calls", 0))
        if s.get("calls", 0):
            most_active = (
                f'<a class="token-stat" href="{link_prefix}projects/{html.escape(slug)}.html">'
                f'<div class="token-stat-label muted">Most MCP-active project</div>'
                f'<div class="token-stat-value">{int(s.get("calls", 0))}</div>'
                f'<div class="token-stat-sub muted">{html.escape(slug)} · calls</div></a>'
            )
    total_items = int(usage_totals.get("total_items_returned", 0) or 0)
    total_procs = int(usage_totals.get("total_server_processes", 0) or 0)
    summary = (
        '<div class="token-stat-grid">'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP calls</div>'
        f'<div class="token-stat-value">{total_calls}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Items returned</div>'
        f'<div class="token-stat-value">{total_items}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP server processes</div>'
        f'<div class="token-stat-value">{total_procs}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Raw documents</div>'
        f'<div class="token-stat-value">{total_docs}</div></div>'
        f'{most_active}'
        '</div>'
    )
    return (
        '<section class="section mcp-usage-section"><div class="container">'
        '<h2>Wiki usage (MCP)</h2>'
        '<p class="muted">Lifetime MCP tool usage, as of last build.</p>'
        f'{summary}{table}'
        '</div></section>'
    )
```

Ensure `is_entity_tool` is imported in `build.py`:
```python
from llmwiki.usage import combined_totals as _mcp_combined_totals, is_entity_tool
```

(c) Update `render_analytics` signature and body. Signature:
```python
def render_analytics(
    groups, all_sources, out_dir, synthesis=None,
    usage_totals=None, docs_by_project=None,
):
```
Rename the heatmap label string `"Activity · last 365 days"` → `"Agents Activity · last 365 days"` and `title_prefix="Activity"` → `title_prefix="Agents Activity"`. Insert the MCP section into `body` (e.g. right after `token_stats_block`):
```python
    mcp_block = render_mcp_usage_section(
        usage_totals or {}, docs_by_project or {}, link_prefix="")
```
and add `{mcp_block}` into the `body` f-string after `{token_stats_block}`.

- [ ] **Step 4: Run tests**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_build_analytics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (with Task 4 & 7 — see sequencing note)

```bash
git add llmwiki/build.py llmwiki/viz_tokens.py tests/test_build_analytics.py
git commit -m "feat(analytics): MCP usage section, merged token card, Agents Activity heatmap (#27)"
```

---

## Task 6: Recent-activity breakdown

**Files:**
- Modify: `llmwiki/changelog_timeline.py` (`render_recent_activity`)
- Modify: `CLAUDE.md` (Log Format note — enriched `Processed:` convention)
- Test: `tests/test_changelog_timeline.py` (create if absent)

**Interfaces:**
- Consumes: `LogEvent.details["Processed"]` string.
- Produces: renderer shows the `Processed` value verbatim when it is non-numeric (a breakdown like `2 Claude · 1 Cursor · 0 docs`); shows `"N processed"` when purely numeric; falls back to `ev.title` when absent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_changelog_timeline.py
from datetime import date
from types import SimpleNamespace
from llmwiki.changelog_timeline import render_recent_activity

def _ev(processed=None, title="t", op="sync"):
    details = {"Processed": processed} if processed is not None else {}
    return SimpleNamespace(date=date(2026, 7, 18), operation=op, title=title, details=details)

def test_recent_activity_numeric_vs_breakdown():
    out = render_recent_activity([_ev(processed="3"), _ev(processed="2 Claude · 1 Cursor · 0 docs")])
    assert "3 processed" in out
    assert "2 Claude · 1 Cursor · 0 docs" in out
    assert "2 Claude · 1 Cursor · 0 docs processed" not in out   # breakdown shown verbatim
```

- [ ] **Step 2: Run to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_changelog_timeline.py -k recent_activity -v`
Expected: FAIL (`... processed` appended to the breakdown).

- [ ] **Step 3: Implement**

In `render_recent_activity`, replace the `right_label` computation:

```python
        processed = ev.details.get("Processed") if hasattr(ev, "details") else None
        if processed is not None and str(processed).strip():
            p = str(processed).strip()
            right_label = f"{p} processed" if p.isdigit() else p
        else:
            right_label = ev.title
        full_label = ev.title if processed else right_label
```

In `CLAUDE.md`, under `## Log Format`, add one line documenting the enriched detail:
```
The `Processed:` detail may carry a short producer breakdown instead of a bare
count, e.g. `- Processed: 2 Claude · 1 Cursor · 0 docs`, which the Analytics
"Recent activity" widget renders verbatim.
```

- [ ] **Step 4: Run test**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_changelog_timeline.py -k recent_activity -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/changelog_timeline.py CLAUDE.md tests/test_changelog_timeline.py
git commit -m "feat(analytics): recent-activity shows producer breakdown (#27)"
```

---

## Task 7: Per-project Analytics block

**Files:**
- Modify: `llmwiki/build.py` (`render_project_page`)
- Test: `tests/test_build_analytics.py`

**Interfaces:**
- Consumes: `usage_totals` (full combined totals), `doc_count: int`.
- Produces: `render_project_page(project_slug, sessions, out_dir, usage_totals=None, doc_count=0)`; `render_project_usage_block(project_slug, usage_totals, doc_count) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_analytics.py — add
from llmwiki.build import render_project_usage_block

def test_project_usage_block_shows_project_slice():
    totals = {"per_project": {"proj-x": {"calls": 7, "items_returned": 20, "server_processes": 2, "resp_bytes": 0}},
              "per_tool": {}}
    out = render_project_usage_block("proj-x", totals, doc_count=4)
    assert "7" in out and "20" in out and "2" in out and "4" in out
    assert "MCP server processes" in out

def test_project_usage_block_empty_without_data():
    totals = {"per_project": {}, "per_tool": {}}
    assert render_project_usage_block("proj-x", totals, doc_count=0) == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/test_build_analytics.py -k project_usage -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement**

Add to `build.py`:

```python
def render_project_usage_block(
    project_slug: str, usage_totals: dict[str, Any], doc_count: int
) -> str:
    """Per-project stats: raw-doc count + MCP calls / items / server processes.
    Empty when the project has neither raw docs nor telemetry."""
    p = (usage_totals or {}).get("per_project", {}).get(project_slug, {})
    calls = int(p.get("calls", 0) or 0)
    items = int(p.get("items_returned", 0) or 0)
    procs = int(p.get("server_processes", 0) or 0)
    if calls == 0 and doc_count == 0:
        return ""
    return (
        '<section class="section project-usage-section"><div class="container">'
        '<div class="token-stat-grid">'
        f'<div class="token-stat"><div class="token-stat-label muted">Raw documents</div>'
        f'<div class="token-stat-value">{int(doc_count)}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP calls</div>'
        f'<div class="token-stat-value">{calls}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP items returned</div>'
        f'<div class="token-stat-value">{items}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP server processes</div>'
        f'<div class="token-stat-value">{procs}</div></div>'
        '</div></div></section>'
    )
```

Update `render_project_page` signature to `(project_slug, sessions, out_dir, usage_totals=None, doc_count=0)`. Build the block and insert it into the page body (near the top, after the breadcrumbs/heatmap — pick the existing `body`/`page` assembly and add `{usage_block}`):
```python
    usage_block = render_project_usage_block(project_slug, usage_totals or {}, doc_count)
```

- [ ] **Step 4: Run the full suite**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/ -q`
Expected: PASS (all prior + new).

- [ ] **Step 5: Commit** (unit with Tasks 4 & 5 per sequencing note)

```bash
git add llmwiki/build.py tests/test_build_analytics.py
git commit -m "feat(analytics): per-project MCP + raw-doc stats block (#27)"
```

---

## Task 8: CHANGELOG + site rebuild + full verification

**Files:**
- Modify: `CHANGELOG.md`
- Generated: `site/` (rebuild)

- [ ] **Step 1: Add CHANGELOG entry** (top of the unreleased/next section)

```
- Analytics pages surface MCP usage (calls, items returned, distinct MCP
  server processes) per tool and per project, plus raw-document counts;
  merged the token summary card, relabeled "Heaviest project (by tokens)",
  renamed the activity heatmap to "Agents Activity", and added a "Most
  MCP-active project" card and a producer breakdown to Recent activity (#27).
```

- [ ] **Step 2: Full test run**

Run: `env -u LLMWIKI_ROOT python -m pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 3: Rebuild the static site** (hard rule #6)

Run: `env -u LLMWIKI_ROOT python -m llmwiki build`
Expected: exit 0; `site/analytics.html` contains "Wiki usage (MCP)" or "Agents Activity" (verify with grep).

Verify: `grep -l "Agents Activity" site/analytics.html`

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for Analytics MCP-usage enrichment (#27)"
```

(Do not commit `site/` unless the repo tracks it — check `git status`; it is a generated artifact and typically gitignored.)

---

## Self-Review (completed by planner)

- **Spec coverage:** A (Tasks 1–2), B (Tasks 4–6), C (Task 7), D (Task 4), E (all tasks + Task 8). Corpus-cost dollar figure explicitly out of scope per spec. ✓
- **Naming:** distinct-process metric labeled "MCP server processes" everywhere (Tasks 5, 7). ✓
- **Type consistency:** aggregate keys (`items_returned`, `server_processes`, `total_items_returned`, `total_server_processes`) identical across Tasks 1, 2, 5, 7. `render_mcp_usage_section` / `render_project_usage_block` / `count_docs_by_project` signatures match their call sites in Task 4. ✓
- **Backward-compat:** legacy-rollup test in Task 2 asserts missing keys read as 0. ✓

"""Synthesize cost-estimate report — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 ``synthesize_estimate_report`` lived inside ``cli.py``. The
function is non-trivial business logic (G-07 / #293 cost-model walk)
that belongs next to the rest of the synth pipeline.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import synthesize_estimate_report`` import path keeps
working for any test or caller that reached for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import is_headless as _is_headless
from llmwiki._frontmatter import is_subagent as _is_subagent
from llmwiki.agent_label import detect_agent_label
from llmwiki.cache import (
    CACHE_WRITE_1H_MULTIPLIER,
    DEFAULT_MODEL,
    MODEL_PRICING,
    TRANSCRIPT_CHARS_PER_TOKEN,
    estimate_tokens,
    resolve_pricing_model,
)
from llmwiki.config_schedule import _load_sessions_config

# ─── Measured per-call constants for the `claude` CLI backend ──────────
#
# The pre-#57 model priced an Anthropic API-style call: a stable prefix
# (CLAUDE.md + wiki/index.md + wiki/overview.md) written to cache once and
# re-read on every later page. The `claude` CLI backend does none of that.
# It never sends index.md or overview.md, and every page is a separate
# process, so there is no prefix to re-read. Numbers below are measured via
# `claude --output-format json`; see docs/reference/synthesis-cost.md.

# What each invocation costs before the prompt is added. Lean mode strips
# tool schemas, MCP servers, skills, CLAUDE.md, and the agent system prompt;
# what is left is framing Claude Code always injects.
LEAN_OVERHEAD_TOKENS = 890
# Without lean mode: the full coding-agent context. Varies with how many MCP
# servers and skills the user has configured — this is a mid-range figure,
# not a ceiling.
FULL_AGENT_OVERHEAD_TOKENS = 35_000
# Non-lean repeat calls re-read about half the scaffolding from the prompt
# cache and re-write the other half (measured: 17,544 read / 17,790 written).
NON_LEAN_CACHE_READ_FRACTION = 0.5
# Typical completion for one source page. Measured across 29 real sessions:
# mean 1,372, spread 902-2,554. (A clean demo session returns ~800; real
# transcripts carry more claims and quotes, so they generate more page.)
DEFAULT_OUTPUT_TOKENS = 1400
# claude_cli.py truncates every body to this many characters before sending,
# so anything past it is never billed.
BODY_CHAR_CAP = 8000


def _rendered_template_tokens(wiki_sources_dir: Any | None = None) -> int:
    """Tokens in the prompt template as actually sent, vocabulary included.

    The `{vocabulary}` block is expanded from the wiki's canonical topics
    and grows with the wiki, so a fixed figure would drift. Falls back to
    the un-expanded template if the wiki can't be read — an estimate that
    is slightly low beats one that raises.
    """

    tmpl_path = Path(__file__).resolve().parent / "prompts" / "source_page.md"
    try:
        template = tmpl_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    try:
        from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
            WIKI_SOURCES,
            _inject_vocabulary,
        )

        wiki_dir = (
            Path(wiki_sources_dir).parent
            if wiki_sources_dir is not None
            else WIKI_SOURCES.parent
        )
        template = _inject_vocabulary(template, wiki_dir)
    except (OSError, UnicodeDecodeError, ValueError, AttributeError):
        pass
    # The body/meta placeholders are replaced by content counted separately.
    for token in ("{body}", "{meta}"):
        template = template.replace(token, "")
    return estimate_tokens(template, TRANSCRIPT_CHARS_PER_TOKEN)


def synthesize_estimate_report(
    *,
    raw_sessions: list[tuple[Any, dict, str]] | None = None,
    state_keys: set[str] | Mapping[str, float] | None = None,
    prefix_tokens: int | None = None,
    output_tokens_per_call: int = DEFAULT_OUTPUT_TOKENS,
    model: str | None = None,
    wiki_sources_dir: Any | None = None,
    raw_root: Any | None = None,
    docs_root: Any | None = None,
    pricing_table: dict[str, dict[str, float]] | None = None,
    include_subagents: str | None = None,
    exclude_headless: bool | None = None,
    lean: bool = True,
    template_tokens: int | None = None,
) -> dict:
    """Compute the incremental vs full-force cost report (G-07 · #293).

    Prices what the ``claude`` CLI backend actually sends per page:
    per-call scaffolding + the rendered prompt template (including the
    injected topic vocabulary) + the body, truncated to
    ``BODY_CHAR_CAP`` as ``claude_cli.py`` truncates it. There is no
    shared cached prefix — each page is a separate process — so cost
    scales linearly with page count.

    Returns a plain dict so the CLI can render it AND tests can inspect
    the numbers without parsing stdout. Keys:

    * ``corpus`` — total raw sessions discovered under ``raw/sessions/``
    * ``synthesized`` — eligible sources the next non-force ``synth`` would
      skip (same state+mtime+pending predicate as the run; #163)
    * ``new`` — ``corpus - synthesized``
    * ``incremental_usd`` — dollars to synthesize the ``new`` bucket
    * ``full_force_usd`` — dollars to re-synthesize the **whole** corpus
      with ``--force`` (N x the per-page cost)
    * ``prefix_tokens`` — fixed per-call overhead in tokens (scaffolding
      + rendered prompt template), i.e. what every page pays before its
      own body
    * ``overhead_tokens`` / ``template_tokens`` — that figure split into
      its agent-scaffolding and prompt-template halves
    * ``lean`` — whether lean-mode scaffolding stripping was assumed
    * ``model`` — model id used for pricing
    * ``warnings`` — list of human-readable warnings
    * ``unsynth_items`` — list of unsynthesized session descriptors
    * ``source_pages_on_disk`` — count of ``.md`` files under ``wiki/sources/``
      (excluding ``_``-prefixed names), from one ``scan_wiki_sources_disk`` pass
    * ``source_page_stubs`` / ``source_pages_sessions`` / ``source_pages_docs`` —
      exclusive file-category subsets of that same scan
    * ``pipeline_rows[*].on_disk`` — per-row file counts; Stubs/Other rows
      carry on-disk only

    ``state_keys`` accepts a full ``{rel: mtime}`` map (preferred) or a bare
    set of rels (tests: each key is treated as fresh enough for any mtime).

    Any of the args can be injected for tests; the default reads from
    disk and is what the CLI invokes.
    """
    from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
        _DOC_CHUNK_MAX_CHARS,
        _chunk_markdown,
        _discover_raw_docs,
        _discover_raw_sessions,
        _load_state,
        page_is_stub,
        page_needs_topics_rewrite,
        scan_wiki_sources_disk,
        source_page_paths,
        source_synth_is_done,
        synth_page_filename,
    )
    from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
        RAW_DOCS as _RAW_DOCS_DEFAULT,
    )
    from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
        RAW_SESSIONS as _RAW_DEFAULT,
    )
    from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
        WIKI_SOURCES as _WIKI_SOURCES,
    )

    chosen_model = model or DEFAULT_MODEL
    rates_table = pricing_table or MODEL_PRICING
    try:
        chosen_model = resolve_pricing_model(chosen_model, rates_table)
    except ValueError:
        chosen_model = resolve_pricing_model(DEFAULT_MODEL, rates_table)
    warnings: list[str] = []

    # The prompt template is sent verbatim on every call, and the topic
    # vocabulary injected into it grows with the wiki — so measure the
    # rendered article rather than assuming a fixed size.
    if template_tokens is None:
        template_tokens = _rendered_template_tokens(wiki_sources_dir)
    overhead_tokens = (
        LEAN_OVERHEAD_TOKENS if lean else FULL_AGENT_OVERHEAD_TOKENS
    )
    # `prefix_tokens` keeps its name (persisted state and the site widget
    # read it) but now means what every page pays before its own body.
    if prefix_tokens is None:
        prefix_tokens = overhead_tokens + template_tokens
    if not lean:
        warnings.append(
            "synthesis.claude_lean is off: every page re-sends the full agent "
            f"context (~{FULL_AGENT_OVERHEAD_TOKENS:,} tok of tool schemas, MCP "
            "servers, skills, and CLAUDE.md that synthesis cannot use)."
        )

    if raw_sessions is None:
        raw_sessions = _discover_raw_sessions()
    # #30: in "only-raw" (the default), subagent transcripts live in raw/ but
    # are not synthesis backlog — the parent session's synthesis already covers
    # them. Drop them from the whole estimate so `new`, `unsynth_items`, and
    # full-force cost all reflect the sessions actually eligible for synthesis.
    from llmwiki.synth.pipeline import (  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
        DEFAULT_INCLUDE_SUBAGENTS,
        INCLUDE_SUBAGENTS_MODES,
    )
    mode = (include_subagents or DEFAULT_INCLUDE_SUBAGENTS)
    if mode not in INCLUDE_SUBAGENTS_MODES:
        mode = DEFAULT_INCLUDE_SUBAGENTS
    excluded_subagents = 0
    if mode == "only-raw":
        before = len(raw_sessions)
        raw_sessions = [
            (p, m, b) for (p, m, b) in raw_sessions
            if not _is_subagent(m if isinstance(m, dict) else {}, p)
        ]
        excluded_subagents = before - len(raw_sessions)
    # #8 follow-up: a headless run is the wiki's own machinery talking to an
    # agent CLI, so synthesizing it pays to summarize our own output — and
    # every synthesis pass manufactures more of them. `exclude_headless`
    # blocks them at ingest; drop any that predate the filter here too, so
    # the estimate and `synthesize` agree on what is eligible.
    from llmwiki.synth.pipeline import resolve_exclude_headless  # noqa: PLC0415 — cycle: synth.pipeline↔synth.estimate
    if exclude_headless is None:
        drop_headless = resolve_exclude_headless(_load_sessions_config())
    else:
        drop_headless = bool(exclude_headless)
    excluded_headless = 0
    if drop_headless:
        before = len(raw_sessions)
        raw_sessions = [
            (p, m, b) for (p, m, b) in raw_sessions
            if not _is_headless(m if isinstance(m, dict) else {})
        ]
        excluded_headless = before - len(raw_sessions)
    sources_root = Path(wiki_sources_dir) if wiki_sources_dir is not None else _WIKI_SOURCES
    raw_root_path = Path(raw_root) if raw_root is not None else _RAW_DEFAULT
    docs_root_path = Path(docs_root) if docs_root is not None else _RAW_DOCS_DEFAULT
    # Map each eligible raw session's source_file key → agent label/css so
    # on-disk wiki/sources pages (which omit agent:) join correctly (#81 C1).
    agent_by_source: dict[str, tuple[str, str]] = {}
    for p, _meta, _body in raw_sessions:
        meta = _meta if isinstance(_meta, dict) else {}
        name = getattr(p, "name", str(p))
        if hasattr(p, "relative_to"):
            try:
                source_rel = str(p.relative_to(raw_root_path))
            except (ValueError, AttributeError):
                source_rel = name
        else:
            source_rel = name
        source_key = ("raw/sessions/" + source_rel).replace("\\", "/")
        agent_by_source[source_key] = detect_agent_label(meta)
    # One wiki/sources walk: stub keys mark backlog (#24). File-category
    # counts (On disk column + CLI snapshot) reuse this same scan — counts
    # are .md files, not unique source_file keys.
    disk_scan = scan_wiki_sources_disk(
        sources_root, agent_by_source=agent_by_source
    )
    stub_source_keys = set(disk_scan["stub_keys"])
    if state_keys is None:
        state: dict[str, float] = _load_state()
    elif isinstance(state_keys, Mapping):
        state = {str(k): float(v) for k, v in state_keys.items()}
    else:
        # Bare set (unit tests): membership alone means fresh enough.
        state = {str(k): float("inf") for k in state_keys}

    corpus = len(raw_sessions)

    # Done = the run's skip predicate (state + mtime + not pending), shared via
    # source_synth_is_done (#163). Pages on disk alone are not enough.
    # #py-m10 (#596): single-pass walk. The previous version walked
    # raw_sessions twice — once to bucket new vs synthesised + collect
    # body strings, once via a list comprehension to materialise the
    # full-force body list — and then ran estimate_tokens(body) twice
    # on each new session inside _bucket_usd. On a 5k-corpus that's
    # 10k token-estimate calls + 2 full body materialisations in RAM.
    # The pass below computes per-session tokens once, accumulates
    # both bucket totals incrementally, and never holds more than one
    # body string at a time.
    synthed_sessions = 0
    new_sessions = 0
    synthed_docs = 0
    new_docs = 0
    incremental_usd = 0.0
    full_force_usd = 0.0
    unsynth_items: list[dict[str, Any]] = []
    # Per-agent (sessions) + Documents row for the Home state widget.
    # Keys are display labels from detect_agent_label; docs use "Documents".
    pipeline_buckets: dict[str, dict[str, Any]] = {}

    def _bucket(label: str, *, kind: str, css: str = "") -> dict[str, Any]:
        row = pipeline_buckets.get(label)
        if row is None:
            row = {
                "id": label.lower().replace(" ", "-"),
                "label": label,
                "kind": kind,
                "css": css,
                "raw": 0,
                "synthesized": 0,
                "pending": 0,
                "next_usd": 0.0,
                "on_disk": 0,
            }
            pipeline_buckets[label] = row
        return row

    def _body_tokens(text: str) -> int:
        """Tokens actually billed for one body — the backend truncates first."""
        return estimate_tokens(
            (text or "")[:BODY_CHAR_CAP], TRANSCRIPT_CHARS_PER_TOKEN
        )

    def _page_usd(body_tokens: int, *, first: bool) -> float:
        """Dollars for one page: overhead + template + body in, completion out.

        Input is billed at the 1-hour cache-*write* rate, not the fresh input
        rate — Claude Code writes every prompt into the cache. The run-stable
        half (the template + its topic vocabulary) rides in the system
        prompt, which the CLI does re-read across invocations: it is written
        once on the first page of a run and read at 0.1x on every page after.
        The body half is unique per page and never re-read.

        Without lean mode the scaffolding is large and stable enough that
        repeat calls also re-read roughly half of it.
        """
        rates = rates_table[chosen_model]
        write_rate = rates["input"] * CACHE_WRITE_1H_MULTIPLIER
        # Cached prefix: full write on page 1, cache read thereafter.
        prefix_rate = write_rate if first else rates["cached_input"]
        billable = template_tokens * prefix_rate + body_tokens * write_rate
        if lean:
            billable += overhead_tokens * (write_rate if first else rates["cached_input"])
        else:
            read = overhead_tokens * NON_LEAN_CACHE_READ_FRACTION
            billable += (
                read * rates["cached_input"] + (overhead_tokens - read) * write_rate
            )
        return (
            billable + output_tokens_per_call * rates["output"]
        ) / 1_000_000

    # The cached prefix is written once per *run*, so the two buckets count
    # their own first call: a full re-synth pays the write on its first page,
    # an incremental run pays it on the first new page.
    call_counts = {"ff": 0, "inc": 0}

    def _ff_usd(body_tokens: int) -> float:
        """Cost of one page in the full-force bucket."""
        cost = _page_usd(body_tokens, first=call_counts["ff"] == 0)
        call_counts["ff"] += 1
        return cost

    def _inc_usd(body_tokens: int) -> float:
        """Cost of one page in the incremental bucket."""
        cost = _page_usd(body_tokens, first=call_counts["inc"] == 0)
        call_counts["inc"] += 1
        return cost

    # Lazy import — estimate is imported from CLI paths that may not need
    # the full build module until this walk runs.

    for p, _meta, body in raw_sessions:
        meta = _meta if isinstance(_meta, dict) else {}
        agent_label, agent_css = detect_agent_label(meta)
        name = getattr(p, "name", str(p))
        source_rel = ""
        if hasattr(p, "relative_to"):
            try:
                source_rel = str(p.relative_to(raw_root_path))
            except (ValueError, AttributeError):
                source_rel = name
        else:
            source_rel = name
        source_key = "raw/sessions/" + source_rel

        filename = synth_page_filename(meta, getattr(p, "stem", name))
        project = str(meta.get("project") or getattr(getattr(p, "parent", None), "name", "unknown"))
        # #24 / #147: stub or topics-stale pages stay pending — same probes as
        # the run (source_page_paths + stub keys).
        targets = source_page_paths(
            sources_root / project, filename, is_doc=False
        )
        page_is_pending = (
            source_key in stub_source_keys
            or any(page_is_stub(t) for t in targets)
            or any(page_needs_topics_rewrite(t) for t in targets)
        )
        try:
            raw_mtime = float(Path(p).stat().st_mtime)
        except (OSError, TypeError, ValueError):
            # Tests inject Path-ish stubs without a real filesystem path.
            raw_mtime = 0.0
        matched = source_synth_is_done(
            source_rel,
            state,
            raw_mtime,
            force=False,
            page_is_pending=page_is_pending,
        )
        body_tokens = _body_tokens(body)
        # Full-force bucket: every session contributes regardless of state.
        ff_cost = _ff_usd(body_tokens)
        full_force_usd += ff_cost
        row = _bucket(agent_label, kind="session", css=agent_css)
        row["raw"] += 1
        # Incremental bucket: only un-synthesised sessions contribute.
        if matched:
            synthed_sessions += 1
            row["synthesized"] += 1
        else:
            new_sessions += 1
            inc_cost = _inc_usd(body_tokens)
            incremental_usd += inc_cost
            row["pending"] += 1
            row["next_usd"] += inc_cost
            project = str(meta.get("project") or getattr(getattr(p, "parent", None), "name", "unknown"))
            mtime_iso = ""
            try:
                mtime_iso = datetime.fromtimestamp(
                    Path(p).stat().st_mtime, tz=UTC
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (OSError, TypeError, ValueError):
                # Tests inject Path-ish stubs without a real filesystem path.
                pass
            unsynth_items.append(
                {
                    "rel": source_rel,
                    "project": project,
                    "source_file": source_key,
                    "mtime": mtime_iso,
                    "is_doc": False,
                    "agent": agent_label,
                    "usd": round(inc_cost, 6),
                }
            )

    # Docs estimate path — mirrors synth pipeline inclusion rules.
    docs_row = _bucket("Documents", kind="docs", css="agent-docs")
    for p, meta, body in _discover_raw_docs(docs_root_path):
        rel = "docs::" + str(p.relative_to(docs_root_path))
        source_key = "raw/docs/" + str(p.relative_to(docs_root_path))
        project = str(meta.get("project") or "docs")
        filename = synth_page_filename(meta, p.stem)
        chunks = _chunk_markdown(body, _DOC_CHUNK_MAX_CHARS)
        out_dir = sources_root / project
        # Pages this doc owns come from disk, exactly as the synth run resolves them.
        # A doc with no pages yet has nothing to probe and stays pending.
        expected = source_page_paths(out_dir, filename, is_doc=True)
        page_is_pending = (
            source_key in stub_source_keys
            or any(page_is_stub(ep) for ep in expected)
            or any(page_needs_topics_rewrite(ep) for ep in expected)
        )
        try:
            raw_mtime = float(Path(p).stat().st_mtime)
        except (OSError, TypeError, ValueError):
            raw_mtime = 0.0
        matched = source_synth_is_done(
            rel,
            state,
            raw_mtime,
            force=False,
            page_is_pending=page_is_pending,
        )
        # An oversized doc is written as one page per chunk, and each page is
        # its own `claude` call — so it is billed per chunk, not per doc.
        chunk_tokens = [_body_tokens(c) for c in chunks] or [0]
        ff_cost = sum(_ff_usd(t) for t in chunk_tokens)
        full_force_usd += ff_cost
        docs_row["raw"] += 1
        if matched:
            synthed_docs += 1
            docs_row["synthesized"] += 1
        else:
            new_docs += 1
            inc_cost = sum(_inc_usd(t) for t in chunk_tokens)
            incremental_usd += inc_cost
            docs_row["pending"] += 1
            docs_row["next_usd"] += inc_cost
            mtime_iso = ""
            try:
                mtime_iso = datetime.fromtimestamp(
                    Path(p).stat().st_mtime, tz=UTC
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (OSError, TypeError, ValueError):
                pass
            unsynth_items.append(
                {
                    "rel": rel,
                    "project": project,
                    "source_file": source_key,
                    "mtime": mtime_iso,
                    "is_doc": True,
                    "agent": "Documents",
                    "usd": round(inc_cost, 6),
                }
            )

    # Merge on-disk file counts into agent / Documents buckets (stubs exclusive).
    for label, info in disk_scan["files_by_agent"].items():
        css = str(info.get("css") or "")
        row = _bucket(label, kind="session", css=css)
        if css and not row.get("css"):
            row["css"] = css
        row["on_disk"] = int(info.get("count") or 0)
    docs_row["on_disk"] = int(disk_scan["files_docs"] or 0)

    files_total = int(disk_scan["files_total"] or 0)
    files_stubs = int(disk_scan["files_stubs"] or 0)
    files_sessions = int(disk_scan["files_sessions"] or 0)
    files_docs = int(disk_scan["files_docs"] or 0)
    files_other = int(disk_scan["files_other"] or 0)

    # Session agents first (most pending, then label); Documents last when present.
    # Include a row when the eligible corpus OR the on-disk file column is non-zero.
    session_rows = [
        row
        for row in pipeline_buckets.values()
        if row["kind"] == "session"
        and (int(row["raw"]) > 0 or int(row.get("on_disk") or 0) > 0)
    ]
    session_rows.sort(
        key=lambda r: (-int(r["pending"]), -int(r["raw"]), -int(r.get("on_disk") or 0), str(r["label"]))
    )
    docs_rows = [
        row
        for row in pipeline_buckets.values()
        if row["kind"] == "docs"
        and (int(row["raw"]) > 0 or int(row.get("on_disk") or 0) > 0)
    ]
    pipeline_rows = session_rows + docs_rows
    # Stubs row only when present (on-disk only; input columns blank in widget).
    # Mirror the Other-row guard so an empty vault keeps rows=[] for onboarding.
    if files_stubs > 0:
        pipeline_rows.append(
            {
                "id": "stubs",
                "label": "Stubs",
                "kind": "stubs",
                "css": "",
                "raw": 0,
                "synthesized": 0,
                "pending": 0,
                "next_usd": 0.0,
                "on_disk": files_stubs,
            }
        )
    if files_other > 0:
        pipeline_rows.append(
            {
                "id": "other",
                "label": "Other",
                "kind": "other",
                "css": "",
                "raw": 0,
                "synthesized": 0,
                "pending": 0,
                "next_usd": 0.0,
                "on_disk": files_other,
            }
        )
    for row in pipeline_rows:
        row["next_usd"] = round(float(row["next_usd"]), 6)
        row["on_disk"] = int(row.get("on_disk") or 0)

    return {
        "corpus": corpus + synthed_docs + new_docs,
        "corpus_sessions": corpus,
        "corpus_docs": synthed_docs + new_docs,
        "synthesized": synthed_sessions + synthed_docs,
        # What the eligibility policy removed before any costing — so
        # `--estimate` can show that `synthesize` will skip these too.
        "excluded_subagents": excluded_subagents,
        "excluded_headless": excluded_headless,
        "include_subagents": mode,
        "exclude_headless": drop_headless,
        "synthesized_sessions": synthed_sessions,
        "synthesized_docs": synthed_docs,
        "new": new_sessions + new_docs,
        "new_sessions": new_sessions,
        "new_docs": new_docs,
        "incremental_usd": incremental_usd,
        "full_force_usd": full_force_usd,
        "prefix_tokens": prefix_tokens,
        # The two halves of prefix_tokens, so the CLI can show where the
        # fixed per-page cost comes from.
        "overhead_tokens": overhead_tokens,
        "template_tokens": template_tokens,
        "output_tokens_per_call": output_tokens_per_call,
        "lean": lean,
        "model": chosen_model,
        "warnings": warnings,
        "unsynth_items": unsynth_items,
        "pipeline_rows": pipeline_rows,
        "pipeline_stages": ["raw", "synthesized"],
        "source_pages_on_disk": files_total,
        "source_page_stubs": files_stubs,
        "source_pages_sessions": files_sessions,
        "source_pages_docs": files_docs,
        "source_pages_other": files_other,
    }

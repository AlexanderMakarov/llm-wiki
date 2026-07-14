"""Synthesize cost-estimate report — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 ``synthesize_estimate_report`` lived inside ``cli.py``. The
function is non-trivial business logic (G-07 / #293 cost-model walk)
that belongs next to the rest of the synth pipeline.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import synthesize_estimate_report`` import path keeps
working for any test or caller that reached for it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from llmwiki import REPO_ROOT


def synthesize_estimate_report(
    *,
    raw_sessions: Optional[list[tuple[Any, dict, str]]] = None,
    state_keys: Optional[set[str]] = None,
    prefix_tokens: Optional[int] = None,
    output_tokens_per_call: int = 1000,
    model: Optional[str] = None,
    synthesized_source_keys: Optional[set[str]] = None,
    wiki_sources_dir: Optional[Any] = None,
    raw_root: Optional[Any] = None,
    docs_root: Optional[Any] = None,
    pricing_table: Optional[dict[str, dict[str, float]]] = None,
) -> dict:
    """Compute the incremental vs full-force cost report (G-07 · #293).

    Returns a plain dict so the CLI can render it AND tests can inspect
    the numbers without parsing stdout. Keys:

    * ``corpus`` — total raw sessions discovered under ``raw/sessions/``
    * ``synthesized`` — count already synthesized (from state file)
    * ``new`` — ``corpus - synthesized``
    * ``incremental_usd`` — dollars to synthesize the ``new`` bucket
    * ``full_force_usd`` — dollars to re-synthesize the **whole** corpus
      with ``--force`` (one cache write + N-1 cache hits)
    * ``prefix_tokens`` — tokens in the stable CLAUDE.md + index.md +
      overview.md prefix
    * ``model`` — model id used for pricing
    * ``warnings`` — list of human-readable warnings (e.g. prefix too
      small to be cached)
    * ``unsynth_items`` — list of unsynthesized session descriptors

    Any of the args can be injected for tests; the default reads from
    disk and is what the CLI invokes.
    """
    from llmwiki.cache import (
        MODEL_PRICING,
        DEFAULT_MODEL,
        resolve_pricing_model,
        estimate_tokens,
        warn_prefix_too_small,
    )
    from pathlib import Path as _Path
    from llmwiki.synth.pipeline import (
        RAW_SESSIONS as _RAW_DEFAULT,
        RAW_DOCS as _RAW_DOCS_DEFAULT,
        WIKI_SOURCES as _WIKI_SOURCES,
        _DOC_CHUNK_MAX_CHARS,
        _chunk_markdown,
        _discover_raw_docs,
        _discover_raw_sessions,
        _load_state,
        discover_stub_source_keys,
        discover_synth_source_keys,
        page_is_stub,
        synth_page_filename,
    )

    chosen_model = model or DEFAULT_MODEL
    rates_table = pricing_table or MODEL_PRICING
    try:
        chosen_model = resolve_pricing_model(chosen_model, rates_table)
    except ValueError:
        chosen_model = resolve_pricing_model(DEFAULT_MODEL, rates_table)
    warnings: list[str] = []

    if prefix_tokens is None:
        prefix_parts: list[str] = []
        for rel in ("CLAUDE.md", "wiki/index.md", "wiki/overview.md"):
            p = REPO_ROOT / rel
            if p.is_file():
                prefix_parts.append(p.read_text(encoding="utf-8"))
        prefix_tokens = estimate_tokens("\n".join(prefix_parts))
    prefix_warning = warn_prefix_too_small(prefix_tokens)
    if prefix_warning:
        warnings.append(prefix_warning)

    if raw_sessions is None:
        raw_sessions = _discover_raw_sessions()
    discovered_source_keys = (
        synthesized_source_keys
        if synthesized_source_keys is not None
        else discover_synth_source_keys()
    )
    sources_root = _Path(wiki_sources_dir) if wiki_sources_dir is not None else _WIKI_SOURCES
    # #24: a source whose page is a stub is backlog. The page names its own
    # source, so this holds for pages a derived filename would not find.
    stub_source_keys = discover_stub_source_keys(sources_root)
    raw_root_path = _Path(raw_root) if raw_root is not None else _RAW_DEFAULT
    docs_root_path = _Path(docs_root) if docs_root is not None else _RAW_DOCS_DEFAULT
    if state_keys is None:
        state_keys = set(_load_state().keys())

    corpus = len(raw_sessions)

    # The real synth state stores rel-paths under ``raw/sessions/``
    # (e.g. ``proj/2026-04-09-slug.md``). Match against those first;
    # fall back to bare filename + suffix-endswith for tests that
    # inject simpler keys. A session counts as "synthesized" if any
    # of those three keys already appears in state_keys.
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
    incremental_first = True
    full_force_first = True
    unsynth_items: list[dict[str, Any]] = []

    def _add_to_bucket(fresh_tokens: int, first: bool) -> tuple[float, bool]:
        """Return (cost, was_first?). Cost-of-this-call uses cache_hit=
        not first, mirroring the old _bucket_usd semantics."""
        rates = rates_table[chosen_model]
        prefix_rate = rates["cached_input"] if not first else rates["cache_write"]
        usd = (
            prefix_tokens * prefix_rate
            + fresh_tokens * rates["input"]
            + output_tokens_per_call * rates["output"]
        ) / 1_000_000
        return usd, False  # second-and-later calls hit the cache

    for p, _meta, body in raw_sessions:
        meta = _meta if isinstance(_meta, dict) else {}
        keys_to_try: set[str] = set()
        name = getattr(p, "name", str(p))
        keys_to_try.add(name)
        if hasattr(p, "relative_to"):
            try:
                keys_to_try.add(str(p.relative_to(raw_root_path)))
            except (ValueError, AttributeError):
                pass
        keys_to_try.add(str(p))
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
        out_path = sources_root / project / f"{filename}.md"
        # #24: a stub page (dummy filler / pending sentinel) is not synthesis —
        # its source stays in the backlog no matter what the state file says.
        output_is_stub = source_key in stub_source_keys or page_is_stub(out_path)
        output_exists = out_path.is_file() and not output_is_stub

        matched = not output_is_stub and (
            bool(keys_to_try & state_keys)
            or any(isinstance(k, str) and k.endswith(name) for k in state_keys)
            or source_key in discovered_source_keys
            or output_exists
        )
        body_tokens = estimate_tokens(body)
        # Full-force bucket: every session contributes regardless of state.
        ff_cost, full_force_first = _add_to_bucket(body_tokens, full_force_first)
        full_force_usd += ff_cost
        # Incremental bucket: only un-synthesised sessions contribute.
        if matched:
            synthed_sessions += 1
        else:
            new_sessions += 1
            inc_cost, incremental_first = _add_to_bucket(
                body_tokens, incremental_first
            )
            incremental_usd += inc_cost
            project = str(meta.get("project") or getattr(getattr(p, "parent", None), "name", "unknown"))
            mtime_iso = ""
            try:
                mtime_iso = datetime.fromtimestamp(
                    _Path(p).stat().st_mtime, tz=timezone.utc
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
                }
            )

    # Docs estimate path — mirrors synth pipeline inclusion rules.
    for p, meta, body in _discover_raw_docs(docs_root_path):
        rel = "docs::" + str(p.relative_to(docs_root_path))
        source_key = "raw/docs/" + str(p.relative_to(docs_root_path))
        project = str(meta.get("project") or "docs")
        filename = synth_page_filename(meta, p.stem)
        chunks = _chunk_markdown(body, _DOC_CHUNK_MAX_CHARS)
        out_dir = sources_root / project
        expected = (
            [out_dir / f"{filename}.md"]
            if len(chunks) <= 1
            else [out_dir / f"{filename}--part-{i:02d}.md" for i in range(1, len(chunks) + 1)]
        )
        output_is_stub = source_key in stub_source_keys or any(page_is_stub(ep) for ep in expected)
        output_exists = all(ep.is_file() for ep in expected) and not output_is_stub
        matched = not output_is_stub and (
            rel in state_keys or source_key in discovered_source_keys or output_exists
        )
        body_tokens = estimate_tokens(body)
        ff_cost, full_force_first = _add_to_bucket(body_tokens, full_force_first)
        full_force_usd += ff_cost
        if matched:
            synthed_docs += 1
        else:
            new_docs += 1
            inc_cost, incremental_first = _add_to_bucket(body_tokens, incremental_first)
            incremental_usd += inc_cost
            mtime_iso = ""
            try:
                mtime_iso = datetime.fromtimestamp(
                    _Path(p).stat().st_mtime, tz=timezone.utc
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
                }
            )

    return {
        "corpus": corpus + synthed_docs + new_docs,
        "corpus_sessions": corpus,
        "corpus_docs": synthed_docs + new_docs,
        "synthesized": synthed_sessions + synthed_docs,
        "synthesized_sessions": synthed_sessions,
        "synthesized_docs": synthed_docs,
        "new": new_sessions + new_docs,
        "new_sessions": new_sessions,
        "new_docs": new_docs,
        "incremental_usd": incremental_usd,
        "full_force_usd": full_force_usd,
        "prefix_tokens": prefix_tokens,
        "model": chosen_model,
        "warnings": warnings,
        "unsynth_items": unsynth_items,
    }

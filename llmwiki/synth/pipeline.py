"""Synthesis pipeline — orchestrates auto-ingest from raw → wiki (v0.5 · #36).

The main entry point is `synthesize_new_sessions()` which:

1. Scans `raw/sessions/` for markdown files
2. Compares against an mtime state file to find NEW files since the last run
3. For each new file, calls the configured synthesizer backend to produce
   a wiki source page
4. Writes `wiki/sources/<slug>.md` with proper frontmatter
5. Updates the mtime state file so re-runs are a no-op
6. Appends to `wiki/log.md`

Idempotency: the pipeline uses `.llmwiki-synth-state.json` (same pattern
as the converter's `.llmwiki-state.json`) to track which files have been
synthesized. Re-running on an unchanged tree is a sub-second no-op.
"""

from __future__ import annotations

import glob
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

# #py-m1 (#587) / #arch-h5 (#610): import directly from _frontmatter
# instead of via build.py. The build module pulls in 145+ transitive
# imports; the parser sits cleanly in _frontmatter.py with no deps.
from llmwiki._frontmatter import is_headless, is_subagent, parse_frontmatter
from llmwiki.agent_label import detect_agent_label
from llmwiki.candidates import apply_review_summary_to_pipeline
from llmwiki.config_schedule import _load_sessions_config

# Same matcher the graph builder uses, so "a link" means the same thing to
# the de-duplicator and to the thing that consumes the links.
from llmwiki.graph import WIKILINK_RE
from llmwiki.reindex import reindex_wiki
from llmwiki.state_store import mtime_from_state, mtime_to_iso
from llmwiki.state_store import read_state as _read_unified_state
from llmwiki.state_store import resolve_state_file as _resolve_state_file
from llmwiki.state_store import update_state as _update_unified_state
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer
from llmwiki.synth.claude_cli import (
    DEFAULT_CLAUDE_TIMEOUT,
    ClaudeCLISynthesizer,
)
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.ollama import OllamaSynthesizer, load_ollama_config
from llmwiki.tags import TagEntry, near_duplicate_tags
from llmwiki.topics import build_topic_graph

# G-21 (#307): shell- and URL-unsafe chars we scrub from slugs at
# synthesize-time. Spaces → hyphens; filesystem-reserved + Windows-
# unsafe chars → hyphens; collapse repeats.
_SLUG_UNSAFE = re.compile(r'[\s/\\:*?"<>|]+')
_SLUG_DASH_RUN = re.compile(r"-{2,}")


def _normalise_slug(raw: str) -> str:
    """Return a URL-safe + shell-safe slug. Preserves case + unicode.

    Examples:
      ``"00 - Master Framework Index"`` → ``"00-Master-Framework-Index"``
      ``"path/with/slashes"``            → ``"path-with-slashes"``
      ``"weird:chars<here>"``            → ``"weird-chars-here"``
    """
    if not raw:
        return "unknown"
    # Defensive: callers occasionally pass non-strings (e.g. a YAML-parsed
    # numeric slug). Never raise from a slug normaliser.
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = _SLUG_UNSAFE.sub("-", raw)
    # Collapse runs of consecutive dashes so "00 - X" doesn't become
    # "00---X" — consecutive hyphens are ugly in URLs and filesystems.
    cleaned = _SLUG_DASH_RUN.sub("-", cleaned).strip("-")
    return cleaned or "unknown"


# Machine-generated filler pages: the dummy backend's canned body and the
# agent-delegate pending sentinel. Real synthesized pages contain neither.
_STUB_MARKERS = ("<!-- llmwiki-pending:", "Auto-synthesized from session")


def _is_stub_page(text: str) -> bool:
    """True when a page body is machine-generated filler (dummy stub or
    pending sentinel) rather than real synthesis output."""
    return any(marker in text for marker in _STUB_MARKERS)


def synth_page_filename(meta: dict[str, Any], fallback_stem: str) -> str:
    """Filename stem (no extension) of the wiki source page for a raw file.

    Single slug scheme for the whole pipeline: the estimate report, the
    stub detector and the writer all resolve a raw file to the same
    ``wiki/sources/<project>/<filename>.md`` target. YAML parses
    numeric-looking session slugs (``15824711``, ``6051e147``) as
    int/float, so a non-string slug falls back to the filename stem.
    """
    raw_slug = meta.get("slug", fallback_stem)
    if not isinstance(raw_slug, str):
        raw_slug = fallback_stem
    slug = _normalise_slug(raw_slug)
    date = str(meta.get("date", "")).strip()
    return f"{date}-{slug}" if date else slug


def page_is_stub(page_path: Path) -> bool:
    """True when ``page_path`` exists and its body is machine-generated filler.

    A stub page holds a slot in ``wiki/sources/`` without carrying any
    synthesis, so backlog discovery counts its source as UNSYNTHESIZED (#24).

    A page that cannot be read or decoded cannot be shown to be filler, so it
    is not one — and it must not take down the run that walks past it.
    """
    try:
        text = Path(page_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    _meta, body = parse_frontmatter(text)
    return _is_stub_page(body)


def source_page_paths(
    out_dir: Path, filename: str, *, is_doc: bool
) -> list[Path]:
    """Every page on disk that ``filename`` synthesizes into, under ``out_dir``.

    An oversized doc is written as ``<filename>--part-NN.md`` chunks rather
    than one page, and the parts are complementary: each holds a slice of the
    doc and none stands for the whole. The parts are found by looking at what
    is on disk, not by re-deriving them from the doc body, so they are found
    whatever chunk size wrote them (#24). Sessions are never chunked.
    """
    paths: list[Path] = []
    single = out_dir / f"{filename}.md"
    if single.is_file():
        paths.append(single)
    if is_doc:
        paths.extend(sorted(out_dir.glob(f"{glob.escape(filename)}--part-*.md")))
    return paths


def resolve_backend(
    cfg: dict[str, Any] | None = None,
) -> BaseSynthesizer:
    """Pick a synthesizer backend from ``cfg["synthesis"]["backend"]``.

    Supported values:
      - ``"dummy"`` (default) — canned offline backend for previews/tests
      - ``"ollama"`` — local Ollama HTTP backend (#35)
      - ``"claude"`` — synchronous ``claude -p`` CLI calls (#16).
        Optional keys: ``claude_path``, ``claude_model``,
        ``claude_timeout``, ``claude_lean``.

    Unknown values fall back to the dummy backend with a warning so a
    typo in config.json doesn't crash sync.
    """
    synth_cfg = (cfg or {}).get("synthesis", {}) or {}
    name = (synth_cfg.get("backend") or "dummy").strip().lower()

    if name == "ollama":
        return OllamaSynthesizer(config=load_ollama_config(cfg))

    if name == "claude":
        # Deliberately NOT the shared `timeout` key: that one belongs to the
        # Ollama block, and reading it here meant a 60s Ollama default
        # silently capped every claude page at 60s instead of 180s.
        return ClaudeCLISynthesizer(
            claude_path=synth_cfg.get("claude_path"),
            model=synth_cfg.get("claude_model") or "sonnet",
            timeout=int(synth_cfg.get("claude_timeout") or DEFAULT_CLAUDE_TIMEOUT),
            lean=synth_cfg.get("claude_lean", True) is not False,
            effort=str(synth_cfg.get("claude_effort", "") or "").strip() or None,
        )

    if name != "dummy":
        logging.getLogger(__name__).warning(
            "Unknown synthesis.backend %r — falling back to dummy", name
        )
    return DummySynthesizer()

# #30: valid values for filters.include_subagents. "only-raw" (default) keeps
# subagent transcripts in raw/ but skips them in synthesize/queue backlog;
# "all" synthesizes them like any session; "off" never converts them (handled
# at sync time in convert.py). Kept here next to the synth policy that reads it.
INCLUDE_SUBAGENTS_MODES = ("all", "only-raw", "off")
DEFAULT_INCLUDE_SUBAGENTS = "only-raw"


def resolve_include_subagents(cfg: dict[str, Any] | None = None) -> str:
    """Normalize ``cfg["filters"]["include_subagents"]`` to a valid mode (#30).

    Unknown/typo values fall back to the shipped default ``only-raw`` rather
    than crashing sync/synthesize — mirroring ``resolve_backend``'s
    tolerance of a bad ``synthesis.backend``.
    """
    filters = (cfg or {}).get("filters", {}) or {}
    raw = str(filters.get("include_subagents", DEFAULT_INCLUDE_SUBAGENTS)).strip().lower()
    return raw if raw in INCLUDE_SUBAGENTS_MODES else DEFAULT_INCLUDE_SUBAGENTS


# #8 follow-up: `filters.exclude_headless` used to act only at ingest, so a
# headless session already in raw/ (converted before the filter shipped, or
# with the filter off) stayed in the synthesis backlog forever. That is the
# expensive half of the feedback loop: synthesis shells out to an agent CLI,
# that run is logged as a session, and the next synthesis pays to summarize
# the wiki's own output. The setting now also governs the backlog, so it
# means what it says — headless runs are never wiki material.
DEFAULT_EXCLUDE_HEADLESS = True


def resolve_exclude_headless(cfg: dict[str, Any] | None = None) -> bool:
    """Read ``cfg["filters"]["exclude_headless"]`` (default True).

    Same key the converter reads, so one setting covers ingest and backlog
    and the two can never disagree.
    """
    filters = (cfg or {}).get("filters", {}) or {}
    raw = filters.get("exclude_headless", DEFAULT_EXCLUDE_HEADLESS)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in ("false", "no", "0", "off")
    return DEFAULT_EXCLUDE_HEADLESS


RAW_SESSIONS = REPO_ROOT / "raw" / "sessions"
# #1: manually-added documents (kbbuilder `wikiAddDocument`) land here.
# Synthesis distils these alongside session transcripts.
RAW_DOCS = REPO_ROOT / "raw" / "docs"
WIKI_SOURCES = REPO_ROOT / "wiki" / "sources"
WIKI_LOG = REPO_ROOT / "wiki" / "log.md"

# #1: ceiling on the body size handed to a single synthesis backend call.
# Oversized docs (e.g. a multi-MB concatenated `llms-full.txt`) are split
# on heading boundaries into part-pages before synthesis. Sessions are
# never chunked — they are bounded by the converter's truncation config.
_DOC_CHUNK_MAX_CHARS = 200_000
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "source_page.md"

# Allow user override of the prompt template: if
# `wiki/prompts/source_page.md` exists, use it instead of the
# built-in one. This lets users customize the synthesis prompt
# without forking the codebase.
USER_PROMPT_OVERRIDE = REPO_ROOT / "wiki" / "prompts" / "source_page.md"


def _load_prompt_template() -> str:
    """Load the synthesis prompt template. User override wins."""
    if USER_PROMPT_OVERRIDE.is_file():
        return USER_PROMPT_OVERRIDE.read_text(encoding="utf-8")
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


# How many top topics to surface as the reuse vocabulary in the prompt.
#
# The vocabulary is byte-identical for every page of a run, so backends put
# it in the cached half of the prompt (see base.split_prompt_template) and
# it is billed once per run rather than once per page. That makes breadth
# cheap: a topic that is missing from this list gets re-coined under a new
# spelling, which fragments the graph and the backlink index — the failure
# this list exists to prevent. Raised 80 -> 200 once caching made the extra
# entries cost ~0.1x on every page after the first.
_VOCAB_LIMIT = 200


def _vocab_attr(value: str) -> str:
    """Sanitize a value for an XML attribute (strip quotes/braces/newlines)."""
    return value.replace('"', "").replace("{", "").replace("}", "").replace("\n", " ").strip()


def _inject_vocabulary(template: str, wiki_dir: Path, *, limit: int = _VOCAB_LIMIT) -> str:
    """Substitute ``{vocabulary}`` with the canonical topics as lean ``<topic>``
    entries for the *regular* per-session synth.

    Regular synth needs just enough to pick the RIGHT topic, not to merge
    spellings (that's the consolidation pass's job) — so each entry carries
    ``name`` + ``desc`` (a one-line description, present once
    ``consolidate-topics`` has run) + ``with`` (co-occurring topics, for
    disambiguation). No ``aka`` noise. All derived from the corpus + cache —
    no LLM call here.

    No-op (placeholder removed) when the template lacks the marker or the wiki
    has no topics yet. Attribute values are quote/brace-free so backends'
    ``{body}``/``{meta}`` rendering downstream is unaffected.
    """
    if "{vocabulary}" not in template:
        return template
    try:

        graph = build_topic_graph(wiki_dir)
    except Exception:
        graph = None
    nodes = (graph or {}).get("nodes") or []
    if not nodes:
        return template.replace("{vocabulary}", "  <!-- none yet — this is an early session -->")

    # Top co-occurring topics per node, for the `with` attribute.
    related: dict[str, list[tuple[int, str]]] = {}
    for e in (graph.get("edges") or []):
        related.setdefault(e["source"], []).append((e["weight"], e["target"]))
        related.setdefault(e["target"], []).append((e["weight"], e["source"]))

    lines = []
    for n in nodes[:limit]:
        name = _vocab_attr(str(n["id"]))
        if not name:
            continue
        attrs = f'name="{name}"'
        desc = _vocab_attr(str(n.get("description", "")))
        if desc:
            attrs += f' desc="{desc}"'
        rel = sorted(related.get(n["id"], []), reverse=True)[:3]
        rel_names = ", ".join(_vocab_attr(r[1]) for r in rel if _vocab_attr(r[1]))
        if rel_names:
            attrs += f' with="{rel_names}"'
        lines.append(f"  <topic {attrs} />")
    return template.replace("{vocabulary}", "\n".join(lines))


def _load_state(state_file: Path | None = None) -> dict[str, float]:
    """Load the mtime state file. Returns {relative_path: mtime}.

    #sec-16 (#560): validate the schema before trusting it. A
    corrupted or hand-edited state file used to be returned verbatim,
    which then crashed every downstream consumer that expected
    `{str: float}`. Now: must be a dict, every value must be int/float,
    every key must be str. Anything else → reset to empty so synthesis
    re-runs from scratch (worst case: extra work, never wrong work).
    """
    target = _resolve_state_file(state_file)
    raw = _read_unified_state(target).get("synth", {}).get("files", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        parsed = mtime_from_state(v)
        if parsed is not None:
            out[k] = parsed
        # Other shapes silently dropped — caller treats as "needs synth"
    return out


def _save_state(state: dict[str, float], state_file: Path | None = None) -> None:
    """Persist synth mtimes into unified state.

    ``state`` is the full in-memory map for this run (loaded then updated).
    Values are written as ISO-8601 strings. Keys present in ``state`` are
    upserted; keys absent from ``state`` are left untouched so a partial
    accidental write cannot wipe the rest of the vault's synth map.
    """
    target = _resolve_state_file(state_file)
    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        files = dict(synth.get("files") or {}) if isinstance(synth.get("files"), dict) else {}
        for k, v in state.items():
            if not isinstance(k, str):
                continue
            files[k] = mtime_to_iso(v)
        synth["files"] = files
        return s
    _update_unified_state(_mut, target)


def _scan_source_page_keys(wiki_sources_dir: Path | None = None) -> tuple[set[str], set[str]]:
    """``source_file`` keys claimed by wiki/sources pages, split real vs stub."""
    roots = wiki_sources_dir or WIKI_SOURCES
    real: set[str] = set()
    stub: set[str] = set()
    if not roots.is_dir():
        return real, stub
    for p in roots.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta, body = parse_frontmatter(text)
        src = str(meta.get("source_file", "")).strip()
        if not src:
            continue
        (stub if _is_stub_page(body) else real).add(src)
    # Re-synthesis can file the real page under a different name than the stub
    # it replaces, leaving both on disk claiming the same source. One real page
    # is enough for that source to be synthesized; the stale stub is the lint
    # rule's business, not the backlog's.
    return real, stub - real


def discover_synth_source_keys(wiki_sources_dir: Path | None = None) -> set[str]:
    """Return ``source_file`` keys already synthesized into wiki/sources pages.

    Stub pages (dummy-backend filler, agent-delegate pending sentinels) carry
    a ``source_file`` key but no synthesis, so they are excluded — their source
    still counts as backlog (#24).
    """
    real, _stub = _scan_source_page_keys(wiki_sources_dir)
    return real


def discover_stub_source_keys(wiki_sources_dir: Path | None = None) -> set[str]:
    """Return ``source_file`` keys whose wiki/sources page is a stub (#24).

    A page states which raw file it stands for in its ``source_file``
    frontmatter, so a stub is tied to its source by that claim rather than by
    re-deriving the page's filename from the raw file. Pages written by an
    older release — a migrated vault — sit under that release's slug scheme,
    where a derived filename does not find them.
    """
    _real, stub = _scan_source_page_keys(wiki_sources_dir)
    return stub


def discover_unsynth_session_rels(
    *,
    raw_dir: Path | None = None,
    wiki_sources_dir: Path | None = None,
    state_file: Path | None = None,
    include_subagents: str | None = None,
    exclude_headless: bool | None = None,
) -> set[str]:
    """Session rel-paths that the shared estimate logic considers unsynth."""

    sessions = _discover_raw_sessions(raw_dir)
    state_keys: set[str]
    if state_file is None and raw_dir is not None:
        try:
            provided = Path(raw_dir).resolve()
            default = RAW_SESSIONS.resolve()
            if provided != default:
                state_keys = set()
            else:
                state_keys = set(_load_state(state_file).keys())
        except OSError:
            state_keys = set(_load_state(state_file).keys())
    else:
        state_keys = set(_load_state(state_file).keys())
    report = synthesize_estimate_report(
        raw_sessions=sessions,
        state_keys=state_keys,
        synthesized_source_keys=discover_synth_source_keys(wiki_sources_dir),
        wiki_sources_dir=wiki_sources_dir,
        raw_root=raw_dir or RAW_SESSIONS,
        docs_root=(raw_dir.parent / "docs") if raw_dir is not None else RAW_DOCS,
        include_subagents=include_subagents,
        exclude_headless=exclude_headless,
    )
    out: set[str] = set()
    for it in report.get("unsynth_items", []):
        rel = str(it.get("rel", "")).strip()
        if rel:
            out.add(rel)
    return out


def refresh_synth_pending(
    *,
    raw_dir: Path | None = None,
    docs_dir: Path | None = None,
    wiki_sources_dir: Path | None = None,
    state_file: Path | None = None,
    include_subagents: str | None = None,
    exclude_headless: bool | None = None,
) -> dict[str, Any]:
    """Compute unsynth backlog and persist it in unified state.

    Stores a lightweight pending list under ``synth.pending`` so users can
    inspect backlog risk before running `llmwiki synthesize`/`llm-wiki-add`.
    The backlog honors ``filters.include_subagents`` (#30) so ``queue status``
    doesn't count skipped subagents as permanently-pending — resolved from the
    user's config when the caller doesn't pass a mode explicitly.
    """
    sources_out = wiki_sources_dir or WIKI_SOURCES
    if include_subagents is None:
        include_subagents = resolve_include_subagents(_load_sessions_config())
    if exclude_headless is None:
        exclude_headless = resolve_exclude_headless(_load_sessions_config())
    raw_sessions = _discover_raw_sessions(raw_dir)
    state = _load_state(state_file)
    report = synthesize_estimate_report(
        raw_sessions=raw_sessions,
        state_keys=set(state.keys()),
        synthesized_source_keys=discover_synth_source_keys(sources_out),
        wiki_sources_dir=sources_out,
        raw_root=raw_dir or RAW_SESSIONS,
        docs_root=docs_dir or ((raw_dir.parent / "docs") if raw_dir is not None else RAW_DOCS),
        include_subagents=include_subagents,
        exclude_headless=exclude_headless,
    )
    pending: list[dict[str, Any]] = []
    for it in report.get("unsynth_items", []):
        rel = str(it.get("rel", "")).strip()
        if not rel:
            continue
        pending.append(
            {
                "rel": rel,
                "source": str(it.get("source_file", "")),
                "project": str(it.get("project", "unknown")),
                "is_doc": bool(it.get("is_doc", False)),
                "mtime": str(it.get("mtime", "")),
                "agent": str(it.get("agent", "")),
                "usd": float(it.get("usd", 0.0) or 0.0),
            }
        )

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    # wiki_sources_dir points at wiki/sources/; review stubs live under wiki/.
    wiki_dir = sources_out.parent
    pipeline = apply_review_summary_to_pipeline(
        {
            "stages": list(report.get("pipeline_stages") or ["raw", "synthesized"]),
            "rows": list(report.get("pipeline_rows") or []),
            "updated_at": stamp,
        },
        wiki_dir,
    )

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        synth["pending"] = pending
        synth["pending_total"] = len(pending)
        synth["pending_updated_at"] = stamp
        synth["pipeline"] = pipeline
        return s

    _update_unified_state(_mut, _resolve_state_file(state_file))
    return {
        "pending_total": len(pending),
        "pending": pending,
        "pipeline": pipeline,
        "updated_at": stamp,
    }


def _format_producer_breakdown(producers: dict[str, int]) -> str:
    """Render a synthesize run's per-producer counts as a short breakdown,
    e.g. ``2 Claude · 1 Cursor · 3 docs``. Agent buckets come first (most
    first), raw documents last. Empty string when nothing was produced —
    callers fall back to a bare count."""
    docs = producers.get("docs", 0)
    agents = [(k, v) for k, v in producers.items() if k != "docs" and v > 0]
    agents.sort(key=lambda kv: (-kv[1], kv[0]))
    parts = [f"{v} {k}" for k, v in agents]
    if docs > 0:
        parts.append(f"{docs} doc" if docs == 1 else f"{docs} docs")
    return " · ".join(parts)


def _append_log(
    title: str,
    *,
    log_path: Path | None = None,
    operation: str = "synthesize",
    details: dict[str, Any] | None = None,
) -> None:
    """Append a rich structured entry to wiki/log.md.

    Parameters
    ----------
    title : str
        Human-readable title for the log entry (e.g. "project/slug").
    log_path : Path, optional
        Override for the log file path — used by tests to avoid writing
        to the real wiki/log.md.  Defaults to ``WIKI_LOG``.
    operation : str
        Operation type: synthesize, ingest, query, lint, build, sync.
    details : dict, optional
        Rich details — created pages, updated pages, entities extracted, etc.
    """
    target = log_path or WIKI_LOG
    if not target.parent.exists():
        return

    # Auto-archive when log exceeds 50 KB
    _auto_archive_log(target)

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    lines = [f"\n## [{date_str}] {operation} | {title}\n"]
    if details:
        if details.get("processed"):
            lines.append(f"- Processed: {details['processed']}\n")
        if details.get("created"):
            lines.append(f"- Created: {', '.join(details['created'])}\n")
        if details.get("updated"):
            lines.append(f"- Updated: {', '.join(details['updated'])}\n")
        if details.get("entities"):
            lines.append(f"- Entities extracted: {', '.join(details['entities'])}\n")
        if details.get("errors"):
            lines.append(f"- Errors: {len(details['errors'])}\n")
    with open(target, "a", encoding="utf-8") as f:
        f.writelines(lines)


LOG_ARCHIVE_THRESHOLD = 50 * 1024  # 50 KB


def _auto_archive_log(log_path: Path) -> Path | None:
    """Archive log.md when it exceeds 50 KB. Returns archive path or None."""
    if not log_path.is_file():
        return None
    if log_path.stat().st_size < LOG_ARCHIVE_THRESHOLD:
        return None

    year = datetime.now(UTC).strftime("%Y")
    archive = log_path.parent / f"log-archive-{year}.md"

    content = log_path.read_text(encoding="utf-8")
    # Keep the header (first 5 lines), archive the rest
    lines = content.split("\n")
    header = "\n".join(lines[:5])
    body = "\n".join(lines[5:])

    # G-10 (#296): seed frontmatter on first write so lint's
    # frontmatter_completeness rule doesn't fail on the archive file.
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    first_write = not archive.is_file()
    if first_write:
        archive.write_text(
            f'---\ntitle: "Wiki log archive — {year}"\n'
            f'type: navigation\nauto_generated: true\n'
            f'last_updated: "{today}"\n---\n',
            encoding="utf-8",
        )

    # Append to archive
    with open(archive, "a", encoding="utf-8") as f:
        f.write(f"\n# Archived from log.md — {year}\n\n")
        f.write(body)

    # Reset log to header only
    log_path.write_text(header + "\n\n---\n", encoding="utf-8")
    return archive


def _rebuild_index(wiki_dir: Path) -> Path | None:
    """Reconcile ``wiki/index.md`` with the pages on disk (G-09 · #295, #71).

    Thin wrapper over :func:`llmwiki.reindex.reindex_wiki`, which owns the
    reconciliation for every caller — ``sync``, ``synthesize``, and
    ``remove``. The local implementation this replaced
    regenerated the ``## Sources`` / ``## Projects`` bullets from frontmatter
    on every run, which clobbered hand-written descriptions, ignored the
    ``(count)`` headings (so it appended a *second* count-less ``## Sources``
    below the seeded ``## Sources (0)``), and never touched entities,
    concepts, or syntheses.

    Returns the index path, or ``None`` for a wiki with no pages and no index.
    """
    plan = reindex_wiki(wiki_dir)
    return None if plan is None else plan.index_path


def _discover_raw_sessions(
    raw_dir: Path | None = None,
) -> list[tuple[Path, dict[str, Any], str]]:
    """Walk raw/sessions/ and return (path, meta, body) for each .md file."""
    root = raw_dir or RAW_SESSIONS
    if not root.is_dir():
        return []
    out: list[tuple[Path, dict[str, Any], str]] = []
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        out.append((p, meta, body))
    return out


def _discover_raw_docs(
    docs_dir: Path | None = None,
) -> list[tuple[Path, dict[str, Any], str]]:
    """Walk raw/docs/ and return (path, meta, body) for each .md file.

    #1: documents added through the manual path (kbbuilder
    ``wikiAddDocument`` → ``raw/docs/<slug>.md``) used to have no synthesis
    consumer. This mirrors :func:`_discover_raw_sessions` so added docs get
    distilled into wiki source pages too. Frontmatter is optional — a bare
    markdown file parses to ``({}, text)``.
    """
    root = docs_dir or RAW_DOCS
    if not root.is_dir():
        return []
    out: list[tuple[Path, dict[str, Any], str]] = []
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        out.append((p, meta, body))
    return out


# #1: top-level markdown heading (``#`` or ``##``) at the start of a line.
_MD_TOP_HEADING = re.compile(r"#{1,2} ")


def _chunk_markdown(text: str, max_chars: int) -> list[str]:
    """Split markdown into chunks no larger than ``max_chars``, breaking on
    top-level (``#``/``##``) heading boundaries where possible.

    Used to make oversized manually-added docs (e.g. a multi-MB
    ``llms-full.txt``) fit a single synthesis backend call. Returns
    ``[text]`` unchanged when the input already fits. Content is preserved:
    concatenating the chunks reproduces the input exactly — heading-aligned
    where sections fit the cap, hard character-split for a heading-less
    blob bigger than the cap.
    """
    if len(text) <= max_chars:
        return [text]

    # Group lines into sections, each starting at a top-level heading.
    sections: list[str] = []
    cur: list[str] = []
    for ln in text.splitlines(keepends=True):
        if cur and _MD_TOP_HEADING.match(ln):
            sections.append("".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        sections.append("".join(cur))

    # Greedily pack sections under the cap. A single section larger than
    # the cap is hard-split on character count so no chunk ever exceeds it.
    chunks: list[str] = []
    buf = ""
    for sec in sections:
        if len(sec) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(sec), max_chars):
                chunks.append(sec[i:i + max_chars])
            continue
        if buf and len(buf) + len(sec) > max_chars:
            chunks.append(buf)
            buf = sec
        else:
            buf += sec
    if buf:
        chunks.append(buf)
    return chunks


# ─── #351: AI-suggested tags ──────────────────────────────────────────

# Emitted by the LLM as the first line of its response — we strip it
# from the body before writing, merge the tags into the frontmatter.
# Format: ``<!-- suggested-tags: a, b, c -->``
_SUGGESTED_TAGS_RE = re.compile(
    r"^\s*<!--\s*suggested-tags:\s*(?P<body>[^>]*?)\s*-->\s*\n?",
    re.IGNORECASE,
)

# Cap on AI-suggested tags per page (deterministic baseline is separate
# and never counted against this budget).  5 keeps the frontmatter list
# readable and prevents runaway tag-space growth on noisy sessions.
_AI_TAG_CAP = 5

# Tags the LLM sometimes proposes that duplicate the deterministic
# baseline or add no value — drop silently so we don't pollute the tag
# space with boilerplate the pipeline already emits.
_AI_TAG_STOPWORDS = frozenset({
    "session-transcript", "session", "claude-code", "codex-cli", "cursor",
    "copilot-chat", "gemini-cli", "opencode", "chatgpt", "obsidian",
    "claude", "gpt", "gemini", "llama", "opus",
    "summary", "discussion", "conversation", "transcript",
    # Empty-ish noise from malformed LLM responses.
    "", "-", "tag", "tags",
})


_CONNECTIONS_HEADING_RE = re.compile(r"^##[ \t]+Connections[ \t]*$", re.M)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+", re.M)


def _dedupe_connections(body: str) -> str:
    """Drop repeat ``[[links]]`` from the ``## Connections`` section.

    Models sometimes list the same scope twice — the smaller ones more
    often, e.g. ``[[MCP]]`` in two bullets of one page. The graph already
    de-duplicates (``graph.py`` collects links into a set, and topic edge
    weights count distinct sessions), so this is a rendering fix, not a
    correctness one: the duplicate bullets are visible on the page.

    Only the Connections section is touched — the same scope named in
    ``## Summary`` and again under Connections is normal prose, not a
    repeat. The first bullet wins, since it carries the description the
    model wrote first.

    Matching is case-sensitive, so ``[[MCP]]`` and ``[[Mcp]]`` both
    survive: they are distinct nodes to the graph, and collapsing spelling
    variants is the topic-consolidation pass's job, not this one.
    """
    heading = _CONNECTIONS_HEADING_RE.search(body)
    if not heading:
        return body
    start = heading.end()
    nxt = _NEXT_HEADING_RE.search(body, start)
    end = nxt.start() if nxt else len(body)

    seen: set[str] = set()
    kept: list[str] = []
    for line in body[start:end].splitlines(keepends=True):
        targets = WIKILINK_RE.findall(line)
        if not targets:
            kept.append(line)          # blank lines, prose, "(none)" markers
            continue
        key = targets[0].strip()
        if key in seen:
            continue
        seen.add(key)
        kept.append(line)
    return body[:start] + "".join(kept) + body[end:]


def _extract_suggested_tags(body: str) -> tuple[list[str], str]:
    """Pull the ``<!-- suggested-tags: … -->`` block off the top of
    ``body`` and return ``(tags, cleaned_body)``.

    Invariants:

    * Missing / malformed block → ``([], body)`` (body untouched).
    * Tags are kebab-cased + lowercased + deduped preserving order.
    * Empty strings / stop-words filtered out.
    * Hard-capped at :data:`_AI_TAG_CAP` before stop-word filtering so
      a noisy LLM can't drown out the cap check.

    Runs in pure Python — no LLM call.  This just parses whatever the
    synthesizer already produced.
    """
    m = _SUGGESTED_TAGS_RE.match(body)
    if not m:
        return [], body
    raw = m.group("body") or ""
    cleaned_body = body[m.end():]
    # Split on comma, normalise each.
    tags: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        t = part.strip().lower().replace(" ", "-")
        if not t or t in seen or t in _AI_TAG_STOPWORDS:
            continue
        tags.append(t)
        seen.add(t)
        if len(tags) >= _AI_TAG_CAP:
            break
    return tags, cleaned_body


def _merge_tags(
    baseline: list[str],
    suggested: list[str],
    existing: list[str] | None = None,
) -> list[str]:
    """Merge the three tag sources into the final frontmatter list.

    Precedence (first-win, order preserved):

    1. Maintainer-curated ``existing`` tags (preserve on re-synthesize).
    2. Deterministic ``baseline`` (adapter + project + model family).
    3. AI-``suggested`` topical tags — only if they don't collide with
       or near-duplicate something already in 1 or 2.

    Near-duplicate detection uses ``tags.near_duplicate_tags`` so we
    reject ``prompt-cache`` when ``prompt-caching`` is already present.
    """
    # Local import to avoid a circular at module load.

    out: list[str] = []
    seen: set[str] = set()

    def _push(tag: str) -> None:
        t = tag.strip()
        if not t:
            return
        key = t.lower()
        if key in seen:
            return
        out.append(t)
        seen.add(key)

    for t in (existing or []):
        _push(t)
    for t in baseline:
        _push(t)
    # For each suggested tag, skip if a near-duplicate already exists.
    # Uses a tighter threshold (0.80) than the CLI default (0.85) — we
    # want auto-merge to be conservative so ``prompt-cache`` (0.846 vs
    # ``prompt-caching``) gets rejected at ingest time.  Maintainers can
    # still add it explicitly via ``llmwiki tag add``.
    if suggested:
        existing_snapshot = list(out)
        for candidate in suggested:
            candidate_lc = candidate.lower()
            # Cheap prefix check: one is a prefix of the other.
            def _substr_near(a: str, b: str) -> bool:
                a_l, b_l = a.lower(), b.lower()
                if a_l == b_l:
                    return True
                shorter, longer = sorted((a_l, b_l), key=len)
                return len(shorter) >= 5 and shorter in longer
            if any(_substr_near(candidate, existing_t) for existing_t in existing_snapshot):
                continue
            # Expensive fuzzy check for other near-dupes (typos, plural, etc.).
            entries = [
                TagEntry(page=Path("/virtual"), field="tags", tag=t)
                for t in existing_snapshot + [candidate]
            ]
            dups = near_duplicate_tags(entries, threshold=0.80)
            collides = any(
                candidate_lc in (a.lower(), b.lower()) and a.lower() != b.lower()
                for (a, b, _score) in dups
            )
            if collides:
                continue
            _push(candidate)
            existing_snapshot.append(candidate)
    return out


def _derive_baseline_tags(meta: dict[str, Any]) -> list[str]:
    """Return a never-empty baseline tag list for synthesized source pages.

    Takes the raw session's ``meta["tags"]`` and augments it with tags
    derived from the project slug + model (when the raw list is empty
    or just carries the boilerplate ``[session-transcript]``).  The
    goal: **every** synthesized page leaves the pipeline with at least
    one meaningful tag so filters / graph chips / the new
    ``tags_topics_convention`` lint rule don't see empty lists.
    """
    out: list[str] = []
    seen: set[str] = set()
    # Start with whatever the raw frontmatter shipped.
    for t in meta.get("tags", []) or []:
        t = str(t).strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    # Ensure the adapter source stamp (claude-code / codex-cli / obsidian / …)
    # appears at least as session-transcript so routing by source stays cheap.
    if "session-transcript" not in seen and "claude-code" not in seen:
        out.append("session-transcript")
        seen.add("session-transcript")
    # Add the project slug as a tag so filters-by-project work out-of-the-box.
    project = str(meta.get("project", "") or "").strip()
    if project and project != "unknown" and project not in seen:
        out.append(project)
        seen.add(project)
    # Model family as a coarse bucket (claude-sonnet-4-6 → claude).
    model = str(meta.get("model", "") or "").strip().lower()
    for family in ("claude", "gpt", "gemini", "llama", "opus"):
        if family in model and family not in seen:
            out.append(family)
            seen.add(family)
            break
    return out


def _build_source_page(
    meta: dict[str, Any],
    synthesized_body: str,
    existing_page_path: Path | None = None,
) -> str:
    """Combine frontmatter + synthesized body into a full wiki source page.

    #351: If the ``synthesized_body`` starts with a
    ``<!-- suggested-tags: ... -->`` block (emitted by the LLM per the
    ``source_page.md`` prompt), the tags are extracted, de-duplicated
    against the deterministic baseline, and merged into the frontmatter.
    The comment is stripped from the body so it never reaches the
    rendered site.

    If ``existing_page_path`` points at an existing wiki source file,
    its current frontmatter ``tags`` are preserved verbatim (maintainer
    curation is never overwritten on re-synthesize).
    """
    slug = meta.get("slug", "unknown")
    title = meta.get("title", f"Source: {slug}")
    project = meta.get("project", "unknown")
    date = meta.get("date", "")
    model = meta.get("model", "")
    source_file = meta.get("source_file", "")

    # #351: pull AI-suggested tags off the top of the body.
    ai_tags, clean_body = _extract_suggested_tags(synthesized_body)
    clean_body = _dedupe_connections(clean_body)

    # Preserve any maintainer-curated tags on re-synthesize.
    # #py-h5 (#584): the broad `except Exception` was eating real
    # parse failures + unicode errors silently, dropping the curated
    # tags on every regression. Narrow to the failures that are
    # actually expected here (file read OSError, frontmatter format
    # issues): everything else (MemoryError, KeyboardInterrupt,
    # surprise type errors) bubbles up so the regression is visible
    # instead of silently producing a tag-loss diff.
    existing_tags: list[str] = []
    if existing_page_path is not None and existing_page_path.exists():
        try:
            existing_meta, _existing_body = parse_frontmatter(
                existing_page_path.read_text(encoding="utf-8")
            )
            existing_tags = list(existing_meta.get("tags", []) or [])
        except (OSError, ValueError, UnicodeDecodeError) as e:
            # Log loud — silent drop is what #584 was about.
            print(
                f"warning: could not preserve tags from "
                f"{existing_page_path}: {e}",
                file=sys.stderr,
            )
            existing_tags = []

    baseline = _derive_baseline_tags(meta)
    tags = _merge_tags(baseline, ai_tags, existing_tags)

    fm = [
        "---",
        f'title: "{title}"',
        "type: source",
        f"tags: [{', '.join(tags)}]",
        f"date: {date}",
        f"source_file: {source_file}",
        f"project: {project}",
        f"model: {model}",
        f"last_updated: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "---",
        "",
    ]
    return "\n".join(fm) + clean_body


def synthesize_new_sessions(
    backend: BaseSynthesizer | None = None,
    raw_dir: Path | None = None,
    wiki_sources_dir: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    log_path: Path | None = None,
    state_file: Path | None = None,
    docs_dir: Path | None = None,
    doc_chunk_max_chars: int | None = None,
    include_sessions: bool = True,
    include_docs: bool = True,
    only_paths: set[Path] | set[str] | None = None,
    include_subagents: str | None = None,
    exclude_headless: bool | None = None,
) -> dict[str, Any]:
    """Main entry point. Returns a summary dict:

    {
        "total_scanned": int,
        "new_files": int,
        "synthesized": int,
        "skipped": int,
        "errors": list[str],
        "backend": str,
    }

    ``include_sessions`` / ``include_docs`` — restrict the scan to one
    corpus (CLI ``--sessions-only`` / ``--docs-only``). Both default True.

    ``only_paths`` — when set, only synthesize these raw files (resolved
    paths). Used by ``llmwiki add`` so a single add does not drain the
    whole unsynthesized backlog.
    """
    if backend is None:
        backend = DummySynthesizer()

    if not backend.is_available():
        return {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [f"Backend {backend.name} is not available"],
            "backend": backend.name,
        }

    reset_usage = getattr(backend, "reset_usage", None)
    if callable(reset_usage):
        reset_usage()

    sources_out = wiki_sources_dir or WIKI_SOURCES
    # #30: resolve the subagent policy once. In "only-raw" (the default),
    # subagent transcripts are skipped here even under --force — the flag means
    # "redo synthesis", not "override which sessions are eligible".
    if include_subagents is None:
        include_subagents = resolve_include_subagents(_load_sessions_config())
    else:
        include_subagents = resolve_include_subagents(
            {"filters": {"include_subagents": include_subagents}}
        )
    # #8 follow-up: same policy the estimate applies, resolved the same way,
    # so `--estimate` and a real run never disagree about what is eligible.
    if exclude_headless is None:
        exclude_headless = resolve_exclude_headless(_load_sessions_config())
    else:
        exclude_headless = bool(exclude_headless)
    prompt_template = _load_prompt_template()
    # #54: feed the auto-derived topic vocabulary back into the prompt so the
    # model reuses canonical spellings instead of coining new variants. Filled
    # once here (corpus-wide); backends only substitute {body}/{meta} after.
    prompt_template = _inject_vocabulary(prompt_template, sources_out.parent)
    state_file = _resolve_state_file(state_file)
    state = {} if force else _load_state(state_file)
    chunk_max = doc_chunk_max_chars or _DOC_CHUNK_MAX_CHARS
    only_resolved: set[Path] | None = None
    if only_paths is not None:
        only_resolved = {Path(p).expanduser().resolve() for p in only_paths}

    # #1: synthesize BOTH session transcripts and manually-added docs.
    # Sessions keep their existing rel state-keys (relative to the sessions
    # root) so pre-existing .llmwiki-synth-state.json files stay valid.
    # Docs are namespaced with a ``docs::`` rel prefix and grouped under a
    # ``docs`` pseudo-project. The docs root defaults to the sibling
    # ``raw/docs`` of whatever sessions root was given.
    session_base = raw_dir or RAW_SESSIONS
    docs_base = docs_dir or (raw_dir.parent / "docs" if raw_dir else RAW_DOCS)
    # When only_paths is set (llmwiki add), skip the full unsynth scan —
    # we only care about the explicit allow-list below.
    unsynth_session_rels: set[str] = set()
    if include_sessions and only_resolved is None:
        unsynth_session_rels = discover_unsynth_session_rels(
            raw_dir=raw_dir,
            wiki_sources_dir=wiki_sources_dir,
            state_file=state_file,
            include_subagents=include_subagents,
            exclude_headless=exclude_headless,
        )

    items: list[dict[str, Any]] = []
    if include_sessions:
        for p, meta, body in _discover_raw_sessions(raw_dir):
            # #30: "only-raw" keeps subagents in raw/ but out of synthesis — even
            # when --force or an explicit only_paths list would otherwise pull them
            # in. Switching to "all" is the only way to make them eligible.
            if include_subagents == "only-raw" and is_subagent(
                meta if isinstance(meta, dict) else {}, p
            ):
                continue
            # Headless runs are the wiki's own agent-CLI calls; synthesizing them
            # summarizes our own output and breeds more of them. Skipped even
            # under --force/only_paths, exactly like the subagent rule above.
            if exclude_headless and is_headless(meta if isinstance(meta, dict) else {}):
                continue
            if only_resolved is not None:
                try:
                    if p.resolve() not in only_resolved:
                        continue
                except OSError:
                    continue
            else:
                rel = str(p.relative_to(session_base))
                if rel not in unsynth_session_rels and not force:
                    continue
            rel = str(p.relative_to(session_base))
            items.append({
                "path": p, "meta": meta, "body": body,
                "rel": rel,
                "project": meta.get("project", p.parent.name),
                "is_doc": False,
            })
    if include_docs:
        for p, meta, body in _discover_raw_docs(docs_base):
            if only_resolved is not None:
                try:
                    if p.resolve() not in only_resolved:
                        continue
                except OSError:
                    continue
            # Group under the doc's own project if it declares one, else the
            # ``docs`` pseudo-project. Inject it into meta too so the built
            # page's `project:` frontmatter matches where the page lives —
            # otherwise the index/graph mis-group it as ``unknown``.
            doc_project = meta.get("project") or "docs"
            items.append({
                "path": p, "meta": {**meta, "project": doc_project}, "body": body,
                "rel": "docs::" + str(p.relative_to(docs_base)),
                "project": doc_project,
                "is_doc": True,
            })

    # Split the source-page scan once: real keys drive the dedup guard
    # below, stub keys keep filler slots in the backlog (#24).
    real_source_keys, stub_source_keys = _scan_source_page_keys(sources_out)

    new_items: list[dict[str, Any]] = []
    dedup_skipped = 0
    for it in items:
        try:
            mtime = it["path"].stat().st_mtime
        except OSError:
            continue
        # A state entry only means "done" when the page it produced is a real
        # one. A stub still on disk is pending work, so re-synthesize it (#24).
        # It is found either by the source key it claims — which holds for a
        # page an older release filed under another name — or at the pages this
        # source actually wrote, part-pages included: a doc's parts are
        # complementary, so a real part does not cover a stub one. The
        # write-guard below keeps a real page safe from a stub.
        rel = str(it["rel"])
        source_key = (
            "raw/docs/" + rel[len("docs::"):] if it["is_doc"] else "raw/sessions/" + rel
        )
        targets = source_page_paths(
            sources_out / str(it["project"]),
            synth_page_filename(it["meta"], it["path"].stem),
            is_doc=bool(it["is_doc"]),
        )
        page_is_pending = source_key in stub_source_keys or any(
            page_is_stub(t) for t in targets
        )
        if (
            it["rel"] in state
            and (state[it["rel"]] + 1e-6) >= mtime
            and not force
            and not page_is_pending
        ):
            continue
        # Dedup guard (#37): a REAL page under any folder/slug already claims
        # this source. A hand-written page lives outside synth state and off
        # the derived target path, so neither the state check above nor the
        # write-guard below sees it — synth would drop a sibling duplicate.
        # Skip only when the real page is elsewhere: a real page AT the derived
        # target is the normal overwrite/protect path, and --force re-synthesizes.
        derived_has_real = any(
            t.exists() and not page_is_stub(t) for t in targets
        )
        if not force and source_key in real_source_keys and not derived_has_real:
            print(
                f"  skipped: {it['project']} → {source_key} "
                "(real source page already claims this source; not duplicating)"
            )
            dedup_skipped += 1
            continue
        new_items.append(it)

    summary: dict[str, Any] = {
        "total_scanned": len(items),
        "new_files": len(new_items),
        "synthesized": 0,
        "skipped": dedup_skipped,
        "protected": 0,
        "errors": [],
        "backend": backend.name,
    }

    if dry_run:
        summary["skipped"] = len(new_items)
        print(
            f"[dry-run] Would synthesize {len(new_items)} new sources "
            f"using {backend.name}"
        )
        for it in new_items:
            print(f"  {it['meta'].get('slug', it['path'].stem)}")
        return summary

    # #27: tally what each successful synthesis produced (raw doc vs which
    # agent's session) so the log entry carries a producer breakdown the
    # Analytics "Recent activity" widget renders verbatim.
    producers: dict[str, int] = {}

    for it in new_items:
        p, meta, body = it["path"], it["meta"], it["body"]
        project, rel = it["project"], it["rel"]
        # G-21 (#307): slug is normalised (spaces → hyphens, filesystem-unsafe
        # chars stripped) and G-06 (#292): date-prefixed so Claude Code's
        # 3-word auto-slugs can't silently collide. Output path is
        # `wiki/sources/<project>/<YYYY-MM-DD>-<slug>.md`.
        raw_slug = meta.get("slug", p.stem)
        slug = _normalise_slug(raw_slug if isinstance(raw_slug, str) else p.stem)
        filename = synth_page_filename(meta, p.stem)

        # #1: oversized docs are split on headings into part-pages so each
        # chunk fits one backend call. Sessions are never chunked.
        chunks = _chunk_markdown(body, chunk_max) if it["is_doc"] else [body]
        multi = len(chunks) > 1

        try:
            out_dir = sources_out / project
            out_dir.mkdir(parents=True, exist_ok=True)
            for idx, chunk in enumerate(chunks, start=1):
                # #py-h7 (#585): pass the raw template — backends own
                # rendering. The pipeline hands over the unrendered
                # template; each backend renders it with the format it was
                # designed against (textual vs JSON meta).
                synthesized = backend.synthesize_source_page(
                    chunk, meta, prompt_template
                )
                name = f"{filename}--part-{idx:02d}" if multi else filename
                # #351: pass the existing path so maintainer-curated tags
                # are preserved on re-synthesize.
                out_path = out_dir / f"{name}.md"
                page_content = _build_source_page(
                    meta, synthesized, existing_page_path=out_path
                )
                # Stub output (dummy backend, agent-delegate pending
                # sentinel) must never replace a real synthesized page —
                # not even under --force. A stub carries no link data,
                # so the swap silently destroys the knowledge graph.
                if _is_stub_page(page_content) and out_path.exists():
                    try:
                        existing = out_path.read_text(encoding="utf-8")
                    except OSError:
                        existing = ""
                    if existing and not _is_stub_page(existing):
                        summary["protected"] += 1
                        print(
                            f"  protected: {project} → {name} "
                            "(kept real page; stub not written)"
                        )
                        continue
                out_path.write_text(page_content, encoding="utf-8")
                # G-08 (#294): clean separator so slugs with spaces don't
                # break awk/sed parsing. See G-20/#306 for the batched
                # summary emitted after the loop.
                print(f"  synthesized: {project} → {name}")

            # Update state once per source (after all parts succeed).
            state[rel] = p.stat().st_mtime
            _save_state(state, state_file)
            try:
                target_state = _resolve_state_file(state_file)
                def _drop_pending(s: dict[str, Any], rel=rel) -> dict[str, Any]:
                    synth = s.setdefault("synth", {})
                    rows = synth.setdefault("pending", [])
                    if isinstance(rows, list):
                        rows = [r for r in rows if not (isinstance(r, dict) and str(r.get("rel", "")) == rel)]
                        synth["pending"] = rows
                        synth["pending_total"] = len(rows)
                    return s
                _update_unified_state(_drop_pending, target_state)
            except Exception:
                pass
            summary["synthesized"] += 1
            key = "docs" if it["is_doc"] else detect_agent_label(meta)[0]
            producers[key] = producers.get(key, 0) + 1

        except Exception as e:
            summary["errors"].append(f"{slug}: {e}")
            summary["skipped"] += 1
            print(f"  error: {slug}: {e}")

    # G-20 (#306): emit ONE summary log entry per invocation, not one
    # per page. Includes project counts + error count. The old per-page
    # entries flooded wiki/log.md (60+ lines per run).
    if summary["synthesized"] > 0 or summary["errors"]:
        projects_touched: dict[str, int] = {}
        for it in new_items:
            projects_touched[it["project"]] = projects_touched.get(it["project"], 0) + 1
        _append_log(
            f"{summary['synthesized']} sessions across {len(projects_touched)} projects",
            log_path=log_path,
            operation="synthesize",
            details={
                "processed": _format_producer_breakdown(producers) or summary["synthesized"],
                "created": sorted(projects_touched.keys()),
                "errors": summary["errors"],
            },
        )

    _save_state(state, state_file)
    refresh_synth_pending(
        raw_dir=raw_dir,
        docs_dir=docs_dir,
        wiki_sources_dir=wiki_sources_dir,
        state_file=state_file,
        include_subagents=include_subagents,
    )

    # G-09 (#295): rebuild wiki/index.md so lint's index_sync rule
    # passes on fresh synthesized corpora. Synthesize is authoritative
    # for `## Sources` — the index reflects whatever's on disk now.
    # #arch-m7 (#619): gate behind a "did anything actually change?"
    # check. The index rebuild walks the entire wiki + parses every
    # frontmatter; on a 5k-page corpus that's seconds. Skip when zero
    # pages were synthesized in this pass.
    if summary.get("synthesized", 0) > 0:
        try:
            _rebuild_index(sources_out.parent)
        except (OSError, ValueError, RuntimeError) as e:
            summary["errors"].append(f"index rebuild: {e}")

    take_usage = getattr(backend, "take_usage", None)
    if callable(take_usage):
        tokens, cost_usd = take_usage()
        if tokens is not None:
            summary["tokens"] = tokens
        if cost_usd is not None:
            summary["cost_usd"] = cost_usd

    return summary

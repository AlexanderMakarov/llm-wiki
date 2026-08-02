"""llmwiki — static HTML site builder.

Reads converted markdown sources under `raw/` and produces a complete static
site under `site/` with:

- Home + projects index + sessions index + per-project + per-session pages
- Inter + JetBrains Mono typography, purple accent (#7C3AED)
- Light / dark theme toggle (data-theme + system preference + localStorage)
- Global search index (site/search-index.json) — client-side fuzzy matcher
- Cmd+K command palette (vanilla JS, no framework)
- Keyboard shortcuts: /, g h, g p, g s, j/k, ?
- highlight.js client-side syntax highlighting (CDN, light + dark themes)
- Collapsible tool-result sections (<details>) for long outputs
- Copy-as-markdown + copy-code buttons (Clipboard API + execCommand fallback)
- Breadcrumbs + reading progress bar
- Filter bar on the sessions table
- Mobile-responsive, print-friendly
- ARIA focus rings and prefers-reduced-motion support

Stdlib + `markdown` (required). No optional deps — highlight.js loads from CDN.
Usage:
    python3 -m llmwiki build [--synthesize] [--out <dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import markdown
from markdown.preprocessors import Preprocessor

from llmwiki import PACKAGE_ROOT, REPO_ROOT

# 1×1 PNG (valid image/png bytes) served as site/favicon.ico so Chromium's
# automatic /favicon.ico probe does not 404 into the browser console.
_FAVICON_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da6364f8cf500f00038601805a347d6b0000000049454e44ae426082"
)

# Repo-authored content (editorial docs/, README.md, CONTRIBUTING.md,
# .claude/commands) ships with the tool's source checkout. Resolve it
# from the package location, NOT REPO_ROOT — with LLMWIKI_ROOT set,
# REPO_ROOT points at the user's vault, which has none of these files.
SOURCE_ROOT = PACKAGE_ROOT.parent
from llmwiki import raw_docs_site
from llmwiki.agent_label import detect_agent_label, render_agent_badge
from llmwiki.automation_status import load_status
from llmwiki.candidates import apply_review_summary_to_pipeline, candidate_review_summary
from llmwiki.candidates_site import render_candidates_body
from llmwiki.changelog_timeline import (
    extract_price_points,
    parse_changelog,
    render_changelog_timeline,
    render_price_sparkline,
    render_recent_activity,
)
from llmwiki.claude_path import resolve_claude_path as _resolve_claude_path
from llmwiki.compare import (
    discover_user_overrides,
    generate_pairs,
    pair_slug,
    render_comparison_body,
    render_comparisons_index,
)
from llmwiki.context_md import is_context_file
from llmwiki.convert import restore_local_path
from llmwiki.docs_pages import (
    _first_paragraph,
    compile_docs_site,
    iter_docs_pages,
    rewrite_md_links_to_html,
    rewrite_source_code_links_to_github,
    strip_dead_session_refs,
)
from llmwiki.exporters import export_all
from llmwiki.freshness import freshness_badge, load_freshness_config
from llmwiki.graph import copy_to_site as copy_graph_to_site
from llmwiki.graph import write_html as write_graph_html
from llmwiki.log_reader import recent_events as _recent_log_events
from llmwiki.manifest import write_manifest
from llmwiki.models_page import (
    discover_model_entities,
    discover_model_entities_with_meta,
    render_model_info_card,
    render_models_index,
)
from llmwiki.project_topics import (
    extract_session_topics,
    get_project_topics,
    load_project_profile,
    render_topic_chips,
)
from llmwiki.search_facets import aggregate_facets, enrich_entry
from llmwiki.search_tree import (
    annotate_entry_headings,
    decide_search_mode,
    search_index_footer_badge,
)
from llmwiki.state_store import read_state, resolve_state_file, synth_pipeline_shape_ok, update_state
from llmwiki.synth.claude_cli import overview_argv
from llmwiki.synth.pipeline import refresh_synth_pending
from llmwiki.tag_utils import NOISE_TAGS
from llmwiki.topics import build_topic_graph, topic_slug
from llmwiki.topics_page import build_topic_pages
from llmwiki.usage import (
    combined_totals as _mcp_combined_totals,
)
from llmwiki.usage import (
    corpus_source_mix as _mcp_corpus_mix,
)
from llmwiki.usage import (
    iter_live_records as _mcp_live_records,
)
from llmwiki.usage import (
    page_retrievals as _mcp_page_retrievals,
)
from llmwiki.usage import (
    read_mix_from_retrievals as _mcp_read_mix,
)
from llmwiki.usage import (
    refresh_daily as _mcp_refresh_daily,
)
from llmwiki.viz_heatmap import (
    activity_heatmap_div,
    collect_session_counts,
    day_int_counts,
    mcp_day_has_signal,
    render_heatmap,
)
from llmwiki.viz_tokens import (
    render_project_token_card,
    render_session_token_card,
    render_site_token_stats,
)
from llmwiki.viz_tools import (
    render_project_tool_chart,
    render_session_tool_chart,
)
from llmwiki.viz_wiki_value import (  # noqa: F401
    render_candidates_review_section,
    render_mcp_heaviest_card,
    render_project_usage_block,
    render_wiki_value_section,
)
from llmwiki.wiki_adoption import daily_wiki_sessions_from_dir as _wiki_session_days

# ─── paths ─────────────────────────────────────────────────────────────────

RAW_DIR = REPO_ROOT / "raw"
RAW_SESSIONS = RAW_DIR / "sessions"
DEFAULT_OUT_DIR = REPO_ROOT / "site"
# v0.7+: optional per-project metadata (topics, description, homepage).
# Users drop a `wiki/projects/<slug>.md` file with frontmatter.
PROJECTS_META_DIR = REPO_ROOT / "wiki" / "projects"


# ─── frontmatter ───────────────────────────────────────────────────────────

# #409 / #423: build.py used to ship a divergent regex (LF-only, no BOM
# handling, simpler list parser) which silently dropped frontmatter on
# Windows-authored files. Unified to the canonical parser in
# `_frontmatter.py`. Re-exported under the historical name so external
# consumers (and `tests/test_render_split.py`) keep working.
from llmwiki._frontmatter import (  # noqa: E402
    parse_frontmatter,
)

# ─── discovery ─────────────────────────────────────────────────────────────


# #405 path-traversal guard. Site paths are composed by joining `out_dir`
# with `project_slug` and other slug values from frontmatter. A poisoned
# `project: ../../etc/passwd` would otherwise write outside `out_dir`.
_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_slug(value: str | None, *, fallback: str = "_unknown") -> str:
    """Return a path-safe single-segment slug.

    Rejects empty values, traversal segments (``..``), absolute paths
    (leading ``/`` or backslash), null bytes, and anything containing
    characters outside ``[A-Za-z0-9._-]``. Falls back to ``fallback`` so
    the build keeps going on poisoned frontmatter — the offending
    session lands under a clearly abnormal slug rather than escaping
    ``out_dir``.
    """
    if not value:
        return fallback
    s = str(value).strip()
    # Strip surrounding quotes leaked from naive YAML parsers.
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    if not s or s in (".", ".."):
        return fallback
    if "/" in s or "\\" in s or "\x00" in s:
        return fallback
    if not _SAFE_SLUG_RE.match(s):
        return fallback
    return s


# Single source of truth lives in _frontmatter (shared with the synth
# pipeline's include_subagents policy, #30). Aliased here so build.py's
# call sites keep the familiar private name.
from llmwiki._frontmatter import is_subagent as _is_subagent  # noqa: E402


def discover_sources(root: Path) -> list[tuple[Path, dict[str, Any], str]]:
    out: list[tuple[Path, dict[str, Any], str]] = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.md")):
        # v0.5 (#60): `_context.md` files are folder metadata for LLM
        # navigation, not pages. Skip them so they never appear in the
        # session index, search index, or AI-consumable exports.
        if is_context_file(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        # #405: sanitize the frontmatter values that compose output paths.
        # Original values stay available via meta.get(); the *_safe_*
        # versions are what every path-composition site downstream uses.
        meta["project"] = _safe_slug(
            meta.get("project") or p.parent.name,
            fallback=_safe_slug(p.parent.name, fallback="_unknown"),
        )
        if "slug" in meta:
            meta["slug"] = _safe_slug(meta["slug"], fallback=p.stem)
        out.append((p, meta, body))
    return out


def group_by_project(
    sources: list[tuple[Path, dict[str, Any], str]],
) -> dict[str, list[tuple[Path, dict[str, Any], str]]]:
    g: dict[str, list[tuple[Path, dict[str, Any], str]]] = defaultdict(list)
    for p, meta, body in sources:
        project = str(meta.get("project") or p.parent.name)
        g[project].append((p, meta, body))
    for k in g:
        g[k].sort(key=lambda t: str(t[1].get("started", t[0].name)))
    return g


_SLUG_SPLIT_RE = re.compile(r"[-_]+")


def _humanize_slug(slug: str) -> str:
    """Turn a kebab/snake-case slug into a human-readable title.

    `my-cool-project` → `My Cool Project`. Single-letter parts are
    upper-cased the same way as multi-letter parts. Empty / whitespace
    input returns the original (callers handle the empty case).
    """
    parts = [p for p in _SLUG_SPLIT_RE.split(slug.strip()) if p]
    if not parts:
        return slug.strip()
    return " ".join(p[:1].upper() + p[1:] for p in parts)


def _derive_stub_description(
    sessions: list[tuple[Path, dict[str, Any], str]],
) -> str:
    """Pick a sensible description from the most-recent session.

    Prefers an explicit `summary` (truncated to ~140 chars), then the
    humanised session slug, then empty. `sessions` arrives sorted oldest
    → newest by `discover_sources`/grouping, so we walk the tail.
    """
    for _path, meta, _body in reversed(sessions):
        summary = meta.get("summary")
        if isinstance(summary, str) and summary.strip():
            text = summary.strip().splitlines()[0].strip()
            if len(text) > 140:
                text = text[:137].rstrip() + "..."
            return text
        raw_slug = meta.get("slug")
        if isinstance(raw_slug, str) and raw_slug.strip():
            humanised = _humanize_slug(raw_slug)
            if humanised:
                return humanised
    return ""


def _derive_stub_topics(
    sessions: list[tuple[Path, dict[str, Any], str]],
    max_topics: int = 6,
) -> list[str]:
    """Aggregate topics from session frontmatter, then `tools_used` as a
    secondary source. Uses `extract_session_topics` for the tags path so
    the noise filter stays in sync with `project_topics.py`. Falls back
    to `min_count=1` because most projects have only a few sessions and
    the `min_count=2` default in `extract_session_topics` would suppress
    nearly everything at seed time. Returns at most `max_topics` topics.
    """
    metas = [meta for _path, meta, _body in sessions]
    topics = extract_session_topics(metas, max_topics=max_topics, min_count=1)
    if topics:
        return topics
    # Fallback: tools_used aggregation (filtered by the same noise set).
    counts: dict[str, int] = {}
    for meta in metas:
        raw = meta.get("tools_used")
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = list(raw.keys())
        else:
            items = []
        for item in items:
            tag = str(item).strip().lower()
            if tag and tag not in NOISE_TAGS:
                counts[tag] = counts.get(tag, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [tag for tag, _ in ordered[:max_topics]]


def _format_topics_yaml(topics: list[str]) -> str:
    """Inline-list YAML serialisation that matches the parser in
    `project_topics._parse_topics_frontmatter`."""
    if not topics:
        return "[]"
    return "[" + ", ".join(topics) + "]"


def ensure_project_stubs(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    meta_dir: Path,
) -> list[Path]:
    """Auto-seed ``wiki/projects/<slug>.md`` for any discovered project
    that doesn't already have one (`issues-commands.md` I-12).

    Without this, real projects render a bare hero — no description, no
    topic chips, no homepage — because those fields come from a hand-
    authored file that never gets created on sync. Seeding pre-populates
    `topics:` from session tags/tools and `description:` from the most-
    recent session's summary or slug, so every real project lights up the
    moment its first session lands (closes #425). Existing hand-authored
    files are never overwritten — only the absence of a file triggers a
    write, so the user's edits always win.

    Returns the list of stub paths actually written (empty if all project
    metadata files already existed).
    """
    meta_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for slug in sorted(groups):
        target = meta_dir / f"{slug}.md"
        if target.exists():
            continue
        sessions = groups[slug]
        topics = _derive_stub_topics(sessions)
        description = _derive_stub_description(sessions)
        # Escape embedded double-quotes in description so the YAML stays
        # valid — slugs/summaries from real sessions occasionally contain
        # quotes (`"why didn't this work"`).
        description_safe = description.replace("\\", "\\\\").replace('"', '\\"')
        # #py-l8 (#606): drop f-prefix on lines that have no
        # placeholders so ruff's F541 doesn't flag the file. Mixed
        # f-/plain in a concatenation chain is fine.
        stub = (
            "---\n"
            f'title: "{slug}"\n'
            "type: entity\n"
            "entity_type: project\n"
            f"project: {slug}\n"
            f"topics: {_format_topics_yaml(topics)}\n"
            f'description: "{description_safe}"\n'
            'homepage: ""\n'
            "---\n\n"
            f"# {slug}\n\n"
            "*Auto-generated project stub. `topics` and `description` are "
            "pre-filled from session metadata — edit any field above and "
            "the build will pick it up. Fill in `homepage` to add a link "
            "chip to the project hero.*\n"
        )
        target.write_text(stub, encoding="utf-8")
        written.append(target)
    return written


# ─── markdown normaliser + renderer ───────────────────────────────────────

_H1_LINE_RE = re.compile(r"^#\s+.*\n", re.MULTILINE)


def strip_leading_h1(body: str) -> str:
    m = _H1_LINE_RE.search(body)
    if m and m.start() < 200:
        body = body[: m.start()] + body[m.end() :]
        body = body.lstrip("\n")
    return body


def normalize_markdown(body: str) -> str:
    """Fix common markdown glitches from the converter:
    1. Insert blank line before lists that follow a bold header.
    2. Outdent fenced code blocks that are 2-space-indented under a list item.
    """
    body = re.sub(
        r"(\*\*(?:Tools used|Tool results):\*\*)\n(?!\n)", r"\1\n\n", body,
    )
    lines = body.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "```" and line.startswith("  "):
            if out and out[-1].strip():
                out.append("")
            out.append("```")
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                bl = lines[i]
                if bl.startswith("  "):
                    bl = bl[2:]
                out.append(bl)
                i += 1
            if i < len(lines):
                out.append("```")
                i += 1
                if i < len(lines) and lines[i].strip():
                    out.append("")
        else:
            out.append(line)
            i += 1
    return "\n".join(out)


# v0.5 (#74): Session content frequently mentions HTML-ish strings in prose —
# e.g. an assistant describing how a hidden `<textarea class="md-source">` works.
# The default Python markdown library passes raw HTML tags through unchanged,
# which means a session that mentions `<textarea>` outside of backticks leaks
# an unclosed textarea into the DOM, swallowing every following element
# (including the <script> tag that boots highlight.js). The v0.5 hljs swap
# made this pre-existing bug catastrophic — before, Pygments rendered code
# server-side so the broken tail didn't visibly matter; now, a single
# unescaped tag breaks the whole page's syntax highlighting.
#
# The preprocessor below escapes anything that *looks* like an HTML tag start
# (`<tagname` or `</tagname`) outside of inline backticks. Fenced code blocks
# are already extracted into placeholders by `fenced_code` (priority 25) before
# this runs (priority 22). Priority 22 also ensures we run *before*
# `html_block` (priority 20) so raw HTML blocks never get a chance to be
# preserved as-is. Bare `<` / `<space>` (e.g. `x < 10`) are left alone —
# markdown's own escaper handles those. HTML comments (`<!-- ... -->`) are
# preserved because the regex only matches `<[letter]`, not `<!`, and
# build.py emits an `<!-- llmwiki:metadata -->` comment that AI agents parse.
_TAG_START_RE = re.compile(r"<(/?[A-Za-z][A-Za-z0-9:_-]*)")
# #sec-13 (#557): also neutralise raw `<![CDATA[` blocks in prose. CDATA
# isn't allowed in HTML but some browsers / parsers treat it as a
# start-of-foreign-content marker; surfaces in MathML / SVG islands or
# in legacy XHTML rendering paths. Escape the leading `<` so the
# surrounding markdown processor doesn't pass it through as-is.
_CDATA_START_RE = re.compile(r"<!\[CDATA\[")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


class _EscapeRawHtmlPreprocessor(Preprocessor):
    """Escape HTML tag-start patterns outside code spans so raw `<textarea>`
    etc. in session prose can never leak into the DOM as live elements.
    See the comment above `md_to_html` for the full rationale."""

    def run(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        for line in lines:
            parts: list[tuple[str, str]] = []
            last = 0
            for m in _INLINE_CODE_RE.finditer(line):
                parts.append(("text", line[last : m.start()]))
                parts.append(("code", m.group(0)))
                last = m.end()
            parts.append(("text", line[last:]))
            rebuilt: list[str] = []
            for kind, part in parts:
                if kind == "text":
                    # #sec-13: neutralise CDATA markers BEFORE the tag-
                    # start sub so we don't accidentally double-escape.
                    part = _CDATA_START_RE.sub(r"&lt;![CDATA[", part)
                    rebuilt.append(_TAG_START_RE.sub(r"&lt;\1", part))
                else:
                    rebuilt.append(part)
            out.append("".join(rebuilt))
        return out


# #283: in-memory content-hash cache for md_to_html. Same markdown body
# always produces the same HTML, and build steps call md_to_html on the
# same boilerplate (e.g. `## Connections`) across hundreds of pages.
# blake2b(digest_size=8) keyed + bounded by a size cap so repeated
# builds in the same Python process (tests, watch mode, bulk exports)
# don't re-parse.
#
# #417: switched from SHA-256 hex (allocates 64-byte string per call)
# to blake2b(digest_size=8) returning bytes. ~3× faster + 8× less
# allocation per cache key on a 5000-page corpus. The 8-byte (64-bit)
# digest gives a birthday-collision threshold around 4×10^9 entries —
# the 4096-entry cap stays many orders of magnitude below that.
_MD_CACHE: dict[bytes, str] = {}
_PLAIN_CACHE: dict[bytes, str] = {}
_MD_CACHE_MAX = 4096  # entries; ~20 MB ceiling at ~5 KB avg
_md_cache_hits = 0
_md_cache_misses = 0
_plain_cache_hits = 0
_plain_cache_misses = 0


def _content_key(body: str) -> bytes:
    """Compute the cache key for a markdown body (#417).

    blake2b is significantly faster than SHA-256 for short strings,
    and the 8-byte digest is enough headroom for the 4096-entry cap.
    Bytes (not hex) avoids the encode-back-to-string allocation.
    """
    return hashlib.blake2b(body.encode("utf-8"), digest_size=8).digest()


def md_to_html_cache_stats() -> dict[str, int]:
    """Return ``{hits, misses, size}`` for observability (#283)."""
    return {
        "hits": _md_cache_hits,
        "misses": _md_cache_misses,
        "size": len(_MD_CACHE),
        "plain_hits": _plain_cache_hits,
        "plain_misses": _plain_cache_misses,
        "plain_size": len(_PLAIN_CACHE),
    }


def md_to_html_cache_clear() -> None:
    """Clear the md_to_html + md_to_plain caches (used in tests)."""
    global _md_cache_hits, _md_cache_misses
    global _plain_cache_hits, _plain_cache_misses
    _MD_CACHE.clear()
    _PLAIN_CACHE.clear()
    _md_cache_hits = 0
    _md_cache_misses = 0
    _plain_cache_hits = 0
    _plain_cache_misses = 0


def _evict_first(cache: dict) -> None:
    """FIFO-evict the oldest cache entry."""
    try:
        first_key = next(iter(cache))
        del cache[first_key]
    except StopIteration:
        pass


def md_to_html(body: str) -> str:
    global _md_cache_hits, _md_cache_misses
    key = _content_key(body)
    cached = _MD_CACHE.get(key)
    if cached is not None:
        _md_cache_hits += 1
        return cached
    _md_cache_misses += 1
    result = _md_to_html_uncached(body)
    if len(_MD_CACHE) >= _MD_CACHE_MAX:
        _evict_first(_MD_CACHE)
    _MD_CACHE[key] = result
    return result


def _md_to_html_uncached(body: str) -> str:
    body = normalize_markdown(body)
    # v0.5: highlight.js replaces server-side Pygments/codehilite. The
    # fenced_code extension emits `<pre><code class="language-xxx">` and
    # highlight.js (loaded via CDN in page_head) picks it up client-side.
    # Benefits: lighter builds, no optional dep, consistent look across pages,
    # and auto-detection for untagged blocks.
    extensions = ["fenced_code", "tables", "toc", "sane_lists"]
    ext_configs: dict[str, dict[str, Any]] = {
        # #646: drop `permalink: True`. The Python-Markdown TOC
        # extension's permalink emits a `<a class="headerlink">¶</a>`
        # next to every heading; the site CSS doesn't style
        # `.headerlink` (only `.deep-link` is styled), so axe-core
        # flags every one as a `link-in-text-block` violation
        # (links that aren't visually distinguishable). The JS-
        # driven `.deep-link` icon next to each heading (rendered by
        # render/js.py) is the canonical deep-link affordance — it
        # has CSS + hover state + aria-hidden treatment. Two emitters
        # for the same job; the markdown one is the older one. Anchor
        # targets (`<h2 id="...">`) still ship via toc — links to
        # `#section-name` keep working.
        "toc": {"toc_depth": "2-3"},
    }
    md = markdown.Markdown(extensions=extensions, extension_configs=ext_configs)
    # v0.5 (#74): escape raw HTML tags in prose so session content mentioning
    # `<textarea>` etc. can't break the page. Runs after fenced_code (25) and
    # before html_block (20), so fenced code is preserved verbatim (through
    # placeholders), inline code via backticks is preserved by this
    # preprocessor's own backtick-skipping, and everything else is safe.
    md.preprocessors.register(
        _EscapeRawHtmlPreprocessor(md), "escape_raw_html_tags", 22
    )
    return md.convert(body)


def md_to_plain_text(body: str) -> str:
    """Strip markdown to plain text for the search index.

    #417: memoized on the same content key as md_to_html. The build
    pipeline calls md_to_html and md_to_plain_text on the same body
    repeatedly (per-page render + search-index extract + RSS summary
    + RSS summary). Sharing the key makes the second + third + …
    calls free.
    """
    global _plain_cache_hits, _plain_cache_misses
    key = _content_key(body)
    cached = _PLAIN_CACHE.get(key)
    if cached is not None:
        _plain_cache_hits += 1
        return cached
    _plain_cache_misses += 1
    result = _md_to_plain_text_uncached(body)
    if len(_PLAIN_CACHE) >= _MD_CACHE_MAX:
        _evict_first(_PLAIN_CACHE)
    _PLAIN_CACHE[key] = result
    return result


def _md_to_plain_text_uncached(body: str) -> str:
    body = normalize_markdown(strip_leading_h1(body))
    # Remove code blocks (they're noisy in search)
    body = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    # Inline code
    body = re.sub(r"`([^`]*)`", r"\1", body)
    # Links: [text](url) → text
    body = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", body)
    # Wikilinks: [[name]] → name
    body = re.sub(r"\[\[([^\]]*)\]\]", r"\1", body)
    # Headings: strip leading #
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
    # Bold/italic marks
    body = re.sub(r"\*\*([^*]*)\*\*", r"\1", body)
    body = re.sub(r"\*([^*]*)\*", r"\1", body)
    # HTML comments
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # Collapse whitespace
    body = re.sub(r"\s+", " ", body).strip()
    return body


# ─── helpers for frontmatter consumers ─────────────────────────────────────

def get_tools_list(meta: dict[str, Any]) -> list[str]:
    tools = meta.get("tools_used", [])
    if isinstance(tools, str):
        return [t.strip() for t in tools.strip("[]").split(",") if t.strip()]
    return list(tools) if tools else []


def short_started(meta: dict[str, Any]) -> str:
    s = str(meta.get("started", ""))
    return s[:16].replace("T", " ")


# ─── freshness (content staleness) ────────────────────────────────────────
# Cached once per build so every page sees the same "now" and the same
# thresholds. Populated lazily by render_freshness().
_FRESHNESS_CONFIG: tuple[int, int] | None = None
_BUILD_NOW: datetime | None = None


def render_freshness(meta: dict[str, Any]) -> str:
    """Render a freshness badge for a page's frontmatter using cached config.

    Thresholds come from ``config.json`` (freshness.green_days /
    yellow_days) or the module defaults. Build-time "now" is cached the
    first call so the whole site renders with one consistent clock.
    """
    global _FRESHNESS_CONFIG, _BUILD_NOW
    if _FRESHNESS_CONFIG is None:
        _FRESHNESS_CONFIG = load_freshness_config()
    if _BUILD_NOW is None:
        _BUILD_NOW = datetime.now(UTC).replace(tzinfo=None)
    green, yellow = _FRESHNESS_CONFIG
    return freshness_badge(meta, now=_BUILD_NOW, green_days=green, yellow_days=yellow)


# ─── html template helpers ─────────────────────────────────────────────────

# v0.5: highlight.js for client-side syntax highlighting. Two themes so the
# switcher can swap between light/dark without a network round-trip. Pinned
# to a major version for stability, served from jsdelivr.
HLJS_VERSION = "11.9.0"
HLJS_LIGHT_CSS = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/styles/github.min.css"
)
HLJS_DARK_CSS = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/styles/github-dark.min.css"
)
HLJS_SCRIPT = (
    f"https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS_VERSION}"
    "/build/highlight.min.js"
)


def _hljs_head_tags() -> str:
    """Return the `<link>` tags for highlight.js themes. The dark theme is
    loaded with ``disabled`` and the light theme is the default — the runtime
    swaps the ``disabled`` flag when the theme toggles, so code blocks stay in
    sync with the rest of the page."""
    return (
        f'  <link id="hljs-light" rel="stylesheet" href="{HLJS_LIGHT_CSS}">\n'
        f'  <link id="hljs-dark" rel="stylesheet" href="{HLJS_DARK_CSS}" disabled>\n'
    )


_PRE_PAINT_THEME_SCRIPT = """  <script>
    /* #458: read localStorage.llmwiki-theme BEFORE first paint so users
       never see a flash of the wrong theme when navigating between pages.
       Falls back to prefers-color-scheme, then dark. Mirrors the same
       pre-paint pattern graph.html already uses (#477). */
    (function () {
      try {
        var t = localStorage.getItem('llmwiki-theme');
        if (t !== 'dark' && t !== 'light') {
          t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
        }
        document.documentElement.setAttribute('data-theme', t);
      } catch (e) {
        document.documentElement.setAttribute('data-theme', 'dark');
      }
    })();
  </script>
"""


def page_head(title: str, description: str, css_prefix: str = "", lang: str = "en") -> str:
    # #ui-m13 (#576): lang argument lets callers override the default
    # `<html lang="en">` for translated docs (`docs/i18n/<locale>/`).
    # See also page_head_article() which has the same parameter.
    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}" dir="auto">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
{_PRE_PAINT_THEME_SCRIPT}  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <!-- #ui-m14 (#577): async-load Google Fonts via media="print" + onload swap so it doesn't render-block first paint. <noscript> fallback for JS-disabled users. -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
  <noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"></noscript>
{_hljs_head_tags()}  <link rel="stylesheet" href="{css_prefix}style.css">
  <!-- Inline SVG favicon so browsers never 404 /favicon.ico on a static tree. -->
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%237C3AED'/%3E%3Cpath d='M8 22V10l8 6 8-6v12' fill='none' stroke='%23fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>
<div class="progress-bar" id="progress-bar"></div>
"""


def page_head_article(
    title: str,
    description: str,
    css_prefix: str = "",
    canonical: str = "",
    date: str = "",
    metadata_comment: str = "",
    lang: str = "en",
) -> str:
    """v0.4: Extended page head for session (Article) pages with schema.org
    microdata, canonical link, and an AI-readable metadata HTML comment.

    #ui-m13 (#576): `lang` arg lets translated docs override the
    default `en`. `dir="auto"` lets the browser infer RTL/LTR per
    paragraph for sessions whose body contains Arabic / Hebrew
    transliterations or quotes."""
    canonical_tag = ""
    if canonical:
        canonical_tag = f'  <link rel="canonical" href="{html.escape(canonical)}">\n'
    og_tags = f"""  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
"""
    if date:
        og_tags += f'  <meta property="article:published_time" content="{html.escape(date)}">\n'
    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}" dir="auto">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
{_PRE_PAINT_THEME_SCRIPT}{canonical_tag}{og_tags}  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <!-- #ui-m14 (#577): async-load Google Fonts via media="print" + onload swap so it doesn't render-block first paint. <noscript> fallback for JS-disabled users. -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
  <noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"></noscript>
{_hljs_head_tags()}  <link rel="stylesheet" href="{css_prefix}style.css">
  <!-- Inline SVG favicon so browsers never 404 /favicon.ico on a static tree. -->
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%237C3AED'/%3E%3Cpath d='M8 22V10l8 6 8-6v12' fill='none' stroke='%23fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
</head>
<body>
{metadata_comment}<a href="#main-content" class="skip-link">Skip to content</a>
<div class="progress-bar" id="progress-bar"></div>
"""


def _build_metadata_comment(
    meta: dict[str, Any],
    slug: str,
    project_slug: str,
    reading_min: int,
    html_stem: str = "",
) -> str:
    """An HTML comment at the top of every session page that AI agents can
    parse without needing a separate sidecar file."""
    fields = [
        f"slug: {slug}",
        f"project: {project_slug}",
    ]
    for key in (
        "date", "started", "ended", "model", "gitBranch", "permissionMode",
        "user_messages", "tool_calls", "sessionId",
    ):
        val = meta.get(key)
        if val is not None:
            fields.append(f"{key}: {val}")
    # #36: restore local username in cwd so agents scraping the HTML
    # comment get a usable path (raw frontmatter keeps USER).
    cwd_local = local_cwd(meta)
    if cwd_local:
        fields.append(f"cwd: {cwd_local}")
    tools = get_tools_list(meta)
    if tools:
        fields.append(f"tools_used: [{', '.join(tools)}]")
    fields.append(f"reading_min: {reading_min}")
    stem = html_stem or slug
    fields.append(f"md_source: sources/{project_slug}/{stem}.md")
    body = "\n".join(fields)
    return f"<!-- llmwiki:metadata\n{body}\n-->\n"


def nav_bar(active: str, link_prefix: str = "") -> str:
    def link(href: str, label: str, key: str) -> str:
        cls = ' class="active"' if key == active else ""
        return f'<a href="{link_prefix}{href}"{cls}>{label}</a>'

    # #460: hamburger pattern for tablet/mobile (≤1023px). The desktop
    # nav-links row is hidden below 1024 (CSS rule), so without this
    # button the Recent / Graph / Analytics / Docs entries would be
    # unreachable on mobile (the bottom nav only carries
    # Home / Projects / Sessions). The drawer below mirrors the same
    # links vertically. JS in render/js.py wires aria-expanded,
    # ESC-to-close, and focus return.
    def drawer_link(href, label, key):
        return (
            f'  <a href="{link_prefix}{href}" class="nav-drawer-link'
            + (' active' if key == active else '') + '">'
            + label + '</a>'
        )
    # Post-review: dropped `role="menu"` + `aria-labelledby` — children
    # are plain <a>, not role="menuitem", so screen readers were being
    # told "press arrow keys" which did nothing. The drawer is a
    # disclosure nav, not an ARIA menu. The hamburger's aria-controls
    # already provides the trigger→drawer association; no role needed
    # on the container.
    nav_drawer_html = f"""<div id="nav-drawer" class="nav-drawer" hidden aria-label="Main navigation">
{drawer_link("index.html", "Home", "home")}
{drawer_link("raw.html", "Raw", "raw")}
{drawer_link("graph.html", "Graph", "graph")}
{drawer_link("projects/index.html", "Projects", "projects")}
{drawer_link("sessions/index.html", "Sessions", "sessions")}
{drawer_link("analytics.html", "Analytics", "analytics")}
{drawer_link("candidates.html", "Candidates", "candidates")}
{drawer_link("docs/index.html", "Docs", "docs")}
</div>"""
    return f"""<header class="nav">
  <div class="nav-inner">
    <a href="{link_prefix}index.html" class="nav-brand">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
      LLM Wiki
    </a>
    <button type="button" class="nav-hamburger" id="nav-hamburger"
            aria-expanded="false" aria-controls="nav-drawer"
            aria-label="Open navigation menu">
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <nav class="nav-links">
      {link("index.html", "Home", "home")}
      {link("raw.html", "Raw", "raw")}
      {link("graph.html", "Graph", "graph")}
      {link("projects/index.html", "Projects", "projects")}
      {link("sessions/index.html", "Sessions", "sessions")}
      {link("analytics.html", "Analytics", "analytics")}
      {link("candidates.html", "Candidates", "candidates")}
      {link("docs/index.html", "Docs", "docs")}
      <button class="nav-search-btn" id="open-palette"
              aria-label="Open command palette"
              aria-haspopup="dialog" aria-expanded="false" aria-controls="palette">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span>Search</span>
        <kbd>⌘K</kbd>
      </button>
      <button class="theme-toggle" id="theme-toggle"
              aria-label="Toggle dark mode" aria-pressed="false">
        <svg aria-hidden="true" class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg aria-hidden="true" class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      </button>
    </nav>
  </div>
  {nav_drawer_html}
</header>
"""


def breadcrumbs_bar(crumbs: list[tuple[str, str]], link_prefix: str = "") -> str:
    if not crumbs:
        return ""
    parts = []
    for label, href in crumbs:
        if href:
            parts.append(f'<a href="{link_prefix}{html.escape(href)}">{html.escape(label)}</a>')
        else:
            parts.append(f'<span aria-current="page">{html.escape(label)}</span>')
    sep = ' <span class="crumb-sep">›</span> '
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb">{sep.join(parts)}</nav>'


def hero(
    title: str,
    subtitle: str,
    size: str = "",
    subtitle_is_html: bool = False,
    main_class: str = "",
) -> str:
    cls = f"hero {size}".strip()
    sub = subtitle if subtitle_is_html else html.escape(subtitle)
    main_attr = f' class="{main_class}"' if main_class else ""
    return f"""<main id="main-content"{main_attr}>
<section class="{cls}">
  <div class="container">
    <h1>{html.escape(title)}</h1>
    <p class="hero-sub">{sub}</p>
  </div>
</section>
"""


def search_palette_markup(js_prefix: str = "") -> str:
    """Command palette + shortcuts dialog + the search-data globals.

    Shared so every page carrying the nav's search button also carries the
    dialog that button opens. graph.html loads script.js for the palette
    (#456) but injected only the nav, so the button and Cmd+K silently
    no-opped on `#palette` being absent (#20 follow-up).
    """
    return f"""<div id="palette" class="palette">
  <div class="palette-backdrop" id="palette-backdrop"></div>
  <div class="palette-modal" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-header">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="text" id="palette-input" aria-label="Search pages" placeholder="Search… or type:session project:llm-wiki date:>2026-03 sort:date" autocomplete="off" spellcheck="false">
      <kbd>ESC</kbd>
    </div>
    <ul class="palette-results" id="palette-results"></ul>
    <div class="palette-footer muted">
      <span><kbd>↑↓</kbd> navigate</span>
      <span><kbd>↵</kbd> open</span>
      <span><kbd>ESC</kbd> close</span>
    </div>
  </div>
</div>
<div id="help-dialog" class="help-dialog">
  <div class="palette-backdrop" id="help-backdrop"></div>
  <div class="help-modal">
    <h2>Keyboard shortcuts</h2>
    <table>
      <tr><td><kbd>⌘K</kbd> / <kbd>Ctrl+K</kbd></td><td>Open command palette</td></tr>
      <tr><td><kbd>/</kbd></td><td>Focus search</td></tr>
      <tr><td><kbd>g h</kbd></td><td>Go to home</td></tr>
      <tr><td><kbd>g p</kbd></td><td>Go to projects</td></tr>
      <tr><td><kbd>g s</kbd></td><td>Go to sessions</td></tr>
      <tr><td><kbd>j</kbd> / <kbd>k</kbd></td><td>Next / prev row (tables)</td></tr>
      <tr><td><kbd>?</kbd></td><td>Show this help</td></tr>
      <tr><td><kbd>Esc</kbd></td><td>Close dialogs</td></tr>
    </table>
    <h3>Structured queries</h3>
    <p class="muted help-dialog-hint">Mix key:value filters with free text in the palette:</p>
    <table>
      <tr><td><code>type:session</code></td><td>Only session pages</td></tr>
      <tr><td><code>project:llm-wiki</code></td><td>Filter by project name (substring)</td></tr>
      <tr><td><code>model:claude</code></td><td>Filter by model name (substring)</td></tr>
      <tr><td><code>date:&gt;2026-03-01</code></td><td>Sessions after a date</td></tr>
      <tr><td><code>date:&lt;2026-04-01</code></td><td>Sessions before a date</td></tr>
      <tr><td><code>tags:rust</code></td><td>Pages mentioning a tag/topic</td></tr>
      <tr><td><code>sort:date</code></td><td>Sort results by date (newest first)</td></tr>
    </table>
    <p class="muted help-dialog-example">Example: <code>type:session project:llm-wiki date:&gt;2026-04 sort:date</code></p>
    <button class="btn" id="help-close">Close</button>
  </div>
</div>
<script>
  window.LLMWIKI_INDEX_URL = "{js_prefix}search-index.json";
  // #20: the search data the page actually loads. Injected as a script tag on
  // demand, which is the only channel that also works over file://.
  window.LLMWIKI_INDEX_JS_URL = "{js_prefix}search-index.js";
</script>"""


def page_foot(js_prefix: str = "") -> str:
    built = (
        f" · built {_BUILD_NOW.strftime('%Y-%m-%d %H:%M')} UTC" if _BUILD_NOW else ""
    )
    return f"""<footer class="footer">
  <div class="container">
    <p class="muted">llmwiki · <a href="{js_prefix}index.html">home</a> · press <kbd>?</kbd> for shortcuts{built}</p>
  </div>
</footer>
<nav class="mobile-bottom-nav" aria-label="Mobile navigation">
  <a href="{js_prefix}index.html" class="mbn-link" data-page="home">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
    <span>Home</span>
  </a>
  <a href="{js_prefix}projects/index.html" class="mbn-link" data-page="projects">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
    <span>Projects</span>
  </a>
  <a href="{js_prefix}sessions/index.html" class="mbn-link" data-page="sessions">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
    <span>Sessions</span>
  </a>
  <button type="button" class="mbn-link" id="mbn-search" aria-label="Search">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <span>Search</span>
  </button>
  <button type="button" class="mbn-link" id="mbn-theme" aria-label="Toggle theme" aria-pressed="false">
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    <span>Theme</span>
  </button>
</nav>
{search_palette_markup(js_prefix)}
<script src="{js_prefix}llmwiki-state.js"></script>
<script src="{HLJS_SCRIPT}" defer></script>
<script>
  // v0.5: Run highlight.js once the CDN script lands. Defer keeps it out of
  // the critical path; the DOMContentLoaded fallback covers the case where
  // hljs arrives before/after DOM ready depending on cache state.
  function __llmwikiHljsInit() {{
    if (window.hljs) {{ window.hljs.highlightAll(); }}
    else {{ window.addEventListener('load', function() {{ if (window.hljs) window.hljs.highlightAll(); }}); }}
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', __llmwikiHljsInit);
  }} else {{
    __llmwikiHljsInit();
  }}
</script>
<script src="{js_prefix}script.js"></script>
</body>
</html>
"""


# ─── page renderers ────────────────────────────────────────────────────────

def _pluralize(n: int, singular: str, plural: str | None = None) -> str:
    """Return ``"1 session"`` for n=1, ``"3 sessions"`` for n=3.

    Closes #387 U7. The hero subtitle and any other count-bearing
    user-facing string should never read as ``"1 sessions"``."""
    if plural is None:
        plural = singular + "s"
    return f"{n} {singular if n == 1 else plural}"


def calc_reading_time(body: str, wpm: int = 225) -> int:
    """Estimate reading time in minutes from a markdown body."""
    words = len(re.findall(r"\w+", body))
    return max(1, round(words / wpm))


# #36: stale greying for the copyable resume one-liner.
# Only Claude Code gets a resume command today (issue #36); its transcript
# retention is ~30 days. Cursor (`agent --resume`) and OpenClaw are not
# wired here yet — when they are, give each adapter its own window rather
# than reusing this Claude-specific constant.
RESUME_RETENTION_DAYS = 30


def local_cwd(meta: dict[str, Any]) -> str:
    """Session cwd with username redaction reversed for local use (#36).

    Convert already wrote the absolute cwd into frontmatter — then
    redacted the home-dir username to ``USER`` so ``raw/`` is safe to
    commit. Build reverses that single substitution so resume / project
    titles show a real path. See ``restore_local_path``.
    """

    return restore_local_path(str(meta.get("cwd") or "").strip())


def supports_resume(meta: dict[str, Any], path: Path | None = None) -> bool:
    """True when this session can be resumed with ``claude --resume``.

    Issue #36 only specified Claude Code. Cursor has ``agent --resume``
    and OpenClaw is unconfirmed — both stay hidden until we wire them
    with the right CLI shape (not ``claude --resume``).
    """
    if _is_subagent(meta, path or Path("session.md")):
        return False
    _label, css_class = detect_agent_label(meta)
    return css_class == "agent-claude"


def resume_command(meta: dict[str, Any], path: Path | None = None) -> str | None:
    """Return ``cd <real-cwd> && claude --resume <sessionId>``, or None."""
    if not supports_resume(meta, path):
        return None
    cwd = local_cwd(meta)
    session_id = str(meta.get("sessionId") or "").strip()
    if not cwd or not session_id:
        return None
    return f"cd {cwd} && claude --resume {session_id}"


def resume_is_stale(meta: dict[str, Any], *, now: datetime | None = None) -> bool:
    """True when the session is older than Claude Code's retention window."""
    raw = str(meta.get("started") or meta.get("ended") or meta.get("date") or "")
    if not raw:
        return False
    try:
        # Accept both ISO timestamps and bare YYYY-MM-DD.
        if "T" in raw:
            started = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            started = datetime.fromisoformat(raw).replace(tzinfo=UTC)
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    ref = now or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return (ref - started) > timedelta(days=RESUME_RETENTION_DAYS)


def project_disk_paths(
    sessions: list[tuple[Path, dict[str, Any], str]],
) -> tuple[str | None, list[str]]:
    """Derive a project's on-disk path(s) from session ``cwd`` values.

    Returns ``(primary, all_distinct)`` where ``primary`` is the most
    common *local* (un-redacted) cwd, and ``all_distinct`` is every
    unique cwd in frequency-then-alpha order. Divergent cwds (renames,
    worktrees) stay visible so the reader isn't lied to by a single path.
    """
    counts: Counter[str] = Counter()
    for _path, meta, _body in sessions:
        cwd = local_cwd(meta)
        if cwd:
            counts[cwd] += 1
    if not counts:
        return None, []
    # Most common first; ties broken alphabetically for stability.
    ordered = sorted(counts.keys(), key=lambda c: (-counts[c], c))
    return ordered[0], ordered


def render_resume_block(meta: dict[str, Any], path: Path | None = None) -> str:
    """HTML for the copyable ``claude --resume`` one-liner (#36)."""
    cmd = resume_command(meta, path)
    if not cmd:
        return ""
    stale = resume_is_stale(meta)
    stale_cls = " resume-stale" if stale else ""
    hint = (
        "Resume may fail — session is older than Claude Code's ~30-day "
        "transcript retention window."
        if stale
        else "Resume works while the transcript is within Claude Code's "
        "retention window (~30 days)."
    )
    return (
        f'<div class="resume-command{stale_cls}">'
        f'<code class="resume-cmd-text">{html.escape(cmd)}</code>'
        f'<button class="btn resume-copy-btn" type="button" '
        f'title="Copy resume command" onclick="copyResume(this)">Copy</button>'
        f'<span class="muted resume-hint">{html.escape(hint)}</span>'
        f"</div>"
    )


def render_project_disk_path_html(primary: str | None, all_paths: list[str]) -> str:
    """HTML strip listing *additional* project paths when they diverge (#36).

    The primary absolute path is the project page title — only emit this
    strip when there is more than one distinct cwd.
    """
    if not primary or len(all_paths) <= 1:
        return ""
    chips = ", ".join(f"<code>{html.escape(p)}</code>" for p in all_paths)
    return (
        f'<div class="project-disk-path muted">'
        f'Also seen at <span class="project-disk-path-list">{chips}</span></div>'
    )


def render_session(
    path: Path,
    meta: dict[str, Any],
    body: str,
    out_dir: Path,
    project_slug: str,
) -> Path:
    slug = meta.get("slug", path.stem)
    date = meta.get("date", "")
    title_raw = meta.get("title", f"Session: {slug}")

    body = strip_leading_h1(body)
    body_html = md_to_html(body)
    # #270: session transcripts often reference files the user had open
    # during the session (tasks.md, CLAUDE.md, convert.py, etc). Route
    # the ones that look like repo source code or root files to GitHub
    # so the links don't dead-end after ingest.
    body_html = rewrite_source_code_links_to_github(body_html)
    # #284: now that README.md and CONTRIBUTING.md compile to
    # site/README.html / site/CONTRIBUTING.html, session bodies that
    # reference those files should route to the compiled pages.
    # Generic .md → .html pass runs AFTER the GitHub rewrite so
    # source-code and repo-root-only refs (CLAUDE.md, AGENTS.md) still
    # go to GitHub.
    body_html = rewrite_md_links_to_html(body_html)
    # #336: for remaining session-local refs (tasks.md, user_profile.md,
    # wiki/sources/<proj>/... wikilinks), drop the anchor but keep the
    # text — they point at files unique to the user's project and don't
    # compile to anywhere on the site.
    body_html = strip_dead_session_refs(body_html)
    raw_md_for_copy = html.escape(body)
    reading_min = calc_reading_time(body)

    bits: list[str] = []
    if meta.get("project"):
        bits.append(
            f'<a href="../../projects/{html.escape(str(meta["project"]))}.html">{html.escape(str(meta["project"]))}</a>'
        )
    # Agent badge — shows Claude / Codex / Copilot / Cursor / Gemini
    bits.append(render_agent_badge(meta))
    if meta.get("gitBranch"):
        bits.append(f'branch <code>{html.escape(str(meta["gitBranch"]))}</code>')
    if meta.get("model"):
        bits.append(f'<code>{html.escape(str(meta["model"]))}</code>')
    # #36: surface cwd + real sessionId in the hero (the page title is
    # llmwiki's 8-hex slug, useless for `claude --resume`). cwd is
    # restored to the local absolute path (frontmatter stores USER).
    cwd_local = local_cwd(meta)
    if cwd_local:
        bits.append(f'cwd <code>{html.escape(cwd_local)}</code>')
    if meta.get("sessionId"):
        bits.append(
            f'id <code class="session-id">{html.escape(str(meta["sessionId"]))}</code>'
        )
    if meta.get("started"):
        bits.append(f'<span class="muted">{html.escape(short_started(meta))}</span>')
    if meta.get("user_messages"):
        bits.append(f'{html.escape(str(meta["user_messages"]))} msgs')
    if meta.get("tool_calls"):
        bits.append(f'{html.escape(str(meta["tool_calls"]))} tools')
    bits.append(f'<span class="muted">{reading_min} min read</span>')
    bits.append(render_freshness(meta))
    meta_strip = " · ".join(bits) if bits else ""

    tools_list = get_tools_list(meta)
    tools_preview = ""
    if tools_list:
        preview = ", ".join(tools_list[:6])
        if len(tools_list) > 6:
            preview += f", +{len(tools_list) - 6} more"
        tools_preview = f'<div class="meta-tools muted">tools: {html.escape(preview)}</div>'

    # v0.8 (#65): horizontal bar chart of tool calls in this session.
    # Uses the `tool_counts` JSON dict from frontmatter (#63). Empty
    # sessions (no recorded calls) render nothing.
    tool_chart_svg = render_session_tool_chart(meta)
    tool_chart_block = ""
    if tool_chart_svg:
        tool_chart_block = (
            '<div class="tool-chart-card">'
            '<div class="tool-chart-label muted">Tool calls</div>'
            f'{tool_chart_svg}'
            '</div>'
        )

    # v0.8 (#66): session token-usage card. Input / cache_creation /
    # cache_read / output plus a cache-hit-ratio tier badge. Sessions
    # missing token_totals (older converter output) render nothing.
    token_card_block = render_session_token_card(meta)

    # IMPORTANT: The HTML file is named `<path.stem>.html` (e.g. date-slug),
    # NOT `<slug>.html`. The Download .md link + canonical must use path.stem.
    html_stem = path.stem
    raw_md_path = f"../../sources/{project_slug}/{path.name}"
    resume_html = render_resume_block(meta, path)
    actions_html = f"""<div class="session-actions">
  <button class="btn btn-primary" type="button" aria-label="Copy session content as markdown" title="Copy as markdown" onclick="copyMarkdown(this)">Copy as markdown</button>
  <a class="btn" href="../../projects/{html.escape(project_slug)}.html">← {html.escape(project_slug)}</a>
  <a class="btn" href="{html.escape(raw_md_path)}" download>Download .md</a>
  <textarea class="md-source" hidden>{raw_md_for_copy}</textarea>
</div>
{resume_html}"""

    crumbs = [
        ("Home", "index.html"),
        ("Projects", "projects/index.html"),
        (project_slug, f"projects/{project_slug}.html"),
        (str(slug), ""),
    ]
    breadcrumbs = breadcrumbs_bar(crumbs, link_prefix="../../")

    # v0.4: machine-readable metadata appendix (HTML comment that AI agents
    # scraping HTML can parse; full markdown lives under sources/<project>/).
    metadata_comment = _build_metadata_comment(meta, slug, project_slug, reading_min, html_stem=html_stem)

    # v0.4: page_head with schema.org article microdata + canonical link.
    # Canonical is relative to the current page (same dir) so the link checker
    # resolves it correctly whether served from a subdomain root or any path.
    page = (
        page_head_article(
            title=f"{title_raw} — LLM Wiki",
            description=f"Session transcript from {meta.get('project', '')} on {date}",
            css_prefix="../../",
            canonical=f"{html_stem}.html",
            date=str(meta.get("started") or date),
            metadata_comment=metadata_comment,
        )
        + nav_bar("sessions", link_prefix="../../")
        + hero(str(title_raw), meta_strip, size="hero-sm", subtitle_is_html=True)
        # #471: human-readable description rendered as a subtitle below
        # the hero, before the meta-strip. Only emit if frontmatter
        # carries the field; older sessions skip this block cleanly.
        + (
            f'<div class="container session-description"><p>{html.escape(str(meta["description"]))}</p></div>'
            if meta.get("description") else ""
        )
        + f'<section class="section">\n  <div class="container">\n{breadcrumbs}\n{tools_preview}\n{actions_html}\n{tool_chart_block}\n{token_card_block}\n    <article class="content" itemscope itemtype="https://schema.org/Article">\n'
        + f'<meta itemprop="headline" content="{html.escape(str(title_raw))}">\n'
        + f'<meta itemprop="datePublished" content="{html.escape(str(meta.get("started") or date))}">\n'
        + '<meta itemprop="inLanguage" content="en">\n'
        + body_html
        + '\n    </article>\n  </div>\n</section>\n</main>\n'
        + page_foot(js_prefix="../../")
    )

    out_path = out_dir / "sessions" / project_slug / f"{path.stem}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_project_page(
    project_slug: str,
    sessions: list[tuple[Path, dict[str, Any], str]],
    out_dir: Path,
    usage_totals: dict[str, Any] | None = None,
    doc_count: int = 0,
) -> Path:
    main_sessions = [s for s in sessions if not _is_subagent(s[1], s[0])]
    subagent_sessions = [s for s in sessions if s not in main_sessions]

    def card(p: Path, meta: dict[str, Any]) -> str:
        slug = meta.get("slug", p.stem)
        title = meta.get("title", slug)
        # Strip "Session: project/" prefix for cleaner display
        if title.startswith("Session: "):
            title = title[9:]
        date = meta.get("date", "")
        model = meta.get("model", "")
        umsgs = meta.get("user_messages", "")
        tcalls = meta.get("tool_calls", "")
        href = f"../sessions/{project_slug}/{p.stem}.html"
        badge = render_freshness(meta)
        return f"""  <a class="card" href="{href}">
    <div class="card-title">{html.escape(str(title))}</div>
    <div class="card-meta">{html.escape(str(date))} · {html.escape(str(model))}</div>
    <div class="card-stats muted">{html.escape(str(umsgs))} messages · {html.escape(str(tcalls))} tool calls</div>
    <div class="card-badge">{badge}</div>
  </a>"""

    cards_main = "\n".join(card(p, m) for p, m, _ in main_sessions)
    cards_sub = "\n".join(card(p, m) for p, m, _ in subagent_sessions)

    sub_section = ""
    if subagent_sessions:
        sub_section = (
            '<details class="sub-section"><summary>Sub-agent runs ('
            + str(len(subagent_sessions))
            + ")</summary>\n<div class=\"card-grid\">\n"
            + cards_sub
            + "\n</div>\n</details>\n"
        )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Projects", "projects/index.html"), (project_slug, "")],
        link_prefix="../",
    )

    # v0.8 (#64, #72): per-project 365-day heatmap — same window as the
    # aggregate on the home page, but filtered to just this project's
    # sessions. Sparse projects (only a handful of sessions) still render
    # the full grid with the rest as level-0 cells, so the shape matches.
    proj_entries = [m for _, m, _ in sessions]
    proj_counts = collect_session_counts(proj_entries, project_slug=project_slug)
    proj_heatmap = render_heatmap(proj_counts, title_prefix=f"{project_slug} agents activity")
    heatmap_block = f"""<section class="section heatmap-section">
  <div class="container">
    <div class="activity-heatmap">
      <div class="heatmap-label muted">Agents Activity · last 18 months · {html.escape(project_slug)}</div>
      {proj_heatmap}
    </div>
  </div>
</section>"""

    # v0.8 (#65): aggregate tool-call bar chart across all sessions in
    # this project. Projects with no recorded tool calls render nothing.
    proj_tool_chart = render_project_tool_chart(proj_entries, project_slug)
    tool_chart_block = ""
    if proj_tool_chart:
        tool_chart_block = f"""<section class="section tool-chart-section">
  <div class="container">
    <div class="tool-chart-card">
      <div class="tool-chart-label muted">Tool calls · {html.escape(project_slug)} aggregate</div>
      {proj_tool_chart}
    </div>
  </div>
</section>"""

    # v0.8 (#66): project token timeline card (log-scale area chart of
    # total tokens per session date + aggregate cache hit ratio in the
    # header). Empty for projects without any token data.
    proj_token_card_html = render_project_token_card(proj_entries, project_slug)
    token_timeline_block = ""
    if proj_token_card_html:
        token_timeline_block = f"""<section class="section token-timeline-section">
  <div class="container">
    {proj_token_card_html}
  </div>
</section>"""

    # Project topics strip — renders below the hero, above the heatmap.
    # Explicit profile via wiki/projects/<slug>.md wins over the
    # session-tag fallback. Projects with no topics render an empty
    # strip (no chip row at all).
    proj_profile = load_project_profile(PROJECTS_META_DIR, project_slug)
    proj_topics = get_project_topics(PROJECTS_META_DIR, project_slug, proj_entries)
    topics_html = render_topic_chips(
        proj_topics, max_visible=12, classname="project-topics project-hero-topics"
    )
    description_html = ""
    if proj_profile and proj_profile.get("description"):
        description_html = (
            f'<p class="project-description muted">'
            f'{html.escape(proj_profile["description"])}</p>'
        )
    # homepage from wiki/projects/<slug>.md is intentionally not rendered
    # on the project page (#36 follow-up) — the absolute cwd is the
    # identity; an external URL under the chips was noise.
    topics_strip = ""
    if topics_html or description_html:
        topics_strip = (
            '<section class="section project-topics-section">\n'
            '  <div class="container">\n'
            f'    {description_html}\n'
            f'    {topics_html}\n'
            '  </div>\n'
            '</section>\n'
        )

    usage_block = render_project_usage_block(project_slug, usage_totals or {}, doc_count)

    # #36: surface the project's on-disk path (most common cwd across
    # its sessions; list all distinct cwds when they diverge).
    primary_cwd, all_cwds = project_disk_paths(sessions)
    disk_path_html = render_project_disk_path_html(primary_cwd, all_cwds)
    disk_path_strip = ""
    if disk_path_html:
        disk_path_strip = (
            '<section class="section project-disk-section">\n'
            '  <div class="container">\n'
            f'    {disk_path_html}\n'
            '  </div>\n'
            '</section>\n'
        )

    body = f"""{topics_strip}
{disk_path_strip}
{heatmap_block}
{tool_chart_block}
{token_timeline_block}
{usage_block}
<section class="section">
  <div class="container">
    {crumbs}
    <h2>Main sessions ({len(main_sessions)})</h2>
    <div class="card-grid">
{cards_main}
    </div>
    {sub_section}
  </div>
</section>
</main>
"""

    # #36: project identity is the absolute disk path, not the slug.
    # Filename stays `<slug>.html` for stable URLs; the hero title is
    # the restored local cwd. Slug stays in the subtitle for search.
    display_name = primary_cwd or project_slug
    hero_sub_bits = [
        f"slug <code>{html.escape(project_slug)}</code>",
        f"{len(main_sessions)} main sessions",
        f"{len(subagent_sessions)} sub-agent runs",
    ]
    page = (
        page_head(
            f"{display_name} — LLM Wiki",
            f"{len(sessions)} Claude Code sessions from {display_name}",
            css_prefix="../",
        )
        + nav_bar("projects", link_prefix="../")
        + hero(
            display_name,
            " · ".join(hero_sub_bits),
            subtitle_is_html=True,
            main_class="project-page",
        )
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "projects" / f"{project_slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_projects_index(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
) -> Path:
    cards = []
    for project, sessions in sorted(groups.items(), key=lambda x: -len(x[1])):
        main_count = sum(1 for p, m, _ in sessions if not _is_subagent(m, p))
        sub_count = len(sessions) - main_count
        # Freshness reflects the newest session in the project.
        newest_meta = max(
            (m for _, m, _ in sessions),
            key=lambda m: str(m.get("ended") or m.get("started") or m.get("date") or ""),
            default={},
        )
        badge = render_freshness(newest_meta)
        # #36: project cards are titled by absolute disk path; slug is
        # secondary meta so munged names like `aleksandrmakarov-code`
        # aren't the only identity the reader sees.
        primary_cwd, all_cwds = project_disk_paths(sessions)
        title = primary_cwd or project
        extra = ""
        if primary_cwd and len(all_cwds) > 1:
            n_other = len(all_cwds) - 1
            extra = (
                f' <span class="muted">'
                f'(+{n_other} other cwd{"-s" if n_other != 1 else ""})</span>'
            )
        slug_bit = (
            f'<div class="card-meta">slug <code>{html.escape(project)}</code>'
            f' · {main_count} main · {sub_count} sub-agent</div>'
        )
        cards.append(
            f"""  <a class="card card-project" href="{html.escape(project)}.html">
    <div class="card-title"><code>{html.escape(title)}</code>{extra}</div>
    {slug_bit}
    <div class="card-badge">{badge}</div>
  </a>"""
        )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Projects", "")], link_prefix="../"
    )

    body = f"""<section class="section">
  <div class="container">
    {crumbs}
    <div class="card-grid">
{chr(10).join(cards)}
    </div>
  </div>
</section>
</main>
"""

    page = (
        page_head("Projects — LLM Wiki", "All projects with Claude Code session history", css_prefix="../")
        + nav_bar("projects", link_prefix="../")
        + hero("Projects", _pluralize(len(groups), "project"))
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "projects" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_sessions_index(
    sources: list[tuple[Path, dict[str, Any], str]],
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
) -> Path:

    rows = []

    def key(t: tuple[Path, dict[str, Any], str]) -> str:
        return str(t[1].get("started", "")) or str(t[0].name)

    for p, meta, _ in sorted(sources, key=key, reverse=True):
        project = meta.get("project", p.parent.name)
        slug = meta.get("slug", p.stem)
        title = meta.get("title", slug)
        # Strip "Session: " prefix for cleaner display
        if title.startswith("Session: "):
            title = title[9:]
        # #452: titles auto-generated from session frontmatter follow the
        # pattern "<slug> — <date>" but the table already has a dedicated
        # Date column, so the trailing date is redundant. Strip it so the
        # Session cell shows just the slug (or whatever custom title the
        # user gave) and the Date column carries the date alone.
        date = meta.get("date", "")
        if date and title.endswith(f" — {date}"):
            title = title[: -(len(date) + 3)]
        # Truncate long titles for table display
        display_title = title[:70] + "..." if len(title) > 70 else title
        # #471: human-readable description from the first user turn —
        # if frontmatter carries one, render it as a small muted line
        # below the slug. Falls back to no second line for older
        # sessions without the field.
        # #56: descriptions were redacted at convert time; restore local
        # paths so the index matches session detail / resume paths.
        description = restore_local_path(
            str(meta.get("description") or "").strip()
        )
        desc_line = (
            f'<div class="session-cell-desc muted">{html.escape(description)}</div>'
            if description else ""
        )
        model = meta.get("model", "")
        umsgs = meta.get("user_messages", "")
        tcalls = meta.get("tool_calls", "")
        agent_label, _agent_css = detect_agent_label(meta)
        # #56: surface restored cwd so the index matches the detail page
        # one click away (and so encoded ``-Users-USER-`` segments are
        # reversed like the leading ``/Users/USER/``).
        cwd_local = local_cwd(meta)
        cwd_cell = (
            f"<code>{html.escape(cwd_local)}</code>" if cwd_local else ""
        )
        href = f"{project}/{p.stem}.html"
        rows.append(
            f"""        <tr data-project="{html.escape(str(project))}" data-agent="{html.escape(agent_label)}" data-model="{html.escape(str(model))}" data-date="{html.escape(str(date))}" data-slug="{html.escape(str(slug))}">
          <td><a href="{html.escape(str(href))}">{html.escape(str(display_title))}</a>{desc_line}</td>
          <td>{render_agent_badge(meta)}</td>
          <td><a href="../projects/{html.escape(str(project))}.html">{html.escape(str(project))}</a></td>
          <td>{html.escape(str(date))}</td>
          <td class="session-cwd">{cwd_cell}</td>
          <td><code>{html.escape(str(model))}</code></td>
          <td class="num">{html.escape(str(umsgs))}</td>
          <td class="num">{html.escape(str(tcalls))}</td>
        </tr>"""
        )

    project_options = "\n".join(
        f'        <option value="{html.escape(p)}">{html.escape(p)}</option>'
        for p in sorted(groups.keys())
    )

    agents = sorted({
        detect_agent_label(m)[0]
        for _, m, _ in sources
    })
    agent_options = "\n".join(
        f'        <option value="{html.escape(a)}">{html.escape(a)}</option>'
        for a in agents
    )

    models = sorted(
        {str(m.get("model", "")) for _, m, _ in sources if m.get("model")}
    )
    model_options = "\n".join(
        f'        <option value="{html.escape(m)}">{html.escape(m)}</option>'
        for m in models
    )

    crumbs = breadcrumbs_bar(
        [("Home", "index.html"), ("Sessions", "")], link_prefix="../"
    )

    body = f"""<section class="section">
  <div class="container">
    {crumbs}
    <div class="filter-bar">
      <label>Project
        <select id="filter-project">
          <option value="">All projects</option>
{project_options}
        </select>
      </label>
      <label>Agent
        <select id="filter-agent">
          <option value="">All agents</option>
{agent_options}
        </select>
      </label>
      <label>Model
        <select id="filter-model">
          <option value="">All models</option>
{model_options}
        </select>
      </label>
      <label>From
        <input type="date" id="filter-date-from">
      </label>
      <label>To
        <input type="date" id="filter-date-to">
      </label>
      <label>Slug
        <input type="text" id="filter-text" placeholder="part of slug…">
      </label>
      <button class="btn" id="filter-clear">Clear</button>
      <span class="filter-count muted" id="filter-count"></span>
    </div>
    <div class="table-wrap">
    <table class="sessions-table">
      <colgroup>
        <col style="width: 18%">
        <col style="width: 7%">
        <col style="width: 16%">
        <col style="width: 10%">
        <col style="width: 26%">
        <col style="width: 13%">
        <col style="width: 5%">
        <col style="width: 5%">
      </colgroup>
      <thead>
        <tr><th>Session</th><th>Agent</th><th>Project</th><th>Date</th><th>Cwd</th><th>Model</th><th>Msgs</th><th>Tools</th></tr>
      </thead>
      <tbody id="sessions-tbody">
{chr(10).join(rows)}
      </tbody>
    </table>
    </div>
  </div>
</section>
</main>
"""

    page = (
        page_head("Sessions — LLM Wiki", "All Claude Code sessions, newest first", css_prefix="../")
        + nav_bar("sessions", link_prefix="../")
        + hero("All sessions", _pluralize(len(sources), "session") + " total")
        + body
        + page_foot(js_prefix="../")
    )

    out_path = out_dir / "sessions" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_analytics(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    all_sources: list[tuple[Path, dict[str, Any], str]],
    out_dir: Path,
    synthesis: str | None = None,
    usage_totals: dict[str, Any] | None = None,
    docs_by_project: dict[str, int] | None = None,
    wiki_dir: Path | None = None,
    wiki_value: dict[str, Any] | None = None,
) -> Path:
    """Render ``analytics.html`` — hero stats, activity heatmaps, token
    stats, wiki usage (#52), recently-updated, projects grid."""
    total = len(all_sources)
    mains = sum(1 for p, m, _ in all_sources if not _is_subagent(m, p))
    subs = total - mains

    synth_block = ""
    if synthesis:
        synth_block = f"""<section class="section">
  <div class="container">
    <div class="synthesis">
      <h2>Overview</h2>
      {md_to_html(synthesis)}
    </div>
  </div>
</section>"""

    # Aggregate GitHub-style heatmaps (~18 months) — agents,
    # MCP calls, and optional read-type splits in one Activity section.
    heatmap_entries = [m for _, m, _ in all_sources]
    heatmap_counts = collect_session_counts(heatmap_entries)
    wv = wiki_value or {}
    mcp_days = wv.get("mcp_days") or {}
    activity_heatmaps = [
        activity_heatmap_div("Agents Activity", heatmap_counts, unit="sessions"),
        activity_heatmap_div(
            "Wiki MCP calls", day_int_counts(mcp_days, "mcp_calls"), unit="calls",
        ),
    ]
    if mcp_day_has_signal(mcp_days, "session_reads"):
        activity_heatmaps.append(activity_heatmap_div(
            "Session-page reads",
            day_int_counts(mcp_days, "session_reads"),
            unit="reads",
        ))
    if mcp_day_has_signal(mcp_days, "doc_reads"):
        activity_heatmaps.append(activity_heatmap_div(
            "Doc-page reads",
            day_int_counts(mcp_days, "doc_reads"),
            unit="reads",
        ))
    heatmap_block = (
        '<section class="section heatmap-section">\n'
        '  <div class="container">\n'
        '    <h2>Activity</h2>\n'
        + "\n".join(activity_heatmaps)
        + '\n  </div>\n</section>'
    )

    # v0.8 (#66): site-wide token summary stats — three cards showing
    # Tokens (value + avg per session), best cache hit project, and heaviest
    # project (by tokens). Empty if no session has token_totals data.
    metas_by_project: dict[str, list[dict[str, Any]]] = {}
    for project, sessions in groups.items():
        metas_by_project[project] = [m for _, m, _ in sessions]
    # #27: the "Heaviest project by MCP usage" card shares the token-stats
    # row, so the analytics page opens with a single line of stat cards.
    mcp_heaviest_card = render_mcp_heaviest_card(usage_totals or {}, link_prefix="")
    token_stats_block = render_site_token_stats(
        metas_by_project, link_prefix="", extra_cards=mcp_heaviest_card)

    # Wiki usage (#52): value cards, corpus mix, top pages, MCP table.
    wiki_usage_block = render_wiki_value_section(
        usage_totals or {},
        mcp_days=mcp_days,
        session_days=wv.get("session_days") or {},
        corpus_mix=wv.get("corpus_mix") or {},
        read_mix=wv.get("read_mix") or {},
        top_pages=wv.get("top_pages") or [],
        dead_stock=wv.get("dead_stock") or [],
        dead_stock_total=int(wv.get("dead_stock_total") or 0),
        wiki_page_count=int(wv.get("wiki_page_count") or 0),
        estimate=wv.get("estimate"),
        docs_by_project=docs_by_project or {},
    )
    candidates_block = render_candidates_review_section(
        pending=int(wv.get("candidates_pending") or 0),
        stale=int(wv.get("candidates_stale") or 0),
        by_kind=wv.get("candidates_by_kind") or {},
        stale_days=int(wv.get("candidates_stale_days") or 30),
    )

    # Recently updated — show last 10 entries from the wiki's log.md. Read
    # from the vault's wiki_dir (falling back to REPO_ROOT for a repo build),
    # not the module REPO_ROOT — otherwise a vault site shows the repo's log.
    log_events = _recent_log_events(
        (wiki_dir or (REPO_ROOT / "wiki")) / "log.md", limit=10
    )
    recent_block_inner = render_recent_activity(log_events)
    recent_block = (
        f'<section class="section recently-updated-section">\n'
        f'  <div class="container">\n'
        f'    {recent_block_inner}\n'
        f'  </div>\n'
        f'</section>\n'
    ) if recent_block_inner else ""

    cards = []
    for project, sessions in sorted(groups.items(), key=lambda x: -len(x[1])):
        main_count = sum(1 for p, m, _ in sessions if not _is_subagent(m, p))
        # Project topics — explicit profile in wiki/projects/<slug>.md
        # takes precedence, falls back to aggregated session tags with
        # noise filtered out. Rendered as chips below the card meta.
        proj_metas = [m for _, m, _ in sessions]
        topics = get_project_topics(PROJECTS_META_DIR, project, proj_metas)
        topics_html = render_topic_chips(topics, max_visible=4,
                                         classname="project-topics card-topics")
        # #455: render the activity date range under the meta line so
        # users can spot fresh vs stale projects without clicking. Pull
        # `date:` from frontmatter (already YYYY-MM-DD strings); ignore
        # missing/blank values; format as `2026-03-12 → 2026-04-01` for
        # multi-day, just `2026-04-01` if first == last.
        dates = sorted(
            {str(m.get("date", "")) for _, m, _ in sessions if m.get("date")}
        )
        if dates:
            if dates[0] == dates[-1]:
                date_range_html = (
                    f'<div class="card-date-range">{html.escape(dates[0])}</div>'
                )
            else:
                date_range_html = (
                    f'<div class="card-date-range">'
                    f'{html.escape(dates[0])} → {html.escape(dates[-1])}'
                    f'</div>'
                )
        else:
            date_range_html = ""
        cards.append(
            f"""  <a class="card card-project" href="projects/{html.escape(project)}.html">
    <div class="card-title">{html.escape(project)}</div>
    <div class="card-meta">{main_count} main · {len(sessions) - main_count} sub-agent</div>
    {date_range_html}
    {topics_html}
  </a>"""
        )

    body = f"""{token_stats_block}
{candidates_block}
{heatmap_block}
{recent_block}
<section class="section">
  <div class="container">
    <h2>Projects</h2>
    <div class="card-grid">
{chr(10).join(cards)}
    </div>
  </div>
</section>
{wiki_usage_block}
</main>
"""

    page = (
        page_head("Analytics — LLM Wiki", "Session activity, wiki value, and project analytics", css_prefix="")
        + nav_bar("analytics", link_prefix="")
        + hero(
            "Analytics",
            f"{_pluralize(mains, 'main session')} · {_pluralize(subs, 'sub-agent run')} · {_pluralize(len(groups), 'project')}",
            main_class="analytics-page",
        )
        + synth_block
        + body
        + page_foot(js_prefix="")
    )

    out_path = out_dir / "analytics.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_automation_panel(content_root: Path | None) -> str:
    """HTML panel describing install-automation status for the Home page."""
    if content_root is None:
        status = None
    else:
        status = load_status(content_root)

    if not status:
        return (
            '<div class="automation-panel" aria-label="Automation">'
            "<h2>Automation</h2>"
            "<p class=\"muted\">No automation configured. Run "
            "<code>llmwiki install-automation</code> or <code>./setup.sh</code> "
            "to set a daily scheduler, optional watch, and synth backend.</p>"
            "</div>"
        )

    profile = status.get("profile") or "none"
    hour = int(status.get("hour") or 8)
    minute = int(status.get("minute") or 0)
    watch = "on" if status.get("watch_enabled") else "off"
    hooks = status.get("hooks") or []
    hooks_s = ", ".join(str(h) for h in hooks) if hooks else "none (recommended)"
    backend = html.escape(str(status.get("synth_backend") or "dummy"))
    log_path = html.escape(str(status.get("log_path") or ""))
    updated = html.escape(str(status.get("updated_at") or ""))
    note = html.escape(str(status.get("note") or (
        "Scheduled runs with no new sessions are a no-op."
    )))
    return (
        '<div class="automation-panel" aria-label="Automation">'
        "<h2>Automation</h2>"
        "<ul>"
        f"<li>Scheduler profile: <strong>{html.escape(str(profile))}</strong> "
        f"at <strong>{hour:02d}:{minute:02d}</strong> local</li>"
        f"<li>Watch: <strong>{watch}</strong></li>"
        f"<li>Agent hooks: {html.escape(hooks_s)}</li>"
        f"<li>Synth backend: <code>{backend}</code></li>"
        f"<li>Last-run log: <code>{log_path}</code></li>"
        f"<li class=\"muted\">Updated: {updated}</li>"
        "</ul>"
        f"<p class=\"muted\">{note}</p>"
        "</div>"
    )


def render_index(
    docs_root: raw_docs_site.DocFolder,
    doc_entries: list[raw_docs_site.DocEntry],
    doc_file_count: int,
    out_dir: Path,
    *,
    content_root: Path | None = None,
) -> Path:
    """Render ``index.html`` — queue/dashboard landing page."""
    body = raw_docs_site.render_dashboard_body(
        doc_entries,
        doc_file_count,
        vault_root=content_root,
        repo_root=SOURCE_ROOT,
        automation_html=render_automation_panel(content_root),
    )
    page = (
        page_head("LLM Wiki", "Karpathy-style knowledge base from Claude Code sessions", css_prefix="")
        + nav_bar("home", link_prefix="")
        + hero(
            "LLM Wiki",
            "Pipeline state for sync, synthesis, and candidate review",
        )
        + body
        + page_foot(js_prefix="")
    )
    out_path = out_dir / "index.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_raw(
    docs_root: raw_docs_site.DocFolder,
    doc_entries: list[raw_docs_site.DocEntry],
    doc_file_count: int,
    out_dir: Path,
) -> Path:
    """Render ``raw.html`` — the raw-documents file-tree browser."""
    body = raw_docs_site.render_raw_body(docs_root, doc_entries, doc_file_count)
    page = (
        page_head("Raw — LLM Wiki", "Browse raw documents and synthesis backlog context", css_prefix="")
        + nav_bar("raw", link_prefix="")
        + hero(
            "Raw documents",
            f"{_pluralize(len(doc_entries), 'document')} · browse the raw knowledge base",
        )
        + body
        + page_foot(js_prefix="")
    )
    out_path = out_dir / "raw.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_recent(
    doc_entries: list[raw_docs_site.DocEntry],
    out_dir: Path,
) -> Path:
    """Render ``recent.html`` — newest raw documents first."""
    body = raw_docs_site.render_recent_body(doc_entries)
    page = (
        page_head("Recent — LLM Wiki", "Recently added raw documents", css_prefix="")
        + nav_bar("recent", link_prefix="")
        + hero(
            "Recent documents",
            f"{_pluralize(len(doc_entries), 'document')}, newest first",
        )
        + body
        + page_foot(js_prefix="")
    )
    out_path = out_dir / "recent.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_candidates_page(wiki_dir: Path | None, out_dir: Path) -> Path:
    """Render ``candidates.html`` — pending entity/concept review tables (#97)."""
    body = render_candidates_body(wiki_dir)
    page = (
        page_head(
            "Candidates — LLM Wiki",
            "Review pending entity and concept candidates",
            css_prefix="",
        )
        + nav_bar("candidates", link_prefix="")
        + hero(
            "Candidates",
            "Promote, flip and promote, merge, or discard pending stubs",
        )
        + body
        + page_foot(js_prefix="")
    )
    out_path = out_dir / "candidates.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def _render_root_md_page(
    src_name: str,
    out_name: str,
    title: str,
    subtitle: str,
    meta_description: str,
    out_dir: Path,
    *,
    active_nav: str = "docs",
) -> Path | None:
    """Compile a repo-root ``.md`` file to a standalone site page (#284).

    Used for ``README.md`` and ``CONTRIBUTING.md`` so visitors don't get
    bounced out to GitHub for content we're already shipping as HTML.
    """
    src = SOURCE_ROOT / src_name
    if not src.is_file():
        return None
    raw = src.read_text(encoding="utf-8")
    body_md = raw
    lines = raw.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        body_md = "\n".join(lines[1:]).lstrip("\n")
    content_html = md_to_html(body_md)
    # #270: route embedded source-code + repo-root links to GitHub, then
    # the generic .md→.html pass for anything remaining.  README has
    # plenty of such links.
    content_html = rewrite_source_code_links_to_github(content_html)
    content_html = rewrite_md_links_to_html(content_html)

    body = f"""<section class="section docs-body">
  <div class="container narrow">
    <article class="article docs-article">
      {content_html}
    </article>
  </div>
</section>
</main>
"""
    page = (
        page_head(
            f"{title} — LLM Wiki",
            meta_description,
            css_prefix="",
        )
        + nav_bar(active_nav, link_prefix="")
        + hero(title, subtitle)
        + body
        + page_foot(js_prefix="")
    )
    out_path = out_dir / out_name
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_404(out_dir: Path) -> Path:
    """Emit ``site/404.html`` with the standard site chrome and a "Page not
    found" panel. Closes #387 U8 — without this, ``llmwiki serve`` falls
    back to the stdlib ``http.server`` default 404 (an unstyled error string
    with no nav). The page itself is not linked from the index, but
    ``serve.py`` injects it as the body of every 404 response.
    """
    head = page_head(
        title="Page not found · llmwiki",
        description="The page you tried to open doesn't exist on this site.",
    )
    nav = nav_bar(active="")
    foot = page_foot()
    body = """<main id="main-content">
<section class="hero">
  <div class="container">
    <h1>Page not found</h1>
    <p class="hero-sub">The page you tried to open doesn't exist on this site. The link may be stale, the page may have been removed, or the URL may have a typo.</p>
  </div>
</section>
<section class="section">
  <div class="container">
    <p>Try one of these:</p>
    <ul class="not-found-links">
      <li><a href="index.html">Home</a> — queue and synthesis dashboard</li>
      <li><a href="raw.html">Raw</a> — browse the raw documents</li>
      <li><a href="projects/index.html">Projects</a> — every project with sessions</li>
      <li><a href="sessions/index.html">Sessions</a> — every session, sortable + filterable</li>
      <li><a href="analytics.html">Analytics</a> — activity heatmap and token stats</li>
    </ul>
    <p class="muted">Or press <kbd>⌘K</kbd> / <kbd>Ctrl+K</kbd> to open the command palette and search.</p>
  </div>
</section>
</main>
"""
    page = head + nav + body + foot
    out_path = out_dir / "404.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_readme_page(out_dir: Path) -> Path | None:
    """Compile ``README.md`` to ``site/README.html`` (#284)."""
    return _render_root_md_page(
        "README.md", "README.html",
        title="README",
        subtitle="The public README of llmwiki, rendered from `README.md`.",
        meta_description="llmwiki — Karpathy-style LLM wiki from your Claude Code, Codex CLI, Cursor, and Obsidian sessions.",
        out_dir=out_dir,
    )


def render_contributing_page(out_dir: Path) -> Path | None:
    """Compile ``CONTRIBUTING.md`` to ``site/CONTRIBUTING.html`` (#284)."""
    return _render_root_md_page(
        "CONTRIBUTING.md", "CONTRIBUTING.html",
        title="Contributing",
        subtitle="The 8 rules + review bar for contributing to llmwiki.",
        meta_description="Contribution rules, PR checklist, and review bar for llmwiki.",
        out_dir=out_dir,
    )


# ─── v0.7 (#55) models section ─────────────────────────────────────────────

def render_models_section(out_dir: Path) -> tuple[Path | None, int]:
    """Discover `wiki/entities/*.md` pages with `entity_kind: ai-model`,
    render one detail page per model + a sortable `/models/index.html`.

    Returns `(index_path_or_None, model_count)`. If there's no
    `wiki/entities/` directory OR no model pages there, we still write
    an empty-state index so the nav link doesn't 404.
    """
    # Post-review: imports lazily so this function actually works the
    # next time someone wires it from the CLI. Previously these names
    # were referenced but never imported — function body was reachable
    # but would crash with NameError on first call.
    entities_dir = REPO_ROOT / "wiki" / "entities"
    entries_with_meta = discover_model_entities_with_meta(entities_dir)
    # Backwards-compatible list without meta for render_models_index.
    entries = [
        (path, profile, warnings, body)
        for path, _meta, profile, warnings, body in entries_with_meta
    ]
    models_out = out_dir / "models"
    models_out.mkdir(parents=True, exist_ok=True)

    # Index page — always write it so the nav link resolves.
    index_body = render_models_index(entries)
    index_page = (
        page_head(
            "Models — LLM Wiki",
            "Directory of AI-model entities tracked by the wiki with pricing, "
            "context windows, and benchmark scores.",
            css_prefix="../",
        )
        + nav_bar("models", link_prefix="../")
        + hero("Models", f"{len(entries)} model entities tracked")
        + index_body
        + "</main>\n"
        + page_foot(js_prefix="../")
    )
    index_path = models_out / "index.html"
    index_path.write_text(index_page, encoding="utf-8")

    # Per-model detail page — info card + body markdown rendered normally.
    for path, meta, profile, warnings, body in entries_with_meta:
        slug = path.stem
        title = profile.get("title", slug)
        info_card = render_model_info_card(profile)

        # v0.7 (#56): changelog timeline + pricing sparkline below the
        # info card. The sparkline only shows if there are ≥2 dated
        # input-price changes in the changelog.
        changelog_entries, changelog_warnings = parse_changelog(meta)
        warnings = list(warnings) + changelog_warnings
        timeline_html = render_changelog_timeline(changelog_entries)
        timeline_block = ""
        if timeline_html:
            price_pts = extract_price_points(
                changelog_entries, field_suffix="pricing.input_per_1m"
            )
            sparkline = render_price_sparkline(price_pts)
            sparkline_block = (
                f'<div class="timeline-sparkline">'
                f'<span class="muted">Input pricing trend</span> {sparkline}'
                f'</div>'
                if sparkline else ""
            )
            timeline_block = (
                '<div class="timeline-card">'
                '<div class="timeline-card-title">Changelog</div>'
                + sparkline_block
                + timeline_html
                + '</div>'
            )

        body_html = md_to_html(body)
        warnings_html = ""
        if warnings:
            items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
            warnings_html = (
                '<details class="model-warnings"><summary>Schema warnings '
                f'({len(warnings)})</summary><ul>{items}</ul></details>'
            )
        page = (
            page_head(
                f"{title} — LLM Wiki",
                f"AI-model entity: {title}",
                css_prefix="../",
            )
            + nav_bar("models", link_prefix="../")
            + hero(title, profile.get("provider", ""))
            + '<section class="section">\n  <div class="container narrow">\n'
            + info_card
            + timeline_block
            + warnings_html
            + f'    <article class="article content">\n      {body_html}\n    </article>\n'
            + '  </div>\n</section>\n</main>\n'
            + page_foot(js_prefix="../")
        )
        (models_out / f"{slug}.html").write_text(page, encoding="utf-8")

    return index_path, len(entries)


# ─── v0.7 (#58) auto-generated vs-comparison pages ────────────────────────

def render_vs_section(
    out_dir: Path,
    max_pairs: int = 500,
    min_shared_fields: int = 3,
) -> tuple[Path | None, int]:
    """Generate `/vs/<slug_a>-vs-<slug_b>.html` for every pair of
    comparable model entities + an index at `/vs/index.html`.

    Honors user overrides under `wiki/vs/<slug>.md` — a hand-written
    comparison replaces the auto-gen for that URL. Returns
    `(index_path, pair_count)`. Always writes the index so the nav
    link resolves even when no entities exist.
    """
    # Post-review: lazy imports so this function actually works the
    # next time someone wires it. Previously these names were referenced
    # but never imported — first call would have crashed with NameError.
    entities_dir = REPO_ROOT / "wiki" / "entities"
    overrides_dir = REPO_ROOT / "wiki" / "vs"
    entries = discover_model_entities(entities_dir)
    # Strip down to (path, profile) for compare.generate_pairs
    pair_entries = [(p, profile) for p, profile, _w, _b in entries]
    pairs = generate_pairs(
        pair_entries,
        min_shared_fields=min_shared_fields,
        max_pairs=max_pairs,
    )

    vs_out = out_dir / "vs"
    vs_out.mkdir(parents=True, exist_ok=True)

    # Index
    index_body = render_comparisons_index(pairs)
    index_page = (
        page_head(
            "Model comparisons — LLM Wiki",
            "Auto-generated side-by-side comparisons of AI-model entities.",
            css_prefix="../",
        )
        + nav_bar("vs", link_prefix="../")
        + hero("Model comparisons", f"{len(pairs)} auto-generated pairs")
        + index_body
        + "</main>\n"
        + page_foot(js_prefix="../")
    )
    index_path = vs_out / "index.html"
    index_path.write_text(index_page, encoding="utf-8")

    # User overrides replace the auto-gen for matching slugs
    overrides = discover_user_overrides(overrides_dir)

    for pair in pairs:
        slug = pair_slug(pair)
        if slug in overrides:
            # User override — render the raw body through md_to_html
            body_html = md_to_html(overrides[slug])
            article_body = (
                '<section class="section"><div class="container narrow">'
                f'<article class="article content">{body_html}</article>'
                '</div></section>'
            )
        else:
            # Auto-gen — three structured sections
            comparison_body = render_comparison_body(pair)
            article_body = (
                '<section class="section"><div class="container narrow">'
                f'{comparison_body}'
                '</div></section>'
            )

        title = f"{pair['title_a']} vs {pair['title_b']}"
        page = (
            page_head(
                f"{title} — LLM Wiki",
                f"Side-by-side comparison of {title}.",
                css_prefix="../",
            )
            + nav_bar("vs", link_prefix="../")
            + hero(title, f"{pair['score']} shared structured fields")
            + article_body
            + "</main>\n"
            + page_foot(js_prefix="../")
        )
        (vs_out / f"{slug}.html").write_text(page, encoding="utf-8")

    return index_path, len(pairs)


# ─── search index ──────────────────────────────────────────────────────────

# #20: search payloads are emitted as .js sidecars too, so the site works
# when opened over file://. Re-exported for callers importing it from here.
from llmwiki.render.data import write_js_sidecar  # noqa: E402


def build_search_index(
    sources: list[tuple[Path, dict[str, Any], str]],
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    out_dir: Path,
    *,
    search_mode: str = "auto",
    doc_files: list[raw_docs_site.RawDocFile] | None = None,
    topics: list[dict[str, Any]] | None = None,
) -> Path:
    """Build a chunked search index for lazy loading (#47).

    Each ``.json`` below is emitted a second time as a ``.js`` sidecar so the
    site works when opened over ``file://`` — see :func:`write_js_sidecar`.

    Writes:
      search-index.json          — meta entries (projects + pages + topics) +
                                  _chunks manifest + _mode + _tree_eligible_ratio (#53)
      search-chunks/<project>.json — session entries per project, each
                                    carrying heading_max_depth + count_by_depth

    `search_mode` accepts ``auto`` (default, heuristic), ``tree``, or
    ``flat`` — matches the `llmwiki build --search-mode` flag.

    `topics` is the ``nodes`` list from :func:`build_topic_graph` (#50). Each
    node becomes a ``type: "topic"`` meta entry whose ``body`` carries aliases
    so non-canonical spellings match in the Cmd+K palette.
    """
    # ── session entries grouped by project ──
    chunks: dict[str, list[dict[str, Any]]] = {}
    for p, meta, body in sources:
        project = str(meta.get("project") or p.parent.name)
        slug = str(meta.get("slug", p.stem))
        plain = md_to_plain_text(body)[:1200]
        entry = {
            "id": f"session:{project}/{p.stem}",
            "url": f"sessions/{project}/{p.stem}.html",
            "title": slug,
            "type": "session",
            "project": project,
            "date": str(meta.get("date", "")),
            "model": str(meta.get("model", "")),
            # #36: searchable by real agent session id
            "sessionId": str(meta.get("sessionId") or ""),
            "body": plain,
        }
        # v1.0 (#161): enrich with facet fields.
        enrich_entry(entry, meta)
        # v1.2 (#53): inject heading depth so the client can tree-walk.
        annotate_entry_headings(entry, body)
        chunks.setdefault(project, []).append(entry)

    # ── write per-project chunks ──
    chunks_dir = out_dir / "search-chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_manifest: list[str] = []
    total_chunk_bytes = 0
    for project_slug, entries in sorted(chunks.items()):
        chunk_path = chunks_dir / f"{project_slug}.json"
        data = json.dumps(entries, ensure_ascii=False)
        chunk_path.write_text(data, encoding="utf-8")
        rel = f"search-chunks/{project_slug}.json"
        # #20: keyed by its manifest path, which is the exact string the
        # client already holds — no key-derivation rules to keep in sync.
        write_js_sidecar(chunk_path, rel, data)
        chunk_manifest.append(rel)
        total_chunk_bytes += len(data.encode("utf-8"))

    # ── meta index: projects + static pages + chunk manifest ──
    meta_entries: list[dict[str, Any]] = []

    for project, sessions in groups.items():
        meta_entries.append(
            {
                "id": f"project:{project}",
                "url": f"projects/{project}.html",
                "title": project,
                "type": "project",
                "project": project,
                "date": "",
                "model": "",
                "body": f"{len(sessions)} sessions",
            }
        )

    meta_entries.append(
        {"id": "home", "url": "index.html", "title": "Home", "type": "page",
         "project": "", "date": "", "model": "", "body": "raw documents file tree"}
    )
    meta_entries.append(
        {"id": "recent", "url": "recent.html", "title": "Recent documents",
         "type": "page", "project": "", "date": "", "model": "", "body": "newest raw documents"}
    )
    meta_entries.append(
        {"id": "analytics", "url": "analytics.html", "title": "Analytics",
         "type": "page", "project": "", "date": "", "model": "",
         "body": "activity heatmap token stats projects overview"}
    )
    meta_entries.append(
        {"id": "candidates", "url": "candidates.html", "title": "Candidates",
         "type": "page", "project": "", "date": "", "model": "",
         "body": "review pending entity concept candidates promote flip merge discard"}
    )
    meta_entries.append(
        {"id": "projects-index", "url": "projects/index.html", "title": "Projects",
         "type": "page", "project": "", "date": "", "model": "", "body": "all projects"}
    )
    meta_entries.append(
        {"id": "sessions-index", "url": "sessions/index.html", "title": "All sessions",
         "type": "page", "project": "", "date": "", "model": "", "body": "sortable sessions table"}
    )

    # Raw documents (wiki-add layer) — one palette entry per file so a
    # chunked doc is findable by any of its section titles.
    for doc in (doc_files or []):
        meta_entries.append({
            "id": f"document:{doc.rel.as_posix()}",
            "url": doc.out_rel,
            "title": doc.title,
            "type": "document",
            "project": "",
            "date": doc.date,
            "model": "",
            "body": md_to_plain_text(doc.body)[:300],
        })

    # #277: index every docs/ page + every slash command so the palette
    # becomes a universal quick-find (not just sessions + projects).
    docs_dir = SOURCE_ROOT / "docs"
    if docs_dir.is_dir():
        for page in iter_docs_pages(docs_dir):
            meta_entries.append({
                "id": f"docs:{page.rel}",
                "url": f"docs/{page.rel.replace('.md', '.html')}",
                "title": page.title,
                "type": "docs",
                "project": "",
                "date": "",
                "model": "",
                "body": _first_paragraph(page.body)[:300],
            })

    # Slash commands — read the first non-empty line of each .md as
    # the description so the palette shows what each /wiki-* does.
    slash_dir = SOURCE_ROOT / ".claude" / "commands"
    if slash_dir.is_dir():
        for p in sorted(slash_dir.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            first_para = next(
                (ln.strip() for ln in text.splitlines() if ln.strip()),
                "",
            )
            meta_entries.append({
                "id": f"slash:{p.stem}",
                # Slashes aren't URLs — the palette shows a non-clickable
                # entry with the command to type inside Claude Code.
                "url": "",
                "title": f"/{p.stem}",
                "type": "slash",
                "project": "",
                "date": "",
                "model": "",
                "body": first_para[:300],
            })

    # #50: topic pages + their aliases. Built earlier in build_site so the
    # graph nodes exist before this index is written; aliases live in body
    # so a query using any non-canonical spelling still finds the topic.
    for node in (topics or []):
        name = str(node.get("id") or "")
        if not name:
            continue
        slug = topic_slug(name)
        aliases = [a for a in (node.get("aliases") or []) if a and a != name]
        body_parts: list[str] = [f"{int(node.get('session_count') or 0)} sessions"]
        if aliases:
            body_parts.append("also: " + ", ".join(aliases))
        desc = str(node.get("description") or "").strip()
        if desc:
            body_parts.append(desc)
        meta_entries.append({
            "id": f"topic:{slug}",
            "url": str(node.get("site_url") or f"topics/{slug}.html"),
            "title": name,
            "type": "topic",
            "project": "",
            "date": "",
            "model": "",
            "body": " · ".join(body_parts)[:500],
        })

    # v1.0 (#161): aggregate facet counts across all session chunks so the
    # client can render filter checkboxes without scanning the full index.
    all_entries: list[dict[str, Any]] = []
    for chunk_entries in chunks.values():
        all_entries.extend(chunk_entries)
    facets = aggregate_facets(all_entries)

    # v1.2 (#53): decide tree vs flat across *all* entries, surface
    # the ratio so the client can show it in the palette footer.
    mode, tree_ratio = decide_search_mode(all_entries, override=search_mode)
    mode_badge = search_index_footer_badge(mode, tree_ratio)

    index_obj = {
        "entries": meta_entries,
        "_chunks": chunk_manifest,
        "_facets": facets,
        "_mode": mode,
        "_tree_eligible_ratio": round(tree_ratio, 4),
        "_mode_badge": mode_badge,
    }
    out_path = out_dir / "search-index.json"
    index_json = json.dumps(index_obj, ensure_ascii=False)
    out_path.write_text(index_json, encoding="utf-8")
    write_js_sidecar(out_path, "search-index", index_json)

    meta_kb = len(json.dumps(index_obj).encode("utf-8")) // 1024
    chunks_kb = total_chunk_bytes // 1024
    print(
        f"  wrote search-index.json ({meta_kb} KB meta) + "
        f"{len(chunk_manifest)} chunks ({chunks_kb} KB total) · {mode_badge}"
    )

    return out_path


# ─── css + js constants ────────────────────────────────────────────────────

# ─── css + js ────────────────────────────────────────────────────────────
# CSS + JS constants live in llmwiki/render/ since v1.1 (#217). Re-export
# here for backwards compatibility — any external caller still doing
# `from llmwiki.build import CSS` keeps working.
from llmwiki.render.css import CSS  # noqa: F401 (re-exported)
from llmwiki.render.js import JS  # noqa: F401 (re-exported)

# ─── claude synthesis (optional) ───────────────────────────────────────────

# #421: shell metacharacters that have no business in a path-to-an-
# executable. We refuse paths containing any of these rather than
# trying to escape them — the CLI argv is never shell-interpreted
# (we use list-form subprocess.run), but the same path may end up in
# user-facing logs, scripts, or future code paths that *do* interpolate.
# Reject loudly to keep hygiene tight.
# #sec-6 (#550): extended to reject NUL + control chars + unprintable
# bytes. The original list caught the obvious shell-special characters;
# control chars (0x00–0x1F minus tab) get rejected too because they
# survive the rejection of `\n` and `\r` only by accident, and can
# break log parsers / shell prompts in subtle ways.
# Re-exported from llmwiki.claude_path for tests / back-compat (#58).
# (_resolve_claude_path imported at module top.)


# #486: validate slug shape before it lands in the synthesize_overview
# prompt. Anything that doesn't match this is replaced by `_invalid_`.
# - Length cap 80 chars (real slugs are far shorter)
# - Charset: alphanumerics + `.`, `_`, `-` (no whitespace, no shell
#   metachars, no NUL bytes, no unicode-confusable categories)
_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")

# #486: cap the total prompt size sent to the claude CLI. 32 KB is well
# inside any LLM's context, well inside macOS's ~256 KB argv limit, and
# small enough that a malicious large slug list can't push the prompt
# past the OS argv limit. (We also pass via stdin below so this is
# defence-in-depth.)
_MAX_OVERVIEW_PROMPT_BYTES = 32_000


def _validate_overview_slug(s: Any) -> str:
    """Return ``s`` if it's a safe slug, ``"_invalid_"`` otherwise.

    #486: a malicious .jsonl could land arbitrary content in the
    `slug` field of a session's frontmatter. That string then ends
    up inside the prompt sent to the claude CLI for overview
    synthesis. Without validation, an attacker-controlled slug could:
    - inject prompt text ("ignore previous instructions, …")
    - contain `\\x00` and crash subprocess.run with a ValueError
    - balloon argv past the OS limit (~256 KB on macOS)
    Replace anything sketchy with the literal `_invalid_` so the
    prompt stays well-formed and the synthesis output stays
    trustworthy.
    """
    if not isinstance(s, str):
        return "_invalid_"
    if not _SAFE_SLUG_RE.match(s):
        return "_invalid_"
    return s


def synthesize_overview(
    groups: dict[str, list[tuple[Path, dict[str, Any], str]]],
    claude_path: str,
    model: str | None = None,
) -> str | None:
    resolved = _resolve_claude_path(claude_path)
    if resolved is None:
        return None
    claude_path = str(resolved)

    lines: list[str] = [
        "You are writing a short (200-300 word) overview for a personal knowledge-base",
        "landing page. Below is a JSON summary of the user's Claude Code session history",
        "across multiple projects. Write 2-3 paragraphs of prose in markdown that:",
        "  1. Names the main projects and what each is about (infer from session slugs and tool usage)",
        "  2. Highlights the busiest project(s) and the overall scale of the work",
        "  3. Is written in third person, referring to the user as 'the developer'",
        "Do NOT use bullet points. Just 2-3 short paragraphs of prose.",
        "",
        "Data:",
        "",
    ]
    brief: dict[str, Any] = {}
    for project, sessions in sorted(groups.items()):
        brief[project] = {
            "session_count": len(sessions),
            "main_sessions": sum(1 for p, m, _ in sessions if not _is_subagent(m, p)),
            "dates": sorted({str(m.get("date", "")) for _, m, _ in sessions if m.get("date")}),
            "models": sorted({str(m.get("model", "")) for _, m, _ in sessions if m.get("model")}),
            # #486: every slug filtered through the safe-slug regex so
            # malicious .jsonl content can't prompt-inject or crash
            # subprocess.run via embedded NUL bytes.
            "slugs": [_validate_overview_slug(m.get("slug", p.stem)) for p, m, _ in sessions[:8]],
        }
    prompt = "\n".join(lines) + json.dumps(brief, indent=2)

    # #486: cap total prompt size so a malicious large slug list can't
    # push the prompt past the OS argv limit. Truncation is fine here —
    # the LLM gets the head of the JSON and produces a partial overview;
    # better than a build that silently fails.
    if len(prompt.encode("utf-8")) > _MAX_OVERVIEW_PROMPT_BYTES:
        prompt = prompt.encode("utf-8")[:_MAX_OVERVIEW_PROMPT_BYTES].decode(
            "utf-8", errors="ignore"
        )

    print("  calling claude CLI for overview synthesis…")
    try:
        # #486: pass the prompt via stdin (`-p -`) instead of argv so we
        # dodge the OS argv-length limit entirely. The byte cap above is
        # defence-in-depth — argv-length DoS path closed regardless.
        # Same scaffolding-stripping flags as page synthesis: this call
        # writes prose from a JSON brief and can't use a single tool.
        result = subprocess.run(
            overview_argv(claude_path, model),
            input=prompt,
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("  warning: claude CLI timed out after 120s", file=sys.stderr)
        return None
    # #py-m4 (#590): narrow `except Exception` to the families we
    # actually expect from a subprocess call. Catching MemoryError or
    # ImportError silently here would mask real failures.
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  warning: claude CLI failed: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        print(f"  warning: claude CLI exited {result.returncode}", file=sys.stderr)
        return None
    return result.stdout.strip() or None


# ─── main ──────────────────────────────────────────────────────────────────

def _ensure_synth_pipeline_snapshot(
    *,
    content_root: Path,
    raw_dir: Path,
    wiki_sources: Path,
) -> bool:
    """Backfill ``synth.pipeline`` once when state predates the Home widget (#70).

    Returns True when ``refresh_synth_pending`` ran. Only fires on a shape
    mismatch (missing / non-dict ``pipeline``, or ``rows`` not a list) — not
    when the snapshot is merely stale vs newest raw. Sync / add / estimate
    already refresh on content changes; paying estimate cost on every build
    would be a permanent tax for a one-time v1.4→v1.5 migration.
    """

    state_path = content_root / "llmwiki-state.json"
    try:
        synth = read_state(state_path).get("synth") or {}
    except (OSError, ValueError, TypeError):
        synth = {}
    if synth_pipeline_shape_ok(synth):
        return False
    print("  backfilling synth.pipeline for Home State widget...")
    refresh_synth_pending(
        raw_dir=raw_dir / "sessions",
        docs_dir=raw_dir / "docs",
        wiki_sources_dir=wiki_sources,
        state_file=state_path,
    )
    return True


def _refresh_candidate_review_snapshot(
    *,
    content_root: Path,
    wiki_dir: Path,
) -> dict[str, object]:
    """Cheap every-build recount of pending candidates into ``synth.pipeline`` (#84).

    Unlike ``_ensure_synth_pipeline_snapshot``, this always runs — walking
    ``wiki/candidates/`` is cheap and Home/Analytics must stay accurate after
    promote / discard without forcing a full estimate refresh.
    """
    state_path = content_root / "llmwiki-state.json"
    summary = candidate_review_summary(wiki_dir)

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        pipeline = synth.get("pipeline")
        if not isinstance(pipeline, dict):
            pipeline = {"stages": ["raw", "synthesized"], "rows": []}
        synth["pipeline"] = apply_review_summary_to_pipeline(pipeline, wiki_dir)
        return s

    try:
        update_state(_mut, state_path)
    except OSError:
        # Fresh vaults may lack a writable state file; Analytics still gets
        # ``summary`` from the direct return below.
        pass
    return summary


def build_site(
    out_dir: Path | None = None,
    synthesize: bool = False,
    claude_path: str = "",
    search_mode: str = "auto",
    seed_project_stubs: bool = False,
    raw_sessions: Path | None = None,
    raw_dir: Path | None = None,
    wiki_dir: Path | None = None,
) -> int:
    # #54 vault-overlay: resolved here (not as param defaults, which are
    # captured at def time) so monkeypatched module constants take effect.
    out_dir = DEFAULT_OUT_DIR if out_dir is None else out_dir
    raw_sessions = RAW_SESSIONS if raw_sessions is None else raw_sessions
    raw_dir = RAW_DIR if raw_dir is None else raw_dir
    wiki_dir = (REPO_ROOT / "wiki") if wiki_dir is None else wiki_dir
    if not raw_sessions.exists():
        print(
            f"error: {raw_sessions} does not exist. Run `llmwiki init` + `llmwiki sync` first.",
            file=sys.stderr,
        )
        return 2

    print(f"==> scanning {raw_sessions}")
    sources = discover_sources(raw_sessions)
    if not sources:
        print("  no sources found.", file=sys.stderr)
        return 2
    print(f"  found {len(sources)} source markdowns")
    groups = group_by_project(sources)
    print(f"  grouped into {len(groups)} projects")

    # #414: stub-seeding used to be unconditional. `build` is documented
    # as read-only on `wiki/`, but seeding wrote to `wiki/projects/` —
    # CI users running `llmwiki build` on a curated checkout discovered
    # surprise commits in their working tree. Now opt-in: callers that
    # have already accepted mutation (sync, the new `--seed-project-stubs`
    # flag) request seeding explicitly; the default `build` is pure.
    if seed_project_stubs:
        stubs_written = ensure_project_stubs(groups, PROJECTS_META_DIR)
        if stubs_written:
            print(f"  seeded {len(stubs_written)} new wiki/projects/ stubs")

    # Reset output dir (clear contents only — the HTTP server may be cwd'd here)
    # #py-m12 (#598): drop ignore_errors=True. A failure to remove a
    # site/ subtree means we'll write a corrupted partial site on top
    # of stale files; users have hit this when one CI runner left a
    # read-only directory behind. Surface OSError instead so the build
    # halts with a clear message.
    if out_dir.exists():
        rmtree_errors: list[str] = []

        def _on_rmtree_error(func, path, exc_info):
            err = exc_info[1] if isinstance(exc_info, tuple) else exc_info
            rmtree_errors.append(f"{path}: {err}")

        for child in out_dir.iterdir():
            if child.is_dir():
                # Python 3.12+ uses onexc; pre-3.12 uses onerror. Use
                # onerror for back-compat with the 3.9 floor.
                shutil.rmtree(child, onerror=_on_rmtree_error)
            else:
                try:
                    child.unlink()
                except OSError as e:
                    rmtree_errors.append(f"{child}: {e}")
        if rmtree_errors:
            raise OSError(
                "could not reset site dir " + str(out_dir) + ":\n  "
                + "\n  ".join(rmtree_errors)
            )
    else:
        out_dir.mkdir(parents=True)

    # CSS + JS
    (out_dir / "style.css").write_text(CSS, encoding="utf-8")
    (out_dir / "script.js").write_text(JS, encoding="utf-8")
    # Tiny 1×1 PNG at /favicon.ico — Chromium still probes this path even
    # when <link rel="icon"> points at a data URI, and the probe 404
    # shows up as a console.error that breaks e2e cleanliness checks.
    (out_dir / "favicon.ico").write_bytes(_FAVICON_PNG)
    print("  wrote style.css, script.js, favicon.ico")

    # Copy raw markdown under sources/<project>/ for "Download .md" links
    # (matches session action hrefs + docs/architecture.md). Flat copytree
    # used to put every file at sources/<stem>.md while links expected a
    # project subdir — every Download .md button 404'd.
    sources_out = out_dir / "sources"
    if sources_out.exists():
        shutil.rmtree(sources_out)
    sources_out.mkdir(parents=True)

    # v0.7 (#96): copy downloaded image assets into site/assets/
    raw_assets = raw_dir / "assets"
    if raw_assets.exists() and any(raw_assets.iterdir()):
        site_assets = out_dir / "assets"
        if site_assets.exists():
            shutil.rmtree(site_assets)
        shutil.copytree(raw_assets, site_assets)
        asset_count = sum(1 for _ in site_assets.iterdir() if _.is_file())
        print(f"  copied {asset_count} image assets to assets/")

    # Synthesis
    synthesis = None
    if synthesize:
        synthesis = synthesize_overview(groups, claude_path)
        if synthesis:
            print(f"  synthesis: {len(synthesis)} chars")

    # Render session HTML + nest the .md copy for agents in one pass.
    # Per-page .txt / .json siblings were dropped: agents use
    # sources/<project>/<stem>.md (and site-level llms.txt / llms-full.txt).
    n_sessions = 0
    n_md_sources = 0
    md_copy_failures: list[tuple[str, BaseException]] = []
    for path, meta, body in sources:
        project = str(meta.get("project") or path.parent.name)
        render_session(path, meta, body, out_dir, project)
        n_sessions += 1
        dest = sources_out / project / path.name
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            n_md_sources += 1
        except OSError as e:
            md_copy_failures.append((str(path), e))

    if md_copy_failures:
        first_path, first_err = md_copy_failures[0]
        print(
            f"  warning: sources/ .md copy failed on "
            f"{len(md_copy_failures)} of {n_sessions} sessions; "
            f"first failure: {first_path}: {first_err}",
            file=sys.stderr,
        )
    print(f"  wrote {n_sessions} session pages")
    print(f"  copied {n_md_sources} raw .md sources to sources/<project>/")

    # Raw-doc tree + MCP usage totals are needed by both the per-project
    # pages and the analytics page, so compute them once up front. MCP
    # telemetry lives in ``<content_root>/usage/``; the content root is the
    # parent of ``raw/`` (the vault when one is configured, else REPO_ROOT) —
    # the MCP server writes there, so read from the same place.
    raw_docs_dir = raw_dir / "docs"
    content_root = raw_dir.parent
    doc_files = raw_docs_site.scan_raw_docs(raw_docs_dir)
    docs_by_project = raw_docs_site.count_docs_by_project(doc_files)
    usage_totals = _mcp_combined_totals(content_root)

    # #52: refresh durable daily MCP series, then gather wiki-value inputs.
    mcp_days = _mcp_refresh_daily(content_root)
    session_days = _wiki_session_days(raw_dir / "sessions")
    wiki_sources = (wiki_dir or (content_root / "wiki")) / "sources"
    wiki_root = wiki_sources.parent
    corpus_mix = _mcp_corpus_mix(wiki_sources)
    live_records = list(_mcp_live_records(content_root))
    retrievals = _mcp_page_retrievals(live_records)
    read_mix = _mcp_read_mix(retrievals, wiki_root=wiki_root)
    top_pages = list(retrievals.items())[:12]
    # Dead stock: synthesized sources with zero read_page hits in retained logs.
    # Full list — Analytics folds it behind a collapse section (no build-time cap).
    retrieved = set(retrievals)
    dead: list[str] = []
    source_page_count = 0
    if wiki_sources.is_dir():
        for p in sorted(wiki_sources.rglob("*.md")):
            if p.name.startswith("_"):
                continue
            source_page_count += 1
            rel = "wiki/sources/" + p.relative_to(wiki_sources).as_posix()
            alt = "sources/" + p.relative_to(wiki_sources).as_posix()
            keys = {rel, alt, "wiki/" + alt}
            if retrieved.isdisjoint(keys):
                dead.append(rel)
    dead_total = len(dead)
    # #70: one-shot backfill when llmwiki-state.json predates synth.pipeline
    # (v1.4→v1.5). Skip when the expected shape is already present.
    _ensure_synth_pipeline_snapshot(
        content_root=content_root,
        raw_dir=raw_dir,
        wiki_sources=wiki_sources,
    )
    review_summary = _refresh_candidate_review_snapshot(
        content_root=content_root,
        wiki_dir=wiki_dir,
    )
    # Ship the Home State sidecar inside site/ so a site-only HTTP root
    # (e2e, GitHub Pages of site/) resolves {js_prefix}llmwiki-state.js.
    # Vault root still keeps its copy for sync/synthesize writers.
    vault_sidecar = content_root / "llmwiki-state.js"
    site_sidecar = out_dir / "llmwiki-state.js"
    if vault_sidecar.is_file():
        shutil.copy2(vault_sidecar, site_sidecar)
    elif not site_sidecar.is_file():
        site_sidecar.write_text(
            "window.LLMWIKI_STATE_SNAPSHOT = {};\n", encoding="utf-8"
        )

    estimate: dict[str, Any] = {}
    try:
        state_path = resolve_state_file(None)
        # Prefer the vault's state when content_root differs from the default.
        vault_state = content_root / "llmwiki-state.json"
        if vault_state.is_file():
            state_path = vault_state
        estimate = (read_state(state_path).get("synth") or {}).get("estimate") or {}
    except (OSError, ValueError, TypeError):
        estimate = {}
    wiki_value = {
        "mcp_days": mcp_days,
        "session_days": session_days,
        "corpus_mix": corpus_mix,
        "read_mix": read_mix,
        "top_pages": top_pages,
        "dead_stock": dead,
        "dead_stock_total": dead_total,
        "wiki_page_count": source_page_count or int(corpus_mix.get("total", 0) or 0),
        "estimate": estimate if isinstance(estimate, dict) else {},
        "candidates_pending": int(review_summary.get("to_review") or 0),
        "candidates_stale": int(review_summary.get("to_review_stale") or 0),
        "candidates_by_kind": dict(review_summary.get("to_review_by_kind") or {}),
        "candidates_stale_days": int(review_summary.get("stale_days") or 30),
    }

    for project, sessions in groups.items():
        render_project_page(
            project, sessions, out_dir,
            usage_totals=usage_totals,
            doc_count=docs_by_project.get(project, 0),
        )
    print(f"  wrote {len(groups)} project pages")

    render_projects_index(groups, out_dir)
    render_sessions_index(sources, groups, out_dir)

    # Home (index.html) is the queue dashboard; raw.html is the raw-docs
    # tree browser; recent.html lists newest documents; analytics.html
    # carries the heatmap,
    # token stats, and projects grid.
    docs_root = raw_docs_site.build_tree(doc_files)
    doc_entries = raw_docs_site.group_documents(doc_files)
    tree_path = raw_docs_site.write_documents_tree(docs_root, out_dir)
    tree_kb = max(1, tree_path.stat().st_size // 1024)
    print(f"  wrote documents-tree.json ({tree_kb} KB) + .js sidecar")
    render_index(
        docs_root, doc_entries, len(doc_files), out_dir,
        content_root=wiki_dir.parent if wiki_dir is not None else None,
    )
    render_raw(docs_root, doc_entries, len(doc_files), out_dir)
    render_recent(doc_entries, out_dir)
    render_analytics(
        groups, sources, out_dir, synthesis=synthesis,
        usage_totals=usage_totals,
        docs_by_project=docs_by_project,
        wiki_dir=wiki_dir,
        wiki_value=wiki_value,
    )
    render_candidates_page(wiki_dir, out_dir)
    doc_pages = raw_docs_site.render_document_pages(
        doc_files,
        docs_root,
        out_dir,
        md_to_html=md_to_html,
        page_head=page_head,
        nav_builder=lambda prefix: nav_bar("raw", link_prefix=prefix),
        page_foot=lambda prefix: page_foot(js_prefix=prefix),
        breadcrumbs_bar=breadcrumbs_bar,
    )
    if doc_pages:
        print(f"  wrote {len(doc_pages)} document pages under documents/")

    # #387 U8: branded 404 page that serve.py returns as the body of any
    # 404 response, instead of the stdlib http.server default.
    render_404(out_dir)
    # #284: compile README + CONTRIBUTING as standalone site pages so
    # they don't bounce visitors out to GitHub for content we're already
    # shipping as HTML.
    render_readme_page(out_dir)
    render_contributing_page(out_dir)
    print(
        "  wrote index.html, raw.html, recent.html, analytics.html, "
        "candidates.html, projects/index.html, sessions/index.html, 404.html"
    )

    # #50: build the topic graph *before* the search index so topic pages
    # (and their aliases) can be indexed. Graph HTML / topic pages still
    # render below — we only hoist the CPU-side construction.
    _TOPIC_GRAPH_MIN_NODES = 5
    topic_graph: dict[str, Any] | None = None
    try:
        topic_graph = build_topic_graph(wiki_dir)
    except Exception as e:  # noqa: BLE001 — never fail the build over the graph
        print(f"  warning: topic graph build failed: {e}", file=sys.stderr)
    topic_nodes = (topic_graph or {}).get("nodes") or []
    use_topic_graph = bool(topic_graph) and len(topic_nodes) >= _TOPIC_GRAPH_MIN_NODES

    # Search index (chunked — #47) + tree/flat auto-routing (#53) + topics (#50)
    build_search_index(
        sources,
        groups,
        out_dir,
        search_mode=search_mode,
        doc_files=doc_files,
        topics=topic_nodes if use_topic_graph else None,
    )

    # v0.4: AI-consumable exports (llms.txt, llms-full.txt, graph.jsonld,
    # sitemap.xml, rss.xml, robots.txt, ai-readme.md)
    # #py-m4 (#590): narrow the catch so MemoryError, ImportError,
    # and KeyboardInterrupt aren't silently swallowed into a warning
    # line. ImportError in particular hides a broken module — the
    # build should crash loud, not log "warning: AI exports failed:
    # No module named ..." and ship a half-built site.
    try:
        extra_pages: list[tuple[str, str | None, str]] = [
            ("raw.html", None, "0.9"),
            ("recent.html", None, "0.9"),
            ("analytics.html", None, "0.8"),
            ("candidates.html", None, "0.8"),
        ] + [
            (doc.out_rel, doc.date or None, "0.7") for doc in doc_files
        ]
        ai_paths = export_all(out_dir, groups, sources, extra_pages=extra_pages)
        print(f"  wrote {len(ai_paths)} AI-consumable exports: {', '.join(sorted(ai_paths.keys()))}")
    except (OSError, ValueError, RuntimeError) as e:
        print(f"  warning: AI exports failed: {e}", file=sys.stderr)

    # v1.1 (#118): copy the interactive knowledge graph into the site
    # so the "Graph" nav link works without a separate `llmwiki graph` step.
    try:
        # #54: prefer the topic-first graph (topics as nodes, sessions as the
        # edges/backlinks between them) when the wiki has enough topics to be
        # useful; fall back to the page graph otherwise (repo mode, empty
        # wikis, or a tiny demo corpus where min_sessions=2 leaves 1–2 nodes
        # — see #69 Pages demo). All local CPU.
        # Sparse topic graphs look broken in the viewer (one edge, two nodes).
        # Prefer the full page graph until the vocabulary is rich enough.
        if use_topic_graph and topic_graph is not None:
            write_graph_html(topic_graph, out_dir / "graph.html")
            tpages = build_topic_pages(topic_graph, out_dir)
            print(f"  wrote graph.html (topic graph: {len(topic_graph['nodes'])} topics, "
                  f"{len(topic_graph['edges'])} connections) + {len(tpages)} topic pages")
        else:
            if topic_nodes:
                print(
                    f"  topic graph too sparse ({len(topic_nodes)} topics "
                    f"< {_TOPIC_GRAPH_MIN_NODES}); falling back to page graph",
                )
            # #54: graph the same wiki we built the site from (vault or repo).
            graph_path = copy_graph_to_site(out_dir, wiki_dir=wiki_dir)
            if graph_path:
                print(f"  wrote {graph_path.relative_to(out_dir.parent)} (interactive graph viewer)")
    except (OSError, ValueError, RuntimeError) as e:
        print(f"  warning: graph viewer copy failed: {e}", file=sys.stderr)

    # v1.2 (#265): compile the editorial docs (tutorials + hub) under
    # site/docs/. Only pages with `docs_shell: true` in frontmatter
    # are included — reference docs that stay GitHub-rendered aren't
    # touched.
    try:
        docs_dir = SOURCE_ROOT / "docs"

        # nav_builder gets called per-page with the right link_prefix so
        # the nav bar's hrefs resolve from whatever depth the page sits at.
        def _docs_nav(link_prefix: str) -> str:
            return nav_bar(active="docs", link_prefix=link_prefix)

        docs_written = compile_docs_site(
            docs_dir,
            out_dir,
            md_to_html=md_to_html,
            page_head=page_head,
            nav_builder=_docs_nav,
            page_foot=lambda prefix: page_foot(js_prefix=prefix),
        )
        if docs_written:
            print(
                f"  wrote site/docs/ ({len(docs_written)} editorial pages: "
                "hub + tutorials + style guide)"
            )
    # #py-m4: same narrow-catch pattern as above.
    except (OSError, ValueError, RuntimeError) as e:
        print(f"  warning: docs compile failed: {e}", file=sys.stderr)

    # Session markdown for agents is under sources/<project>/ (copied in the
    # render loop above). Per-page .txt / .json siblings are no longer emitted.

    # v0.4: Build manifest with SHA-256 hashes
    try:
        manifest_path = write_manifest(out_dir)
        print(f"  wrote {manifest_path.relative_to(out_dir.parent) if manifest_path.is_relative_to(out_dir.parent) else manifest_path.name}")
    except (OSError, ValueError, RuntimeError) as e:
        print(f"  warning: manifest failed: {e}", file=sys.stderr)

    total_files = sum(1 for _ in out_dir.rglob("*.html"))
    total_bytes = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    print(
        f"==> build complete: {total_files} HTML files, {total_bytes / 1024:.0f} KB total"
    )
    print(f"    output: {out_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--synthesize", action="store_true")
    p.add_argument("--claude", type=str, default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return build_site(
        out_dir=args.out,
        synthesize=args.synthesize,
        claude_path=args.claude,
    )


if __name__ == "__main__":
    sys.exit(main())

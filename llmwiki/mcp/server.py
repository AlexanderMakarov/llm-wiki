"""Full MCP server for llmwiki (v0.2).

Exposes llmwiki operations as Model Context Protocol tools that any MCP
client (Claude Desktop, Claude Code, Codex, Cline, Cursor, ChatGPT desktop)
can call directly via stdio.

v0.2 tool surface (6 production tools):

- `wiki_query(question)` — search the wiki's index and return relevant
  content from the matching pages
- `wiki_search(term, kind?, include_raw?)` — page-level search over the
  wiki by name and body text, narrowable to one page kind
- `wiki_list_sources(project?)` — list raw source files, optionally filtered
- `wiki_read_page(path)` — return the full content of a single wiki page
- `wiki_lint(rules?, min_refs?)` — run every registered quality check
  and return the same JSON report `llmwiki lint --json` prints
- `wiki_sync(dry_run?)` — trigger a converter sync

Protocol: Model Context Protocol, stdio transport, JSON-RPC 2.0.
Reference: https://modelcontextprotocol.io/

Ships as stdlib-only Python — no MCP SDK dependency.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT as SOURCE_ROOT
from llmwiki import __version__
from llmwiki import usage as _usage
from llmwiki._frontmatter import parse_frontmatter_dict
from llmwiki._system_pages import is_archived_path
from llmwiki.add_doc import add_sources
from llmwiki.categories import scan_tags
from llmwiki.config_schedule import resolve_content_root
from llmwiki.lint import LintOptions, UnknownRuleError, load_pages, run_lint
from llmwiki.lint.report import render_json as render_lint_json
from llmwiki.schema import PAGE_KINDS
from llmwiki.thresholds import DEFAULT_MIN_REFS
from llmwiki.vault_settings import (
    VaultSettingsError,
    disabled_lint_rules,
    load_vault_settings,
    vault_settings_path,
)

CONTENT_ROOT = resolve_content_root()
# Back-compat test seam: many MCP tests monkeypatch llmwiki.mcp.server.REPO_ROOT.
REPO_ROOT = CONTENT_ROOT


SERVER_INFO = {
    "name": "llmwiki",
    "version": __version__,
}

PROTOCOL_VERSION = "2024-11-05"

# ─── Usage telemetry (#26) ────────────────────────────────────────────────
# Every tool call is logged locally so we can answer "is this wiki earning
# its synthesis spend?". Collection is per-process (each server owns one
# JSONL file under <root>/usage/), lock-free, and strictly best-effort —
# a telemetry failure must never break a tool call. Set the env var
# LLMWIKI_MCP_TELEMETRY=0 to opt out entirely.
TELEMETRY_ENABLED = os.environ.get(
    "LLMWIKI_MCP_TELEMETRY", "1").strip().lower() not in {"0", "false", "no", "off"}

# One recorder per content root (keyed by str so tests that repoint
# REPO_ROOT get their own isolated file).
_RECORDERS: dict[str, _usage.UsageRecorder] = {}


def _get_recorder() -> _usage.UsageRecorder | None:
    if not TELEMETRY_ENABLED:
        return None
    key = str(REPO_ROOT)
    rec = _RECORDERS.get(key)
    if rec is None:
        rec = _usage.UsageRecorder(REPO_ROOT)
        _RECORDERS[key] = rec
    return rec


# ─── Caller identity (#51) ────────────────────────────────────────────────
# Telemetry has to say *who* called, and a stdio server's own cwd doesn't
# answer that — it's wherever the process was launched, unchanged across
# every session it serves. MCP's `roots` are the client's own workspace
# directories, so we ask for them (once the client says it's initialized,
# and only if it advertised the capability) and attribute each call to them.
_CLIENT: dict[str, Any] = {"supports_roots": False, "roots": [], "pending": set(), "seq": 0}
_ROOTS_ID_PREFIX = "llmwiki-roots-"


def reset_client_state() -> None:
    _CLIENT.update({"supports_roots": False, "roots": [], "pending": set(), "seq": 0})


def client_roots() -> list[str]:
    """Workspace root URIs last reported by the client; empty until it
    answers, or forever if it doesn't speak the roots protocol."""
    return list(_CLIENT["roots"])


def pending_roots_ids() -> list[str]:
    return sorted(_CLIENT["pending"])


def request_client_roots() -> None:
    """Send a `roots/list` request. Fire-and-forget: the reply is picked up
    by the main loop whenever it arrives, and calls made before then are
    recorded as unattributed rather than blocking on the client."""
    if not _CLIENT["supports_roots"]:
        return
    _CLIENT["seq"] += 1
    req_id = f"{_ROOTS_ID_PREFIX}{_CLIENT['seq']}"
    # Supersede any outstanding request: the client only tells us roots
    # changed when the older answer is already stale, and keeping every id
    # would grow the set for the life of the session.
    _CLIENT["pending"] = {req_id}
    send({"jsonrpc": "2.0", "id": req_id, "method": "roots/list"})


def handle_client_notification(method: str) -> None:
    """Client → server notifications we act on. Everything else is ignored,
    per JSON-RPC (a notification never gets a response)."""
    if method in ("notifications/initialized", "notifications/roots/list_changed"):
        request_client_roots()


def handle_client_response(message: dict[str, Any]) -> bool:
    """Consume a reply to a server-initiated request. Returns False for an
    id we never sent, so the caller can fall through to its normal handling
    instead of silently swallowing someone else's frame."""
    req_id = message.get("id")
    if req_id not in _CLIENT["pending"]:
        return False
    _CLIENT["pending"].discard(req_id)
    result = message.get("result")
    if isinstance(result, dict):
        # An error reply (client can't or won't list roots) leaves the last
        # known roots in place — no roots is honest, a wrong guess isn't.
        _CLIENT["roots"] = [
            r["uri"] for r in result.get("roots") or []
            if isinstance(r, dict) and isinstance(r.get("uri"), str)
        ]
    return True


def _result_text(result: dict[str, Any]) -> str:
    """Concatenate the text parts of a tool result payload."""
    parts = result.get("content") or []
    return "".join(
        p.get("text", "") for p in parts if isinstance(p, dict))


def _hit_count_from_text(is_error: bool, text: str) -> int | None:
    """Best-effort result count for a JSON tool payload (already serialized
    to ``text``, so the hot path stringifies the result only once).

    A zero-hit call is the signal that matters (knowledge gap / noise).
    An error is 0 hits; a top-level list is its length; a dict exposes its
    results under one of the known list keys. A non-JSON prose payload is
    skipped without an exception-throwing parse. Anything we can't
    interpret is ``None`` (unknown, not a miss). Tools that can report
    their own exact count do so via the private ``_hits`` result key
    instead of relying on this — see ``_record_usage``."""
    if is_error:
        return 0
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "[{":
        return None  # prose payload → unknown; don't pay for a failed parse
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("matches", "results", "pages", "sources",
                    "items", "entities", "hits"):
            val = data.get(key)
            if isinstance(val, list):
                return len(val)
    return None


def _resolve_hits(result: dict[str, Any], text: str) -> int | None:
    """Prefer the exact count a tool reported out-of-band (``_hits``); fall
    back to inferring it from the serialized payload."""
    explicit = result.get("_hits")
    if isinstance(explicit, int):
        return explicit
    return _hit_count_from_text(bool(result.get("isError")), text)


def _record_usage(
    name: str, args: dict[str, Any], result: dict[str, Any], duration_ms: int,
) -> None:
    # The whole body — recorder construction included — is best-effort:
    # telemetry is observability, never a failure mode for the caller.
    try:
        recorder = _get_recorder()
        if recorder is None:
            return
        text = _result_text(result)
        project, source = _usage.resolve_caller(
            args, client_roots=client_roots(), content_root=REPO_ROOT)
        recorder.record(
            tool=name,
            query=_usage.extract_query(args),
            hits=_resolve_hits(result, text),
            resp_bytes=len(text.encode("utf-8")),
            duration_ms=duration_ms,
            caller_project=project,
            caller_source=source,
        )
    except Exception:
        pass

# ─── Tool definitions ─────────────────────────────────────────────────────

#: Rendering modes for wiki_search: prose for a reader, JSON for a parser.
_SEARCH_FORMATS = ("text", "json")

TOOLS = [
    {
        "name": "wiki_query",
        "description": (
            "Search the llmwiki by keyword and return relevant page content. "
            "Reads wiki/index.md, wiki/overview.md, and any matching pages. "
            "Use for questions like 'what did I decide about X' or 'what's my "
            "preferred approach to Y'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural-language question or keyword(s) to search for.",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum pages to return (default 5).",
                    "default": 5,
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "wiki_search",
        "description": (
            "Search the wiki for a term by page name and page text. Results "
            "are page-level — `path — title` with the matching lines beneath "
            "it — and pages whose title or path matches are listed before "
            "pages that match only in their body. `include_raw` widens the "
            "scan to raw session transcripts and `kind` filters on frontmatter "
            "`type`; the two compose, so `kind=source` with `include_raw` "
            "returns source pages and the raw transcripts behind them. The "
            "result reports `truncated` when output caps dropped matches and "
            "`budget_exhausted` when the scan stopped short of the corpus."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Search term (literal, case-insensitive substring match).",
                },
                "kind": {
                    "type": "string",
                    "enum": list(PAGE_KINDS),
                    "description": (
                        "Only return files whose frontmatter `type` is this kind. "
                        "Applies to every corpus scanned, raw sessions included; "
                        "raw session files carry `type: source`. Omit it to search "
                        "every page, generated navigation and folder context "
                        "pages included."
                    ),
                },
                "include_raw": {
                    "type": "boolean",
                    "description": (
                        "Also search raw/sessions/ (default false — only wiki/). "
                        "Combines with kind, which then filters both corpora."
                    ),
                    "default": False,
                },
                "format": {
                    "type": "string",
                    "enum": list(_SEARCH_FORMATS),
                    "description": (
                        "`text` (default) renders the prose listing; `json` "
                        "returns the same result as a parseable payload with "
                        "`pages[].lines[]` and the completeness flags."
                    ),
                    "default": "text",
                },
            },
            "required": ["term"],
        },
    },
    {
        "name": "wiki_list_sources",
        "description": "List all raw source markdown files under raw/sessions/ with their metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Optional project slug to filter by.",
                },
            },
        },
    },
    {
        "name": "wiki_read_page",
        "description": (
            "Return the full content of one wiki or raw page. Path is relative "
            "to the repo root (e.g. 'wiki/sources/clever-munching-parnas.md')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Page path relative to the repo root.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "wiki_lint",
        "description": (
            "Run every registered quality check over the wiki and return the "
            "same JSON report `llmwiki lint --json` prints: {summary, issues, "
            "total_pages, disabled_rules, ran}. The checks cover link "
            "integrity, orphan pages, contradictions, staleness, frontmatter "
            "and catalog health. Rules the vault switches off in its "
            "llmwiki.json are skipped and named in `disabled_rules`, and "
            "`ran` names the checks that actually produced the report — so a "
            "report narrowed by `rules`, or by the vault, can never be "
            "mistaken for a full one."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Run only these checks by name (a comma-separated "
                        "string is also accepted). Default: all of them. An "
                        "unrecognised name is an error, not a silent skip."
                    ),
                },
                "min_refs": {
                    "type": "integer",
                    "description": (
                        "How many distinct source pages must name a wikilink "
                        "target before an unresolved link to it counts as "
                        f"broken. Default: {DEFAULT_MIN_REFS}, the same "
                        "threshold the candidate harvest uses. Lowering it "
                        "reports more broken links."
                    ),
                },
            },
        },
    },
    {
        "name": "wiki_sync",
        "description": (
            "Run the session-transcript converter to pull in any new sessions "
            "from the agent's session store into raw/sessions/. Returns the "
            "converter's summary line. Defaults to dry-run; pass confirm=true "
            "to actually write."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                # #sec-12 (#556): default to dry_run=true so an MCP client
                # can't silently mutate raw/ on a misclick / hallucinated
                # tool call. Pass `confirm: true` to actually write.
                "dry_run": {
                    "type": "boolean",
                    "description": (
                        "If true (default), preview without writing. Set "
                        "false ONLY together with confirm=true."
                    ),
                    "default": True,
                },
                "confirm": {
                    "type": "boolean",
                    "description": (
                        "Required to actually write. Without confirm=true "
                        "the call always runs as a dry-run regardless of "
                        "dry_run."
                    ),
                    "default": False,
                },
            },
        },
    },
    {
        "name": "wiki_export",
        "description": (
            "Dump the entire wiki in a machine-readable format for AI agents. "
            "Returns the requested format as text. Use 'llms-txt' for the "
            "short llms.txt index, 'llms-full-txt' for the flattened content "
            "dump, 'jsonld' for the schema.org JSON-LD graph, 'sitemap' for "
            "the sitemap.xml, or 'list' to list every available export."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["llms-txt", "llms-full-txt", "jsonld", "sitemap", "rss", "manifest", "list"],
                    "description": "Which export format to return.",
                },
            },
            "required": ["format"],
        },
    },
    # v1.0 (#159) — MCP tools for confidence, lifecycle, dashboard and
    # category browse.
    {
        "name": "wiki_confidence",
        "description": (
            "Return confidence scores for wiki pages. Filters by minimum "
            "confidence threshold. Pages below threshold may need review."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_confidence": {
                    "type": "number",
                    "description": "Only return pages with confidence >= this (0.0-1.0). Default 0.",
                    "default": 0.0,
                },
                "max_confidence": {
                    "type": "number",
                    "description": "Only return pages with confidence <= this (0.0-1.0). Default 1.0.",
                    "default": 1.0,
                },
            },
        },
    },
    {
        "name": "wiki_lifecycle",
        "description": (
            "List pages by lifecycle state: draft, reviewed, verified, stale, "
            "or archived. Use to find pages needing review or archival."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["draft", "reviewed", "verified", "stale", "archived"],
                    "description": "Which lifecycle state to filter by.",
                },
            },
            "required": ["state"],
        },
    },
    {
        "name": "wiki_dashboard",
        "description": (
            "Return a summary of wiki health: page counts by type, "
            "confidence distribution, lifecycle distribution, stale pages, "
            "and recent updates."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    # #37 A3: the one write tool other than wiki_sync — MCP-only agents
    # otherwise have no supported way to land a new document.
    {
        "name": "wiki_add",
        "description": (
            "Ingest one source into the wiki via the add pipeline — the "
            "same conversion/write path the `llmwiki add` CLI uses. "
            "Converts the source to markdown and writes it under the "
            "resolved vault's raw/docs/ (never the repo's own wiki/). "
            "Exactly one of url, path, or content is required."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "http(s) URL to fetch and convert.",
                },
                "path": {
                    "type": "string",
                    "description": "Local file or folder path to convert.",
                },
                "content": {
                    "type": "string",
                    "description": "Literal markdown/text content to land directly.",
                },
                "title": {
                    "type": "string",
                    "description": "Override title derivation.",
                },
                "project": {
                    "type": "string",
                    "description": "Group under raw/docs/<project>/ instead of the doc's own slug.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra frontmatter tags.",
                },
                "note": {
                    "type": "string",
                    "description": "Blockquote note prepended to the document body.",
                },
            },
        },
    },
    {
        "name": "wiki_category_browse",
        "description": (
            "List tags and the count of pages for each. Optionally return "
            "all pages for a specific tag."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Optional tag to drill into. If omitted, returns counts for all tags.",
                },
                "min_count": {
                    "type": "integer",
                    "description": "Only include tags with >= this many pages (default 1).",
                    "default": 1,
                },
            },
        },
    },
]


# ─── Tool implementations ─────────────────────────────────────────────────


# #482: top-level directories the MCP read-page tool is allowed to
# return content from. Anything outside this set is rejected even
# though it lives under REPO_ROOT — e.g. .git/, .env, .venv/, the
# state files (.llmwiki-state.json contains absolute paths to every
# Claude session file → host directory listing leak), and dotfiles
# in general. README, CHANGELOG, CONTRIBUTING are allowed by name
# because they're the documentation surface every consumer expects.
_READ_PAGE_ALLOWED_DIRS: tuple[str, ...] = (
    "wiki", "raw", "docs", "examples", "site",
)
_READ_PAGE_ALLOWED_ROOT_FILES: frozenset[str] = frozenset({
    "README.md", "CHANGELOG.md", "CONTRIBUTING.md",
    "LICENSE", "LICENSE.md",
})


def _safe_path(rel: str) -> Path | None:
    """Resolve a user-supplied path relative to REPO_ROOT and refuse if it
    escapes the repo (path traversal guard)."""
    if not rel:
        return None
    head = Path(rel).parts[0] if Path(rel).parts else ""
    base = REPO_ROOT if head in {"wiki", "raw"} else SOURCE_ROOT
    p = (base / rel).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        return None
    return p


def _is_read_page_allowed(p: Path) -> bool:
    """#482: restrict `tool_wiki_read_page` to a documented surface.

    The path-traversal guard in `_safe_path` only checks the file is
    *under* REPO_ROOT. That still leaks every dotfile, the .git
    directory, the state files, and node_modules. Apply an explicit
    allowlist on top — the docs surface, plus the user's wiki/raw
    content. Anything else is silently a "not found".
    """
    try:
        rel_parts = p.resolve().relative_to(SOURCE_ROOT.resolve()).parts
    except ValueError:
        try:
            rel_parts = p.resolve().relative_to(REPO_ROOT.resolve()).parts
        except ValueError:
            return False
    if not rel_parts:
        return False
    head = rel_parts[0]
    # Top-level allowlisted directory?
    if head in _READ_PAGE_ALLOWED_DIRS:
        return True
    # Single allowlisted file at the root?
    if len(rel_parts) == 1 and head in _READ_PAGE_ALLOWED_ROOT_FILES:
        return True
    return False


def tool_wiki_query(args: dict[str, Any]) -> dict[str, Any]:
    question = (args.get("question") or "").strip()
    max_pages = int(args.get("max_pages", 5))
    if not question:
        return _err("question is required")

    wiki = REPO_ROOT / "wiki"
    if not wiki.exists():
        return _ok(
            "wiki/ does not exist yet — run `llmwiki init` and `/wiki-sync` first"
        )

    # Read the index + overview
    index = (wiki / "index.md").read_text(encoding="utf-8") if (wiki / "index.md").exists() else ""
    overview = (wiki / "overview.md").read_text(encoding="utf-8") if (wiki / "overview.md").exists() else ""

    # Scan every .md under wiki/ for matches on title + body.
    # #418: ranking is now length-normalised — body matches are
    # divided by ``log2(max(len(content), 256))`` so a 1MB log
    # page can't beat a perfectly-relevant 1-paragraph entity page
    # just by accidentally containing every query token. Title
    # matches are unchanged since titles are already short and
    # high-signal.
    query_lower = question.lower()
    tokens = [t for t in re.split(r"\W+", query_lower) if t]
    matches: list[tuple[float, Path, str]] = []
    # #483: bound input bytes so a single large file or a giant corpus
    # can't OOM the MCP server.
    budget = _MCP_SCAN_AGGREGATE_BYTES
    skipped_oversize = 0
    for page in wiki.rglob("*.md"):
        if budget <= 0:
            break
        # Cold storage (#140): a discarded page must never be quoted back
        # as an answer — the reviewer dismissed the term as noise.
        if is_archived_path(page.relative_to(wiki).parts):
            continue
        content, consumed = _read_capped(page, remaining_budget=budget)
        if consumed == 0:
            try:
                if page.stat().st_size > _MCP_SCAN_PER_FILE_BYTES:
                    skipped_oversize += 1
            except OSError:
                pass
            continue
        budget -= consumed
        content_lower = content.lower()
        body_score = 0
        if query_lower in content_lower:
            body_score += 50
        body_score += sum(10 for t in tokens if t in content_lower)
        # Length normalisation: divide raw body score by
        # log2(max(len, 256)). The 256-byte floor keeps very short
        # pages (frontmatter-only) from getting a massive boost on
        # zero-token queries.
        if body_score > 0:
            length_factor = math.log2(max(len(content), 256))
            normalised_body = body_score / length_factor
        else:
            normalised_body = 0.0
        # Title bonus — unchanged. Titles are already short and
        # high-signal; no normalisation needed.
        title_score = 0
        title_match = re.search(r'^title:\s*"?([^"\n]+)', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).lower()
            if query_lower in title:
                title_score += 100
            title_score += sum(20 for t in tokens if t in title)
        score = normalised_body + title_score
        if score > 0:
            snippet = _extract_snippet(content, tokens, max_chars=400)
            matches.append((score, page, snippet))

    matches.sort(key=lambda x: -x[0])
    top = matches[:max_pages]

    out = [f"# Query: {question}\n"]
    if not top:
        out.append("No matching pages found.\n")
        out.append("\n## wiki/index.md\n\n" + index[:1500])
    else:
        for score, page, snippet in top:
            rel = page.relative_to(REPO_ROOT)
            out.append(f"## `{rel}` (score: {score:.1f})\n")
            out.append(snippet)
            out.append("")
    out.append("---\n")
    out.append("## Overview context\n")
    out.append(overview[:1000] if overview else "(no overview.md)")

    # Report the exact matched-page count to telemetry out-of-band (#26):
    # deriving it from the prose above is unreliable because a page body
    # can contain a line shaped like a result heading. `_hits` is stripped
    # before the result is sent to the client.
    result = _ok("\n".join(out))
    result["_hits"] = len(top)
    return result


def _extract_snippet(content: str, tokens: list[str], max_chars: int = 400) -> str:
    """Return a ±max_chars window around the first token match, or the first
    max_chars of the body if no match."""
    content_lower = content.lower()
    for t in tokens:
        idx = content_lower.find(t)
        if idx >= 0:
            start = max(0, idx - max_chars // 2)
            end = min(len(content), idx + max_chars // 2)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(content) else ""
            return prefix + content[start:end] + suffix
    return content[:max_chars] + ("…" if len(content) > max_chars else "")


_SEARCH_HIT_CAP = 200

# A page rendered without any body line still costs one output row, so the
# matching-line cap alone does not bound the response. Cap the pages too.
_SEARCH_PAGE_CAP = 200

# #483: per-file + aggregate byte caps for wiki_search / wiki_query.
# Without these, a single large file (e.g. a 100MB Obsidian transcript
# with embedded video, or a malicious user-supplied .md) gets fully
# read into memory by every MCP call. _SEARCH_HIT_CAP capped output
# only — the loop still read every byte of every file. Cap inputs
# explicitly so the worst-case is bounded regardless of corpus shape.
_MCP_SCAN_PER_FILE_BYTES = 4 * 1024 * 1024   # 4 MiB / file
_MCP_SCAN_AGGREGATE_BYTES = 50 * 1024 * 1024  # 50 MiB / call


def _read_capped(p: Path, *, remaining_budget: int) -> tuple[str, int]:
    """Read up to min(per-file cap, remaining_budget) bytes of `p`.

    Returns (text, bytes_consumed). ``bytes_consumed == 0`` signals
    the file was skipped entirely (over-budget or unreadable). Caller
    decrements the aggregate budget by ``bytes_consumed`` and bails
    when it hits zero.
    """
    try:
        size = p.stat().st_size
    except OSError:
        return "", 0
    cap = min(_MCP_SCAN_PER_FILE_BYTES, max(0, remaining_budget))
    if size > _MCP_SCAN_PER_FILE_BYTES:
        # Skip the file entirely — do not partial-read. The truncation
        # would slice query tokens across the boundary and produce
        # confusing partial hits.
        return "", 0
    if cap <= 0:
        return "", 0
    try:
        with p.open("rb") as f:
            raw = f.read(cap + 1)
    except OSError:
        return "", 0
    # If we read more than cap, the file grew between stat and read.
    # Trust the stat-based skip above; truncate defensively here.
    if len(raw) > cap:
        return "", 0
    try:
        return raw.decode("utf-8", errors="replace"), len(raw)
    except Exception:
        return "", 0


def _iter_scan_files(
    roots: Iterable[Path], *, cold_storage_root: Path | None = None
) -> Iterator[Path]:
    """Yield every ``.md`` file under the given roots as one flat sequence.

    A single iterator gives the caller a single termination check, so one
    hit cap applies across all roots instead of once per root (#413).
    Missing roots are skipped silently.

    ``cold_storage_root`` names the wiki root whose ``archive/`` subtree is
    withheld (#140): a discarded candidate is a term the reviewer called
    noise, so search must not offer it back. The test is per root rather
    than per path because only ``wiki/archive/**`` is cold storage — a raw
    transcript filed under a folder named ``archive`` is ordinary source
    material and stays searchable.
    """
    for root in roots:
        if not root.exists():
            continue
        cold = cold_storage_root is not None and root == cold_storage_root
        for path in root.rglob("*.md"):
            if cold and is_archived_path(path.relative_to(root).parts):
                continue
            yield path


def tool_wiki_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search wiki pages (and optionally raw sessions) for a literal term.

    Results are page-level: ``path — title`` with the matching lines
    indented beneath it. Pages whose title or path matches the term sort
    above pages that match only in the body, and each group sorts by path
    so repeated calls return the same order. A title/path match with no
    body hit still returns its page.

    ``include_raw`` selects the corpora to scan; ``kind`` filters on
    frontmatter ``type`` within whatever is scanned. They compose:
    ``kind="source"`` with ``include_raw`` returns wiki source pages and
    the raw session files behind them (raw sessions carry
    ``type: source``), while a kind no raw file declares simply gets no
    contribution from the raw corpus.

    ``format="json"`` returns the same result as a machine-readable
    payload for callers that parse rather than read.

    Completeness is reported explicitly: ``truncated`` when output caps
    dropped matches, ``budget_exhausted`` when the scan stopped short of
    the corpus because the byte budget ran out (#483).
    """
    term = (args.get("term") or "").strip()
    kind = str(args.get("kind") or "").strip().lower()
    include_raw = bool(args.get("include_raw", False))
    fmt = str(args.get("format") or "text").strip().lower()
    if not term:
        return _err("term is required")
    if fmt not in _SEARCH_FORMATS:
        return _err(f"unknown format {fmt!r} (expected one of {_SEARCH_FORMATS})")
    if kind and kind not in PAGE_KINDS:
        return _err(f"unknown kind {kind!r} (expected one of {list(PAGE_KINDS)})")

    wiki_root = REPO_ROOT / "wiki"
    roots = [wiki_root]
    if include_raw:
        roots.append(REPO_ROOT / "raw" / "sessions")

    term_lower = term.lower()
    # Two buckets so the documented ranking is a property of collection,
    # not a sort over whatever survived: name/path matches keep their own
    # capacity and cannot be crowded out by body matches (#413 starvation).
    name_pages: list[dict[str, Any]] = []
    body_pages: list[dict[str, Any]] = []
    hit_count = 0
    line_cap_reached = False
    dropped_pages = False
    # #483: aggregate byte budget across all roots, plus a per-file cap
    # via _read_capped. Output is capped by _SEARCH_HIT_CAP matching lines
    # and _SEARCH_PAGE_CAP pages across every root (#413).
    budget = _MCP_SCAN_AGGREGATE_BYTES
    skipped_oversize = 0
    budget_exhausted = False
    for p in _iter_scan_files(roots, cold_storage_root=wiki_root):
        if budget <= 0:
            budget_exhausted = True
            break
        # With the line cap reached, only a name match can still add
        # output; once those are capped too, nothing more can be collected.
        if line_cap_reached and len(name_pages) >= _SEARCH_PAGE_CAP:
            break
        text, consumed = _read_capped(p, remaining_budget=budget)
        if consumed == 0:
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size > _MCP_SCAN_PER_FILE_BYTES:
                skipped_oversize += 1
            elif size > budget:
                # In-spec file the call no longer has the budget to read.
                budget_exhausted = True
            continue
        # Charge the budget before filtering: a file we read and then drop
        # still consumed its bytes, in every corpus (#483).
        budget -= consumed
        meta = parse_frontmatter_dict(text)
        if kind and str(meta.get("type", "")).strip().lower() != kind:
            continue
        rel = str(p.relative_to(REPO_ROOT))
        title = str(meta.get("title", "") or "").strip()
        name_match = term_lower in title.lower() or term_lower in rel.lower()
        lines: list[tuple[int, str]] = []
        # The hit cap stops body-line collection, not the walk — a page
        # named for the term is still worth returning after the cap.
        if not line_cap_reached:
            for i, line in enumerate(text.splitlines(), start=1):
                if term_lower in line.lower():
                    lines.append((i, line.strip()[:200]))
                    hit_count += 1
                    if hit_count >= _SEARCH_HIT_CAP:
                        line_cap_reached = True
                        break
        if not (lines or name_match):
            continue
        bucket = name_pages if name_match else body_pages
        if len(bucket) >= _SEARCH_PAGE_CAP:
            dropped_pages = True
            continue
        bucket.append({"path": rel, "title": title,
                       "name_match": name_match, "lines": lines})

    # Name matches first, then body-only matches; path order inside each
    # group so the same corpus always renders the same way.
    name_pages.sort(key=lambda pg: pg["path"])
    body_pages.sort(key=lambda pg: pg["path"])
    pages = name_pages + body_pages
    if len(pages) > _SEARCH_PAGE_CAP:
        pages = pages[:_SEARCH_PAGE_CAP]
        dropped_pages = True
    truncated = line_cap_reached or dropped_pages

    if fmt == "json":
        result = _ok(json.dumps({
            "term": term,
            "kind": kind or None,
            "include_raw": include_raw,
            "pages": [
                {
                    "path": pg["path"],
                    "title": pg["title"],
                    "name_match": pg["name_match"],
                    "lines": [{"line": n, "text": t} for n, t in pg["lines"]],
                }
                for pg in pages
            ],
            "truncated": truncated,
            "budget_exhausted": budget_exhausted,
            "skipped_oversize_files": skipped_oversize,
        }, indent=2))
    else:
        scope = f" (kind: {kind})" if kind else ""
        out = [f"{len(pages)} page(s) matching {term!r}{scope}:", ""]
        for pg in pages:
            header = f"{pg['path']} — {pg['title']}" if pg["title"] else pg["path"]
            out.append(header)
            out.extend(f"  :{num}: {text_}" for num, text_ in pg["lines"])
            out.append("")
        out.append(f"truncated: {str(truncated).lower()}")
        # A scan that ran out of budget never reached the rest of the
        # corpus — say so instead of implying the result is complete.
        out.append(f"budget_exhausted: {str(budget_exhausted).lower()}")
        # #483: surface the skipped-oversize count so callers know we didn't
        # silently miss content from huge files.
        out.append(f"skipped_oversize_files: {skipped_oversize}")
        result = _ok("\n".join(out))

    # `hits` is one number across the whole persisted usage series, so keep
    # it in the unit that series already uses: result rows returned. Every
    # row is a matching line, except a page matched by name alone, which
    # renders as its header (#26).
    result["_hits"] = sum(len(pg["lines"]) or 1 for pg in pages)
    return result


def tool_wiki_list_sources(args: dict[str, Any]) -> dict[str, Any]:
    project_filter = args.get("project")
    raw_sessions = REPO_ROOT / "raw" / "sessions"
    if not raw_sessions.exists():
        return _ok(json.dumps([], indent=2))
    out = []
    for p in sorted(raw_sessions.rglob("*.md")):
        project = p.parent.name
        if project_filter and project_filter not in project:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        out.append(
            {
                "path": str(p.relative_to(REPO_ROOT)),
                "project": project,
                "filename": p.name,
                "size_bytes": size,
            }
        )
    return _ok(json.dumps(out, indent=2))


def tool_wiki_read_page(args: dict[str, Any]) -> dict[str, Any]:
    rel = args.get("path")
    if not rel:
        return _err("path is required")
    p = _safe_path(rel)
    if p is None:
        return _err(f"path escapes repo root: {rel!r}")
    # #482: restrict to documented allowlist (wiki/, raw/, docs/,
    # examples/, site/, plus README/CHANGELOG/etc. at the root).
    # Reject .git/, .env, .llmwiki-state.json, node_modules, etc.
    # even though they live under REPO_ROOT.
    if not _is_read_page_allowed(p):
        return _err(
            f"path is outside the readable surface: {rel!r}. "
            f"Allowed: {', '.join(_READ_PAGE_ALLOWED_DIRS)}/, "
            f"plus {', '.join(sorted(_READ_PAGE_ALLOWED_ROOT_FILES))} at the root."
        )
    if not p.exists():
        return _err(f"path does not exist: {rel}")
    if not p.is_file():
        return _err(f"path is not a file: {rel}")
    try:
        content = p.read_text(encoding="utf-8")
    except OSError as e:
        return _err(f"read error: {e}")
    return _ok(content)


def _lint_rule_selection(args: dict[str, Any]) -> list[str] | None:
    """Normalise the ``rules`` argument to the list ``run_lint`` expects.

    Accepts the CLI's comma-separated string as well as a JSON array, so a
    client can pass ``"link_integrity,orphan_pages"`` or
    ``["link_integrity", "orphan_pages"]`` and get the same run.
    """
    raw = args.get("rules")
    if raw is None:
        return None
    names = raw.split(",") if isinstance(raw, str) else list(raw)
    selected = [str(name).strip() for name in names if str(name).strip()]
    return selected or None


def tool_wiki_lint(args: dict[str, Any]) -> dict[str, Any]:
    """Run the registered lint rules over the vault's wiki/ (#150).

    Parity, not resemblance: this is `load_pages` + `run_lint` + `render_json`
    — byte-for-byte the payload `llmwiki lint --json` prints for the same
    vault, including the rules the vault switched off in `llmwiki.json`. An
    agent and a person must not be working from two accounts of one wiki.
    """
    root = REPO_ROOT
    wiki = root / "wiki"
    if not wiki.is_dir():
        return _err("wiki/ does not exist")

    # Read the opt-out declaration before anything can print a result: a
    # settings file nobody can parse might be switching every check off, so
    # reporting the vault as clean would be a guess dressed up as a result.
    try:
        disabled = disabled_lint_rules(load_vault_settings(root))
    except VaultSettingsError as exc:
        return _err(f"error: {exc}")

    try:
        min_refs = int(args.get("min_refs", DEFAULT_MIN_REFS))
    except (TypeError, ValueError):
        return _err(f"error: min_refs must be an integer, got {args.get('min_refs')!r}")
    # Same range the CLI flag enforces: below 1 the suppression gate
    # (`0 < n_refs < min_refs`) silently behaves like 1, so accepting it
    # would answer a threshold the caller did not ask for.
    if min_refs < 1:
        return _err(f"error: min_refs must be at least 1, got {min_refs}")

    pages = load_pages(wiki)
    try:
        outcome = run_lint(
            pages,
            selected=_lint_rule_selection(args),
            disabled=disabled,
            options=LintOptions(min_refs=min_refs),
        )
    except UnknownRuleError as exc:
        # Name the file when the bad name came from it — the reader is
        # editing a declaration, not passing `rules`.
        origin = (f"{vault_settings_path(root)}: "
                  if any(name in disabled for name in exc.unknown) else "")
        return _err(f"error: {origin}{exc}")

    return _ok(json.dumps(render_lint_json(outcome, len(pages)), indent=2))


def tool_wiki_sync(args: dict[str, Any]) -> dict[str, Any]:
    # #sec-12 (#556): default to dry_run=true. Real writes require BOTH
    # dry_run=false AND confirm=true. Either flag missing = dry-run.
    dry_run = bool(args.get("dry_run", True))
    confirm = bool(args.get("confirm", False))
    if not dry_run and not confirm:
        # Caller asked for live sync without confirmation — downgrade to
        # dry-run + tell them why. Better than silently mutating raw/.
        dry_run = True
    cmd = [sys.executable, "-m", "llmwiki", "sync"]
    if dry_run:
        cmd.append("--dry-run")
    # #py-h1 (#582): capture_output=True buffers all stdout in RAM. A
    # very chatty sync (thousands of sessions) can blow past the
    # 1 GB-ish ceiling Python can hold + grow before OOM-killing.
    # Stream stdout via Popen + readline, capping the captured tail
    # to a fixed byte budget so the MCP response stays bounded.
    OUTPUT_CAP_BYTES = 256 * 1024  # 256 KB tail in the response
    captured: list[str] = []
    captured_bytes = 0
    truncated = False
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(SOURCE_ROOT),
        )
        # Read line-by-line so a hung child doesn't block forever — the
        # outer try wraps a 120s timeout via proc.wait below.
        assert proc.stdout is not None
        deadline = time.time() + 120.0
        for line in proc.stdout:
            if captured_bytes < OUTPUT_CAP_BYTES:
                captured.append(line)
                captured_bytes += len(line)
            else:
                truncated = True
            if time.time() > deadline:
                proc.kill()
                return _err("sync timed out after 120s")
        proc.wait(timeout=max(0.1, deadline - time.time()))
    except subprocess.TimeoutExpired:
        try:
            proc.kill()  # type: ignore[name-defined]
        except Exception:
            pass
        return _err("sync timed out after 120s")
    except (OSError, subprocess.SubprocessError) as e:
        return _err(f"sync failed: {e}")
    output = "".join(captured)
    if truncated:
        output += f"\n[output truncated at {OUTPUT_CAP_BYTES // 1024} KB]"
    return _ok(output or "(no output)")


def tool_wiki_export(args: dict[str, Any]) -> dict[str, Any]:
    """Return one of the AI-consumable export files (v0.4)."""
    fmt = args.get("format")
    site_dir = REPO_ROOT / "site"

    if fmt == "list":
        candidates = [
            "llms.txt",
            "llms-full.txt",
            "graph.jsonld",
            "sitemap.xml",
            "rss.xml",
            "robots.txt",
            "ai-readme.md",
            "manifest.json",
            "search-index.json",
        ]
        out = []
        for name in candidates:
            p = site_dir / name
            if p.exists():
                out.append({"format": name, "size_bytes": p.stat().st_size, "url": name})
        return _ok(json.dumps(out, indent=2))

    mapping = {
        "llms-txt": "llms.txt",
        "llms-full-txt": "llms-full.txt",
        "jsonld": "graph.jsonld",
        "sitemap": "sitemap.xml",
        "rss": "rss.xml",
        "manifest": "manifest.json",
    }
    filename = mapping.get(fmt)
    if not filename:
        return _err(f"unknown format: {fmt}. Valid: {sorted(mapping.keys())} + 'list'")
    p = site_dir / filename
    if not p.exists():
        return _err(f"{filename} does not exist. Run 'llmwiki build' first.")
    try:
        content = p.read_text(encoding="utf-8")
    except OSError as e:
        return _err(f"read error: {e}")
    # Cap response size at 200 KB to keep MCP responses sane
    if len(content) > 200 * 1024:
        content = content[: 200 * 1024] + f"\n\n…(truncated at 200 KB; full file is {p.stat().st_size} bytes at /{filename})"
    return _ok(content)


def tool_wiki_add(args: dict[str, Any]) -> dict[str, Any]:
    """Ingest one source (url | path | content) via the add pipeline
    (#37 A3). A thin wrapper around ``add_sources`` — the same
    conversion/write path the ``llmwiki add`` CLI and the queue's
    ``add_doc`` task use — so MCP-only agents have a supported write
    path. Runs synchronously and only writes raw/docs/: post-steps
    (synthesize, build) are the caller's job, exactly like the queue's
    ``add_doc`` task leaves them to a separate ``synthesize`` task.
    """

    url = (args.get("url") or "").strip()
    path = (args.get("path") or "").strip()
    content = args.get("content") or ""
    provided = [v for v in (url, path, content) if v]
    if len(provided) != 1:
        return _err(
            "exactly one of url, path, or content is required "
            f"(got {len(provided)})"
        )

    title = args.get("title")
    project = args.get("project")
    tags = tuple(args.get("tags") or ())
    note = args.get("note")

    docs_dir = REPO_ROOT / "raw" / "docs"

    tmp_path: Path | None = None
    try:
        if content:
            fd, tmp_name = tempfile.mkstemp(suffix=".md", prefix="wiki-add-content-")
            os.close(fd)
            tmp_path = Path(tmp_name)
            tmp_path.write_text(content, encoding="utf-8")
            source = str(tmp_path)
        else:
            source = url or path

        result = add_sources(
            [source], docs_dir,
            title=title, project=project, tags=tags, note=note,
            dry_run=False,
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    if result["errors"]:
        return _err("; ".join(result["errors"]))

    written_rel = [str(p.relative_to(REPO_ROOT)) for p in result["written"]]
    payload = {
        "written": written_rel,
        "titles": result["titles"],
        "warnings": result["warnings"],
    }
    out = _ok(json.dumps(payload, indent=2))
    out["_hits"] = len(written_rel)
    return out


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _err(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def tool_wiki_confidence(args: dict[str, Any]) -> dict[str, Any]:
    """List pages filtered by confidence score range (v1.0 · #159)."""

    min_c = float(args.get("min_confidence", 0.0))
    max_c = float(args.get("max_confidence", 1.0))

    wiki = REPO_ROOT / "wiki"
    pages = load_pages(wiki)

    results: list[dict[str, Any]] = []
    for rel, page in pages.items():
        conf_raw = page["meta"].get("confidence", "")
        if not conf_raw:
            continue
        try:
            conf = float(conf_raw)
        except (ValueError, TypeError):
            continue
        if min_c <= conf <= max_c:
            results.append({
                "path": rel,
                "title": page["meta"].get("title", ""),
                "confidence": conf,
                "lifecycle": page["meta"].get("lifecycle", ""),
            })

    results.sort(key=lambda r: r["confidence"])
    text = f"{len(results)} pages with confidence in [{min_c}, {max_c}]:\n\n"
    for r in results[:50]:
        text += f"  {r['confidence']:.2f}  {r['path']}  — {r['title']}\n"
    if len(results) > 50:
        text += f"\n  ... and {len(results) - 50} more\n"
    return _ok(text)


def tool_wiki_lifecycle(args: dict[str, Any]) -> dict[str, Any]:
    """List pages filtered by lifecycle state (v1.0 · #159)."""

    state = (args.get("state") or "").strip().lower()
    if not state:
        return _err("state is required")

    wiki = REPO_ROOT / "wiki"
    pages = load_pages(wiki)

    matches = [
        (rel, page["meta"].get("title", ""), page["meta"].get("last_updated", ""))
        for rel, page in pages.items()
        if page["meta"].get("lifecycle", "").lower() == state
    ]
    matches.sort(key=lambda m: m[2], reverse=True)

    text = f"{len(matches)} pages in lifecycle '{state}':\n\n"
    for rel, title, updated in matches[:50]:
        text += f"  {updated}  {rel}  — {title}\n"
    if len(matches) > 50:
        text += f"\n  ... and {len(matches) - 50} more\n"
    return _ok(text)


def tool_wiki_dashboard(args: dict[str, Any]) -> dict[str, Any]:
    """Return wiki health summary (v1.0 · #159)."""

    wiki = REPO_ROOT / "wiki"
    pages = load_pages(wiki)

    by_type: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    conf_buckets = {"high (≥0.8)": 0, "medium (0.5-0.8)": 0, "low (<0.5)": 0, "none": 0}

    for page in pages.values():
        meta = page["meta"]
        t = meta.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        lc = meta.get("lifecycle", "none")
        by_lifecycle[lc] = by_lifecycle.get(lc, 0) + 1

        conf_raw = meta.get("confidence", "")
        if not conf_raw:
            conf_buckets["none"] += 1
        else:
            try:
                c = float(conf_raw)
                if c >= 0.8:
                    conf_buckets["high (≥0.8)"] += 1
                elif c >= 0.5:
                    conf_buckets["medium (0.5-0.8)"] += 1
                else:
                    conf_buckets["low (<0.5)"] += 1
            except (ValueError, TypeError):
                conf_buckets["none"] += 1

    lines = [f"# Wiki Dashboard — {len(pages)} pages\n"]
    lines.append("## By type\n")
    for t in sorted(by_type):
        lines.append(f"  {by_type[t]:4d}  {t}")
    lines.append("\n## By lifecycle\n")
    for lc in sorted(by_lifecycle):
        lines.append(f"  {by_lifecycle[lc]:4d}  {lc}")
    lines.append("\n## Confidence distribution\n")
    for bucket in ["high (≥0.8)", "medium (0.5-0.8)", "low (<0.5)", "none"]:
        lines.append(f"  {conf_buckets[bucket]:4d}  {bucket}")

    return _ok("\n".join(lines))


def tool_wiki_category_browse(args: dict[str, Any]) -> dict[str, Any]:
    """Browse tags / categories (v1.0 · #159)."""

    tag = (args.get("tag") or "").strip().lower()
    min_count = int(args.get("min_count", 1))

    wiki = REPO_ROOT / "wiki"
    pages = load_pages(wiki)
    tags = scan_tags(pages)

    if tag:
        page_rels = tags.get(tag, [])
        text = f"{len(page_rels)} pages tagged '{tag}':\n\n"
        for rel in page_rels[:50]:
            title = pages[rel]["meta"].get("title", "")
            text += f"  {rel}  — {title}\n"
        return _ok(text)

    # List all tags with counts
    filtered = [(t, len(pgs)) for t, pgs in tags.items() if len(pgs) >= min_count]
    filtered.sort(key=lambda x: x[1], reverse=True)

    text = f"{len(filtered)} tags with >= {min_count} pages:\n\n"
    for t, count in filtered[:100]:
        text += f"  {count:4d}  {t}\n"
    return _ok(text)


TOOL_IMPLS = {
    "wiki_query": tool_wiki_query,
    "wiki_search": tool_wiki_search,
    "wiki_list_sources": tool_wiki_list_sources,
    "wiki_read_page": tool_wiki_read_page,
    "wiki_lint": tool_wiki_lint,
    "wiki_sync": tool_wiki_sync,
    "wiki_export": tool_wiki_export,
    # #37 A3
    "wiki_add": tool_wiki_add,
    # v1.0 (#159)
    "wiki_confidence": tool_wiki_confidence,
    "wiki_lifecycle": tool_wiki_lifecycle,
    "wiki_dashboard": tool_wiki_dashboard,
    "wiki_category_browse": tool_wiki_category_browse,
}


# ─── JSON-RPC plumbing ────────────────────────────────────────────────────


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    # Note the roots capability but don't use it yet — the spec allows
    # server-initiated requests only after `notifications/initialized`.
    caps = params.get("capabilities") or {}
    _CLIENT["supports_roots"] = isinstance(caps, dict) and isinstance(
        caps.get("roots"), dict)
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": SERVER_INFO,
        "capabilities": {"tools": {}},
    }


def handle_tools_list(params: dict[str, Any]) -> dict[str, Any]:
    return {"tools": TOOLS}


def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return _err(f"Unknown tool: {name}")
    start = time.perf_counter()
    try:
        result = impl(args)
    except Exception as e:
        result = _err(f"Internal error in {name}: {e}")
    duration_ms = int((time.perf_counter() - start) * 1000)
    _record_usage(name, args, result, duration_ms)
    # `_hits` is a private telemetry channel — never leak it to the client.
    result.pop("_hits", None)
    return result


HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def main() -> int:
    """Run the MCP server on stdin/stdout."""
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                send(error_response(None, -32700, "Parse error"))
                continue

            method = req.get("method", "")
            req_id = req.get("id")
            params = req.get("params", {}) or {}

            # A frame with no method is a reply to something *we* asked for
            # (`roots/list`), not a request — answering it with an error
            # would corrupt the client's request/response bookkeeping.
            if not method:
                if handle_client_response(req) or "result" in req or "error" in req:
                    # Ours, or a reply to a request we've since superseded —
                    # either way a response frame never earns an error back:
                    # the client would read it as the reply to its next call.
                    continue
                if req_id is None:
                    continue
                send(error_response(req_id, -32600, "Invalid Request"))
                continue

            handler = HANDLERS.get(method)
            if handler is None:
                if req_id is None:
                    handle_client_notification(method)
                    continue  # notifications don't get a response
                send(error_response(req_id, -32601, f"Method not found: {method}"))
                continue

            try:
                result = handler(params)
            except Exception as e:
                send(error_response(req_id, -32603, f"Internal error: {e}"))
                continue

            if req_id is not None:
                send({"jsonrpc": "2.0", "id": req_id, "result": result})
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        sys.stderr.write(f"MCP server error: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

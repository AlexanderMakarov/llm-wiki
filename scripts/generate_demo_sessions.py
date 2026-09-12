#!/usr/bin/env python3
"""Generate the demo vault's session corpus.

The demo needs transcripts that look like real agent work so the pages
llmwiki builds from them look like real output. They are **written**, not
captured: a published demo built from someone's actual transcripts leaks
whatever those transcripts happened to discuss — machine paths, client and
project names, personal handles, unrelated private work — and no scrubber can
enumerate that space ahead of time. Authoring the input removes the risk class
instead of chasing it.

Everything downstream is still genuine product output: these files go through
the real `synth`, candidate harvest, review, `build` and `graph`.

The corpus is deterministic — same inputs, same *slugs* — so regenerating
it should not rename files. Writes are **in-place by slug**: find an
existing ``*-{slug}.md``, rewrite body + frontmatter (including ``date`` /
``started`` / ``ended`` from ``--today``), keep the filename. New slugs get
a dated path once; removed slugs delete their file. No ``rmtree``.

Bodies match ``llmwiki.convert`` shape (project/stats header, shared
turn index for User/Assistant, ``**Tools used:**`` / ``**Tool results:**``
bullets) so the demo sessions index looks like a real vault — varied
``user_messages``, not a flat ``2`` on every row.

For a **release cut** (#225), bump ``--today`` to refresh calendar fields
inside frontmatter; filenames stay put, so wiki ``source_file:`` links
usually remain valid without a rename-driven re-synth. CI and ``pages.yml``
never regenerate this corpus — they only build what is committed.

Three authored sessions carry `#180` headless markers (`is_headless: true`).
They stay in `raw/` for coverage but are skipped by default synth under
`filters.exclude_headless`.

Run from the repository root:

    python3 scripts/generate_demo_sessions.py --dry-run
    python3 scripts/generate_demo_sessions.py --today 2026-09-08

#197 search seeds (every run, not a one-time patch)
----------------------------------------------------
Do **not** hand-edit planted terms into ``demo/raw/sessions/``. Authored
``SESSIONS`` stay plant-free; ``PLANTED_PRESENT`` / ``PHRASE_WORD_SEEDS`` /
``ABSENT_CANDIDATES`` are applied in ``sessions_with_plants()`` on every
write. The same run always rewrites ``tests/fixtures/demo_search_terms.json``
(present + confirmed-absent). Ranking baselines stay in
``tests/fixtures/demo_search_baseline.json`` (maintainer-measured; not
emitted here).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_SESSIONS = REPO_ROOT / "demo" / "raw" / "sessions"
DEMO_VAULT = REPO_ROOT / "demo"
SEARCH_TERMS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "demo_search_terms.json"

# Matches llmwiki.lint.rules._helpers._TOOL_BULLET_RE / convert output.
_TOOL_BULLET_RE = re.compile(r"^- `[^`]+`:", re.MULTILINE)
_SLUG_FROM_NAME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-.+-(.+)\.md$")

# (label, target_user_messages, target_tool_calls) — cycle across the corpus
# so the sessions index MSGS column is not a flat 2.
_ACTIVITY_PROFILES: tuple[tuple[str, int, int], ...] = (
    ("chat", 1, 0),
    ("short", 1, 3),
    ("pair", 2, 6),
    ("pair", 2, 10),
    ("medium", 4, 16),
    ("medium", 6, 24),
    ("long", 11, 36),
    ("long", 15, 48),
)

_FOLLOWUPS: tuple[tuple[str, str], ...] = (
    (
        "Does that cover the edge case we hit last week?",
        "Yes — the retry path handles it. I left a short note on the page so the next pass does not rediscover it.",
    ),
    (
        "Can you show the command you ran?",
        "Listed below in the tool trace. The interesting bit is the exit code and the first matching line.",
    ),
    (
        "What should I commit?",
        "The touched modules plus the test that locks the behaviour. Skip regenerating unrelated demo wiki pages.",
    ),
    (
        "Any lint fallout?",
        "One warning-severity count mismatch on an old stub — unrelated. The new pages are clean.",
    ),
    (
        "How do we verify on a fresh vault?",
        "Init a throwaway vault, sync once, then search for the durable handle. If rank-1 is wrong, check title collisions first.",
    ),
    (
        "Is the headless path affected?",
        "No — headless fixtures stay excluded from default synth. This change is interactive-session only.",
    ),
    (
        "Document it?",
        "A one-line CHANGELOG under Unreleased is enough; the CLI reference already describes the flag.",
    ),
    (
        "Ship it?",
        "After ruff + the focused pytest file, yes. Full suite can wait for CI on the PR.",
    ),
)


@dataclass(frozen=True)
class Session:
    """One authored transcript."""

    project: str
    slug: str
    adapter: str
    model: str
    branch: str
    title: str
    summary: str
    subjects: tuple[str, ...]
    turns: tuple[tuple[str, str], ...]
    tools: tuple[str, ...] = ("Read", "Edit", "Bash")
    age_days: int = 0
    entrypoint: str = "cli"
    tags: tuple[str, ...] = field(default=("session",))
    # #180 headless launch markers (optional; interactive demos leave defaults).
    is_headless: bool = False
    prompt_source: str = "typed"
    approval_mode: str | None = None
    subagent_type_name: str | None = None


def _s(project, slug, adapter, model, branch, title, summary, subjects, turns,
       tools=("Read", "Edit", "Bash"), age_days=0, entrypoint="cli",
       tags=("session",), is_headless=False, prompt_source="typed",
       approval_mode=None, subagent_type_name=None) -> Session:
    return Session(
        project, slug, adapter, model, branch, title, summary,
        tuple(subjects), tuple(turns), tuple(tools), age_days, entrypoint,
        tuple(tags), is_headless, prompt_source, approval_mode, subagent_type_name,
    )


# ─── The corpus ────────────────────────────────────────────────────────────
# Subjects recur deliberately across sessions: a topic named by only one
# session is dropped from the topic graph (min_sessions=2), so overlap is what
# makes the graph and the harvested candidates non-trivial.

SESSIONS: list[Session] = [
    # ── llm-wiki: the product itself ───────────────────────────────────────
    _s("llm-wiki", "adapter-registry-refactor", "claude_code", "claude-opus-5", "feat/adapters",
       "Refactor the adapter registry so contrib adapters stay opt-in",
       "Split the adapter registry so core adapters auto-detect while contrib ones require an explicit flag.",
       ["Session Adapters", "Claude Code", "Codex CLI", "Contrib Adapters", "Incremental Sync"],
       [("user", "The adapter registry auto-detects everything it finds, including contrib adapters nobody asked for. Can we make core auto-detect and contrib opt-in?"),
        ("assistant", "Looked at the registry. `llmwiki/adapters/` holds the core two — Claude Code and Codex CLI — and everything else lives under `contrib/`. The detection loop treats both directories identically, which is the bug.\n\nI split the lookup: core adapters are probed on every `sync`, contrib ones only when named with `--adapter` or enabled in config. Added a test that a contrib adapter stays silent on a default sync even when its session store exists."),
        ("user", "Good. Make sure `llmwiki adapters` still lists everything so people can discover them."),
        ("assistant", "It does — listing is separate from activation. `llmwiki adapters --wide` shows every adapter with a present/absent column, and contrib rows now carry an `opt-in` marker so the distinction is visible before you run a sync.")],
       tools=("Read", "Edit", "Bash", "Grep"), age_days=120),

    _s("llm-wiki", "incremental-synth-state", "claude_code", "claude-opus-5", "fix/synth-state",
       "Stop re-synthesising sources that have not changed",
       "Traced why a second synth run re-processed everything and fixed the state comparison.",
       ["Incremental Sync", "Wiki Synthesis", "Session Adapters"],
       [("user", "Running synth twice in a row re-synthesises everything. It should be a no-op the second time."),
        ("assistant", "Found it. The state file records a modification time per source, and the comparison was strictly greater-than rather than greater-or-equal, so a file whose timestamp exactly matched its recorded value looked new.\n\nFixed the comparison and added a small epsilon so filesystems with coarse timestamp resolution do not flip the result. A second run is now genuinely a no-op — the run summary reports `skipped` for every source."),
        ("user", "Does that survive a fresh clone?"),
        ("assistant", "No, and that is worth knowing. Checkout rewrites modification times, so every source looks new on a fresh clone and the next synth reprocesses the whole corpus. Content hashing would fix it properly; the state file would need a migration. I have written it up rather than changing it here.")],
       age_days=80),

    _s("llm-wiki", "topic-graph-sparsity", "claude_code", "claude-opus-5", "feat/graph",
       "Fall back to the page graph when the topic vocabulary is thin",
       "A two-node topic graph rendered as an empty-looking viewer, so the build now falls back when topics are sparse.",
       ["Knowledge Graph", "Topic Pages", "Static Site", "WikiLinks"],
       [("user", "The graph page looks broken on a small vault — one edge and two nodes floating in space."),
        ("assistant", "That is the topic graph with almost nothing in it. Topics are dropped below two mentioning sessions, so a young vault produces two or three nodes and the viewer looks empty rather than small.\n\nI added a threshold: below five topics the build falls back to the full page graph, which always has content because every page is a node. The build prints which graph it chose and why, so the fallback is visible rather than mysterious."),
        ("user", "Does the fallback change the topic pages?"),
        ("assistant", "Yes — topic pages are generated from the topic graph, so below the threshold none are written. The build says so explicitly in its output. It is a real limitation of a small vault rather than something to paper over.")],
       tools=("Read", "Edit", "Bash", "Glob"), age_days=44),

    _s("llm-wiki", "candidate-review-gate", "claude_code", "claude-opus-5", "feat/candidates",
       "Add the candidate review gate between harvest and promotion",
       "Harvest now writes stubs to a review folder instead of publishing pages directly.",
       ["Candidate Review", "Wiki Synthesis", "WikiLinks", "Frontmatter"],
       [("user", "Harvest is writing entity pages straight into the wiki. I want to review them first."),
        ("assistant", "Changed harvest to write into `wiki/candidates/` rather than the destination folder. Nothing reaches `entities/` or `concepts/` until it is promoted.\n\nReview happens through `llmwiki candidates`: list, promote, flip-promote when the kind is wrong, merge when two stubs describe the same subject, discard with a reason. Discards are archived rather than deleted so the decision is recoverable."),
        ("user", "What decides whether something becomes a candidate at all?"),
        ("assistant", "The number of distinct source pages naming it. Default is three; `--min-refs` lowers it. A subject mentioned once is usually incidental, and promoting it produces a page with a single fact on it.")],
       tools=("Read", "Edit", "Bash", "Grep"), age_days=32),

    _s("llm-wiki", "mcp-server-tools", "claude_code", "claude-opus-5", "feat/mcp",
       "Expose the wiki over MCP so any agent can read it",
       "Added search, read-page and query tools to the MCP server and pinned the kind vocabulary to one source.",
       ["MCP Server", "Claude Code", "Cursor", "Frontmatter"],
       [("user", "I want Cursor to be able to read the wiki without me pasting anything."),
        ("assistant", "The MCP server already exposed a search tool. I added read-page and query alongside it, so an agent can search, open a specific page, and ask a question that walks the graph.\n\nOne thing worth noting: the tool schema advertises the page kinds a caller can filter by, and that list was hardcoded separately from the schema module. I pointed both at the same constant so they cannot drift."),
        ("user", "Does it work from Cursor specifically?"),
        ("assistant", "Yes — it is a stdio server, so any MCP client can launch it. Cursor, Claude Code and Codex CLI all connect the same way. The server is a consumer surface and is entirely separate from the adapters that read session stores.")],
       tools=("Read", "Edit", "Bash"), age_days=22),

    _s("llm-wiki", "lint-rule-severities", "openclaw", "claude-opus-5", "chore/lint",
       "Sort the lint rules into errors, warnings and information",
       "Reviewed all seventeen rules and settled which ones should be able to fail a build.",
       ["Lint Rules", "Static Site", "Frontmatter", "WikiLinks"],
       [("user", "Lint reports everything at the same volume. Which of these should actually block a build?"),
        ("assistant", "Went through all seventeen. Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere.\n\nNine are warnings — broken cross-references, stub pages, near-duplicate detection, tag conventions. They mean something is worth fixing but not that the output is wrong. The remaining four are informational, including orphan detection, which fires constantly on a young vault."),
        ("user", "Freshness — error or warning?"),
        ("assistant", "Warning, and arguably it should not fire at all on a fixed corpus. It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal.")],
       tools=("Read", "Grep", "Bash"), age_days=15),

    _s("llm-wiki", "static-site-offline", "claude_code", "claude-opus-5", "feat/offline",
       "Make the built site work without a server or a network",
       "Vendored the graph library and moved state into a script tag so the site opens from a file.",
       ["Static Site", "Knowledge Graph", "Deployment"],
       [("user", "Can I just open the site from disk, or do I need to serve it?"),
        ("assistant", "You can now. Two things were in the way. The graph library loaded from a CDN, so an offline machine got an empty viewer; it is vendored beside the page with a pinned version and a notice file recording its licence.\n\nThe bigger one: page data was fetched as JSON, and a file-opened page cannot fetch a sibling file. It is now emitted as a script tag the page loads directly, which works identically over HTTP and from disk."),
        ("user", "What still needs a server?"),
        ("assistant", "Only the candidates page, which posts review decisions to a small endpoint. Everything else — home, projects, sessions, topics, search, graph — is static.")],
       tools=("Read", "Edit", "Bash"), age_days=9),

    _s("llm-wiki", "project-page-aggregation", "cursor_cli", "claude-opus-5", "feat/projects",
       "Seed project pages from session metadata",
       "Project pages are now derived from session frontmatter rather than written by hand.",
       ["Session Metadata", "Frontmatter", "Static Site"],
       [("user", "Project pages are stale — I have to edit them whenever I add sessions."),
        ("assistant", "They are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists.\n\nOne consequence worth knowing: those stubs carry no last-updated date of their own. A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it."),
        ("user", "What if two clones of the same repo produce different project names?"),
        ("assistant", "They currently produce two projects. The name comes from the working directory, so a second clone reads as separate work. Worth solving, but it needs a stable project identity rather than a path.")],
       tools=("Read", "Edit", "Bash"), age_days=5),

    _s("llm-wiki", "key-facts-prompt", "claude_code", "claude-haiku-4-5", "feat/key-facts",
       "Constrain the Key Facts prompt to attributed bullets",
       "Tightened the synthesis prompt so every fact carries the source that supports it.",
       ["Wiki Synthesis", "Key Facts", "Frontmatter", "Candidate Review"],
       [("user", "Some Key Facts read like the model's general knowledge rather than anything from my sessions."),
        ("assistant", "The prompt allowed it. I rewrote it to require that every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added however well known it is.\n\nIt now returns nothing at all rather than inventing a fact when the evidence supports none. Fewer bullets, but each one is traceable."),
        ("user", "Should these pages have an intro paragraph too?"),
        ("assistant", "Nothing writes one today — the prompt produces bullets and the harvest stub is a heading. Adding one would be a new generated field with its own cost and quality bar, so it is worth deciding deliberately rather than drifting into it.")],
       tools=("Read", "Edit", "Bash"), age_days=3),

    _s("llm-wiki", "search-index-chunks", "claude_code", "claude-opus-5", "perf/search",
       "Split the search index into per-project chunks",
       "A single index file was downloading everything up front; it is now chunked and loaded on demand.",
       ["Static Site", "Session Metadata", "Deployment"],
       [("user", "The site takes a while before search works on a big vault."),
        ("assistant", "The whole index was one file, downloaded before the first keystroke. It is now split per project, with a small manifest loaded up front and each chunk fetched when a result from that project is needed.\n\nOn the demo corpus the difference is invisible. On a vault with a thousand sessions it is the difference between a pause and none."),
        ("user", "Does that break search when the page is opened from disk?"),
        ("assistant", "Good catch — it would have. The chunks are emitted as script files rather than fetched JSON for exactly that reason, so a file-opened page still searches.")],
       tools=("Read", "Edit", "Bash", "Glob"), age_days=2),

    _s("llm-wiki", "docs-ingest-pipeline", "openclaw", "claude-opus-5", "feat/add-docs",
       "Ingest arbitrary documents alongside sessions",
       "Added a path for pulling documents into the vault so the wiki is not limited to transcripts.",
       ["Document Ingest", "Wiki Synthesis", "Markdown", "Incremental Sync"],
       [("user", "I want reference documents in the wiki, not just my sessions."),
        ("assistant", "Added an ingest path that takes a file, a folder or a URL, converts it to Markdown, and lands it beside the sessions as immutable input. It is then synthesised into a source page like anything else.\n\nDuplicate content is detected by hash, so re-adding an unchanged document is a no-op rather than a second copy."),
        ("user", "What happens if the document changed since I added it?"),
        ("assistant", "You get a second copy under a new slug, and the original stays. There is no in-place update — the immutability rule for raw input means nothing rewrites what is already there. Removing the original first is the way to replace it, and that is a rough edge worth smoothing.")],
       tools=("Read", "Edit", "Bash", "WebFetch"), age_days=1),

    _s("llm-wiki", "wikilink-resolution", "claude_code", "claude-opus-5", "fix/wikilinks",
       "Confirm how cross-references resolve before moving pages",
       "Established that links resolve by filename, which decides whether a page can be relocated safely.",
       ["WikiLinks", "Knowledge Graph", "Lint Rules"],
       [("user", "If I move a page from one folder to another, do links to it break?"),
        ("assistant", "They do not. Every consumer keys pages by filename — the graph builder, the backlink index, the reference index and the link lint rule all use the file stem. The folder only decides the page's kind and its URL on the site.\n\nSo moving a page between folders is safe as long as the filename is unchanged. I added a test that moves a page and asserts the graph edge, the backlink and the lint result are all identical afterwards."),
        ("user", "What about a page that was merged into another one?"),
        ("assistant", "That is the case where links do break. Merging records the old name as an alias, but nothing consults aliases during resolution, so every existing reference to the merged-away name dangles.")],
       tools=("Read", "Grep", "Bash"), age_days=0),

    # ── other projects: a realistic multi-project vault ────────────────────
    _s("pocket-ledger", "csv-import-rounding", "claude_code", "claude-opus-5", "fix/rounding",
       "Fix cent-rounding drift on imported statements",
       "Repeated float rounding was losing a cent per few hundred rows; switched to integer minor units.",
       ["Python", "pytest", "Data Import"],
       [("user", "Imported totals are off by a few cents against the statement."),
        ("assistant", "Amounts were parsed to floats and rounded per row, so the error accumulated. I switched the internal representation to integer minor units and round once at the presentation edge.\n\nAdded a regression test with a fixture that reproduced the drift — it was off by four cents over six hundred rows before the change and exact after."),
        ("user", "Any migration needed for existing data?"),
        ("assistant", "No. Stored values are re-parsed from the original statements on import, so the fix applies on the next run without touching anything already saved.")],
       tools=("Read", "Edit", "Bash"), age_days=105),

    _s("pocket-ledger", "category-rules-engine", "cursor_cli", "claude-opus-5", "feat/rules",
       "Add a rules engine for transaction categories",
       "Replaced a hardcoded keyword map with ordered user-defined rules.",
       ["Python", "Configuration"],
       [("user", "Category matching is a giant if-chain. I want to define my own rules."),
        ("assistant", "Replaced it with an ordered rule list loaded from config: each rule has a matcher and a category, first match wins, and an explicit fallback catches the rest.\n\nOrdering is the whole design — the previous behaviour depended on dictionary order, which was accidental."),
        ("user", "Can a rule match on amount as well as description?"),
        ("assistant", "Yes, and the two combine with an implicit and. There is a test for a rule matching only above a threshold, since that was the case the old code could not express at all.")],
       tools=("Read", "Edit", "Bash"), age_days=12),

    _s("trailhead-api", "pagination-cursors", "claude_code", "claude-opus-5", "feat/pagination",
       "Move list endpoints from offset to cursor pagination",
       "Offset paging skipped rows when records were inserted mid-scan; cursors fixed it.",
       ["REST API", "SQLite", "Python"],
       [("user", "Clients paging through the list endpoint are missing records."),
        ("assistant", "Classic offset problem — a row inserted before the current offset shifts everything and the next page skips one. I moved to cursor paging keyed on a stable sort column plus the primary key as a tiebreak.\n\nThe cursor is opaque to clients and encodes both values, so ordering stays stable even when rows are inserted mid-scan."),
        ("user", "Is the old parameter still accepted?"),
        ("assistant", "Yes, for now — it still works and returns a deprecation header. Removing it is a breaking change and belongs in a version bump.")],
       tools=("Read", "Edit", "Bash"), age_days=92),

    _s("trailhead-api", "request-id-logging", "codex_cli", "gpt-5-codex", "chore/logging",
       "Thread a request id through the log output",
       "Concurrent requests interleaved in the log with no way to separate them.",
       ["REST API", "Observability", "Python"],
       [("user", "I cannot follow a single request through the logs when there is any traffic."),
        ("assistant", "Added a request id generated at the edge, stored in a context variable, and included by the log formatter on every line. Nothing has to pass it explicitly.\n\nIt is also returned as a response header, so a report about a specific failed request can be traced directly."),
        ("user", "Does it survive a background task?"),
        ("assistant", "Only if the task is spawned from the request context. Anything scheduled outside it gets a fresh id, which is correct — it is a different unit of work.")],
       tools=("Read", "Edit", "Bash"), age_days=27),

    _s("trailhead-api", "schema-migration-safety", "claude_code", "claude-opus-5", "chore/migrations",
       "Make migrations safe to run twice",
       "A partially applied migration left the schema unrunnable; each step is now idempotent.",
       ["SQLite", "REST API", "pytest"],
       [("user", "A migration failed halfway and now I cannot run it again."),
        ("assistant", "Each step now checks its own precondition, so re-running skips what already applied rather than failing on a duplicate column. The runner records each completed step separately instead of marking the whole migration done at the end.\n\nAdded a test that interrupts a migration mid-way and re-runs it to completion."),
        ("user", "Does that cover a rollback?"),
        ("assistant", "No — this only makes forward runs repeatable. Rollback would need a down step per migration, which is a bigger change than the failure warranted.")],
       tools=("Read", "Edit", "Bash"), age_days=1),

    _s("dotfiles", "shell-startup-profiling", "openclaw", "claude-opus-5", "perf/startup",
       "Cut shell startup time by deferring completions",
       "Startup was dominated by loading completion scripts that were rarely used.",
       ["Shell", "Configuration"],
       [("user", "New terminals take almost a second to become usable."),
        ("assistant", "Profiled the startup file. Most of the time was loading completion scripts eagerly, including several for tools not installed on this machine.\n\nThey are now loaded lazily on first use of the command, and missing tools are skipped rather than failing silently. Startup went from roughly nine hundred milliseconds to under two hundred."),
        ("user", "Do completions still work on first use?"),
        ("assistant", "Yes — the first tab press pays the load cost once, then it is cached for the session. Noticeable only if you are looking for it.")],
       tools=("Read", "Edit", "Bash"), age_days=70),

    _s("dotfiles", "git-hooks-sync", "cursor_cli", "claude-opus-5", "feat/hooks",
       "Version the git hooks instead of copying them",
       "Hooks drifted between machines because they lived outside the repository.",
       ["Shell", "Git", "Configuration"],
       [("user", "My pre-push hook is different on each machine."),
        ("assistant", "Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull.\n\nThe setup script wires the path, and the hook itself checks only the files in the push rather than the whole tree, which keeps it fast enough that nobody is tempted to skip it."),
        ("user", "What if someone needs to bypass it?"),
        ("assistant", "The standard no-verify flag still works. The point is that skipping is a deliberate act rather than the default state.")],
       tools=("Read", "Edit", "Bash"), age_days=7),

    _s("recipe-box", "image-upload-limits", "claude_code", "claude-opus-5", "feat/uploads",
       "Validate image uploads before they reach storage",
       "Oversized and mistyped uploads were rejected only after being written.",
       ["Web App", "Validation"],
       [("user", "Someone uploaded a video and it was stored before anything complained."),
        ("assistant", "Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered.\n\nThe error names the limit and the detected type, since the previous message said only that the upload failed."),
        ("user", "What is the cap?"),
        ("assistant", "Configurable, defaulting to eight megabytes. The cap is enforced during the read, so an attempt to send more is cut off rather than measured after the fact.")],
       tools=("Read", "Edit", "Bash"), age_days=38),

    _s("recipe-box", "ingredient-scaling", "claude_code", "claude-opus-5", "feat/scaling",
       "Scale ingredient quantities without mangling fractions",
       "Doubling a recipe produced unreadable decimals instead of familiar fractions.",
       ["Web App", "Validation"],
       [("user", "Doubling a recipe gives me 0.6666666666666666 cups."),
        ("assistant", "Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display, snapping to the denominators people actually use in a kitchen.\n\nTwo thirds doubled now reads as one and a third rather than a decimal expansion."),
        ("user", "What about something that does not divide nicely?"),
        ("assistant", "It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway.")],
       tools=("Read", "Edit", "Bash"), age_days=2),

    _s("sensor-mesh", "backfill-gap-detection", "codex_cli", "gpt-5-codex", "feat/backfill",
       "Detect and backfill gaps in the sensor stream",
       "Dropped readings left silent gaps that looked like flat readings downstream.",
       ["Time Series", "Observability", "Python"],
       [("user", "A sensor dropped out for an hour and the dashboard drew a flat line through it."),
        ("assistant", "There was no distinction between a missing reading and a repeated one. Gaps are now detected against the expected interval and recorded explicitly, so downstream can draw a break instead of interpolating.\n\nBackfill re-requests a bounded window when a device reconnects, and refuses beyond that rather than pulling unbounded history."),
        ("user", "How does it know the expected interval?"),
        ("assistant", "Declared per device rather than inferred. Inference was the original approach and it adapted to the outage, which is exactly when you need it not to.")],
       tools=("Read", "Edit", "Bash"), age_days=60),

    _s("sensor-mesh", "mqtt-reconnect-backoff", "openclaw", "claude-opus-5", "fix/reconnect",
       "Add backoff to broker reconnection",
       "A dropped broker connection produced a tight reconnect loop.",
       ["Time Series", "Observability"],
       [("user", "When the broker goes down the logs fill up in seconds."),
        ("assistant", "The reconnect had no delay. It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep.\n\nThe log line moved to a summary — one line per attempt with the current delay, rather than one per failure."),
        ("user", "Does it give up eventually?"),
        ("assistant", "No, it keeps retrying at the ceiling. For a background collector, continuing to try is more useful than exiting and needing supervision to restart it.")],
       tools=("Read", "Edit", "Bash"), age_days=4),

    _s("paper-notes", "bibtex-key-collisions", "cursor_cli", "claude-opus-5", "fix/bibtex",
       "Resolve citation key collisions on import",
       "Two papers by the same author in the same year overwrote each other.",
       ["Markdown", "Data Import", "Validation"],
       [("user", "Importing two papers by the same author from the same year silently keeps one."),
        ("assistant", "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly.\n\nExisting keys are left alone so citations already written do not shift."),
        ("user", "What if the same paper is imported twice?"),
        ("assistant", "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers.")],
       tools=("Read", "Edit", "Bash"), age_days=52),

    _s("paper-notes", "pdf-text-extraction", "claude_code", "claude-opus-5", "feat/pdf",
       "Extract readable text from two-column PDFs",
       "Column-aware extraction replaced a naive reader that interleaved lines.",
       ["Markdown", "Data Import", "Python"],
       [("user", "Extracted text from two-column papers is interleaved nonsense."),
        ("assistant", "The reader walked the page in raw order. It now detects column boundaries from text block positions and reads each column through before moving on.\n\nSingle-column pages take the same path and are unaffected, since one detected column is just the page."),
        ("user", "Does it handle a paper that switches layout mid-document?"),
        ("assistant", "Yes — detection runs per page rather than once per document, so a single-column abstract followed by two-column body works.")],
       tools=("Read", "Edit", "Bash"), age_days=18),

    # ── #180 headless fixtures (synthetic; excluded from synth by default) ─
    # These exist in raw/ so the demo shows headless frontmatter markers.
    # `filters.exclude_headless` (default on) keeps them out of wiki/sources/.

    _s("llm-wiki", "sdk-cli-headless-lint-pass", "claude_code", "claude-opus-5",
       "chore/headless-demo",
       "Headless SDK lint pass over a synthetic fixture vault",
       "Synthetic Claude SDK-CLI headless run that would be skipped under exclude_headless.",
       ["Lint Rules", "Session Adapters", "Incremental Sync"],
       [("user", "Run the lint rules against the fixture vault and report only errors."),
        ("assistant", "Scanned the fixture. Four structural rules are clean; two warning-severity findings remain on stub pages that the fixture deliberately leaves unfinished.\n\nThis transcript is authored demo material — not a captured session — so paths stay under `/home/USER/code/llm-wiki`."),
        ("user", "Exit non-zero on warnings too."),
        ("assistant", "Re-ran with the stricter gate. The two stub warnings now fail the pass, matching what `lint --fail-on warnings` would do on a real vault.")],
       tools=("Read", "Bash", "Grep"), age_days=6,
       entrypoint="sdk-cli", prompt_source="sdk", is_headless=True,
       tags=("claude-code", "session")),

    _s("llm-wiki", "auto-review-headless-diff", "cursor_cli", "claude-opus-5",
       "chore/headless-demo",
       "Auto-review headless pass on a synthetic diff",
       "Synthetic Cursor Agent CLI auto-review launch; headless via approvalMode.",
       ["Lint Rules", "Static Site", "Frontmatter"],
       [("user", "Review the synthetic patch for frontmatter and link issues only."),
        ("assistant", "Checked the fixture diff. No broken wikilinks; one frontmatter date disagrees with the filename stamp and is noted as a warning.\n\nAuthored for the demo corpus — no real user vault content."),
        ("user", "Is that enough to block merge under the demo policy?"),
        ("assistant", "Under errors-only, no. Under fail-on-warnings, yes. The demo policy matches the product default of reporting without failing a scheduled job.")],
       tools=("Read", "Grep", "Bash"), age_days=3,
       is_headless=True, approval_mode="auto-review",
       tags=("cursor-cli", "session")),

    _s("llm-wiki", "code-reviewer-subagent-headless", "cursor_cli", "claude-opus-5",
       "chore/headless-demo",
       "Code-reviewer subagent: synthetic PR findings",
       "Synthetic Cursor nested code-reviewer subagent session; headless via subagentTypeName.",
       ["Candidate Review", "Wiki Synthesis", "Lint Rules"],
       [("user", "Spawn a code-reviewer subagent on the synthetic PR fixture."),
        ("assistant", "Nested review complete. Three findings: one missing CHANGELOG bullet, one docs cross-link that still points at a retired path, and one test that asserts the old filter summary wording.\n\nThis is a fabricated subagent transcript for headless-coverage demos."),
        ("user", "Which finding is highest priority?"),
        ("assistant", "The retired docs link — readers hit a dead page. The CHANGELOG gap and the stale assertion are follow-ups once the link is fixed.")],
       tools=("Read", "Grep", "Bash"), age_days=1,
       is_headless=True, subagent_type_name="code-reviewer",
       tags=("cursor-cli", "session")),
]


# ─── #197 planted search terms / phrases (static; independent of --today) ─
# Invented subject-matter words that cannot collide with privacy greps.
# Keyed by (session slug, placement). Each present value appears in exactly
# one placement. Phrase component words are seeded separately (below) so
# extract-mode's whole-phrase bonus is under test.

@dataclass(frozen=True)
class PlantedPresent:
    """One term or phrase that acceptance must find (#197 R5)."""

    session: str
    placement: str  # title | user | assistant | tool
    value: str
    kind: str  # term | phrase


# Spread across the four demo adapters and four placements (R5).
PLANTED_PRESENT: tuple[PlantedPresent, ...] = (
    # terms — title
    PlantedPresent("adapter-registry-refactor", "title", "korvindex", "term"),
    PlantedPresent("category-rules-engine", "title", "orbicast", "term"),
    PlantedPresent("shell-startup-profiling", "title", "marnitask", "term"),
    PlantedPresent("backfill-gap-detection", "title", "brexinode", "term"),
    # terms — user
    PlantedPresent("project-page-aggregation", "user", "nexovault", "term"),
    PlantedPresent("docs-ingest-pipeline", "user", "veldmark", "term"),
    PlantedPresent("static-site-offline", "user", "plixbuffer", "term"),
    PlantedPresent("search-index-chunks", "user", "skylorbit", "term"),
    # terms — assistant
    PlantedPresent("lint-rule-severities", "assistant", "tarnifold", "term"),
    PlantedPresent("request-id-logging", "assistant", "syntraxon", "term"),
    PlantedPresent("key-facts-prompt", "assistant", "wintrelap", "term"),
    PlantedPresent("bibtex-key-collisions", "assistant", "quorilith", "term"),
    # terms — tool
    PlantedPresent("mcp-server-tools", "tool", "glypherun", "term"),
    PlantedPresent("git-hooks-sync", "tool", "hexalume", "term"),
    PlantedPresent("mqtt-reconnect-backoff", "tool", "farnodeck", "term"),
    PlantedPresent("pdf-text-extraction", "tool", "draxelume", "term"),
    # phrases — contiguous plant; component words seeded elsewhere
    PlantedPresent("candidate-review-gate", "user", "zeldo route mesh", "phrase"),
    PlantedPresent("incremental-synth-state", "assistant", "tymar flux gate", "phrase"),
    PlantedPresent("topic-graph-sparsity", "tool", "ovrix delta plan", "phrase"),
    PlantedPresent("csv-import-rounding", "title", "lundric scale map", "phrase"),
)

# Silent seeds: phrase words that must also occur apart from the phrase page.
# Not listed in the present fixture (those entries are unique).
PHRASE_WORD_SEEDS: tuple[tuple[str, str, str], ...] = (
    # zeldo route mesh — route/mesh already recur in the authored corpus
    ("wikilink-resolution", "assistant", "zeldo"),
    # tymar flux gate — gate already common; seed tymar + flux
    ("schema-migration-safety", "user", "tymar"),
    ("ingredient-scaling", "assistant", "flux"),
    # ovrix delta plan — plan already present; seed ovrix + delta
    ("image-upload-limits", "user", "ovrix"),
    ("pagination-cursors", "user", "delta"),
    # lundric scale map — scale/map already present; seed lundric
    ("pagination-cursors", "assistant", "lundric"),
)

# Synthetic absents — confirmed by scan after write. Phrase tokens must
# *all* be invented: extract mode scores individual tokens, so a common
# word like "cycle" would produce hits even when the whole phrase is absent.
ABSENT_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("zzqorvexil", "term"),
    ("zznultramod", "term"),
    ("zzphlentari", "term"),
    ("zzgrobunex", "term"),
    ("zzymeldora", "term"),
    ("zzqorvexil zzmundrel", "phrase"),
    ("zznultramod zzweaveor", "phrase"),
    ("zzphlentari zzvaultor", "phrase"),
)


def _session_by_slug() -> dict[str, Session]:
    return {s.slug: s for s in SESSIONS}


def _inject_into_text(text: str, value: str, *, kind: str) -> str:
    """Append a plausible subject-matter sentence carrying ``value``."""
    if kind == "phrase":
        sentence = (
            f"We should keep the {value} wording intact in the summary "
            f"so later lookup can recover the whole phrase."
        )
    else:
        sentence = (
            f"Call out {value} explicitly in the notes — it is the durable "
            f"handle we want search to recover later."
        )
    if text.rstrip().endswith((".", "!", "?")):
        return f"{text.rstrip()} {sentence}"
    return f"{text.rstrip()}. {sentence}"


def _inject_title(title: str, value: str) -> str:
    """Embed a planted value in the session title without looking like scaffolding."""
    return f"{title} ({value})"


def _tool_plant_blocks(value: str, *, kind: str) -> str:
    """Convert-shaped tool use + result carrying a planted term/phrase."""
    if kind == "phrase":
        cmd = f"llmwiki search --mode phrase {value!r}"
        result = f"1. wiki/sources/… — score 12.4 (phrase hit on {value})"
    else:
        cmd = f"rg -n {value} wiki/"
        result = f"wiki/overview.md:14: … {value} …"
    return (
        "**Tools used:**\n\n"
        f"- `Bash`: `{cmd}`\n\n"
        "**Tool results:**\n\n"
        f"  → result (ok): {result}\n"
    )


def _apply_title_plants(s: Session) -> Session:
    """Title plants only — body plants apply after activity expansion."""
    for plant in PLANTED_PRESENT:
        if plant.session == s.slug and plant.placement == "title":
            s = replace(s, title=_inject_title(s.title, plant.value))
    return s


def _plant_into_pairs(
    s: Session,
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Inject present + phrase-seed plants into expanded (user, assistant) pairs."""
    pairs = list(pairs)
    if not pairs:
        return pairs

    def _ensure_assistant() -> None:
        if not pairs:
            pairs.append(("Noted for the record.", "Acknowledged."))

    for plant in PLANTED_PRESENT:
        if plant.session != s.slug or plant.placement == "title":
            continue
        if plant.placement == "user":
            u, a = pairs[0]
            pairs[0] = (_inject_into_text(u, plant.value, kind=plant.kind), a)
        elif plant.placement == "assistant":
            u, a = pairs[0]
            pairs[0] = (u, _inject_into_text(a, plant.value, kind=plant.kind))
        elif plant.placement == "tool":
            _ensure_assistant()
            u, a = pairs[-1]
            block = _tool_plant_blocks(plant.value, kind=plant.kind)
            pairs[-1] = (u, f"{a.rstrip()}\n\n{block}")

    for session, placement, word in PHRASE_WORD_SEEDS:
        if session != s.slug:
            continue
        if placement == "user":
            u, a = pairs[0]
            pairs[0] = (_inject_into_text(u, word, kind="term"), a)
        elif placement == "assistant":
            u, a = pairs[0]
            pairs[0] = (u, _inject_into_text(a, word, kind="term"))
        elif placement == "tool":
            _ensure_assistant()
            u, a = pairs[-1]
            pairs[-1] = (u, f"{a.rstrip()}\n\n{_tool_plant_blocks(word, kind='term')}")
    return pairs


def sessions_with_plants() -> list[Session]:
    """Apply title plants; body plants land later in ``render_session``."""
    return [_apply_title_plants(s) for s in SESSIONS]


def _adapter_for_slug(slug: str) -> str:
    return _session_by_slug()[slug].adapter


def build_present_fixture_rows() -> list[dict[str, str]]:
    """Fixture rows for present terms/phrases (generator is the source of truth)."""
    rows: list[dict[str, str]] = []
    for plant in PLANTED_PRESENT:
        rows.append({
            "value": plant.value,
            "kind": plant.kind,
            "session": plant.session,
            "placement": plant.placement,
            "adapter": _adapter_for_slug(plant.session),
        })
    return rows


def confirm_absent(
    candidates: tuple[tuple[str, str], ...],
    corpus_blob_lower: str,
) -> list[dict[str, str]]:
    """Keep candidates whose full string *and* every token are absent."""
    out: list[dict[str, str]] = []
    for value, kind in candidates:
        lower = value.lower()
        if lower in corpus_blob_lower:
            raise RuntimeError(
                f"absent candidate {value!r} unexpectedly present in demo corpus"
            )
        for token in lower.split():
            if token in corpus_blob_lower:
                raise RuntimeError(
                    f"absent candidate token {token!r} from {value!r} "
                    f"is present in demo corpus"
                )
        out.append({"value": value, "kind": kind})
    return out


def emit_search_terms_fixture(
    present: list[dict[str, str]],
    absent: list[dict[str, str]],
    dest: Path = SEARCH_TERMS_FIXTURE,
) -> None:
    """Write ``tests/fixtures/demo_search_terms.json`` (#197)."""
    payload = {
        "_doc": (
            "Planted present / synthetic absent search terms for demo search "
            "acceptance (tests/test_search_acceptance.py). Written by "
            "scripts/generate_demo_sessions.py on every regenerate of "
            "demo/raw/sessions — never hand-edit. present entries are keyed to "
            "a single (session, placement); absent entries were confirmed "
            "missing from the demo vault by literal scan at generation time. "
            "kind is term (match mode) or phrase (extract mode)."
        ),
        "present": present,
        "absent": absent,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _activity_for_index(index: int) -> tuple[str, int, int]:
    return _ACTIVITY_PROFILES[index % len(_ACTIVITY_PROFILES)]


def _authored_pairs(turns: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    """Collapse authored turns into (user, assistant) pairs; drop bare tool roles."""
    users: list[str] = []
    assistants: list[str] = []
    pending_user: str | None = None
    for role, text in turns:
        if role == "user":
            if pending_user is not None:
                users.append(pending_user)
                assistants.append("Acknowledged.")
            pending_user = text
        elif role == "assistant":
            if pending_user is None:
                pending_user = "(continued)"
            users.append(pending_user)
            assistants.append(text)
            pending_user = None
        elif role == "tool":
            # Legacy plant shape — fold into the last assistant if any.
            if assistants:
                assistants[-1] = f"{assistants[-1].rstrip()}\n\n{text}"
            elif pending_user is not None:
                users.append(pending_user)
                assistants.append(text)
                pending_user = None
    if pending_user is not None:
        users.append(pending_user)
        assistants.append("Done.")
    return list(zip(users, assistants, strict=True))


def _synthetic_tool_block(s: Session, tool_index: int) -> str:
    name = s.tools[tool_index % len(s.tools)] if s.tools else "Bash"
    digest = hashlib.sha256(f"{s.slug}:{tool_index}".encode()).hexdigest()[:6]
    if name == "Bash":
        bullet = f"`Bash`: `python3 -m pytest tests/ -q -k {s.slug.replace('-', '_')}  # {digest}`"
        result = f"… {2 + tool_index % 9} passed in 0.{tool_index % 10}s"
    elif name == "Read":
        bullet = f"`Read`: `llmwiki/{s.slug[:12].replace('-', '_')}.py` L1–80"
        result = f"(file, {120 + tool_index * 17} lines)"
    elif name == "Edit":
        bullet = f"`Edit`: `llmwiki/{s.project.replace('-', '_')}/handler.py`"
        result = "ok — 1 hunk"
    elif name == "Grep":
        bullet = f"`Grep`: pattern `{s.slug}` path `llmwiki/`"
        result = f"llmwiki/cli.py:{10 + tool_index}: …"
    else:
        bullet = f"`{name}`: `{s.project}/{s.slug}`"
        result = f"ok ({digest})"
    return (
        "**Tools used:**\n\n"
        f"- {bullet}\n\n"
        "**Tool results:**\n\n"
        f"  → result (ok): {result}\n"
    )


def _expand_pairs(
    s: Session,
    pairs: list[tuple[str, str]],
    *,
    target_users: int,
    target_tools: int,
) -> list[tuple[str, str]]:
    """Pad/trim pairs and attach convert-shaped tool traces to assistants."""
    if target_users < 1:
        target_users = 1
    # Prefer authored content; trim from the end if the profile is shorter.
    if len(pairs) > target_users:
        pairs = pairs[:target_users]
    seed = int(hashlib.sha256(s.slug.encode()).hexdigest()[:8], 16)
    while len(pairs) < target_users:
        u, a = _FOLLOWUPS[(seed + len(pairs)) % len(_FOLLOWUPS)]
        # Tie follow-ups to this session's subjects so synth still has signal.
        if s.subjects:
            subj = s.subjects[len(pairs) % len(s.subjects)]
            a = f"{a} Related: [[{subj}]]."
        pairs.append((u, a))

    # Count tool bullets already present (from plants).
    existing = sum(len(_TOOL_BULLET_RE.findall(a)) for _, a in pairs)
    need = max(0, target_tools - existing)
    # Force at least one tool when plants used tool placement (already in text).
    if need == 0:
        return pairs

    out: list[tuple[str, str]] = []
    # Spread new tools across assistant turns (later turns get more, like real work).
    for i, (u, a) in enumerate(pairs):
        share = need // len(pairs) + (1 if i >= len(pairs) - (need % len(pairs)) else 0)
        if share:
            blocks = [
                _synthetic_tool_block(s, existing + i * 10 + j)
                for j in range(share)
            ]
            a = f"{a.rstrip()}\n\n" + "\n".join(blocks)
        out.append((u, a))
    return out


def _count_tool_bullets(text: str) -> int:
    return len(_TOOL_BULLET_RE.findall(text))


def _tool_counts_from_body(body: str, tools: tuple[str, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for m in re.finditer(r"^- `([^`]+)`:", body, re.MULTILINE):
        counts[m.group(1)] += 1
    if not counts and tools:
        return {t: 0 for t in tools}
    return dict(counts)


def index_existing_by_slug(root: Path) -> dict[str, Path]:
    """Map session slug → existing markdown path (first wins if duplicates)."""
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.md")):
        slug = None
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines()[:40]:
            if line.startswith("slug:"):
                slug = line.split(":", 1)[1].strip().strip('"')
                break
        if not slug:
            m = _SLUG_FROM_NAME_RE.match(path.name)
            if m:
                slug = m.group(1)
        if slug and slug not in found:
            found[slug] = path
    return found


def resolve_dest(
    s: Session,
    when: datetime,
    existing: dict[str, Path],
) -> Path:
    """Keep the on-disk path for a known slug; otherwise mint a dated filename."""
    if s.slug in existing:
        return existing[s.slug]
    fname = f"{when:%Y-%m-%dT%H-%M}-{s.project}-{s.slug}.md"
    return DEMO_SESSIONS / s.project / fname


def frontmatter(
    s: Session,
    when: datetime,
    index: int,
    *,
    rel_source: str,
    user_messages: int,
    tool_calls: int,
    tool_counts: dict[str, int],
) -> str:
    digest = hashlib.sha256(f"{s.project}/{s.slug}".encode()).hexdigest()
    sid = f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
    # Longer sessions run longer — still deterministic.
    ended = when + timedelta(
        minutes=5 + user_messages * 7 + tool_calls * 2 + (index * 3) % 17
    )
    tools_used = list(tool_counts.keys()) or list(s.tools)
    counts_json = json.dumps(tool_counts or {t: 0 for t in s.tools}, sort_keys=False)
    # Adapter-ish tags like real transcripts (session-transcript + agent family).
    tag_list = list(s.tags)
    if "session-transcript" not in tag_list:
        tag_list = ["session-transcript", *tag_list]
    lines = [
        "---",
        f'title: "{s.title}"',
        "type: source",
        f'description: "{s.summary}"',
        f"tags: [{', '.join(tag_list)}]",
        f"date: {when:%Y-%m-%d}",
        f"source_file: {rel_source}",
        f"sessionId: {sid}",
        f"slug: {s.slug}",
        f"project: {s.project}",
        f"started: {when.isoformat()}",
        f"ended: {ended.isoformat()}",
        f"cwd: /home/USER/code/{s.project}",
        f"gitBranch: {s.branch}",
        "permissionMode: default",
        f"model: {s.model}",
        f"user_messages: {user_messages}",
        f"tool_calls: {tool_calls}",
        f"tools_used: [{', '.join(tools_used)}]",
        f"tool_counts: {counts_json}",
        'token_totals: {"input": '
        + str(800 + user_messages * 900 + tool_calls * 120 + index * 40)
        + ', "output": '
        + str(200 + user_messages * 180 + tool_calls * 35)
        + "}",
        # convert.py: turn_count == user_messages (User headings only).
        f"turn_count: {user_messages}",
        f"duration_seconds: {int((ended - when).total_seconds())}",
        "is_subagent: false",
        f"entrypoint: {s.entrypoint}",
        f"promptSource: {s.prompt_source}",
        f"is_headless: {str(s.is_headless).lower()}",
    ]
    if s.approval_mode:
        lines.append(f"approvalMode: {s.approval_mode}")
    if s.subagent_type_name:
        lines.append(f"subagentTypeName: {s.subagent_type_name}")
    lines.extend([
        f"agent: {s.adapter.replace('_', '-')}",
        "---",
    ])
    return "\n".join(lines)


def body(s: Session, when: datetime, pairs: list[tuple[str, str]]) -> str:
    """Render Conversation in the same shape as ``llmwiki.convert``."""
    short = hashlib.sha256(s.slug.encode()).hexdigest()[:8]
    pairs = list(pairs)
    # Weave subjects into the last assistant (real convert has no ## Subjects).
    if s.subjects and pairs:
        last_u, last_a = pairs[-1]
        if "[[" not in last_a:
            links = ", ".join(f"[[{name}]]" for name in s.subjects)
            pairs[-1] = (last_u, f"{last_a.rstrip()}\n\nConnections: {links}.")

    tools_flat: list[str] = []
    for _, a in pairs:
        for m in re.finditer(r"^- `([^`]+)`:", a, re.MULTILINE):
            if m.group(1) not in tools_flat:
                tools_flat.append(m.group(1))
    tool_calls = sum(_count_tool_bullets(a) for _, a in pairs)
    tools_phrase = ", ".join(tools_flat) if tools_flat else "none"
    out = [
        f"# Session: {short} — {when:%Y-%m-%d}",
        "",
        f"**Project:** `{s.project}` · **Branch:** `{s.branch}` · "
        f"**Mode:** `default` · **Model:** `{s.model}`",
        "",
        f"**Stats:** {len(pairs)} user messages, {tool_calls} tool calls, "
        f"tools used: {tools_phrase}.",
        "",
        "## Conversation",
        "",
    ]
    for idx, (user_text, asst_text) in enumerate(pairs, start=1):
        out += [f"### Turn {idx} — User", "", user_text, ""]
        out += [f"### Turn {idx} — Assistant", "", asst_text, ""]
    return "\n".join(out)


def render_session(
    s: Session,
    when: datetime,
    index: int,
    *,
    dest: Path,
) -> str:
    """Full markdown for one session (frontmatter + convert-shaped body)."""
    _label, target_users, target_tools = _activity_for_index(index)
    pairs = _expand_pairs(
        s,
        _authored_pairs(s.turns),
        target_users=target_users,
        target_tools=target_tools,
    )
    pairs = _plant_into_pairs(s, pairs)
    body_text = body(s, when, pairs)
    user_messages = len(pairs)
    tool_calls = _count_tool_bullets(body_text)
    tool_counts = _tool_counts_from_body(body_text, s.tools)
    try:
        rel_source = dest.resolve().relative_to(DEMO_VAULT.resolve()).as_posix()
    except ValueError:
        rel_source = f"raw/sessions/{s.project}/{dest.name}"
    fm = frontmatter(
        s,
        when,
        index,
        rel_source=rel_source,
        user_messages=user_messages,
        tool_calls=tool_calls,
        tool_counts=tool_counts,
    )
    return fm + "\n\n" + body_text


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="Report the plan, write nothing")
    ap.add_argument("--today", help="Anchor date as YYYY-MM-DD (default: today, UTC)")
    args = ap.parse_args()

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").replace(tzinfo=UTC)
        if args.today
        else datetime.now(UTC)
    ).replace(hour=0, minute=0, second=0, microsecond=0)

    planted = sessions_with_plants()
    ordered = sorted(planted, key=lambda s: (-s.age_days, s.project, s.slug))
    interactive = [s for s in ordered if not s.is_headless]
    headless = [s for s in ordered if s.is_headless]
    clock_order = interactive + headless
    projects = sorted({s.project for s in ordered})
    adapters = sorted({s.adapter for s in ordered})
    print(
        f"{len(ordered)} sessions · {len(projects)} projects · {len(adapters)} adapters"
        f" · {len(headless)} headless"
    )
    print(f"  projects: {', '.join(projects)}")
    print(f"  adapters: {', '.join(adapters)}")
    print(
        f"  planted present: {len(PLANTED_PRESENT)} "
        f"({sum(1 for p in PLANTED_PRESENT if p.kind == 'term')} terms · "
        f"{sum(1 for p in PLANTED_PRESENT if p.kind == 'phrase')} phrases)"
    )
    print("  write mode: in-place by slug (filenames stick; dates move in frontmatter)\n")

    existing = index_existing_by_slug(DEMO_SESSIONS)
    keep_paths: set[Path] = set()
    written_texts: list[str] = []
    msg_hist: Counter[int] = Counter()

    for i, s in enumerate(clock_order):
        when = today - timedelta(
            days=s.age_days, hours=(i * 5) % 12, minutes=(i * 17) % 60
        )
        dest = resolve_dest(s, when, existing)
        keep_paths.add(dest.resolve())
        label, n_user, n_tool = _activity_for_index(i)
        mark = " headless" if s.is_headless else ""
        action = "update" if s.slug in existing else "create"
        print(
            f"  {when:%Y-%m-%d}  {s.adapter:<11} {s.project:<14} {s.slug}"
            f"{mark}  [{action} {label} ~{n_user}u/{n_tool}t] → {dest.name}"
        )
        content = render_session(s, when, i, dest=dest)
        written_texts.append(content)
        # Approximate MSGS from rendered content for the summary line.
        um = sum(1 for line in content.splitlines() if line.startswith("### Turn ") and line.endswith(" — User"))
        msg_hist[um] += 1
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    # Delete orphans (on disk but not in authored corpus).
    orphans = []
    if DEMO_SESSIONS.is_dir():
        for path in DEMO_SESSIONS.rglob("*.md"):
            if path.resolve() not in keep_paths:
                orphans.append(path)
    if orphans:
        print(f"\n  orphans to remove: {len(orphans)}")
        for path in orphans:
            print(f"    delete {path.relative_to(REPO_ROOT)}")
            if not args.dry_run:
                path.unlink()

    present_rows = build_present_fixture_rows()
    blob_parts = list(written_texts)
    if DEMO_VAULT.is_dir():
        for path in DEMO_VAULT.rglob("*.md"):
            try:
                rel = path.resolve().relative_to(DEMO_SESSIONS.resolve())
            except ValueError:
                rel = None
            if rel is not None:
                continue  # session files: use written_texts only
            try:
                blob_parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    corpus_blob = "\n".join(blob_parts).lower()
    absent_rows = confirm_absent(ABSENT_CANDIDATES, corpus_blob)

    print("\n  user_messages distribution:", dict(sorted(msg_hist.items())))

    if args.dry_run:
        print("\ndry run — nothing written")
        print(
            f"would emit {SEARCH_TERMS_FIXTURE.relative_to(REPO_ROOT)} "
            f"({len(present_rows)} present · {len(absent_rows)} absent)"
        )
    else:
        emit_search_terms_fixture(present_rows, absent_rows)
        print(f"\nwrote/updated {len(ordered)} sessions under {DEMO_SESSIONS}")
        print(
            f"wrote {SEARCH_TERMS_FIXTURE.relative_to(REPO_ROOT)} "
            f"({len(present_rows)} present · {len(absent_rows)} absent)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

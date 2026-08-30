"""Base class for session-store adapters.

An adapter knows two things about one coding agent:
  1. WHERE its .jsonl session transcripts live on disk
  2. HOW to discover them (walking the directory tree)

Everything else — record filtering, markdown rendering, redaction, state
tracking — is shared in `llmwiki.convert` and operates on the iterator this
class returns.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# #sec-7 (#551): project slugs flow into raw/ + site/ paths. The same
# sanitiser regex is used by build.py for project_slug rendering — keep
# them aligned. Anything outside [A-Za-z0-9._-] gets replaced with `_`,
# leading dots are stripped so the slug can't form a hidden directory.
_PROJECT_SLUG_RE = _re.compile(r"[^A-Za-z0-9._-]")


def _safe_project_slug(raw: str) -> str:
    """Drop path traversal + non-portable characters from a project slug."""
    s = _PROJECT_SLUG_RE.sub("_", raw)
    s = s.lstrip(".")
    return s or "unnamed"


def portable_session_key_fragment(path: Path) -> str:
    """Home-relative posix path for sync state keys, else ``str(path)``.

    Shared by ``SessionRef`` defaults and ``convert._portable_state_key`` so
    file-backed adapters keep stable ``adapter::rel`` keys across machines.
    """
    try:
        return Path(path).resolve().relative_to(Path.home()).as_posix()
    except (ValueError, OSError):
        return str(path)


@dataclass(frozen=True)
class SessionRef:
    """First-class session handle for file-backed or non-file (e.g. DB row) stores.

    ``key`` — portable identity fragment; sync state uses ``adapter::key``.
    ``mtime`` — unix seconds (file ``st_mtime`` or max row timestamp).
    ``locator`` — opaque string passed to ``load_records`` / ``derive_project_slug``
    (real filesystem path, or a logical locator such as ``cursor-ide:composer:<id>``).
    Never requires creating stub files on disk.
    """

    key: str
    mtime: float
    locator: str


@dataclass(frozen=True)
class SyncCandidateEstimate:
    """Cheap sync-size hint for ``configure-sources`` (#192).

    ``eligible`` — sessions that look convertible (adapter-defined).
    ``in_last_30_days`` — subset with activity on or after today UTC − 30 days.
    ``earliest`` — oldest activity/mtime among eligible sessions, if any.
    """

    eligible: int
    in_last_30_days: int
    earliest: datetime | None = None


def lookback_cutoff_ts(*, days: int = 30) -> float:
    """Unix timestamp for UTC midnight of (today UTC − ``days``)."""
    day = datetime.now(UTC).date() - timedelta(days=days)
    return datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()


class BaseAdapter:
    """Adapter interface.

    Subclasses must set `session_store_path` (a Path or list of Paths) and
    implement `is_available()`. The default `discover_sessions()` does a
    recursive glob for `*.jsonl`; override only if your agent uses a different
    extension or layout.
    """

    #: Unique adapter name (set by @register decorator).
    name: str = "base"

    #: Path or list of paths where this agent writes session transcripts.
    #: Subclasses MUST override.
    session_store_path: Path | list[Path] = Path("/dev/null")

    #: True if this adapter wraps an **AI coding-agent session store**
    #: (Claude Code, Codex CLI, Copilot, Cursor, Gemini, etc.).  False
    #: for adapters over user content (Obsidian vaults, Jira tickets,
    #: meeting transcripts, PDFs) — those are opt-in only so
    #: ``llmwiki sync`` never silently ingests non-session content.
    #: See #326.
    is_ai_session: bool = True

    #: False when the adapter registers for discovery but cannot convert
    #: sessions yet (scaffold / incomplete ingest). Bare ``sync`` / ``watch``
    #: skip ``ingest_ready=False``; ``--adapter`` still loads them. Ready
    #: sources (including Cursor IDE after #192) stay ``True`` so
    #: ``configure-sources`` Enable is enough for bare sync.
    ingest_ready: bool = True

    #: #arch-m9 (#621): canonical declaration on BaseAdapter so subclasses
    #: don't redeclare with format drift (`["v1"]` vs `["v1.0"]` vs
    #: `["1.x"]`). Default is ``["v1"]`` — the schema version the
    #: built-in adapters target. Subclasses that consume a different
    #: agent-native format override (or extend) this list.
    SUPPORTED_SCHEMA_VERSIONS: list[str] = ["v1"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    # ─── classmethods used by the registry + UI ────────────────────────

    # #py-l3 (#601): subclasses can override _DESCRIPTION_OVERRIDE so
    # `python3 -OO` (which strips __doc__) doesn't degrade the adapter
    # listing to bare class names. The default reads __doc__ where
    # available and falls back to a stable explicit string when not.
    _DESCRIPTION_OVERRIDE: str = ""

    @classmethod
    def description(cls) -> str:
        """One-line description shown in `llmwiki adapters`."""
        if cls._DESCRIPTION_OVERRIDE:
            return cls._DESCRIPTION_OVERRIDE
        if cls.__doc__:
            return cls.__doc__.split("\n")[0]
        return cls.__name__

    @classmethod
    def is_available(cls) -> bool:
        """True if the session store exists on this machine.

        #496: previously read ``cls.session_store_path`` directly. That
        worked for ``ClaudeCodeAdapter`` (class attribute) but returned
        the *property descriptor object* for the 8 contrib adapters
        which override ``session_store_path`` as a ``@property`` — so
        every contrib adapter had to re-implement its own
        ``is_available()`` classmethod reading ``cls.DEFAULT_ROOTS``.

        Fix: instantiate a config-less temp instance and read
        ``self.session_store_path`` through the same code path
        ``discover_sessions()`` uses. Both class-attribute and
        ``@property``-overriding patterns now flow through this single
        method; the 8 duplicate contrib overrides go away.

        Adapters with expensive ``__init__()`` should override this
        method directly, but no current adapter needs to.
        """
        try:
            inst = cls()
        except Exception:
            # Defensive: an adapter whose __init__ raises (e.g.
            # missing imports surfaced eagerly) is "unavailable" by
            # definition rather than crashing the whole `adapters`
            # listing.
            return False
        paths = inst.session_store_path
        if isinstance(paths, Path):
            paths = [paths]
        return any(Path(p).expanduser().exists() for p in paths)

    # ─── discovery ─────────────────────────────────────────────────────

    def discover_sessions(self) -> list[Path]:
        """Return a sorted list of all .jsonl files under the session store."""
        paths: list[Path] = []
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for store in stores:
            store = Path(store).expanduser()
            if store.exists():
                paths.extend(sorted(store.rglob("*.jsonl")))
        return paths

    def discover_session_refs(
        self, since_dt: datetime | None = None
    ) -> list[SessionRef]:
        """Preferred discovery entry for convert/watch (#2 SessionRef).

        Default wraps ``discover_sessions()`` with file ``st_mtime`` and a
        portable ``key`` fragment. Adapters whose sessions are DB rows (or
        other non-file stores) override this and may leave ``discover_sessions``
        unused by convert.

        ``since_dt`` is optional early lookback (#192). The default ignores it;
        ``convert_all`` still drops ``ref.mtime < since_dt`` before load.
        """
        del since_dt  # default: convert still mtime-prunes after discover
        out: list[SessionRef] = []
        for path in self.discover_sessions():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            out.append(
                SessionRef(
                    key=portable_session_key_fragment(path),
                    mtime=mtime,
                    locator=str(path),
                )
            )
        return out

    def estimate_sync_candidates(self) -> SyncCandidateEstimate:
        """Count candidates for the configure-sources lookback quiz (#192).

        Default: ``discover_session_refs()``; ``eligible`` is the full count;
        ``in_last_30_days`` counts refs with ``mtime >=`` today UTC − 30 days.

        Caveat: this path does **not** apply a headless peek — automated /
        empty sessions that only become obvious after ``load_records`` may
        still be counted. Adapters that can filter cheaply (e.g. Cursor IDE
        headers) override this method.
        """
        cutoff = lookback_cutoff_ts(days=30)
        refs = self.discover_session_refs()
        eligible = len(refs)
        in_window = sum(1 for ref in refs if ref.mtime >= cutoff)
        earliest: datetime | None = None
        if refs:
            earliest = datetime.fromtimestamp(min(ref.mtime for ref in refs), tz=UTC)
        return SyncCandidateEstimate(
            eligible=eligible,
            in_last_30_days=in_window,
            earliest=earliest,
        )

    # ─── per-agent helpers ─────────────────────────────────────────────

    def derive_project_slug(self, jsonl_path: Path | str) -> str:
        """Derive a friendly project slug from a .jsonl file path.

        Default: the immediate parent directory name under the store.
        Override for agents that use flat or encoded directory names.

        #sec-7 (#551): the returned slug is used downstream as a path
        component (`raw/sessions/<slug>-...md`, `site/projects/<slug>.html`).
        A user whose session store contains a directory named `..` or
        `foo/bar` could traverse out of `raw/` or smuggle a sub-path.
        Sanitise via the same regex rule the rest of the build uses.
        """
        jsonl_path = Path(jsonl_path)
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        raw = None
        for store in stores:
            store = Path(store).expanduser()
            try:
                rel = jsonl_path.relative_to(store)
                raw = rel.parts[0] if rel.parts else jsonl_path.parent.name
                break
            except ValueError:
                continue
        if raw is None:
            raw = jsonl_path.parent.name
        return _safe_project_slug(raw)

    def is_subagent(self, jsonl_path: Path | str) -> bool:
        """Default: no adapter has a sub-agent concept — only Claude Code does
        (#406). Subclasses that DO have sub-agents (currently only the
        Claude Code adapter) override this method.

        Why the default returned True for any path containing the substring
        "subagent": that was a holdover from a Claude-specific assumption
        when the adapter abstraction was introduced. It mis-tagged every
        session in any user project named e.g. ``subagent-runner``,
        demoting them on the project page and excluding them from session
        counts. Subclassing fixes the bug at the source.
        """
        return False

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """True if this session is a non-interactive / automated launch (#180).

        Concrete adapters must override. Default returns False (not headless)
        so interactive / unmarked sessions stay eligible. Claude Code maps
        ``entrypoint`` / ``promptSource`` SDK markers; Cursor Agent CLI and
        others add store-specific rules in their overrides.
        """
        return False

    def load_records(self, path: Path | str) -> list[dict[str, Any]]:
        """Load raw records from one discovered session path or locator.

        Default: parse the path as line-delimited JSON (``parse_jsonl``) — the
        format every built-in coding-agent store uses. Adapters whose store is
        NOT line-delimited JSON (e.g. an SQLite content-addressed blob store
        like the Cursor CLI's ``store.db``, or IDE DB-row locators) override
        this to return records in the same raw shape ``parse_jsonl`` would,
        *before* ``normalize_records`` translates them into the shared
        Claude-style schema.

        Called by ``convert.convert_all`` instead of calling ``parse_jsonl``
        directly, so non-JSONL session stores plug in without the renderer or
        the main loop knowing about their on-disk format.

        The import is local to avoid a circular import (``convert`` imports the
        adapter registry at module load).
        """
        from llmwiki.convert import parse_jsonl  # noqa: PLC0415 — cycle: adapters↔convert

        return parse_jsonl(Path(path))

    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize agent-specific JSONL records into the shared Claude-style
        format that ``llmwiki.convert`` expects.

        The shared renderer expects records shaped as:
        - ``{"type": "user", "message": {"role": "user", "content": "..."}}``
        - ``{"type": "assistant", "message": {"role": "assistant", "content": [...]}}``

        The default implementation is a no-op (pass-through) — Claude Code
        sessions already use this format. Adapters for agents with a different
        schema (e.g. Codex CLI, Copilot) override this method to translate
        their native records into the shared shape.

        Called by ``convert.py`` after ``parse_jsonl()`` and before the
        renderer, so the normalization is transparent to the rest of the
        pipeline.
        """
        return records

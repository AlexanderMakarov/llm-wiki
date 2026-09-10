"""Claude Code session-store adapter.

Claude Code writes one .jsonl per session under:
    ~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl

Sub-agent runs live in:
    ~/.claude/projects/<project-dir-slug>/<session-uuid>/subagents/agent-*.jsonl

Project directory names encode the full absolute path with slashes replaced by
dashes, e.g. '-Users-USER-Desktop-2026-production-draft-ai-newsletter'.
We strip the common prefix to produce a friendly slug.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter
from llmwiki.slugs import project_slug_from_encoded_dir

# Headless `claude -p` / Agent-SDK runs (#8 / #180). Match the `sdk-`
# entrypoint *prefix* so a future SDK runtime (sdk-go, …) is caught
# without a code change; promptSource is the belt-and-suspenders signal.
_HEADLESS_ENTRYPOINT_PREFIX = "sdk-"
_HEADLESS_PROMPT_SOURCES = frozenset({"sdk"})


@register("claude_code")
class ClaudeCodeAdapter(BaseAdapter):
    """Claude Code — reads ~/.claude/projects/*/*.jsonl"""

    # Cross-platform: dot-dir works on macOS, Linux, and Windows
    session_store_path = Path.home() / ".claude" / "projects"

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """True if any record marks this as a headless `claude -p` / SDK run."""
        for r in records:
            entrypoint = r.get("entrypoint")
            if isinstance(entrypoint, str) and entrypoint.startswith(
                _HEADLESS_ENTRYPOINT_PREFIX
            ):
                return True
            if r.get("promptSource") in _HEADLESS_PROMPT_SOURCES:
                return True
        return False

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """Strip the '-Users-...-production-draft-' prefix from the project dir name.

        Shares ``slugs.project_slug_from_encoded_dir`` with MCP caller
        attribution (#51) so a project gets the same slug whether it was
        reached through ingestion or through telemetry."""
        store = Path(self.session_store_path).expanduser()
        try:
            rel = jsonl_path.relative_to(store)
        except ValueError:
            return jsonl_path.parent.name
        if not rel.parts:
            return jsonl_path.parent.name
        return project_slug_from_encoded_dir(rel.parts[0])

    def is_subagent(self, jsonl_path: Path) -> bool:
        """Detect Claude Code sub-agent runs by canonical path layout (#406).

        Claude Code stores sub-agent runs at:
            ~/.claude/projects/<project>/<session-uuid>/subagents/agent-*.jsonl

        Old heuristic was a substring check on ``"subagent" in path.parts``,
        which mis-tagged any user project named e.g. ``subagent-runner`` —
        every session in such a project was demoted to sub-agent on the
        project page and excluded from session counts.

        New rule: the file MUST live in a directory literally named
        ``subagents`` (plural) AND have a filename starting with
        ``agent-``. Both conditions match the canonical Claude layout
        and exclude every false-positive case (project name "subagent",
        "subagent-runner", "agent-subagent-helper", etc.).
        """
        parts = jsonl_path.parts
        if "subagents" not in parts:
            return False
        # The 'subagents' segment must be the immediate parent directory.
        try:
            parent_idx = parts.index("subagents")
        except ValueError:
            return False
        if parent_idx >= len(parts) - 1:
            return False
        # And the filename must start with 'agent-' (the canonical pattern).
        return parts[-1].startswith("agent-")

    def assigned_session_name(
        self, path: Path | str, records: list[dict[str, Any]]
    ) -> str | None:
        """Prefer ``custom-title.json`` ``customTitle``, else jsonl ``ai-title`` (#249).

        Sidecar layouts observed on disk:
        - ``<uuid>.jsonl`` with sibling dir ``<uuid>/custom-title.json``
        - ``custom-title.json`` next to the session jsonl
        """
        jsonl = Path(path)
        for sidecar in (
            jsonl.parent / jsonl.stem / "custom-title.json",
            jsonl.with_name("custom-title.json"),
        ):
            title = _read_custom_title(sidecar)
            if title:
                return title
        for r in records:
            if not isinstance(r, dict) or r.get("type") != "ai-title":
                continue
            ai = r.get("aiTitle")
            if isinstance(ai, str) and ai.strip():
                return ai.strip()
        return None

    def normalize_user_prompt(self, text: str) -> str:
        """Collapse Claude Code control XML to ``/cmd`` / prose (#249 / #229)."""
        # Local import: adapters ↔ convert cycle (same pattern as load_records).
        from llmwiki.convert import (  # noqa: PLC0415
            normalize_claude_control_content,
        )

        return normalize_claude_control_content(text)


def _read_custom_title(sidecar: Path) -> str | None:
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    title = data.get("customTitle")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None

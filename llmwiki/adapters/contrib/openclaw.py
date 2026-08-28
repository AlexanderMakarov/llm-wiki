"""OpenClaw session-store adapter.

OpenClaw (https://openclaw.ai) is a TypeScript AI-agent gateway. Each agent
writes one transcript per session under:

    ~/.openclaw/agents/<agent>/sessions/<session-uuid>.jsonl

Alongside each transcript it writes ``<uuid>.trajectory.jsonl`` and
``<uuid>.trajectory-path.json`` (tool-execution traces, 2026.6.1+); those are
NOT conversation transcripts and are skipped here. Some deployments also mirror
sessions into a vault inbox at ``<vault>/.openclaw-sessions-inbox/<agent>/<uuid>.jsonl``
(no ``sessions/`` segment) — a periodic checkpoint sidecar
(``<uuid>.checkpoint.<n>.jsonl``) and a ``_quarantine/`` dir for
failed/rejected mirrors can also appear there, and neither is a conversation
transcript either.

Session roots are configurable via ``config.json``::

    {"adapters": {"openclaw": {"roots": ["/path/to/.openclaw-sessions-inbox"]}}}

When no ``roots`` are configured, the adapter falls back to the default
``~/.openclaw/agents`` layout.

On-disk record shape (one JSON object per line)::

    {"type": "session", "version": ..., "id": ..., "cwd": ...}          # header
    {"type": "model_change", ...}                                        # control
    {"type": "message", "id": ..., "parentId": ..., "timestamp": ...,
     "message": {"role": "user"|"assistant", "content": [...], ...}}     # turn

Only ``type == "message"`` records carry conversation content. Their nested
``message`` block is Anthropic-shaped (``content`` is a list of typed blocks
for assistants; for users it is also a list, which we flatten to a string so
the shared renderer — which expects a string user prompt — keeps it verbatim).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter
from llmwiki.adapters.settings import adapter_block


def _flatten_text_blocks(content: Any) -> str:
    """Join the ``text`` of every text block in an Anthropic-style content list.

    OpenClaw stores even user messages as ``[{"type": "text", "text": "..."}]``.
    The shared ``render_user_prompt`` only renders string content, so user
    prompts must be flattened or they render empty. Non-text blocks are dropped
    (user turns are text in practice).
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts)


def _is_non_transcript(path: Path) -> bool:
    """True for sidecar/control files that are not conversation transcripts.

    - ``*.trajectory.jsonl`` — tool-execution traces (2026.6.1+).
    - ``*.checkpoint.<n>.jsonl`` — periodic checkpoint sidecars written
      alongside the live transcript by the vault-inbox mirror.
    - anything under a ``_quarantine/`` directory — mirrored sessions that
      failed validation and were set aside rather than accepted.
    """
    name = path.name
    if name.endswith(".trajectory.jsonl"):
        return True
    if ".checkpoint." in name and name.endswith(".jsonl"):
        return True
    if "_quarantine" in path.parts:
        return True
    return False


@register("openclaw")
class OpenClawAdapter(BaseAdapter):
    """OpenClaw — reads configured roots (default ~/.openclaw/agents; skips non-transcripts)."""

    is_ai_session = True

    # Default store root; discover_sessions() narrows to <agent>/sessions/*.jsonl.
    DEFAULT_ROOTS = [Path.home() / ".openclaw" / "agents"]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = adapter_block(config or {}, "openclaw")
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    # #496: is_available() inherited from BaseAdapter — temp instance
    # reads self.session_store_path (returns self.roots = DEFAULT_ROOTS
    # when no config override).

    def discover_sessions(self) -> list[Path]:
        """Find every conversation transcript under every configured root.

        Layout is either ``<agent>/sessions/<uuid>.jsonl`` (default install)
        or ``<agent>/<uuid>.jsonl`` (vault inbox mirror). Sidecar/control
        files (trajectories, checkpoints, quarantined mirrors) are filtered
        out via ``_is_non_transcript``.
        """
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            out.extend(
                p for p in sorted(root.rglob("*.jsonl")) if not _is_non_transcript(p)
            )
        return out

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """Use the agent directory name (e.g. 'main') as the project slug."""
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = jsonl_path.relative_to(root)
            except ValueError:
                continue
            agent = rel.parts[0] if rel.parts else jsonl_path.parent.name
            return f"openclaw-{agent}"
        return jsonl_path.parent.name

    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Translate OpenClaw typed records into the shared Claude-style schema.

        Keep only ``type == "message"`` records; re-key by the inner role
        (``{"type": "user"|"assistant", "message": {...}}``) and flatten user
        content to a string so the shared renderer keeps the prompt verbatim.
        Control records (session/model_change/thinking_level_change/custom) are
        dropped — they carry no conversation content.
        """
        out: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict) or rec.get("type") != "message":
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            new_msg = dict(msg)
            if role == "user":
                new_msg["content"] = _flatten_text_blocks(msg.get("content"))
            out.append(
                {
                    "type": role,
                    "uuid": rec.get("id"),
                    "parentUuid": rec.get("parentId"),
                    "timestamp": rec.get("timestamp"),
                    "message": new_msg,
                }
            )
        return out

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """Always False — all OpenClaw session-store transcripts are kept (#180).

        Dreaming / background artifacts live outside the session store, so
        they never appear in these records and need no headless filter here.
        """
        return False

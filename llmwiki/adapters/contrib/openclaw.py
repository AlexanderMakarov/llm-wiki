"""OpenClaw session-store adapter.

OpenClaw (https://openclaw.ai) is a TypeScript AI-agent gateway. Each agent
writes one transcript per session under:

    ~/.openclaw/agents/<agent>/sessions/<session-uuid>.jsonl

Alongside each transcript it writes ``<uuid>.trajectory.jsonl`` and
``<uuid>.trajectory-path.json`` (tool-execution traces, 2026.6.1+); those are
NOT conversation transcripts and are skipped here.

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


@register("openclaw")
class OpenClawAdapter(BaseAdapter):
    """OpenClaw — reads ~/.openclaw/agents/*/sessions/*.jsonl (skips trajectories)"""

    is_ai_session = True

    # The store root; discover_sessions() narrows to <agent>/sessions/*.jsonl.
    session_store_path = Path.home() / ".openclaw" / "agents"

    def discover_sessions(self) -> list[Path]:
        """Find every conversation transcript, excluding trajectory sidecars.

        Layout is ``<agent>/sessions/<uuid>.jsonl``; ``*.trajectory.jsonl`` are
        tool-execution traces, not transcripts, and are filtered out.
        """
        store = Path(self.session_store_path).expanduser()
        if not store.exists():
            return []
        return sorted(
            p
            for p in store.rglob("*.jsonl")
            if not p.name.endswith(".trajectory.jsonl")
        )

    def derive_project_slug(self, jsonl_path: Path) -> str:
        """Use the agent directory name (e.g. 'main') as the project slug."""
        store = Path(self.session_store_path).expanduser()
        try:
            rel = jsonl_path.relative_to(store)
        except ValueError:
            return jsonl_path.parent.name
        agent = rel.parts[0] if rel.parts else jsonl_path.parent.name
        return f"openclaw-{agent}"

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

"""Session readiness — is it safe to run background automation right now? (PR2)

Automation profiles (``llmwiki.automation_install``) run ``llmwiki sync`` /
``synthesize`` / ``build`` on a schedule, or from an agent-startup hook.
Running sync while a coding agent is mid-tool-call — waiting on a shell
command, an edit, a subagent — risks reading a half-written transcript or
racing the very session it's about to summarize. These pure, stdlib
functions classify the *last turn* of a session transcript into one of
three buckets so a caller can decide whether to proceed:

- ``SAFE``        — the agent's turn ended cleanly; nothing pending.
- ``UNSAFE``      — a tool call or an unanswered user turn is in flight;
  skip this automation run.
- ``UNSUPPORTED`` — the records don't carry enough signal to tell (empty,
  malformed, or missing the fields this adapter's schema would normally
  have). Callers should treat this the same as ``UNSAFE`` — fail closed
  rather than guess — unless they have a better source of truth.

No I/O here: every function takes already-parsed records/messages (the
same in-memory shape ``llmwiki.convert``/the adapters already produce) so
this stays trivially unit-testable and reusable from the CLI, the MCP
server, and the automation hooks alike.
"""

from __future__ import annotations

import enum
from typing import Any


class SessionReadiness(enum.Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNSUPPORTED = "unsupported"


# Alias used by ``llmwiki.watch`` and tests.
Ready = SessionReadiness

# Claude message `stop_reason` values that mean the assistant's turn ended
# on its own, without a further tool call or a forced cutoff.
_CLAUDE_SAFE_STOP_REASONS = frozenset({"end_turn", "stop_sequence"})

# Content block types that mean a tool call is still in flight (Claude
# `tool_use`, Cursor CLI raw `tool-call`).
_TOOL_BLOCK_TYPES = frozenset({"tool_use", "tool-call"})


def _content_has_tool_use(content: Any) -> bool | None:
    """Return True/False for a content list, or None if ``content`` isn't a list."""
    if not isinstance(content, list):
        return None
    return any(
        isinstance(b, dict) and b.get("type") in _TOOL_BLOCK_TYPES for b in content
    )


def _last_record_of_type(records: list[Any], record_type: str) -> dict[str, Any] | None:
    for rec in reversed(records):
        if isinstance(rec, dict) and rec.get("type") == record_type:
            return rec
    return None


def _is_unanswered_user_prompt(records: list[Any]) -> bool:
    """True iff the very last record is a genuine (non-tool-result) user prompt.

    A trailing user turn with no assistant reply after it yet means the
    session may currently be mid-turn even though the *last assistant*
    message on its own looked clean — the "awaiting" half of the unsafe
    bucket described in the module docstring.
    """
    if not records:
        return False
    last = records[-1]
    if not isinstance(last, dict) or last.get("type") != "user":
        return False
    message = last.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return isinstance(content, str)


def claude_session_ready(records: list[dict[str, Any]]) -> SessionReadiness:
    """Classify a Claude Code transcript's readiness for background automation.

    Looks at the last ``type: "assistant"`` record. A ``tool_use`` block
    in its content means the turn is still in flight (``UNSAFE``);
    otherwise the message's ``stop_reason`` decides — ``end_turn`` or
    ``stop_sequence`` is ``SAFE``, any other recorded reason (e.g.
    ``max_tokens``, the API's own ``tool_use`` reason) is ``UNSAFE``. A
    trailing, unanswered user prompt after the last assistant turn is
    also ``UNSAFE`` — the session may be about to resume. Missing or
    malformed data (no assistant record, no ``message`` dict, absent
    ``stop_reason``) returns ``UNSUPPORTED`` rather than guessing.
    """
    if not records:
        return SessionReadiness.UNSUPPORTED

    last_assistant = _last_record_of_type(records, "assistant")
    if last_assistant is None:
        # A lone unanswered user prompt is mid-turn (awaiting the agent).
        if _is_unanswered_user_prompt(records):
            return SessionReadiness.UNSAFE
        return SessionReadiness.UNSUPPORTED

    message = last_assistant.get("message")
    if not isinstance(message, dict):
        return SessionReadiness.UNSUPPORTED

    has_tool_use = _content_has_tool_use(message.get("content"))
    if has_tool_use is None:
        return SessionReadiness.UNSUPPORTED
    if has_tool_use:
        return SessionReadiness.UNSAFE

    if _is_unanswered_user_prompt(records):
        return SessionReadiness.UNSAFE

    stop_reason = message.get("stop_reason")
    if stop_reason is None:
        return SessionReadiness.UNSUPPORTED
    if stop_reason in _CLAUDE_SAFE_STOP_REASONS:
        return SessionReadiness.SAFE
    return SessionReadiness.UNSAFE


def codex_session_ready(records: list[dict[str, Any]]) -> SessionReadiness:
    """Classify a Codex CLI transcript's readiness for background automation.

    Codex's normalized records (``llmwiki.adapters.codex_cli.normalize_records``)
    share Claude's ``{"type": "assistant", "message": {"content": [...]}}``
    shape but never carry a ``stop_reason``, so this checks structure
    only: a ``tool_use`` block in the last assistant message is
    ``UNSAFE``; a non-empty, tool-free message is ``SAFE``; anything else
    (no assistant record, empty/malformed content) is ``UNSUPPORTED``.
    """
    if not records:
        return SessionReadiness.UNSUPPORTED

    last_assistant = _last_record_of_type(records, "assistant")
    if last_assistant is None:
        return SessionReadiness.UNSUPPORTED

    message = last_assistant.get("message")
    if not isinstance(message, dict):
        return SessionReadiness.UNSUPPORTED

    content = message.get("content")
    has_tool_use = _content_has_tool_use(content)
    if has_tool_use is None:
        return SessionReadiness.UNSUPPORTED
    if has_tool_use:
        return SessionReadiness.UNSAFE
    if not content:
        return SessionReadiness.UNSUPPORTED

    if _is_unanswered_user_prompt(records):
        return SessionReadiness.UNSAFE

    return SessionReadiness.SAFE


def cursor_session_ready(raw_messages: list[dict[str, Any]]) -> SessionReadiness:
    """Classify a Cursor agent transcript's readiness for background automation.

    Accepts Cursor CLI raw messages (``role`` + ``content`` blocks with
    ``tool-call``) and the OpenAI-ish shape (``tool_calls`` / ``toolCalls``).
    A last assistant message carrying pending tool calls is ``UNSAFE``;
    plain text with nothing pending — and no unanswered trailing user turn —
    is ``SAFE``. Normalized Claude-shaped records (``type: assistant``) are
    also accepted when callers pass adapter ``load_records`` output.
    """
    if not raw_messages:
        return SessionReadiness.UNSUPPORTED

    # Normalized Claude-shaped path (cursor_cli.normalize_records).
    if any(isinstance(m, dict) and m.get("type") in ("assistant", "user") for m in raw_messages):
        return _cursor_from_normalized(raw_messages)

    last_assistant: dict[str, Any] | None = None
    for msg in reversed(raw_messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            last_assistant = msg
            break
    if last_assistant is None:
        last = raw_messages[-1]
        if isinstance(last, dict) and last.get("role") == "user":
            return SessionReadiness.UNSAFE
        return SessionReadiness.UNSUPPORTED

    tool_calls = last_assistant.get("tool_calls") or last_assistant.get("toolCalls")
    if tool_calls:
        return SessionReadiness.UNSAFE

    content = last_assistant.get("content")
    if content is None:
        return SessionReadiness.UNSUPPORTED
    has_tool = _content_has_tool_use(content)
    if has_tool is True:
        return SessionReadiness.UNSAFE
    # String content or list without tool blocks is fine; empty list → unsupported.
    if isinstance(content, list) and not content:
        return SessionReadiness.UNSUPPORTED
    if isinstance(content, str) and not content.strip():
        return SessionReadiness.UNSUPPORTED

    last = raw_messages[-1]
    if isinstance(last, dict) and last.get("role") == "user":
        return SessionReadiness.UNSAFE

    return SessionReadiness.SAFE


def _cursor_from_normalized(records: list[dict[str, Any]]) -> SessionReadiness:
    """Cursor CLI after normalize_records: Claude shape, no stop_reason."""
    return codex_session_ready(records)


def session_ready_for_adapter(
    adapter_name: str,
    *,
    records: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> SessionReadiness:
    """Dispatch readiness for a named adapter (watch / automation)."""
    name = (adapter_name or "").lower().replace("-", "_")
    recs = records or []
    msgs = messages or []
    if name in ("claude_code", "claude", "openclaw"):
        return claude_session_ready(recs)
    if name.startswith("cursor"):
        return cursor_session_ready(msgs or recs)
    if name in ("codex_cli", "codex"):
        return codex_session_ready(recs)
    return SessionReadiness.UNSUPPORTED

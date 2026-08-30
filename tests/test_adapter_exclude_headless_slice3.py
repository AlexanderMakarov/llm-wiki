"""Per-adapter ``is_headless_session`` rules for #180 Slice 3.

Research (in-repo fixtures + local stores on this host) found no verified
automation / nested-agent / second-model markers for these adapters, so each
method returns False. Claude Code and Cursor Agent CLI are covered elsewhere.
"""

from __future__ import annotations

import pytest

from llmwiki.adapters.codex_cli import CodexCliAdapter
from llmwiki.adapters.contrib.chatgpt import ChatGPTAdapter
from llmwiki.adapters.contrib.copilot_chat import CopilotChatAdapter
from llmwiki.adapters.contrib.copilot_cli import CopilotCliAdapter
from llmwiki.adapters.contrib.cursor_ide import CursorAdapter
from llmwiki.adapters.contrib.gemini_cli import GeminiCliAdapter
from llmwiki.adapters.contrib.obsidian import ObsidianAdapter
from llmwiki.adapters.contrib.openclaw import OpenClawAdapter
from llmwiki.adapters.contrib.opencode import OpenCodeAdapter

# Slice 3 adapters: False until verified store markers exist (or N/A).
_SLICE3 = (
    ("codex_cli", CodexCliAdapter),
    ("opencode", OpenCodeAdapter),
    ("openclaw", OpenClawAdapter),
    ("copilot_cli", CopilotCliAdapter),
    ("copilot_chat", CopilotChatAdapter),
    ("chatgpt", ChatGPTAdapter),
    ("gemini_cli", GeminiCliAdapter),
    ("cursor_ide", CursorAdapter),
    ("obsidian", ObsidianAdapter),
)


@pytest.mark.parametrize("name,cls", _SLICE3, ids=[n for n, _ in _SLICE3])
def test_slice3_empty_records_not_headless(name: str, cls: type) -> None:
    assert cls().is_headless_session([]) is False


@pytest.mark.parametrize("name,cls", _SLICE3, ids=[n for n, _ in _SLICE3])
def test_slice3_interactive_shaped_records_not_headless(name: str, cls: type) -> None:
    """Claude/Cursor launch fields must not silently reclassify other adapters."""
    records = [
        {
            "type": "user",
            "entrypoint": "sdk-cli",
            "promptSource": "sdk",
            "approvalMode": "auto-review",
            "subagentInfo": {"typeName": "code-reviewer"},
            "message": {"role": "user", "content": "hello"},
        },
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
        },
    ]
    assert cls().is_headless_session(records) is False


def test_codex_normalized_session_meta_shape_not_headless() -> None:
    """Codex normalize emits init from session_meta; still not headless."""
    records = [
        {"type": "init", "sessionId": "abc", "cwd": "/tmp/proj"},
        {"type": "user", "message": {"role": "user", "content": "ship it"}},
    ]
    assert CodexCliAdapter().is_headless_session(records) is False


def test_opencode_message_records_not_headless() -> None:
    records = [
        {"type": "user", "message": {"role": "user", "content": "refactor"}},
        {"type": "assistant", "message": {"role": "assistant", "content": "ok"}},
    ]
    assert OpenCodeAdapter().is_headless_session(records) is False


def test_openclaw_always_false_including_session_header() -> None:
    """OpenClaw rule: every session-store transcript is eligible (#180 R3)."""
    records = [
        {"type": "session", "id": "s1", "cwd": "/vault"},
        {
            "type": "message",
            "message": {"role": "user", "content": "dreaming is a background mode"},
        },
        {
            "type": "user",
            "message": {"role": "user", "content": "ordinary chat"},
        },
    ]
    assert OpenClawAdapter().is_headless_session(records) is False
    assert OpenClawAdapter().is_headless_session([]) is False


def test_copilot_cli_init_event_not_headless() -> None:
    assert CopilotCliAdapter().is_headless_session([{"type": "init"}]) is False


def test_copilot_chat_records_not_headless() -> None:
    records = [{"type": "user", "message": {"role": "user", "content": "explain"}}]
    assert CopilotChatAdapter().is_headless_session(records) is False


def test_chatgpt_export_records_not_headless() -> None:
    """R4: ChatGPT export — automated-launch detection N/A."""
    records = [
        {
            "type": "user",
            "message": {"role": "user", "content": "from export"},
        }
    ]
    assert ChatGPTAdapter().is_headless_session(records) is False


def test_gemini_cli_scaffold_not_headless() -> None:
    assert GeminiCliAdapter().is_headless_session(
        [{"type": "user", "message": {"role": "user", "content": "q"}}]
    ) is False


def test_cursor_ide_subagent_is_headless() -> None:
    """IDE spawned agents: composerHeaders.isSubagent → headless (#2)."""
    assert CursorAdapter().is_headless_session([{"isSubagent": True}]) is True
    assert CursorAdapter().is_headless_session(
        [
            {
                "type": "user",
                "approvalMode": "auto-review",
                "subagentInfo": {"typeName": "x"},
            }
        ]
    ) is False


def test_obsidian_notes_not_headless() -> None:
    """R4: Obsidian notes intake — automated-launch detection N/A."""
    assert ObsidianAdapter().is_headless_session(
        [{"type": "markdown", "body": "# Note\n\nHand-written."}]
    ) is False

"""Tests for session_ready turn-complete heuristics."""

from __future__ import annotations

from llmwiki.session_ready import (
    Ready,
    claude_session_ready,
    codex_session_ready,
    cursor_session_ready,
)


def test_claude_end_turn_safe():
    records = [
        {"type": "user", "timestamp": "t1", "message": {"content": "hi"}},
        {
            "type": "assistant",
            "timestamp": "t2",
            "message": {
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hello"}],
            },
        },
        {"type": "last-prompt"},
    ]
    assert claude_session_ready(records) == Ready.SAFE


def test_claude_tool_use_unsafe():
    records = [
        {
            "type": "assistant",
            "timestamp": "t1",
            "message": {
                "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "id": "1", "name": "Bash"}],
            },
        },
    ]
    assert claude_session_ready(records) == Ready.UNSAFE


def test_claude_awaiting_user_unsafe():
    records = [
        {"type": "user", "timestamp": "t1", "message": {"content": "go"}},
    ]
    assert claude_session_ready(records) == Ready.UNSAFE


def test_cursor_text_complete_safe():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "done"}]},
    ]
    assert cursor_session_ready(messages) == Ready.SAFE


def test_cursor_tool_call_unsafe():
    messages = [
        {
            "role": "assistant",
            "content": [{"type": "tool-call", "name": "Shell"}],
        },
    ]
    assert cursor_session_ready(messages) == Ready.UNSAFE


def test_codex_empty_unsupported():
    assert codex_session_ready([]) == Ready.UNSUPPORTED

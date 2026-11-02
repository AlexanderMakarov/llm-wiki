"""Seven-day session/token pace card (#321)."""

from __future__ import annotations

from datetime import date

from llmwiki.viz_tokens import compute_seven_day_pace, last_n_calendar_days


def test_last_n_calendar_days_inclusive_end():
    end = date(2026, 11, 1)
    assert last_n_calendar_days(3, end=end) == ["2026-10-30", "2026-10-31", "2026-11-01"]


def test_compute_seven_day_pace_averages():
    window = last_n_calendar_days(7)
    metas = {
        "p": [
            {"date": window[0]},
            {"date": window[0]},
            {"date": window[-1]},
        ],
    }
    usage = {
        "days": {
            window[0]: {"claude_code": {"sum": 1000}},
            window[-1]: {"claude_code": {"sum": 6000}},
        },
    }
    avg_sessions, avg_tokens, avg_tps = compute_seven_day_pace(metas, usage, days=7)
    assert avg_sessions == 3 / 7.0
    assert avg_tokens == 7000 / 7.0
    assert avg_tps == 7000 / 3.0

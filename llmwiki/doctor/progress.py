"""Stage progress lines for long doctor runs (stderr, flushed)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TextIO

ProgressFn = Callable[[str], None]


def make_progress(stream: TextIO | None = None) -> ProgressFn:
    """Return a progress printer: ``doctor: <stage>...`` on ``stream`` (stderr)."""
    out = stream if stream is not None else sys.stderr

    def _progress(stage: str) -> None:
        text = stage.strip()
        if not text.endswith("..."):
            text = f"{text}..."
        print(f"doctor: {text}", file=out, flush=True)

    return _progress


def noop_progress(_stage: str) -> None:
    """Silent progress (tests)."""

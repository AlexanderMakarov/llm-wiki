"""Synchronous synthesis via Cursor's Agent CLI (`agent -p`).

Selectable with ``"synthesis": {"backend": "cursor_cli"}``. Settings live
under the nested ``synthesis.cursor_cli`` block (``model``, ``timeout``).
There is no user-facing binary-path key — llmwiki resolves ``agent`` (then
``cursor-agent``) from ``$PATH`` so the operator's normal session login
applies.

Default model is the cheapest Composer id Agent CLI lists
(``composer-2.5``). Lean invocation: ``-p``, ``--mode ask``,
``--sandbox enabled``, ``--model``, ``--output-format text``.

Prompt delivery: Agent CLI accepts a positional prompt *or* stdin when no
prompt argv is given (verified). Prefer stdin so long pages stay under
OS argv limits; body still capped at 8 KB like Claude / Ollama.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from llmwiki.synth.base import BaseSynthesizer, split_prompt_template
from llmwiki.synth.ollama import _render_prompt

DEFAULT_CURSOR_MODEL = "composer-2.5"
DEFAULT_CURSOR_TIMEOUT = 180

# Same 8 KB body cap as Claude / Ollama / agent-delegate.
_BODY_CHAR_CAP = 8000

# Tiny live probe for ``is_available`` / ``synth --check``. Agent CLI is
# slower than an HTTP tags ping, so this is longer than Ollama's 2s but
# still well under the per-page timeout.
_PROBE_TIMEOUT = 30
_PROBE_PROMPT = "Reply with exactly: OK"

# Prefer stdin (no positional prompt). Flip only if a future Agent CLI
# build stops reading stdin when argv has no prompt.
_PROMPT_VIA_STDIN = True

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CursorCLIConfig:
    """Resolved configuration for :class:`CursorCLISynthesizer`."""

    model: str = DEFAULT_CURSOR_MODEL
    timeout: int = DEFAULT_CURSOR_TIMEOUT


def load_cursor_cli_config(cfg: dict[str, Any] | None) -> CursorCLIConfig:
    """Build a :class:`CursorCLIConfig` from ``synthesis.cursor_cli``.

    Missing keys fall back to module defaults. No flat-key fallback —
    this backend is new and has no legacy flat namespace.
    """
    synth = (cfg or {}).get("synthesis", {}) or {}
    nested = synth.get("cursor_cli") or {}
    if not isinstance(nested, dict):
        nested = {}

    model = nested.get("model") or DEFAULT_CURSOR_MODEL
    timeout = (
        int(nested["timeout"])
        if "timeout" in nested and nested["timeout"]
        else DEFAULT_CURSOR_TIMEOUT
    )
    return CursorCLIConfig(model=str(model), timeout=timeout)


def resolve_cursor_agent_path() -> str | None:
    """Locate the Cursor Agent CLI on ``$PATH`` (no config override).

    Prefers ``agent``, then ``cursor-agent``. Returns ``None`` when neither
    is found.
    """
    return shutil.which("agent") or shutil.which("cursor-agent")


def lean_argv(agent: str, *, model: str | None = None) -> list[str]:
    """Build a non-interactive Agent CLI command line for one-shot text.

    Closest documented lean set: print mode, ask (read-only), sandbox on.
    Does not pass ``--force`` / ``--yolo`` / ``--approve-mcps`` / ``--worktree``.
    """
    argv = [
        agent,
        "-p",
        "--mode",
        "ask",
        "--sandbox",
        "enabled",
    ]
    if model:
        argv += ["--model", model]
    argv += ["--output-format", "text"]
    return argv


class CursorCLIError(RuntimeError):
    """One page failed to synthesize via the Cursor Agent CLI."""


class CursorCLISynthesizer(BaseSynthesizer):
    """Shell out to ``agent -p`` once per page. No pending files, no HTTP."""

    def __init__(
        self,
        model: str | None = None,
        timeout: int = DEFAULT_CURSOR_TIMEOUT,
    ) -> None:
        self.model = model or DEFAULT_CURSOR_MODEL
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "cursor-cli"

    def _argv(self, agent: str) -> list[str]:
        """Build the Agent CLI command line for one page."""
        return lean_argv(agent, model=self.model)

    def _run_agent(
        self,
        agent: str,
        prompt: str,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        """Invoke Agent CLI once; prefer stdin when supported."""
        argv = self._argv(agent)
        if _PROMPT_VIA_STDIN:
            return subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        # Argv fallback: same body cap already applied by the caller.
        return subprocess.run(
            argv + [prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_prompt(self, prompt: str, *, timeout: float | None = None) -> str:
        """One-shot text completion via Agent CLI (shared by page synth + overview).

        Raises :class:`CursorCLIError` on missing binary, timeout, nonzero
        exit, or empty stdout.
        """
        agent = resolve_cursor_agent_path()
        if agent is None:
            raise CursorCLIError(
                "Cursor Agent CLI not found — install `agent` (or "
                "`cursor-agent`) on $PATH, or configure "
                "synthesis.backend=ollama / claude / dummy"
            )
        limit = float(self.timeout if timeout is None else timeout)
        try:
            result = self._run_agent(agent, prompt, timeout=limit)
        except subprocess.TimeoutExpired as exc:
            raise CursorCLIError(
                f"Cursor Agent CLI timed out after {int(limit)}s"
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise CursorCLIError(
                f"Cursor Agent CLI failed to run: {exc}"
            ) from exc
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else "no output"
            raise CursorCLIError(
                f"Cursor Agent CLI exited {result.returncode}: {detail}"
            )
        text = (result.stdout or "").strip()
        if not text:
            raise CursorCLIError("Cursor Agent CLI returned an empty completion")
        return text

    def is_available(self) -> bool:
        """True when ``agent`` is on ``$PATH`` and answers a tiny probe.

        PATH alone is not enough (R5): auth / model / hang failures must
        make ``synth --check`` fail. Probe never raises — returns False.
        """
        probe_timeout = min(float(self.timeout), float(_PROBE_TIMEOUT))
        try:
            return bool(
                self.run_prompt(_PROBE_PROMPT, timeout=probe_timeout).strip()
            )
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            logger.debug("Cursor Agent CLI availability probe failed: %s", exc)
            return False

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        truncated_body = raw_body[:_BODY_CHAR_CAP] if raw_body else ""
        # Cursor Agent CLI has no documented ``--system-prompt`` channel
        # (unlike ``claude -p``), but Cursor *does* bill prompt-cache
        # read/write at the provider layer. Put the run-stable template
        # half as a **leading** stdin prefix so (1) format rules reach
        # the model and (2) identical prefixes across pages are eligible
        # for automatic prefix caching when the routed model supports it.
        stable, per_page = split_prompt_template(prompt_template)
        prompt = _render_prompt(per_page, raw_body=truncated_body, meta=meta)
        if stable:
            prompt = f"{stable.rstrip()}\n\n{prompt}"
        return self.run_prompt(prompt)
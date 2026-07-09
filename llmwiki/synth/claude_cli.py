"""Synchronous synthesis via the `claude` CLI (`claude -p -`).

`llmwiki add` is synchronous by contract — the doc must come out the
other end as a real wiki page in the same invocation, from ANY
environment: a plain terminal (no agent env vars) or nested inside a
Claude Code / Codex session. The agent-delegate backend can't do that
(it parks a pending prompt for a future agent turn), so `add`
substitutes this backend whenever agent-delegate is configured.

Also selectable outright with ``"synthesis": {"backend": "claude"}``.
Optional config keys: ``claude_path`` (else $PATH lookup),
``claude_model`` (defaults to ``sonnet``), ``timeout`` (seconds
per page, default 180).

Reuses build.py's hardened ``_resolve_claude_path`` (#421: shell-metachar
rejection, PATH lookup) and passes the prompt via stdin (#486 precedent:
dodges argv limits and injection-via-argv).
"""

from __future__ import annotations

import subprocess
from typing import Any

from llmwiki.synth.base import BaseSynthesizer
from llmwiki.synth.ollama import _render_prompt

_DEFAULT_TIMEOUT = 180


class ClaudeCLIError(RuntimeError):
    """One page failed to synthesize via the claude CLI."""


class ClaudeCLISynthesizer(BaseSynthesizer):
    """Shell out to ``claude -p -`` once per page. No pending files,
    no HTTP — the answer comes back in-process before the next page."""

    def __init__(
        self,
        claude_path: str | None = None,
        model: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self.claude_path = claude_path
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "claude-cli"

    def _resolved(self) -> str | None:
        # Lazy import: build.py is heavy and claude_cli must stay cheap
        # to import from resolve_backend.
        from llmwiki.build import _resolve_claude_path

        resolved = _resolve_claude_path(self.claude_path)
        return str(resolved) if resolved else None

    def is_available(self) -> bool:
        return self._resolved() is not None

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        claude = self._resolved()
        if claude is None:
            raise ClaudeCLIError(
                "claude CLI not found — install it, pass synthesis.claude_path, "
                "or configure synthesis.backend=ollama"
            )
        # Same 8 KB body cap as the ollama/agent-delegate backends: the
        # add pipeline chunks raw docs to ~7 KB, so nothing is lost.
        truncated_body = raw_body[:8000] if raw_body else ""
        prompt = _render_prompt(prompt_template, raw_body=truncated_body, meta=meta)
        argv = [claude, "-p", "-"]
        if self.model:
            argv += ["--model", self.model]
        try:
            result = subprocess.run(
                argv, input=prompt, capture_output=True, text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCLIError(
                f"claude CLI timed out after {self.timeout}s"
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise ClaudeCLIError(f"claude CLI failed to run: {exc}") from exc
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else "no output"
            raise ClaudeCLIError(
                f"claude CLI exited {result.returncode}: {detail}"
            )
        text = result.stdout.strip()
        if not text:
            raise ClaudeCLIError("claude CLI returned an empty completion")
        return text

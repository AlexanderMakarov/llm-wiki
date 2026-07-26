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
per page, default 180), ``claude_lean`` (default true — strip the
agent scaffolding from each call; see ``_LEAN_ARGV``).

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

# Synthesis is text-in / text-out: the prompt carries everything the model
# needs and we only ever read stdout, so the agent scaffolding `claude`
# assembles by default is pure overhead billed on every page. Measured in
# this repo with a trivial prompt: 35,081 input tokens without these flags
# vs 700 with them. Each flag drops one scaffolding source:
#   --tools ""                → built-in tool schemas
#   --strict-mcp-config       → every configured MCP server's tools
#   --disable-slash-commands  → the skill listing
#   --setting-sources ""      → settings files + CLAUDE.md auto-discovery
#   --system-prompt           → the full agent system prompt
# `--tools` is variadic, so its "" must be followed by another `--flag`.
_LEAN_ARGV: tuple[str, ...] = (
    "--tools", "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--setting-sources", "",
)

# Replaces the agent system prompt. Deliberately minimal — the page format,
# the topic vocabulary, and every rule live in prompts/source_page.md, which
# is rendered into the user prompt.
_LEAN_SYSTEM_PROMPT = (
    "You synthesize wiki source pages from session transcripts. "
    "Follow the user's format instructions exactly. "
    "Output only the requested markdown, with no preamble or commentary."
)


# The site overview is a short prose summary of a JSON brief — the cheapest
# real LLM task in the codebase, so it defaults to the small model rather
# than the (larger) page-synthesis model. Override with
# ``synthesis.overview_model``.
DEFAULT_OVERVIEW_MODEL = "haiku"


_OVERVIEW_SYSTEM_PROMPT = (
    "You write short prose summaries for a knowledge-base landing page. "
    "Output only the requested markdown."
)


def resolve_overview_model(cfg: dict[str, Any] | None = None) -> str:
    """Pick the model for the site-overview call (build.py)."""
    if cfg is None:
        from llmwiki.config_schedule import _load_sessions_config
        cfg = _load_sessions_config()
    synth_cfg = (cfg or {}).get("synthesis", {}) or {}
    return str(synth_cfg.get("overview_model", "") or "").strip() or DEFAULT_OVERVIEW_MODEL


def overview_argv(claude: str, model: str | None = None) -> list[str]:
    """Command line for build.py's site-overview call.

    Lives here rather than in build.py so both `claude` call sites share
    one flag set and one model-resolution path.
    """
    return lean_argv(
        claude,
        system_prompt=_OVERVIEW_SYSTEM_PROMPT,
        model=model or resolve_overview_model(),
    )


def lean_argv(
    claude: str,
    *,
    system_prompt: str,
    model: str | None = None,
    lean: bool = True,
) -> list[str]:
    """Build a `claude -p -` command line for a one-shot text task.

    Shared by every non-interactive `claude` call in the codebase, so the
    scaffolding-stripping flags can't drift between call sites. ``lean=False``
    restores the plain invocation.
    """
    argv = [claude, "-p", "-"]
    if lean:
        argv += list(_LEAN_ARGV)
        argv += ["--system-prompt", system_prompt]
    if model:
        argv += ["--model", model]
    return argv


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
        lean: bool = True,
    ) -> None:
        self.claude_path = claude_path
        self.model = model
        self.timeout = timeout
        self.lean = lean

    def _argv(self, claude: str) -> list[str]:
        """Build the `claude` command line for one page."""
        return lean_argv(
            claude,
            system_prompt=_LEAN_SYSTEM_PROMPT,
            model=self.model,
            lean=self.lean,
        )

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
        argv = self._argv(claude)
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

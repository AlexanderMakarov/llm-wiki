"""Synchronous synthesis via the `claude` CLI (`claude -p -`).

`llmwiki add` is synchronous by contract — the doc must come out the
other end as a real wiki page in the same invocation, from ANY
environment: a plain terminal (no agent env vars) or nested inside a
Claude Code / Codex session. The agent-delegate backend can't do that
(it parks a pending prompt for a future agent turn), so `add`
substitutes this backend whenever agent-delegate is configured.

Also selectable outright with ``"synthesis": {"backend": "claude"}``.
Optional config keys: ``claude_path`` (else $PATH lookup),
``claude_model`` (defaults to ``sonnet``), ``claude_timeout`` (seconds
per page, default 180), ``claude_effort`` (``--effort``; caps extended
thinking, which is billed as output), and ``claude_lean`` (default true —
strip the agent scaffolding from each call; see ``_LEAN_ARGV``).

Reuses ``llmwiki.claude_path.resolve_claude_path`` (#421: shell-metachar
rejection, PATH lookup) and passes the prompt via stdin (#486 precedent:
dodges argv limits and injection-via-argv).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from llmwiki.claude_path import resolve_claude_path as _resolve_claude_path
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.synth.base import BaseSynthesizer, split_prompt_template
from llmwiki.synth.ollama import _render_prompt

DEFAULT_CLAUDE_TIMEOUT = 180

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

# Replaces the agent system prompt when the template carries no stable half
# to put there (a custom prompt without the marker).
_LEAN_SYSTEM_PROMPT = (
    "You synthesize wiki source pages from session transcripts. "
    "Follow the user's format instructions exactly. "
    "Output only the requested markdown, with no preamble or commentary."
)

# Claude Code caches the system prompt across separate `claude -p`
# invocations; the user message it does not — the single cache breakpoint
# sits at the end of that message, so a key that includes the page body is
# unique per page and never re-read. Putting the run-stable half of the
# template into --system-prompt is therefore the difference between paying
# the 2x cache-write rate on it every page and paying the 0.1x read rate
# after the first. Measured on real pages: 4,642 tokens read back per page,
# $0.076 -> $0.057. See docs/reference/synthesis-cost.md.


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
    effort: str | None = None,
) -> list[str]:
    """Build a `claude -p -` command line for a one-shot text task.

    Shared by every non-interactive `claude` call in the codebase, so the
    scaffolding-stripping flags can't drift between call sites. ``lean=False``
    restores the plain invocation.

    ``effort`` maps to ``--effort``, which governs extended thinking. That
    is billed as output at ~5x the input rate, so it dominates the bill on
    the small models: Haiku spent 5,753 output tokens on a page at its
    default effort versus 1,609 at ``low`` — for a summarization task whose
    reasoning is already spelled out in the prompt.
    """
    argv = [claude, "-p", "-"]
    if lean:
        argv += list(_LEAN_ARGV)
        argv += ["--system-prompt", system_prompt]
    if model:
        argv += ["--model", model]
    if effort:
        argv += ["--effort", effort]
    return argv


class ClaudeCLIError(RuntimeError):
    """One page failed to synthesize via the claude CLI."""


def _usage_token_total(usage: dict[str, Any]) -> int:
    """Sum token fields from a ``claude --output-format json`` usage block."""
    keys = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    total = 0
    for key in keys:
        val = usage.get(key)
        if isinstance(val, (int, float)):
            total += int(val)
    return total


def _parse_claude_print_stdout(stdout: str) -> tuple[str, int | None, float | None]:
    """Return (page_text, tokens, cost_usd) from ``claude -p`` stdout.

    Prefer ``--output-format json`` payloads (``result`` + ``usage`` +
    ``total_cost_usd``). Fall back to plain text when the CLI (or a test
    stub) ignores the format flag — then tokens/cost stay unknown.

    Raises ``ClaudeCLIError`` when stdout parses as a JSON object but is
    not a usable success payload (missing/empty ``result``, ``is_error``,
    or a non-success ``subtype``). Never returns the raw JSON envelope as
    page text.
    """
    text = (stdout or "").strip()
    if not text:
        return "", None, None
    if not text.startswith("{"):
        return text, None, None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text, None, None
    if not isinstance(payload, dict):
        return text, None, None

    if payload.get("is_error") is True:
        detail = payload.get("result")
        if not isinstance(detail, str) or not detail.strip():
            detail = "is_error without detail"
        raise ClaudeCLIError(f"claude CLI reported an error: {detail.strip()}")

    subtype = payload.get("subtype")
    if isinstance(subtype, str) and subtype and subtype != "success":
        detail = payload.get("result")
        suffix = f": {detail.strip()}" if isinstance(detail, str) and detail.strip() else ""
        raise ClaudeCLIError(
            f"claude CLI JSON subtype {subtype!r} is not success{suffix}"
        )

    result = payload.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ClaudeCLIError(
            "claude CLI JSON response missing a non-empty result field"
        )

    tokens: int | None = None
    usage = payload.get("usage")
    if isinstance(usage, dict):
        tokens = _usage_token_total(usage)
    cost: float | None = None
    raw_cost = payload.get("total_cost_usd")
    if isinstance(raw_cost, (int, float)):
        cost = float(raw_cost)
    return result.strip(), tokens, cost


class ClaudeCLISynthesizer(BaseSynthesizer):
    """Shell out to ``claude -p -`` once per page. No pending files,
    no HTTP — the answer comes back in-process before the next page."""

    def __init__(
        self,
        claude_path: str | None = None,
        model: str | None = None,
        timeout: int = DEFAULT_CLAUDE_TIMEOUT,
        lean: bool = True,
        effort: str | None = None,
    ) -> None:
        self.claude_path = claude_path
        self.model = model
        self.timeout = timeout
        self.lean = lean
        self.effort = effort
        self._run_tokens = 0
        self._run_cost_usd = 0.0
        self._run_has_usage = False

    def reset_usage(self) -> None:
        """Clear accumulated usage before a multi-page synth run."""
        self._run_tokens = 0
        self._run_cost_usd = 0.0
        self._run_has_usage = False

    def take_usage(self) -> tuple[int | None, float | None]:
        """Return accumulated (tokens, cost_usd) for this run, or Nones."""
        if not self._run_has_usage:
            return None, None
        # Known zeros are still known — do not collapse them to "unknown".
        return self._run_tokens, self._run_cost_usd

    def _argv(self, claude: str, system_prompt: str) -> list[str]:
        """Build the `claude` command line for one page."""
        argv = lean_argv(
            claude,
            system_prompt=system_prompt,
            model=self.model,
            lean=self.lean,
            effort=self.effort,
        )
        # JSON carries result text plus usage / total_cost_usd (#113).
        argv += ["--output-format", "json"]
        return argv

    @property
    def name(self) -> str:
        return "claude-cli"

    def _resolved(self) -> str | None:
        # Lazy import: build.py is heavy and claude_cli must stay cheap
        # to import from resolve_backend.

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
        # Route the run-stable half of the template to the system prompt,
        # which is the only part `claude -p` caches between invocations.
        stable, per_page = split_prompt_template(prompt_template)
        prompt = _render_prompt(per_page, raw_body=truncated_body, meta=meta)
        argv = self._argv(claude, stable or _LEAN_SYSTEM_PROMPT)
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
        text, tokens, cost = _parse_claude_print_stdout(result.stdout)
        if tokens is not None or cost is not None:
            self._run_has_usage = True
            if tokens is not None:
                self._run_tokens += tokens
            if cost is not None:
                self._run_cost_usd += cost
        if not text:
            raise ClaudeCLIError("claude CLI returned an empty completion")
        return text

"""Synthesizer backends — ABC + built-in implementations (v0.5 · #36).

The `BaseSynthesizer` defines the contract: given a raw session markdown
body + its frontmatter, produce a wiki source-page body (the part under
the frontmatter). The concrete backend handles the actual LLM call.

Built-in backends:
- `DummySynthesizer` — returns a canned response. Used for testing and
  for the `--dry-run` path so users can preview what would be generated.
- (Future) `OllamaSynthesizer` — calls a local Ollama instance (#35)
- (Future) `ClaudeAPISynthesizer` — calls the Anthropic API
"""

from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from llmwiki.cache import TRANSCRIPT_CHARS_PER_TOKEN

# Section header in prompts/source_page.md that separates the part which is
# identical for every page in a run (format rules + injected topic
# vocabulary) from the part that changes per page ({meta} + {body}).
#
# Every provider bills a repeated prefix more cheaply than fresh input, but
# each wants it in a different place: a system prompt (Claude CLI, Ollama),
# an automatically-matched leading prefix (OpenAI/OpenRouter), or an
# explicit cache_control breakpoint (Anthropic API). Splitting here — in the
# shared contract — lets each backend map the stable half onto whatever its
# provider caches, instead of every backend re-deriving the boundary.
PER_PAGE_MARKER = "## Session to synthesize"


def split_prompt_template(template: str) -> tuple[str, str]:
    """Split a prompt template into (stable_prefix, per_page_tail).

    The prefix is byte-identical across every page of a run, so it is what
    a backend should hand to its provider's caching mechanism. The tail
    carries the ``{meta}`` / ``{body}`` placeholders.

    A template without the marker (a user's custom prompt) yields an empty
    prefix and the whole template as the tail — caching is an optimisation,
    never a correctness requirement, so an unrecognised template must still
    synthesize correctly.
    """
    head, sep, tail = template.partition(PER_PAGE_MARKER)
    if not sep:
        return "", template
    return head.rstrip(), sep + tail


class BackendUsageLimitError(RuntimeError):
    """The backend's account or session quota is exhausted (#181).

    Distinct from a per-page failure: every later page would fail the same
    way until the quota resets, so the synth pipeline stops dispatching new
    sources and defers the remainder to the next run. ``reset`` carries the
    provider's reset time as text when it gave one.

    Every backend (Claude CLI, Cursor Agent CLI, Ollama) raises it when the
    provider's error message carries account-quota wording, as recognised by
    :func:`usage_limit_from_text`. A bare HTTP 429 or short-lived rate-limit
    throttling is not a usage limit and stays a per-page error.
    """

    def __init__(self, message: str, *, reset: str | None = None) -> None:
        super().__init__(message)
        self.reset = reset


# Account / session quota wording. Throttling ("Rate limit exceeded", "429 Too
# Many Requests", "hit your rate limit") deliberately does not match: it clears
# within seconds, so it is one page's failure, not a reason to stop the run.
_USAGE_LIMIT_TEXT_RE = re.compile(
    r"hit your (?:(?!rate\b)[\w-]+ )*limit"
    r"|\busage limit"
    r"|\bsession limit"
    r"|\bquota (?:exceeded|exhausted|reached)"
    r"|\bexceeded your (?:current )?quota"
    r"|\binsufficient[_ ]quota"
    r"|\bout of credits"
    r"|\bcredit balance is too low",
    re.IGNORECASE,
)
# Reset time as the provider states it, e.g. "resets 1:20pm (Etc/UTC)".
_USAGE_LIMIT_RESET_RE = re.compile(
    r"\bresets\s+(?:at\s+)?(.+?)[\s.]*$", re.IGNORECASE | re.MULTILINE
)
_USAGE_LIMIT_DETAIL_MAX = 300


def usage_limit_from_text(
    text: str | None, *, label: str = "backend"
) -> BackendUsageLimitError | None:
    """Return a :class:`BackendUsageLimitError` when ``text`` reports an exhausted quota.

    ``text`` is a provider error message (CLI stderr, a JSON error result, an
    HTTP error body). The error's message is ``"<label> usage limit: <line>"``
    for the line that carries the quota wording; ``reset`` is the text after
    ``resets`` when the message has one, else ``None``. Returns ``None`` for
    anything else, including plain rate-limit throttling.
    """
    if not text:
        return None
    match = _USAGE_LIMIT_TEXT_RE.search(text)
    if match is None:
        return None
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    line = text[line_start : line_end if line_end != -1 else len(text)].strip()
    reset_match = _USAGE_LIMIT_RESET_RE.search(text)
    reset = reset_match.group(1) if reset_match else None
    return BackendUsageLimitError(
        f"{label} usage limit: {line[:_USAGE_LIMIT_DETAIL_MAX]}", reset=reset
    )


# ─── Body budgets (#311) ───────────────────────────────────────────────
#
# Two different limits, deliberately kept apart:
#
# * ``SESSION_BODY_SEND_CAP_CHARS`` — the historical per-call cap on a body
#   sent through ``synthesize_source_page`` (sessions, harvest evidence,
#   topic consolidation). Unchanged since before #311.
# * the *usable body budget* — how many raw-body characters one call can
#   cover for a **document chunk**. Derived from the backend's context window
#   (see :func:`usable_body_chars_for_window`) or set directly in config.
#   Documents are stored whole and chunked in memory to this budget.

#: Historical send cap for session / evidence bodies (never shrinks).
SESSION_BODY_SEND_CAP_CHARS = 8000


def page_timeout_seconds(configured: int, body_chars: int) -> int:
    """Wall-clock seconds for one page/chunk call, scaled with body size (#311).

    Bodies at or under :data:`SESSION_BODY_SEND_CAP_CHARS` use ``configured``
    as-is (session / evidence path). Larger document chunks scale linearly so
    a lean-Claude ~296k-char chunk under the default 180s timeout gets enough
    wall clock instead of failing the whole document on the first slow call.
    Explicit ``synthesis.<backend>.timeout`` remains the per-unit baseline.
    """
    configured = max(1, int(configured))
    n = max(0, int(body_chars))
    if n <= SESSION_BODY_SEND_CAP_CHARS:
        return configured
    return max(
        configured,
        (configured * n + SESSION_BODY_SEND_CAP_CHARS - 1) // SESSION_BODY_SEND_CAP_CHARS,
    )

#: Tokens reserved for the rendered prompt template (format rules, topic
#: vocabulary, ``{meta}``). The shipped template renders to ~1,800 tokens
#: before the body; the rest is headroom for a growing topic vocabulary.
PROMPT_RESERVE_TOKENS = 2000
#: Tokens reserved for the model's page. Measured output spread is 902–2,554
#: tokens per page (see ``estimate.DEFAULT_OUTPUT_TOKENS``).
OUTPUT_RESERVE_TOKENS = 2600
#: Characters per token used to convert the remaining window into body
#: characters — the measured *transcript* ratio, which is lower (more tokens
#: per character) than prose, so the budget errs on the small side.
BODY_CHARS_PER_TOKEN = TRANSCRIPT_CHARS_PER_TOKEN
#: Window assumed for a bare (non-agent) backend when none is configured or
#: detected — the Ollama fallback and the :class:`BaseSynthesizer` default.
DEFAULT_CONTEXT_WINDOW_TOKENS = 8192
#: Window assumed for the agent backends (Claude, Cursor Agent CLI) when none is
#: configured or known for the model: modern agent models ship 200k windows.
ASSUMED_AGENT_WINDOW_TOKENS = 200_000
#: Floor for a budget the *operator* sized tiny: an explicit
#: ``usable_body_chars``, or a configured ``context_window_tokens`` too small
#: for the per-call reserves. A derived default (assumed / known / detected
#: window) never lands here silently — see :func:`resolve_usable_body_chars`.
MIN_USABLE_BODY_CHARS = 1000
#: Dummy / dry-run: large enough that multi-section fixtures fit in one call.
DUMMY_USABLE_BODY_CHARS = 10_000_000

#: Per-call framing ``claude -p`` injects even with every scaffolding-stripping
#: flag on (measured via ``--output-format json``; see synthesis-cost.md).
LEAN_OVERHEAD_TOKENS = 890
#: Full coding-agent context (tool schemas, MCP servers, skills, CLAUDE.md) a
#: non-lean ``claude -p`` or an Agent CLI call carries before the prompt. A
#: mid-range figure for a typical setup, not a ceiling.
FULL_AGENT_OVERHEAD_TOKENS = 35_000
#: Scaffolding assumed for an Ollama ``/api/generate`` call (chat framing only).
OLLAMA_OVERHEAD_TOKENS = 500

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetClass:
    """How much of a window a backend spends on things other than the body.

    ``scaffolding_tokens`` is fixed per-call framing the backend adds;
    the *working margin* — headroom for the agent's own reasoning, tool use and
    tokenizer drift — is ``max(margin_floor_tokens, margin_percent% of window)``.
    """

    name: str
    scaffolding_tokens: int
    margin_floor_tokens: int
    margin_percent: int

    def working_margin(self, window: int) -> int:
        return max(self.margin_floor_tokens, window * self.margin_percent // 100)

    def fixed_tokens(self) -> int:
        """Tokens reserved regardless of the window: scaffolding + prompt + output."""
        return self.scaffolding_tokens + PROMPT_RESERVE_TOKENS + OUTPUT_RESERVE_TOKENS


#: No agent, no margin — the budget of a backend that has no class of its own
#: (:class:`BaseSynthesizer` default, estimate without a backend).
GENERIC_BUDGET = BudgetClass("generic", 0, 0, 0)
#: Ollama ``/api/generate`` — a bare completion call.
OLLAMA_BUDGET = BudgetClass("ollama", OLLAMA_OVERHEAD_TOKENS, 2048, 10)
#: ``claude -p`` with ``lean`` on (scaffolding stripped).
CLAUDE_LEAN_BUDGET = BudgetClass("claude-lean", LEAN_OVERHEAD_TOKENS, 8192, 25)
#: Non-lean ``claude -p`` and the Cursor Agent CLI (full agent context).
HEAVY_AGENT_BUDGET = BudgetClass("heavy-agent", FULL_AGENT_OVERHEAD_TOKENS, 16_384, 35)


def window_room_tokens(context_window_tokens: int, budget_class: BudgetClass = GENERIC_BUDGET) -> int:
    """Tokens left for the body: ``window - scaffolding - prompt - output - working margin``.

    Zero or negative means the window cannot carry the per-call reserves at all.
    """
    window = int(context_window_tokens)
    return window - budget_class.fixed_tokens() - budget_class.working_margin(window)


def usable_body_chars_for_window(
    context_window_tokens: int,
    budget_class: BudgetClass = GENERIC_BUDGET,
    *,
    floor: int = MIN_USABLE_BODY_CHARS,
) -> int:
    """Body characters one call can carry in a ``context_window_tokens`` window.

    ``usable_tokens = window - scaffolding - prompt reserve - output reserve -
    working margin``; ``chars = max(floor, usable_tokens * BODY_CHARS_PER_TOKEN)``.
    Scaffolding and margin come from ``budget_class``; the generic class has
    neither. No upper cap: a large window yields a large budget. ``floor``
    defaults to :data:`MIN_USABLE_BODY_CHARS` (an operator-sized tiny window).
    """
    room = window_room_tokens(context_window_tokens, budget_class)
    # round() first so float noise (90400 * 2.05 = 185319.99999…) can't cost a character.
    return max(floor, int(round(room * BODY_CHARS_PER_TOKEN, 6)))


def window_tokens_for_body_chars(body_chars: int, budget_class: BudgetClass = GENERIC_BUDGET) -> int:
    """Smallest window whose :func:`usable_body_chars_for_window` holds ``body_chars``."""
    body_tokens = math.ceil(body_chars / BODY_CHARS_PER_TOKEN)
    base = body_tokens + budget_class.fixed_tokens()
    window = base + budget_class.margin_floor_tokens
    if window * budget_class.margin_percent // 100 > budget_class.margin_floor_tokens:
        # The percentage margin dominates: window * (1 - pct) >= base.
        window = math.ceil(base * 100 / (100 - budget_class.margin_percent))
    while usable_body_chars_for_window(window, budget_class) < body_chars:
        window += 1  # absorb rounding in the integer percent / ceil steps
    while window > 1 and usable_body_chars_for_window(window - 1, budget_class) >= body_chars:
        window -= 1  # ...and trim the same rounding going the other way
    return window


#: Budget when nothing configures or identifies the window (derived, not typed).
DEFAULT_USABLE_BODY_CHARS = usable_body_chars_for_window(DEFAULT_CONTEXT_WINDOW_TOKENS)


def _positive_int(value: Any, key: str) -> int | None:
    """``value`` as a positive int, or ``None`` (warned) when unusable."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        ok, number = False, 0
    else:
        try:
            number = int(value)
            ok = number > 0
        except (TypeError, ValueError):
            ok, number = False, 0
    if not ok:
        _log.warning("ignoring synthesis.%s=%r — expected a positive integer", key, value)
        return None
    return number


@dataclass(frozen=True)
class BodyBudgetConfig:
    """``usable_body_chars`` / ``context_window_tokens`` from one backend block."""

    usable_body_chars: int | None = None
    context_window_tokens: int | None = None


def load_body_budget_config(section: Mapping[str, Any] | None, backend: str) -> BodyBudgetConfig:
    """Read the two budget keys from ``synthesis.<backend>`` (bad values warn and are ignored)."""
    section = section if isinstance(section, Mapping) else {}
    return BodyBudgetConfig(
        usable_body_chars=_positive_int(
            section.get("usable_body_chars"), f"{backend}.usable_body_chars"
        ),
        context_window_tokens=_positive_int(
            section.get("context_window_tokens"), f"{backend}.context_window_tokens"
        ),
    )


def resolve_usable_body_chars(
    budget: BodyBudgetConfig,
    *,
    known_window_tokens: Callable[[], int | None] | None = None,
    budget_class: BudgetClass = GENERIC_BUDGET,
    default_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS,
    derived_floor_chars: int = MIN_USABLE_BODY_CHARS,
) -> int:
    """The usable body budget, in resolution order.

    1. explicit ``usable_body_chars`` (used as-is, no class reserves applied);
    2. derived from ``context_window_tokens`` (config);
    3. derived from the backend's own knowledge of its window — a known-model
       table or an auto-detected value — via ``known_window_tokens``;
    4. derived from ``default_window_tokens`` (agent backends pass
       :data:`ASSUMED_AGENT_WINDOW_TOKENS`).

    Derived budgets (2–4) subtract ``budget_class``'s scaffolding and margin.
    The :data:`MIN_USABLE_BODY_CHARS` floor applies only to what the operator
    sized (1, and a configured window in 2). When a *derived default* window
    (3–4) cannot carry the reserves, that is a bug in the numbers rather than an
    operator choice: it is logged and clamped to ``derived_floor_chars``
    (agent backends pass :data:`SESSION_BODY_SEND_CAP_CHARS`) instead of
    silently landing on 1,000.
    """
    if budget.usable_body_chars is not None:
        return budget.usable_body_chars
    if budget.context_window_tokens is not None:
        return usable_body_chars_for_window(budget.context_window_tokens, budget_class)
    window = known_window_tokens() if known_window_tokens is not None else None
    window = window or default_window_tokens
    if window_room_tokens(window, budget_class) <= 0:
        _log.warning(
            "%s window of %d tokens leaves no room for a body after the per-call reserves; "
            "using %d characters — set synthesis.<backend>.context_window_tokens or usable_body_chars",
            budget_class.name,
            window,
            derived_floor_chars,
        )
        return derived_floor_chars
    return usable_body_chars_for_window(window, budget_class, floor=derived_floor_chars)


class BaseSynthesizer(ABC):
    """Interface for LLM-backed wiki-page synthesizers."""

    #: False on backends that return canned text. Callers that must not
    #: publish machine-assembled prose (candidates.promote) check this
    #: instead of pattern-matching on class names.
    is_llm = True

    def usable_body_chars(self) -> int:
        """Max raw-body characters one *document chunk* call can cover (#311).

        Pipeline and estimate chunk long documents to this budget. Backends
        resolve it from config / their context window (see
        :func:`resolve_usable_body_chars`); this default is the budget of the
        :data:`DEFAULT_CONTEXT_WINDOW_TOKENS` window.
        :class:`DummySynthesizer` returns a large value so dry-run and tests
        cover multi-section fixtures in one call. Session bodies are not
        governed by this: they keep the :data:`SESSION_BODY_SEND_CAP_CHARS` cap.
        """
        return DEFAULT_USABLE_BODY_CHARS

    def synthesize_document_chunk(
        self,
        chunk: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Synthesize one in-memory chunk of a stored document (#311).

        ``chunk`` is at most :meth:`usable_body_chars` long, so it is sent
        whole. Backends that cap the body they send override this to lift the
        session cap up to the usable budget; the default is a plain
        :meth:`synthesize_source_page` call.
        """
        return self.synthesize_source_page(chunk, meta, prompt_template)

    def synthesize_key_facts(
        self,
        evidence: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Given an evidence digest for one entity/concept, return its
        ``## Key Facts`` bullets as markdown (#103).

        The call shape is identical to a source page — render the template
        with ``{body}`` / ``{meta}`` and return the completion — so backends
        get this for free and only override to special-case the output.
        """
        return self.synthesize_source_page(evidence, meta, prompt_template)

    @abstractmethod
    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        """Given a raw session body + frontmatter, return a wiki
        source-page body (markdown). The caller handles frontmatter
        generation and file writing — the backend only generates the
        prose content (Summary, Key Claims, Key Quotes, Connections).

        `prompt_template` is the contents of `prompts/source_page.md`
        with `{body}` and `{meta}` placeholders.

        Thread-safety contract: the caller may invoke this method
        concurrently on one backend instance from several threads, one call
        per page. Implementations must be thread-safe — keep per-call state
        in local variables, and guard any instance attribute that
        accumulates across calls (usage counters, caches) with a lock held
        only for the mutation, never across the provider call itself.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is ready to use (e.g. the API
        key is set, or the Ollama server is running)."""
        ...

    def overview_completion(
        self, prompt: str, *, model: str | None = None
    ) -> str:
        """One-shot completion for site-overview synthesis (#230).

        LLM backends override. ``model`` is an optional override (Claude
        overview defaults to ``synthesis.overview_model`` / haiku).
        Callers soft-fail on raised errors. Non-LLM backends leave this
        unimplemented — ``synthesize_overview`` skips them via ``is_llm``.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support overview completion"
        )

    def kill_in_flight(self) -> int:
        """Stop the provider calls this backend has in flight; return how many (#181).

        The synth run calls this when it abandons its drain (a second Ctrl+C),
        so the run exits promptly instead of waiting for each page up to the
        backend timeout. Backends that run child processes kill them; the
        default does nothing and returns 0 — an in-process or HTTP call (Ollama)
        is waited for, up to its own timeout.
        """
        return 0

    @property
    def name(self) -> str:
        return self.__class__.__name__


class DummySynthesizer(BaseSynthesizer):
    """Test/preview backend — returns a canned wiki page without
    calling any LLM. Useful for `--dry-run` and unit tests.

    G-12 (#298): the dummy output used to copy every ``[[wikilink]]``
    mention straight out of the raw body into ``## Connections``.  That
    fabricated 371 dangling links on the compiled demo site because
    those targets almost never existed as wiki pages.  The dummy now
    emits only a single **real** connection — the project entity page,
    which the ingest workflow guarantees exists — and surfaces raw
    mentions as plain text in ``## Raw Mentions`` so the information
    isn't lost but ``check-links`` doesn't cry wolf.
    """

    is_llm = False

    def usable_body_chars(self) -> int:
        """Effectively unlimited — dry-run and tests cover whole fixtures."""
        return DUMMY_USABLE_BODY_CHARS

    def _title_case_project(self, project: str) -> str:
        """``ai-newsletter`` → ``AiNewsletter`` (matches entity filenames)."""
        return "".join(part.capitalize() for part in re.split(r"[-_\s]+", project) if part)

    def synthesize_source_page(
        self,
        raw_body: str,
        meta: dict[str, Any],
        prompt_template: str,
    ) -> str:
        slug = meta.get("slug", "unknown")
        project = meta.get("project", "unknown")
        date = meta.get("date", "unknown")

        # Extract a naive summary from the first 500 chars
        first_para = raw_body.strip().split("\n\n")[0][:500] if raw_body else ""

        # Plain-text mentions — kept for human readers, but NOT emitted as
        # [[wikilinks]] so check-links stays clean on auto-synthesized pages.
        mentions = sorted(set(re.findall(r"\[\[([^\]]+)\]\]", raw_body)))
        raw_mentions_block = (
            "\n".join(f"- {m}" for m in mentions[:10])
            if mentions
            else "*(no mentions detected)*"
        )

        project_entity = self._title_case_project(project) if project and project != "unknown" else ""
        if project_entity:
            # Shape must match parse_source_topics (#147): kind + em dash + nested fact.
            connections_block = (
                f"- [[{project_entity}]] (entity) — parent project\n"
                f"  - fact: Session covered project `{project}`."
            )
        else:
            # No bare [[wikilink]] without kind — rewrite detector must stay quiet.
            connections_block = (
                "*(connections auto-extracted by a real synthesizer will appear here)*"
            )

        return f"""## Summary

Auto-synthesized from session `{slug}` on {date} (project: {project}).

{first_para}

## Key Claims

- Session covered project `{project}`
- Model: {meta.get('model', 'unknown')}
- {meta.get('user_messages', '?')} user messages, {meta.get('tool_calls', '?')} tool calls

## Key Quotes

> (Auto-synthesis — replace with actual quotes from the session)

## Connections

{connections_block}

## Raw Mentions

{raw_mentions_block}
"""

    def is_available(self) -> bool:
        return True  # Always available — no external deps

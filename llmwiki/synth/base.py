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

import re
from abc import ABC, abstractmethod
from typing import Any

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


class BaseSynthesizer(ABC):
    """Interface for LLM-backed wiki-page synthesizers."""

    #: False on backends that return canned text. Callers that must not
    #: publish machine-assembled prose (candidates.promote) check this
    #: instead of pattern-matching on class names.
    is_llm = True

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

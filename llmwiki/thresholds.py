"""Shared numeric thresholds (#150).

Dependency-free on purpose: it imports nothing from :mod:`llmwiki`, so any
module can read a threshold without risking an import cycle.
:mod:`llmwiki.candidates_harvest` already imports ``_norm_slug`` from
:mod:`llmwiki.lint.rules.link_integrity`, so the lint package cannot import
the threshold back from the harvester.
"""

from __future__ import annotations

__all__ = ["DEFAULT_MIN_REFS"]

#: Default significance threshold. A wikilink target must be named by this many
#: distinct source pages before the harvest materializes a candidate stub for
#: it — and before ``link_integrity`` calls an unresolved link to it a defect.
#: Matches the Lint Workflow's definition of a missing entity page ("mentioned
#: in 3+ source pages") so the producer and the checker cannot disagree.
DEFAULT_MIN_REFS = 3

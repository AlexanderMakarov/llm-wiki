"""Section chunker hardening (#311, review N2).

Spec: ``context/spec/324-whole-document-storage/``. ``chunk_markdown_by_sections``
is the one in-memory splitter behind ``synth`` and the estimate. Two guarantees
on top of the basic section / paragraph splitting (covered in ``test_add_doc.py``):

* a heading is never emitted as a chunk of its own — it travels with the
  content after it (or, at the end of a document, before it);
* a hard slice inside an open code fence prefers line boundaries and closes and
  re-opens the fence on every piece, so no chunk carries an unbalanced fence.
"""

from __future__ import annotations

import random
import re

import pytest

from llmwiki.doc_chunking import chunk_markdown_by_sections

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING = re.compile(r"^#{1,6}(?:\s|$)")


def _bodies(md: str, max_chars: int) -> list[str]:
    return [c.body for c in chunk_markdown_by_sections(md, max_chars)]


def _heading_only(body: str) -> bool:
    lines = [ln for ln in body.split("\n") if ln.strip()]
    return bool(lines) and all(_HEADING.match(ln) for ln in lines)


def _fences_balanced(body: str) -> bool:
    opener: str | None = None
    for line in body.split("\n"):
        m = _FENCE.match(line)
        if not m:
            continue
        if opener is None:
            opener = m.group(1)[0]
        elif opener == m.group(1)[0]:
            opener = None
    return opener is None


def _payload(text: str) -> str:
    """Non-whitespace characters outside fence marker lines — what a split must preserve."""
    kept = [ln for ln in text.split("\n") if not _FENCE.match(ln)]
    return re.sub(r"\s+", "", "".join(kept))


# ─── headings never stand alone ────────────────────────────────────────


def test_heading_stays_with_the_paragraph_that_does_not_fit_beside_it() -> None:
    """The old splitter flushed ``## A`` alone when the next paragraph overflowed."""
    md = "## A\n\n" + "x" * 280 + "\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[0].startswith("## A\n")
    assert "x" * 280 == "".join(re.findall(r"x+", "".join(bodies)))
    assert all(len(b) <= 300 for b in bodies)


def test_heading_before_an_oversized_paragraph_shares_its_first_chunk() -> None:
    md = "## A\n\n" + "w" * 900 + "\n"
    bodies = _bodies(md, 300)
    assert len(bodies) > 1
    assert bodies[0].startswith("## A\n\nw")
    assert not any(_heading_only(b) for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)
    assert all(len(b) <= 300 for b in bodies)


def test_heading_run_travels_forward_to_the_next_content() -> None:
    md = "# Doc\n\n## Part\n\n### Sub\n\n" + "p" * 250 + "\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[0].startswith("# Doc")
    assert "### Sub" in bodies[0] and "p" in bodies[0]


def test_heading_only_section_is_not_split_off_at_a_budget_boundary() -> None:
    """``# Title`` then a ``##`` section that cannot share a chunk with it: still no lone title."""
    md = "# Title\n\n## S1\n\n" + "a" * 280 + "\n\n## S2\n\n" + "b" * 280 + "\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[0].startswith("# Title")
    assert _payload("".join(bodies)) == _payload(md)


def test_trailing_heading_joins_the_content_before_it() -> None:
    md = "## A\n\n" + "a" * 280 + "\n\n## End\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[-1].rstrip().endswith("## End")
    assert "a" in bodies[-1]
    assert all(len(b) <= 300 for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)


def test_trailing_heading_after_a_full_oversized_section_is_not_alone() -> None:
    md = "## A\n\n" + "\n\n".join("q" * 90 for _ in range(6)) + "\n\n### Tail\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[-1].rstrip().endswith("### Tail")
    assert all(len(b) <= 300 for b in bodies)


def test_heading_before_a_long_line_that_is_followed_by_a_trailing_heading() -> None:
    """Both ends at once: ``## H`` must not strand before the line, nor ``#### T`` after it."""
    md = "## H\n\n" + "z" * 105 + "\n\n#### T"
    bodies = _bodies(md, 85)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[0].startswith("## H\n\nz")
    assert bodies[-1].rstrip().endswith("#### T") and "z" in bodies[-1]
    assert all(len(b) <= 85 for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)


def test_heading_before_a_paragraph_that_cannot_share_a_chunk_with_the_trailing_heading() -> None:
    md = "### A\n\n" + "a" * 60 + "\n\n#### B\n\n" + "b" * 66 + "\n\n# T"
    bodies = _bodies(md, 81)
    assert not any(_heading_only(b) for b in bodies)
    assert all(len(b) <= 81 for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)


def test_heading_before_an_oversized_single_line_takes_the_head_of_that_line() -> None:
    md = "## A\n\n" + "z" * 1000 + "\n"
    bodies = _bodies(md, 300)
    assert not any(_heading_only(b) for b in bodies)
    assert bodies[0].startswith("## A\n\nz")
    assert all(len(b) <= 300 for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)


def test_review_repro_title_fence_section_has_no_degenerate_chunks() -> None:
    """The review's N2 repro: it used to give 4- and 5-character heading chunks."""
    md = "# T\n\n```python\n" + "x = 1\n" * 400 + "```\n\n## S\n\n" + "word " * 500
    bodies = _bodies(md, 1000)
    assert min(len(b) for b in bodies) > 100
    assert not any(_heading_only(b) for b in bodies)
    assert all(_fences_balanced(b) and len(b) <= 1000 for b in bodies)
    assert bodies[0].startswith("# T\n\n```python\n")


def test_a_document_that_is_only_headings_stays_one_chunk() -> None:
    bodies = _bodies("# A\n\n## B\n", 300)
    assert bodies == ["# A\n\n## B\n"]


# ─── fences stay balanced when a slice lands inside them ───────────────


def _code_block(lines: int, opener: str = "```python", closer: str = "```") -> str:
    body = "\n".join(f"line_{i} = {i}" + (" # c" * 5) for i in range(lines))
    # a blank line mid-block: the old paragraph split cut here, leaving the fence open
    body = body.replace("\nline_5 ", "\n\nline_5 ", 1)
    return f"{opener}\n{body}\n{closer}\n"


def test_oversized_fence_splits_on_lines_and_reopens_every_piece() -> None:
    md = "## Code\n\nintro text\n\n" + _code_block(60)
    bodies = _bodies(md, 400)
    assert len(bodies) > 2
    code_chunks = [b for b in bodies if "line_" in b]
    assert len(code_chunks) > 1
    for b in code_chunks:
        assert _fences_balanced(b), b
        assert b.count("```python") == 1  # re-opened with the original fence line
        assert len(b) <= 400
    assert _payload("".join(bodies)) == _payload(md)


def test_no_line_of_code_is_cut_when_the_lines_fit_the_budget() -> None:
    md = "## Code\n\n" + _code_block(60)
    bodies = _bodies(md, 400)
    original = {ln for ln in md.split("\n") if ln.startswith("line_")}
    seen = {ln for b in bodies for ln in b.split("\n") if ln.startswith("line_")}
    assert seen == original


def test_tilde_fence_is_reopened_with_its_own_marker() -> None:
    md = "## Code\n\n" + _code_block(60, "~~~sh", "~~~")
    bodies = _bodies(md, 400)
    code_chunks = [b for b in bodies if "line_" in b]
    assert len(code_chunks) > 1
    for b in code_chunks:
        assert _fences_balanced(b)
        assert "~~~sh" in b
        assert "```" not in b


def test_a_single_overlong_line_inside_a_fence_is_sliced_with_fences_per_piece() -> None:
    md = "## Code\n\n```text\n" + "k" * 1500 + "\n```\n"
    bodies = _bodies(md, 300)
    assert len(bodies) >= 5
    for b in bodies:
        assert _fences_balanced(b)
        assert len(b) <= 300
    assert _payload("".join(bodies)) == _payload(md)


def test_an_unclosed_fence_is_closed_in_every_piece() -> None:
    md = "## Code\n\n```\n" + "\n".join("row " + "r" * 40 for _ in range(30)) + "\n"
    bodies = _bodies(md, 300)
    assert len(bodies) > 2
    assert all(_fences_balanced(b) for b in bodies)
    assert _payload("".join(bodies)) == _payload(md)


def test_a_fence_that_fits_the_budget_is_left_untouched() -> None:
    md = "## Code\n\n" + _code_block(4)
    assert _bodies(md, 10_000) == [md]


def test_hash_comment_inside_a_fence_never_starts_or_counts_as_a_heading_chunk() -> None:
    md = "## Real\n\n```sh\n" + "\n".join(f"# comment {i}" for i in range(40)) + "\n```\n"
    bodies = _bodies(md, 250)
    assert len(bodies) > 1
    assert all(_fences_balanced(b) for b in bodies)
    assert not any(_heading_only(b) for b in bodies)


# ─── invariants over a messy document at many budgets ──────────────────

_MESSY = (
    "# Title\n\n## Intro\n\nIntro paragraph " + "i" * 120 + ".\n\n"
    "## Code\n\n" + _code_block(25) + "\n"
    "### Nested heading\n\n#### Deeper\n\n" + "d" * 330 + "\n\n"
    "## Table\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
    "## Long line\n\n" + "L" * 700 + "\n\n"
    "## Closing\n\nlast words here.\n\n## Appendix\n"
)


@pytest.mark.parametrize("max_chars", list(range(80, 520, 17)))
def test_invariants_hold_at_every_budget(max_chars: int) -> None:
    chunks = chunk_markdown_by_sections(_MESSY, max_chars)
    bodies = [c.body for c in chunks]
    assert all(len(b) <= max_chars for b in bodies), [len(b) for b in bodies]
    assert not any(_heading_only(b) for b in bodies), [b for b in bodies if _heading_only(b)]
    assert all(_fences_balanced(b) for b in bodies)
    assert _payload("".join(bodies)) == _payload(_MESSY)
    assert [c.index for c in chunks] == list(range(1, len(chunks) + 1))


def _random_doc(rng: random.Random) -> str:
    parts: list[str] = []
    for _ in range(rng.randint(1, 12)):
        kind = rng.random()
        if kind < 0.25:
            parts.append("#" * rng.randint(1, 4) + f" H{rng.randint(0, 99)}")
        elif kind < 0.6:
            parts.append(" ".join(f"w{rng.randint(0, 999)}" for _ in range(rng.randint(1, 80))))
        elif kind < 0.8:
            marker = rng.choice(["```py", "~~~", "```"])
            rows = [rng.choice(["# c", "x = 1", "", "y" * rng.randint(1, 200)]) for _ in range(rng.randint(1, 25))]
            parts.append(marker + "\n" + "\n".join(rows) + "\n" + marker[:3])
        else:
            parts.append("z" * rng.randint(1, 700))
    return "\n\n".join(parts) + rng.choice(["", "\n"])


def test_invariants_hold_on_random_documents() -> None:
    """Seeded sweep: budget, balanced fences, no lone heading, no payload lost (budgets a heading run can fit)."""
    rng = random.Random(311)
    for _ in range(400):
        md, max_chars = _random_doc(rng), rng.randint(100, 600)
        bodies = _bodies(md, max_chars)
        assert all(len(b) <= max_chars for b in bodies), (max_chars, md)
        assert all(_fences_balanced(b) for b in bodies), (max_chars, md)
        assert _payload("".join(bodies)) == _payload(md), (max_chars, md)
        if len(bodies) > 1:
            assert not any(_heading_only(b) for b in bodies), (max_chars, md)

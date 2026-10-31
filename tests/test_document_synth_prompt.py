"""Document-aware synthesis prompt (#308).

Stored documents (``raw/docs/``) are synthesized with
``prompts/document_page.md`` — a document-plus-provenance input contract —
while session transcripts keep ``prompts/source_page.md``. Covers prompt
selection per item, the per-kind vault override, the document prompt's
rules and parser-facing placeholders, chunk position in document meta, the
estimate pricing documents with their own template, and the synthetic
document fixtures under ``tests/fixtures/docs_synth/``.
"""

# @spec: https://github.com/AlexanderMakarov/llm-wiki/issues/308

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth import pipeline
from llmwiki.synth.base import BaseSynthesizer, split_prompt_template
from llmwiki.synth.estimate import _rendered_template_tokens, synthesize_estimate_report
from llmwiki.synth.pipeline import (
    DOCUMENT_PROMPT_TEMPLATE_PATH,
    PROMPT_TEMPLATE_PATH,
    _load_prompt_template,
    synthesize_new_sessions,
)
from llmwiki.topics_consolidate import parse_and_cache

FIXTURES = Path(__file__).parent / "fixtures" / "docs_synth"
EXPECTATIONS = json.loads((FIXTURES / "expectations.json").read_text(encoding="utf-8"))

SESSION = "---\nslug: sess\nproject: proj\ndate: 2026-04-09\n---\n# s\n\nSESSION-BODY\n"
DOC = "---\ntitle: Policy\nslug: policy\n---\n# Policy\n\nDOC-BODY\n"


class RecordingBackend(BaseSynthesizer):
    """Records (body, meta, template) for every call; returns a real page body."""

    name = "recording"
    is_llm = False

    def __init__(self, budget: int | None = None) -> None:
        self.budget = budget
        self.calls: list[tuple[str, dict, str]] = []
        self._lock = threading.Lock()

    def usable_body_chars(self) -> int:
        return self.budget if self.budget is not None else super().usable_body_chars()

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, raw_body, meta, prompt_template, *, timeout=None):
        with self._lock:
            self.calls.append((raw_body, dict(meta), prompt_template))
        return "## Summary\n\nReal.\n\n## Connections\n\n- [[Thing]] (entity) — x\n"

    def template_for(self, marker: str) -> str:
        (tmpl,) = {t for body, _m, t in self.calls if marker in body}
        return tmpl


def _vault(tmp_path: Path, *, session: bool = True, docs: dict[str, str] | None = None) -> dict:
    raw = tmp_path / "raw" / "sessions"
    if session:
        (raw / "proj").mkdir(parents=True)
        (raw / "proj" / "2026-04-09-sess.md").write_text(SESSION, encoding="utf-8")
    docs_dir = tmp_path / "raw" / "docs"
    docs_dir.mkdir(parents=True)
    for name, text in (docs if docs is not None else {"policy.md": DOC}).items():
        (docs_dir / name).write_text(text, encoding="utf-8")
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)
    log = tmp_path / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    return dict(
        raw_dir=raw,
        docs_dir=docs_dir,
        wiki_sources_dir=sources,
        log_path=log,
        state_file=tmp_path / "state.json",
    )


# ─── selection ─────────────────────────────────────────────────────────


def test_document_gets_document_prompt_and_session_keeps_source_page(tmp_path: Path):
    backend = RecordingBackend()
    summary = synthesize_new_sessions(backend=backend, **_vault(tmp_path))
    assert summary["errors"] == []
    assert len(backend.calls) == 2

    doc_tmpl = backend.template_for("DOC-BODY")
    session_tmpl = backend.template_for("SESSION-BODY")
    assert "## Document to synthesize" in doc_tmpl
    assert "stored document" in doc_tmpl
    assert "faithfully" in doc_tmpl.lower()
    assert "## Document to synthesize" in doc_tmpl
    assert "raw session transcript" not in doc_tmpl
    assert "## Session to synthesize" in session_tmpl
    assert "raw session transcript" in session_tmpl
    assert "## Document to synthesize" not in session_tmpl



def test_vocabulary_is_injected_into_both_templates(tmp_path: Path):
    backend = RecordingBackend()
    synthesize_new_sessions(backend=backend, **_vault(tmp_path))
    for marker in ("DOC-BODY", "SESSION-BODY"):
        tmpl = backend.template_for(marker)
        assert "{vocabulary}" not in tmpl
        assert "<existing_topics>" in tmpl


# ─── per-kind vault override ───────────────────────────────────────────


def test_vault_override_is_per_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    prompts = tmp_path / "wiki" / "prompts"
    prompts.mkdir(parents=True)
    doc_override = prompts / "document_page.md"
    doc_override.write_text("CUSTOM DOC {meta} {body}", encoding="utf-8")
    monkeypatch.setattr(pipeline, "USER_DOCUMENT_PROMPT_OVERRIDE", doc_override)
    monkeypatch.setattr(pipeline, "USER_PROMPT_OVERRIDE", prompts / "source_page.md")

    assert _load_prompt_template("document") == "CUSTOM DOC {meta} {body}"
    assert _load_prompt_template("session") == PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def test_session_override_does_not_replace_the_document_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    prompts = tmp_path / "wiki" / "prompts"
    prompts.mkdir(parents=True)
    session_override = prompts / "source_page.md"
    session_override.write_text("CUSTOM SESSION {meta} {body}", encoding="utf-8")
    monkeypatch.setattr(pipeline, "USER_PROMPT_OVERRIDE", session_override)
    monkeypatch.setattr(pipeline, "USER_DOCUMENT_PROMPT_OVERRIDE", prompts / "document_page.md")

    assert _load_prompt_template("session") == "CUSTOM SESSION {meta} {body}"
    assert _load_prompt_template("document") == DOCUMENT_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def test_unknown_prompt_kind_is_rejected():
    with pytest.raises(ValueError, match="unknown prompt kind"):
        _load_prompt_template("transcript")


# ─── document prompt contract ──────────────────────────────────────────


def test_document_prompt_keeps_parser_facing_placeholders_and_format():
    text = DOCUMENT_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    for needle in (
        "{vocabulary}",
        "{meta}",
        "{body}",
        "<!-- suggested-tags:",
        "## Summary",
        "## Key Claims",
        "## Key Quotes",
        "## Connections",
        "## Contradictions",
        "(entity)",
        "(concept)",
        "  - fact:",
    ):
        assert needle in text, needle
    stable, per_page = split_prompt_template(text)
    assert "{vocabulary}" in stable
    assert per_page.startswith("## Document to synthesize")
    assert "{meta}" in per_page and "{body}" in per_page


@pytest.mark.parametrize(
    "rule",
    [
        "Attribute every statement to the document",
        "Do not narrate how the file was ingested",
        "Keep modal words as written (`may`, `must`, `shall`",
        "Keep logical operators as written (`and`, `or`, `not`, `unless`",
        "Keep exceptions and qualifiers attached to the rule they modify",
        "Never describe it as official, approved, binding, or authoritative unless the document itself says that",
        "Record material internal contradictions under ## Contradictions",
        "do not write \"None identified\" when such a conflict is present",
        "Every `fact:` bullet must be supported by the document text below",
        "never restate it, or anything else from the Existing topics list, as a `fact:`",
        "It is not evidence about this document.",
    ],
)
def test_document_prompt_states_the_fidelity_rules(rule: str):
    assert rule in DOCUMENT_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def test_document_prompt_is_self_contained_not_session_contrast():
    """Doc prompt must stand alone — no 'unlike sessions…' framing (#308)."""
    text = DOCUMENT_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    banned = (
        "NOT a session transcript",
        "not a session transcript",
        "There is no conversation",
        "no user, and no assistant",
        "not an activity",
        "this session",
        "the assistant",
        "nobody is talking",
    )
    for phrase in banned:
        assert phrase not in text, phrase


# ─── chunk position in document meta ───────────────────────────────────


def test_multi_chunk_document_meta_carries_chunk_position(tmp_path: Path):
    long_doc = "---\nslug: big\n---\n" + "\n".join(
        f"## Section {i}\n\n" + ("lorem ipsum " * 40) + "\n" for i in range(6)
    )
    backend = RecordingBackend(budget=900)
    kw = _vault(tmp_path, session=False, docs={"big.md": long_doc})
    synthesize_new_sessions(backend=backend, **kw)
    total = len(backend.calls)
    assert total > 1, "fixture must need several chunks"
    assert [m["chunk"] for _b, m, _t in backend.calls] == [f"{i} of {total}" for i in range(1, total + 1)]
    meta, _body = parse_frontmatter((kw["wiki_sources_dir"] / "docs" / "big.md").read_text(encoding="utf-8"))
    assert "chunk" not in meta


def test_single_chunk_document_meta_has_no_chunk_key(tmp_path: Path):
    backend = RecordingBackend()
    synthesize_new_sessions(backend=backend, **_vault(tmp_path, session=False))
    ((_body, meta, _tmpl),) = backend.calls
    assert "chunk" not in meta


# ─── estimate ──────────────────────────────────────────────────────────


def test_estimate_prices_documents_with_the_document_template(tmp_path: Path):
    kw = _vault(tmp_path, session=False)
    common = dict(
        raw_sessions=[],
        state_keys=set(),
        docs_root=kw["docs_dir"],
        raw_root=kw["raw_dir"],
        wiki_sources_dir=kw["wiki_sources_dir"],
        template_tokens=100,
    )
    small = synthesize_estimate_report(doc_template_tokens=100, **common)
    large = synthesize_estimate_report(doc_template_tokens=50_000, **common)
    assert large["doc_template_tokens"] == 50_000
    assert large["incremental_usd"] > small["incremental_usd"]
    assert large["template_tokens"] == small["template_tokens"] == 100


def test_estimate_measures_each_kind_from_its_own_template():
    session_tokens = _rendered_template_tokens(kind="session")
    doc_tokens = _rendered_template_tokens(kind="document")
    assert session_tokens > 0 and doc_tokens > 0
    assert session_tokens != doc_tokens


# ─── synthetic document fixtures ───────────────────────────────────────


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_fixture_text_carries_the_phrases_the_case_depends_on(name: str):
    case = EXPECTATIONS[name]
    text = (FIXTURES / name).read_text(encoding="utf-8")
    for phrase in case["must_keep"]:
        assert phrase in text, f"{name}: fixture lost {phrase!r}"
    for phrase in case["must_not_claim"]:
        assert phrase not in text, f"{name}: fixture itself states {phrase!r}"


def test_every_fixture_has_expectations():
    assert sorted(p.name for p in FIXTURES.glob("*.md")) == sorted(EXPECTATIONS)


def test_fixtures_synthesize_with_the_document_prompt(tmp_path: Path):
    kw = _vault(tmp_path, session=False, docs={})
    for name in EXPECTATIONS:
        shutil.copy(FIXTURES / name, kw["docs_dir"] / name)
    backend = RecordingBackend()
    summary = synthesize_new_sessions(backend=backend, **kw)
    assert summary["errors"] == []
    assert len(backend.calls) == len(EXPECTATIONS)
    for _body, _meta, tmpl in backend.calls:
        assert "## Document to synthesize" in tmpl
        assert "## Session to synthesize" not in tmpl
    sent = "".join(body for body, _m, _t in backend.calls)
    for case in EXPECTATIONS.values():
        for phrase in case["must_keep"]:
            assert phrase in sent


def test_topic_desc_reaches_the_document_prompt_alongside_the_anti_import_rule(tmp_path: Path):
    """A cached topic desc is offered in the document prompt's vocabulary only next to the rule forbidding it as a fact."""
    case = EXPECTATIONS["topic-desc-leak.md"]
    topic = case["topic"]
    kw = _vault(tmp_path, session=False, docs={})
    shutil.copy(FIXTURES / "topic-desc-leak.md", kw["docs_dir"] / "topic-desc-leak.md")
    wiki = tmp_path / "wiki"
    for stem in ("a", "b"):
        (wiki / "sources" / "proj").mkdir(parents=True, exist_ok=True)
        (wiki / "sources" / "proj" / f"{stem}.md").write_text(
            f"---\ntitle: {stem}\ntype: source\nproject: proj\n---\n\n"
            f"## Connections\n\n- [[{topic['name']}]] ({topic['kind']}) — x\n",
            encoding="utf-8",
        )
    parse_and_cache(
        json.dumps({"topics": [{"canonical": topic["name"], "kind": topic["kind"],
                                "description": topic["desc"], "aliases": []}], "dropped": []}),
        wiki,
    )

    backend = RecordingBackend()
    summary = synthesize_new_sessions(backend=backend, **kw)
    assert summary["errors"] == []
    tmpl = backend.template_for(case["must_keep"][0])
    assert f'desc="{topic["desc"]}"' in tmpl
    assert all(phrase in topic["desc"] for phrase in case["must_not_claim"])
    assert "never restate it, or anything else from the Existing topics list, as a `fact:`" in tmpl

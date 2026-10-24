"""Whole-feature acceptance tests: the product explains itself (#109).

# @layer: integration
# @spec: 008-make-product-explain-itself
# @regression

Checks the repository against
``context/spec/008-make-product-explain-itself/functional-spec.md`` as a whole.
Mechanics live with their modules: the serve removal and ``--local-root`` in
``tests/test_static_site_no_server.py``, the ``wiki-checks`` lint gate in
``tests/test_ci_workflow.py``, the source-checkout guard in
``tests/test_source_checkout_guard.py``.

The operator committed the synthesized ``demo/wiki/`` layer so GitHub Pages has sources, entities, concepts and pending candidates to publish. These tests pin that the knowledge layer is present, not that every page is the latest pipeline output.
"""

from __future__ import annotations

import re

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser
from llmwiki.schema import PAGE_KINDS

README = REPO_ROOT / "README.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
AGENTS = REPO_ROOT / "AGENTS.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
PAGE_KINDS_DOC = REPO_ROOT / "docs" / "reference" / "page-kinds.md"
DECLINED = REPO_ROOT / "docs" / "maintainers" / "DECLINED.md"
PAGES = REPO_ROOT / ".github" / "workflows" / "pages.yml"
PRE_PUSH = REPO_ROOT / ".githooks" / "pre-push"
DEMO = REPO_ROOT / "demo"
KIT_COMMANDS = REPO_ROOT / "llmwiki" / "agent_kit" / "commands"
KIT_SKILLS = REPO_ROOT / "llmwiki" / "agent_kit" / "skills"

_MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_HEADING = re.compile(r"^## (.+)$", re.M)


def _choices() -> set[str]:
    return set(build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001


def _readme_before_acknowledgements() -> str:
    text = README.read_text(encoding="utf-8")
    idx = text.index("## Acknowledgements")
    return text[:idx]


# ─── R1 repository shape ─────────────────────────────────────────────────


def test_demo_is_a_self_contained_vault() -> None:
    """The demo vault lives under ``demo/`` and nothing vault-shaped sits at the repo root."""
    for part in ("raw/sessions", "raw/docs", "wiki", "usage"):
        assert (DEMO / part).is_dir(), f"demo/{part} is missing"
    assert (DEMO / "README.md").is_file()
    stray = REPO_ROOT / "wiki"
    assert not stray.exists(), (
        f"{stray} exists: the demo vault must be the only wiki in the checkout; "
        "a code path or test fell back to the repo root"
    )
    assert (REPO_ROOT / ".llmwiki-source-checkout").is_file()


def test_context_is_named_contributor_tooling() -> None:
    """CONTRIBUTING tells contributors that ``context/`` is contributor tooling."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "contributor tooling" in text.lower()
    assert "context/" in text


def test_videos_and_top_level_specs_are_gone() -> None:
    """Retired top-level folders stay gone and maintainer surfaces live under docs."""
    assert not (REPO_ROOT / "docs" / "videos").exists()
    assert not (REPO_ROOT / "specs").exists()
    assert (REPO_ROOT / "docs" / "maintainers" / "surfaces").is_dir()


# ─── R2 demo corpus ──────────────────────────────────────────────────────


def test_demo_wiki_has_a_knowledge_layer_for_pages() -> None:
    """The demo ships sources, curated pages and pending candidates for the published site."""
    sources = list((DEMO / "wiki" / "sources").rglob("*.md"))
    assert len(sources) >= 20
    assert (DEMO / "wiki" / "entities" / "Claude Code.md").is_file()
    assert (DEMO / "wiki" / "concepts" / "Adapters.md").is_file()
    candidates = list((DEMO / "wiki" / "candidates").rglob("*.md"))
    assert candidates, "pending candidates should ship so the demo review UI is not empty"


def test_demo_raw_docs_are_about_llmwiki() -> None:
    """The demo's raw layer documents llmwiki itself, with enough sessions and docs to browse."""
    docs = list((DEMO / "raw" / "docs").rglob("*.md"))
    assert len(docs) >= 20
    names = " ".join(p.stem.lower() for p in docs)
    assert "getting-started" in names or "cli" in names
    sessions = list((DEMO / "raw" / "sessions").rglob("*.md"))
    assert len(sessions) >= 10


def test_demo_readme_does_not_tell_anyone_to_serve() -> None:
    """The demo README points at the static ``index.html`` and the refresh script, never a server."""
    text = (DEMO / "README.md").read_text(encoding="utf-8")
    assert "llmwiki serve" not in text
    assert "index.html" in text
    assert "refresh_demo.py" in text


# ─── R3 refresh is local; CI verifies without a model ────────────────────


def test_refresh_command_exists_and_is_not_a_cli_subcommand() -> None:
    """Demo refresh is a maintainer script with its own guide, not a product subcommand."""
    assert (REPO_ROOT / "scripts" / "refresh_demo.py").is_file()
    assert (REPO_ROOT / "docs" / "maintainers" / "REFRESH_DEMO.md").is_file()
    assert "refresh-demo" not in _choices()
    assert "refresh_demo" not in _choices()


def test_hook_and_pages_verify_the_demo_without_synth() -> None:
    """The pre-push hook dry-runs the refresh and Pages builds the committed demo without a model."""
    hook = PRE_PUSH.read_text(encoding="utf-8")
    assert "refresh_demo.py --dry-run" in hook
    pages = PAGES.read_text(encoding="utf-8")
    assert "llmwiki synth" not in pages
    assert "--vault demo" in pages


# ─── R5 live demo ────────────────────────────────────────────────────────


def test_readme_links_the_live_demo() -> None:
    """The README links the published demo, which Pages builds with a neutral local root."""
    text = README.read_text(encoding="utf-8")
    assert "https://alexandermakarov.github.io/llm-wiki/" in text
    assert "--local-root /home/user" in PAGES.read_text(encoding="utf-8")


# ─── R6 / R7 page body and kinds ─────────────────────────────────────────


def test_agent_schemas_do_not_instruct_a_description_paragraph() -> None:
    """Neither agent schema asks for the retired one-paragraph page description."""
    for path in (CLAUDE, AGENTS):
        text = path.read_text(encoding="utf-8")
        assert "One-paragraph description." not in text
        assert "\nOne paragraph.\n" not in text


def test_removed_page_kinds_are_gone_and_recorded() -> None:
    """Question and comparison pages are not page kinds, and DECLINED records why."""
    assert "question" not in PAGE_KINDS
    assert "comparison" not in PAGE_KINDS
    assert "synthesis" in PAGE_KINDS
    declined = DECLINED.read_text(encoding="utf-8")
    assert "open questions" in declined.lower() or "type: question" in declined
    assert "Comparison pages as a page kind" in declined


# ─── R8 page-kind reference ──────────────────────────────────────────────


def test_page_kinds_reference_exists_and_is_linked() -> None:
    """Every page kind is documented in the reference, which the docs index and UI guide link."""
    assert PAGE_KINDS_DOC.is_file()
    body = PAGE_KINDS_DOC.read_text(encoding="utf-8")
    for kind in PAGE_KINDS:
        assert f"`{kind}`" in body or f"type: {kind}" in body
    index = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert "reference/page-kinds.md" in index
    ui = (REPO_ROOT / "docs" / "reference" / "ui.md").read_text(encoding="utf-8")
    assert "page-kinds.md" in ui


# ─── R9 README as a product page ─────────────────────────────────────────


def test_readme_opens_with_the_benefit_not_lineage() -> None:
    """The README leads with what you get and keeps fork lineage under Acknowledgements."""
    text = README.read_text(encoding="utf-8")
    head = text[:800].lower()
    assert "session" in head or "wiki" in head
    before = _readme_before_acknowledgements()
    assert "fork" not in before.lower()
    assert "upstream this work extends" not in before
    headings = _HEADING.findall(text)
    assert headings[0] == "What you get"
    assert "Acknowledgements" in headings
    assert headings.index("Acknowledgements") < headings.index("License")


def test_readme_has_exactly_one_agent_table() -> None:
    """The README states supported agents and the Python floor once, in one table."""
    text = README.read_text(encoding="utf-8")
    assert text.count("| Agent | Supplies sessions |") == 1
    assert "core (`claude_code`)" in text
    assert "core (`codex_cli`)" in text
    assert "contrib (`chatgpt`)" in text
    assert "contrib (`opencode`)" in text
    assert "Python ≥ 3.12" in text or "Python >= 3.12" in text
    assert "review candidates" in text.lower() or "candidates.html" in text


def test_readme_relative_links_resolve() -> None:
    """Every relative link in the README points at a file in the checkout."""
    text = README.read_text(encoding="utf-8")
    checked: list[str] = []
    missing: list[str] = []
    for target in _MD_LINK.findall(text):
        href = target.split()[0].strip("<>")
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = href.split("#", 1)[0]
        if not path:
            continue
        checked.append(href)
        if not (README.parent / path).resolve().exists():
            missing.append(href)
    assert checked, "the README should carry relative links to check"
    assert missing == []


# ─── R10 agent kit ───────────────────────────────────────────────────────


def test_user_kit_ships_in_the_package_not_the_plugin_manifest() -> None:
    """User commands and skills ship in the package and install via ``install-agent-kit``."""
    assert (KIT_COMMANDS / "wiki-sync.md").is_file()
    assert (KIT_COMMANDS / "wiki-query.md").is_file()
    assert not (KIT_COMMANDS / "wiki-serve.md").exists()
    assert (KIT_SKILLS / "llmwiki-sync" / "SKILL.md").is_file()
    assert (KIT_SKILLS / "llmwiki-all" / "SKILL.md").is_file()
    assert not (KIT_SKILLS / "docs-that-work").exists()
    assert not (REPO_ROOT / ".claude-plugin").exists()
    assert (REPO_ROOT / ".claude" / "commands" / "fix-bug.md").is_file()
    assert not (REPO_ROOT / ".claude" / "commands" / "wiki-sync.md").exists()
    assert "install-agent-kit" in _choices()
    opening = CLAUDE.read_text(encoding="utf-8").split("## Three layers", 1)[0]
    assert "people changing llmwiki itself" in opening.lower()
    assert "install-agent-kit" in opening


def test_kit_files_do_not_point_at_this_repository() -> None:
    """No shipped command or skill tells a user to work inside this repository's own wiki."""
    needles = ("production-draft", "examples/demo-", "this repo's own wiki/")
    files = [*KIT_COMMANDS.glob("*.md"), *KIT_SKILLS.rglob("SKILL.md")]
    assert any(p.parent == KIT_COMMANDS for p in files), "no kit commands found"
    assert any(p.name == "SKILL.md" for p in files), "no kit skills found"
    hits = [
        f"{path.relative_to(REPO_ROOT)}: {needle}"
        for path in files
        for needle in needles
        if needle in path.read_text(encoding="utf-8")
    ]
    assert hits == []

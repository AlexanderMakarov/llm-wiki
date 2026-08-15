"""Whole-feature acceptance tests for #109: make the product explain itself.

# @layer: integration
# @spec: 008-make-product-explain-itself
# @regression

Per-slice tests already cover mechanics (source-checkout guard, page-kind
migration, refresh_demo planning, install-agent-kit, static-site no-server,
wiki-checks lint gate). This file checks the feature as a whole against
``context/spec/008-make-product-explain-itself/functional-spec.md``.

The operator committed the existing synthesized `demo/wiki/` layer so GitHub Pages has sources, entities, concepts and pending candidates to publish. A full `refresh_demo.py` regeneration (Slice 9) is still deferred — these tests pin that the knowledge layer is present, not that every page is the latest pipeline output.
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
WIKI_CHECKS = REPO_ROOT / ".github" / "workflows" / "wiki-checks.yml"
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
    assert (DEMO / "raw" / "sessions").is_dir()
    assert (DEMO / "raw" / "docs").is_dir()
    assert (DEMO / "wiki").is_dir()
    assert (DEMO / "usage").is_dir()
    assert (DEMO / "README.md").is_file()
    assert not (REPO_ROOT / "wiki").is_dir()
    assert (REPO_ROOT / ".llmwiki-source-checkout").is_file()


def test_context_is_named_contributor_tooling() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "contributor tooling" in text.lower()
    assert "`context/`" in text or "context/" in text


def test_videos_and_top_level_specs_are_gone() -> None:
    assert not (REPO_ROOT / "docs" / "videos").exists()
    assert not (REPO_ROOT / "specs").exists()
    assert (REPO_ROOT / "docs" / "maintainers" / "surfaces").is_dir()


# ─── R2 demo corpus (raw layer; wiki synth deferred) ─────────────────────


def test_demo_wiki_has_a_knowledge_layer_for_pages() -> None:
    sources = list((DEMO / "wiki" / "sources").rglob("*.md"))
    assert len(sources) >= 20
    assert (DEMO / "wiki" / "entities" / "Claude Code.md").is_file()
    assert (DEMO / "wiki" / "concepts" / "Adapters.md").is_file()
    candidates = list((DEMO / "wiki" / "candidates").rglob("*.md"))
    assert candidates, "pending candidates should ship so the demo review UI is not empty"


def test_demo_raw_docs_are_about_llmwiki() -> None:
    docs = list((DEMO / "raw" / "docs").rglob("*.md"))
    assert len(docs) >= 20
    names = " ".join(p.stem.lower() for p in docs)
    assert "getting-started" in names or "cli" in names
    sessions = list((DEMO / "raw" / "sessions").rglob("*.md"))
    assert len(sessions) >= 10


def test_demo_readme_does_not_tell_anyone_to_serve() -> None:
    text = (DEMO / "README.md").read_text(encoding="utf-8")
    assert "llmwiki serve" not in text
    assert "index.html" in text
    assert "refresh_demo.py" in text


# ─── R3 refresh is local; CI verifies without a model ────────────────────


def test_refresh_command_exists_and_is_not_a_cli_subcommand() -> None:
    assert (REPO_ROOT / "scripts" / "refresh_demo.py").is_file()
    assert (REPO_ROOT / "docs" / "maintainers" / "REFRESH_DEMO.md").is_file()
    assert "refresh-demo" not in _choices()
    assert "refresh_demo" not in _choices()


def test_ci_and_hook_verify_docs_changes_without_synth() -> None:
    wiki = WIKI_CHECKS.read_text(encoding="utf-8")
    assert "docs/**" in wiki
    assert "refresh_demo.py --dry-run" in wiki
    assert "llmwiki synth" not in wiki
    hook = PRE_PUSH.read_text(encoding="utf-8")
    assert "refresh_demo.py --dry-run" in hook
    pages = PAGES.read_text(encoding="utf-8")
    assert "llmwiki synth" not in pages
    assert "--vault demo" in pages


# ─── R4 / R5 ─────────────────────────────────────────────────────────────


def test_wiki_checks_fail_on_errors_not_strict() -> None:
    text = WIKI_CHECKS.read_text(encoding="utf-8")
    assert "--fail-on-errors" in text
    assert "lint --vault demo --strict" not in text


def test_readme_links_the_live_demo() -> None:
    text = README.read_text(encoding="utf-8")
    assert "https://alexandermakarov.github.io/llm-wiki/" in text
    assert "--local-root /home/user" in PAGES.read_text(encoding="utf-8")


# ─── R6 / R7 page body and kinds ─────────────────────────────────────────


def test_agent_schemas_do_not_instruct_a_description_paragraph() -> None:
    for path in (CLAUDE, AGENTS):
        text = path.read_text(encoding="utf-8")
        assert "One-paragraph description." not in text
        assert "\nOne paragraph.\n" not in text


def test_removed_page_kinds_are_gone_and_recorded() -> None:
    assert "question" not in PAGE_KINDS
    assert "comparison" not in PAGE_KINDS
    assert "synthesis" in PAGE_KINDS
    declined = DECLINED.read_text(encoding="utf-8")
    assert "open questions" in declined.lower() or "type: question" in declined
    assert "Comparison pages as a page kind" in declined


# ─── R8 page-kind reference ──────────────────────────────────────────────


def test_page_kinds_reference_exists_and_is_linked() -> None:
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
    text = README.read_text(encoding="utf-8")
    tables = text.count("| Agent | Supplies sessions |")
    assert tables == 1
    assert "core (`claude_code`)" in text
    assert "core (`codex_cli`)" in text
    assert "contrib (`chatgpt`)" in text
    assert "contrib (`opencode`)" in text
    assert "Python ≥ 3.12" in text or "Python >= 3.12" in text
    assert "review candidates" in text.lower() or "candidates.html" in text


def test_readme_relative_links_resolve() -> None:
    text = README.read_text(encoding="utf-8")
    missing: list[str] = []
    for target in _MD_LINK.findall(text):
        href = target.split()[0].strip("<>")
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = href.split("#", 1)[0]
        if not path:
            continue
        dest = (README.parent / path).resolve()
        if not dest.exists():
            missing.append(href)
    assert missing == []


# ─── R10 agent kit ───────────────────────────────────────────────────────


def test_user_kit_ships_in_the_package_not_the_plugin_manifest() -> None:
    assert (KIT_COMMANDS / "wiki-sync.md").is_file()
    assert (KIT_COMMANDS / "wiki-query.md").is_file()
    assert not (KIT_COMMANDS / "wiki-serve.md").exists()
    assert (KIT_SKILLS / "llmwiki-sync" / "SKILL.md").is_file()
    assert (KIT_SKILLS / "wiki-all" / "SKILL.md").is_file()
    assert not (KIT_SKILLS / "docs-that-work").exists()
    assert not (REPO_ROOT / ".claude-plugin").exists()
    assert (REPO_ROOT / ".claude" / "commands" / "fix-bug.md").is_file()
    assert not (REPO_ROOT / ".claude" / "commands" / "wiki-sync.md").exists()
    assert "install-agent-kit" in _choices()
    opening = CLAUDE.read_text(encoding="utf-8").split("## Three layers", 1)[0]
    assert "people changing llmwiki itself" in opening.lower()
    assert "install-agent-kit" in opening


def test_kit_files_do_not_point_at_this_repository() -> None:
    needles = ("production-draft", "examples/demo-", "this repo's own wiki/")
    hits: list[str] = []
    for path in KIT_COMMANDS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle in text:
                hits.append(f"{path.name}: {needle}")
    for path in KIT_SKILLS.rglob("SKILL.md"):
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle in text:
                hits.append(f"{path.relative_to(KIT_SKILLS)}: {needle}")
    assert hits == []


# ─── R12 / R13 static site ───────────────────────────────────────────────


def test_product_has_no_serve_command() -> None:
    assert "serve" not in _choices()
    assert not (REPO_ROOT / "llmwiki" / "serve.py").exists()
    assert not (REPO_ROOT / "serve.sh").exists()
    assert not (REPO_ROOT / "serve.bat").exists()


def test_build_accepts_local_root() -> None:
    parser = build_parser()
    args = parser.parse_args(["build", "--vault", "demo", "--local-root", "/home/user"])
    assert args.local_root == "/home/user"

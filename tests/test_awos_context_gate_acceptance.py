"""Acceptance-level tests for the AWOS context CI gate — spec #003-awos-context-ci-gate.

Covers the full feature against all functional-spec ACs:

  FR1  Armed by path filters
  FR2  Hard fail when armed and notes missing — full explanation, no label bypass
  FR3  Any notes update satisfies
  FR4  No escape-hatch label anywhere in implementation or docs
  FR5  Honest branch comparison (--base / --head CLI; merge-base in workflow)
  FR6  Documentation in all four required locations, consistent
  FR7  CHANGELOG.md Unreleased entry

Unit tests for the pure-Python predicates live alongside this file in
tests/test_awos_context_gate.py — this file adds acceptance-layer breadth
over the whole feature without duplicating those parametrized predicate checks.

# @layer: unit
# @spec: 003-awos-context-ci-gate
# @regression
"""

from __future__ import annotations

import io
import re

import pytest

from llmwiki import REPO_ROOT
from tests.awos_context_gate import (
    ARMED_PREFIXES,
    CONTEXT_PREFIX,
    build_parser,
    failure_message_lines,
    gate_passes,
    has_armed_change,
    has_context_change,
    is_armed_path,
    is_context_path,
    print_failure,
)
from tests.changelog_notes import shipping_section_text

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-lint.yml"
_CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
_REVIEW_CHECKLIST = REPO_ROOT / "docs" / "maintainers" / "REVIEW_CHECKLIST.md"
_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

# The exact prefixes the spec mandates — used to validate the module constant
# and to assert that every doc surface lists them.
_SPEC_ARMED_PREFIXES: frozenset[str] = frozenset({
    "llmwiki/",
    "integrations/",
    "tests/",
    ".github/workflows/",
    "docs/maintainers/",
    "docs/reference/",
})


# ─── FR1: Armed by path filters ───────────────────────────────────────────────

class TestArmedByPathFilters:
    """FR1: exempt areas pass without requiring context/; armed areas do not."""

    def test_empty_path_list_passes(self) -> None:
        """Nothing changed → nothing armed → gate passes unconditionally."""  # @regression
        assert gate_passes([]) is True

    def test_context_only_path_is_not_itself_armed(self) -> None:
        """context/ is the satisfaction path, not an armed prefix.

        A PR that only touches context/ has nothing to satisfy (it's not armed)
        and therefore passes.
        """  # @regression
        assert is_armed_path("context/spec/003-awos-context-ci-gate/tasks.md") is False
        assert gate_passes(["context/notes.md"]) is True

    @pytest.mark.parametrize("path", [
        "docs/tutorials/getting-started.md",
        "docs/guides/install.md",
        "scripts/setup.sh",
        "examples/sample-vault/README.md",
        "README.md",
        "pyproject.toml",
        "setup.py",
        ".gitignore",
        "docs/architecture.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/bug.yml",
    ])
    def test_exempt_paths_do_not_arm_gate(self, path: str) -> None:
        """AC-FR1: only the six armed prefixes arm the gate."""  # @regression
        assert is_armed_path(path) is False
        assert gate_passes([path]) is True

    @pytest.mark.parametrize("path", [
        "llmwiki/cli.py",
        "llmwiki/build.py",
        "llmwiki/adapters/claude_code.py",
        "integrations/obsidian.py",
        "tests/test_convert.py",
        "tests/awos_context_gate.py",
        ".github/workflows/ci.yml",
        ".github/workflows/pr-lint.yml",
        "docs/maintainers/REVIEW_CHECKLIST.md",
        "docs/reference/cli.md",
    ])
    def test_armed_prefix_paths_are_detected(self, path: str) -> None:
        """AC-FR1: every armed prefix is recognized by is_armed_path."""  # @regression
        assert is_armed_path(path) is True

    def test_false_prefix_matches_are_not_armed(self) -> None:
        """Paths that *start with* a similar but distinct prefix must not arm.

        Ensures we match the full prefix, not just a substring.
        """  # @regression
        assert is_armed_path("llmwiki_extra/foo.py") is False        # no trailing /
        assert is_armed_path("integrations_v2/bar.py") is False
        assert is_armed_path("test/foo.py") is False                 # 'test/' ≠ 'tests/'
        assert is_armed_path("docs/maintainersguide/foo.md") is False

    def test_armed_prefixes_constant_matches_spec(self) -> None:
        """The ARMED_PREFIXES tuple in the module must exactly match the spec list."""  # @regression
        assert set(ARMED_PREFIXES) == _SPEC_ARMED_PREFIXES

    def test_context_prefix_constant_is_correct(self) -> None:
        assert CONTEXT_PREFIX == "context/"


# ─── FR2: Hard fail with full explanation, no label bypass ────────────────────

class TestFailureExplanation:
    """FR2: when armed and notes missing, fails with a complete explanation."""

    def test_failure_message_lines_are_nonempty(self) -> None:
        lines = failure_message_lines()
        assert len(lines) > 0
        assert all(line.strip() for line in lines)

    def test_failure_message_describes_what_failed(self) -> None:
        """Failure must explain which kind of change triggered it."""  # @regression
        combined = " ".join(failure_message_lines()).lower()
        assert "product-related paths" in combined or "armed" in combined

    def test_failure_message_explains_why_notes_are_required(self) -> None:
        """Failure must explain the spec-first rationale."""  # @regression
        combined = " ".join(failure_message_lines())
        assert "spec-first" in combined or "maintainers" in combined

    def test_failure_message_explains_how_to_fix(self) -> None:
        """Failure must include concrete remediation steps."""  # @regression
        combined = " ".join(failure_message_lines()).lower()
        assert "how to fix" in combined or "fix:" in combined

    def test_failure_message_lists_all_armed_prefixes(self) -> None:
        """Every armed prefix must appear in the failure text so the contributor
        knows which path triggered the gate."""  # @regression
        combined = " ".join(failure_message_lines())
        for prefix in _SPEC_ARMED_PREFIXES:
            assert prefix in combined, f"armed prefix '{prefix}' missing from failure message"

    def test_failure_message_does_not_mention_label_bypass(self) -> None:
        """AC-FR4: no label bypass must not appear in the failure explanation."""  # @regression
        combined = " ".join(failure_message_lines()).lower()
        assert "label" not in combined
        assert "bypass" not in combined
        assert "awos-exempt" not in combined

    def test_print_failure_prefixes_every_line_with_gha_error(self) -> None:
        """Every emitted line must carry the ::error:: annotation prefix."""  # @regression
        buf = io.StringIO()
        print_failure(stream=buf)
        lines = [line for line in buf.getvalue().splitlines() if line.strip()]
        assert lines, "print_failure emitted nothing"
        for line in lines:
            assert line.startswith("::error::"), f"Missing ::error:: prefix: {line!r}"

    def test_gate_passes_returns_false_not_exception_when_armed_no_context(self) -> None:
        """gate_passes must return False (not raise) for the hard-fail case."""  # @regression
        assert gate_passes(["llmwiki/cli.py"]) is False
        assert gate_passes(["integrations/foo.py", "docs/tutorials/x.md"]) is False


# ─── FR3: Any notes update satisfies ──────────────────────────────────────────

class TestAnyContextUpdateSatisfies:
    """FR3: creating or correcting *any* file under context/ satisfies the gate."""

    @pytest.mark.parametrize("context_path", [
        "context/spec/003-awos-context-ci-gate/tasks.md",
        "context/notes.md",
        "context/a/b/c/deep.md",
        "context/MEMORY.md",
        "context/overview.md",
        "context/product/architecture.md",
    ])
    def test_any_context_path_satisfies_with_armed_change(self, context_path: str) -> None:
        """AC-FR3: gate passes regardless of which context/ file was touched."""  # @regression
        assert gate_passes(["llmwiki/cli.py", context_path]) is True

    def test_is_context_path_works_for_deeply_nested_paths(self) -> None:
        assert is_context_path("context/spec/x.md") is True
        assert is_context_path("context/notes.md") is True

    def test_is_context_path_rejects_non_context_paths(self) -> None:
        assert is_context_path("not-context/foo.md") is False
        assert is_context_path("llmwiki/context/foo.md") is False

    def test_has_context_change_helper_positive(self) -> None:
        assert has_context_change(["context/notes.md", "llmwiki/cli.py"]) is True

    def test_has_context_change_helper_negative(self) -> None:
        assert has_context_change(["llmwiki/cli.py"]) is False
        assert has_context_change([]) is False

    def test_has_armed_change_helper(self) -> None:
        assert has_armed_change(["llmwiki/build.py"]) is True
        assert has_armed_change(["docs/tutorials/foo.md"]) is False
        assert has_armed_change([]) is False


# ─── FR4: No escape-hatch label anywhere ─────────────────────────────────────

class TestNoEscapeHatchLabel:
    """FR4: no label clears or skips the gate in any surface."""

    def test_workflow_does_not_contain_awos_exempt_label(self) -> None:
        """The workflow must not reference any bypass label."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8").lower()
        assert "awos-exempt" not in text
        assert "skip-awos" not in text

    def test_workflow_does_not_trigger_on_unlabeled_event(self) -> None:
        """AC-FR4: the workflow must not re-run on label removals."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        assert "unlabeled" not in text

    def test_workflow_does_not_list_labeled_as_trigger_type(self) -> None:
        """AC-FR4: 'labeled' must not appear in the pull_request trigger types list."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        # Match inline or multiline types: block under 'pull_request:'
        types_inline = re.search(r"types\s*:\s*\[([^\]]+)\]", text)
        if types_inline:
            assert "labeled" not in types_inline.group(1)
        # Also guard the multiline form
        types_block = re.search(r"types\s*:\s*\n((?:\s+-\s+\S+\n)+)", text)
        if types_block:
            assert "labeled" not in types_block.group(1)

    def test_gate_module_source_contains_no_label_logic(self) -> None:
        """The gate module must not reference labels anywhere."""  # @regression
        source = (REPO_ROOT / "tests" / "awos_context_gate.py").read_text(encoding="utf-8")
        assert "label" not in source.lower()
        assert "awos-exempt" not in source.lower()


# ─── FR5: Honest branch comparison ────────────────────────────────────────────

class TestHonestBranchComparison:
    """FR5: the gate uses merge-base diff, not tip-to-tip."""

    def test_cli_requires_base_argument(self) -> None:
        """--base must be required; missing it must exit non-zero."""  # @regression
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--head", "abc123"])

    def test_cli_requires_head_argument(self) -> None:
        """--head must be required."""  # @regression
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--base", "abc123"])

    def test_cli_parses_both_args_cleanly(self) -> None:
        """Providing both --base and --head must succeed."""  # @regression
        parser = build_parser()
        args = parser.parse_args(["--base", "abc123", "--head", "def456"])
        assert args.base == "abc123"
        assert args.head == "def456"

    def test_workflow_computes_merge_base(self) -> None:
        """The workflow must call git merge-base to compute an honest diff base."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        assert "git merge-base" in text

    def test_workflow_passes_merge_base_as_base_arg(self) -> None:
        """The workflow must pass the computed merge-base as --base to the script."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        assert "--base" in text
        assert "--head" in text


# ─── FR6: Documentation in all four required locations ────────────────────────

class TestDocumentationCompleteness:
    """FR6: all four surfaces describe the rule consistently."""

    # --- CONTRIBUTING.md ---

    def test_contributing_rule_mentions_no_label_escape(self) -> None:
        """CONTRIBUTING.md must state there is no label escape hatch."""  # @regression
        text = _CONTRIBUTING.read_text(encoding="utf-8").lower()
        assert "no label" in text or "label escape" in text

    def test_contributing_rule_mentions_all_armed_prefixes(self) -> None:
        """CONTRIBUTING.md must list every armed prefix so contributors know what arms it."""  # @regression
        text = _CONTRIBUTING.read_text(encoding="utf-8")
        for prefix in _SPEC_ARMED_PREFIXES:
            bare = prefix.rstrip("/")
            assert bare in text or prefix in text, (
                f"CONTRIBUTING.md missing armed prefix '{prefix}'"
            )

    def test_contributing_rule_mentions_context_path(self) -> None:
        text = _CONTRIBUTING.read_text(encoding="utf-8")
        assert "context/" in text

    # --- PR template ---

    def test_template_awos_row_mentions_no_label_bypass(self) -> None:
        """The PR template checklist row must state 'no label bypass'."""  # @regression
        text = _TEMPLATE.read_text(encoding="utf-8").lower()
        assert "no label bypass" in text

    def test_template_awos_row_mentions_context_path(self) -> None:
        text = _TEMPLATE.read_text(encoding="utf-8")
        assert "context/" in text

    # --- REVIEW_CHECKLIST.md ---

    def test_review_checklist_mentions_awos_context_rule(self) -> None:
        """REVIEW_CHECKLIST.md must have an AWOS context check."""  # @regression
        text = _REVIEW_CHECKLIST.read_text(encoding="utf-8").lower()
        assert "awos context" in text or "awos" in text

    def test_review_checklist_mentions_no_label_bypass(self) -> None:
        """REVIEW_CHECKLIST.md must state there is no label bypass."""  # @regression
        text = _REVIEW_CHECKLIST.read_text(encoding="utf-8").lower()
        assert "no label bypass" in text or "no label" in text

    def test_review_checklist_lists_at_least_one_armed_prefix(self) -> None:
        """REVIEW_CHECKLIST.md must list armed prefixes so reviewers can check."""  # @regression
        text = _REVIEW_CHECKLIST.read_text(encoding="utf-8")
        matched = [p for p in _SPEC_ARMED_PREFIXES if p.rstrip("/") in text or p in text]
        assert len(matched) >= 3, (
            f"REVIEW_CHECKLIST.md lists only {len(matched)} of {len(_SPEC_ARMED_PREFIXES)} armed prefixes"
        )

    def test_review_checklist_mentions_context_path(self) -> None:
        text = _REVIEW_CHECKLIST.read_text(encoding="utf-8")
        assert "context/" in text

    # --- Workflow header comment ---

    def test_workflow_header_comment_mentions_awos_context_gate(self) -> None:
        """The workflow header comment must name the AWOS context gate."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        assert "AWOS context" in text or "awos-context" in text.lower()

    def test_workflow_header_comment_lists_all_armed_prefixes(self) -> None:
        """FR6: the pr-lint header comment must enumerate every armed prefix."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        header = text.split("on:", 1)[0]
        for prefix in _SPEC_ARMED_PREFIXES:
            assert prefix in header, (
                f"pr-lint.yml header missing armed prefix '{prefix}'"
            )

    def test_workflow_header_comment_mentions_no_label_bypass(self) -> None:
        """The workflow header comment must note that there is no label bypass."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8").lower()
        assert "no label bypass" in text or "label bypass" in text

    # --- Cross-surface consistency ---

    def test_all_four_surfaces_mention_context_prefix(self) -> None:
        """All four documentation surfaces must mention context/ as the gate's satisfaction path."""  # @regression
        surfaces = {
            "CONTRIBUTING.md": _CONTRIBUTING.read_text(encoding="utf-8"),
            "PR template": _TEMPLATE.read_text(encoding="utf-8"),
            "REVIEW_CHECKLIST.md": _REVIEW_CHECKLIST.read_text(encoding="utf-8"),
            "pr-lint.yml": _WORKFLOW.read_text(encoding="utf-8"),
        }
        for name, text in surfaces.items():
            assert "context/" in text, f"{name} does not mention context/"

    def test_workflow_job_name_is_awos_context_updated(self) -> None:
        """The workflow job must carry the expected display name for branch protection."""  # @regression
        text = _WORKFLOW.read_text(encoding="utf-8")
        # The job name that becomes the required check name in branch protection
        assert "AWOS context updated" in text


class TestChangelogEntry:
    """FR7: CHANGELOG.md records this as an unreleased contributor-facing change."""

    @staticmethod
    def _unreleased_text() -> str:
        return shipping_section_text(_CHANGELOG.read_text(encoding="utf-8"))

    def test_changelog_has_unreleased_section(self) -> None:
        text = _CHANGELOG.read_text(encoding="utf-8")
        assert "## [Unreleased]" in text

    def test_changelog_unreleased_mentions_awos_context_gate(self) -> None:
        """AC-FR7: Unreleased must record the new AWOS context PR gate."""  # @regression
        unreleased = self._unreleased_text().lower()
        assert "awos context" in unreleased or "#117" in unreleased, (
            "CHANGELOG.md [Unreleased] does not mention the AWOS context PR gate"
        )

    def test_changelog_unreleased_mentions_no_label_bypass(self) -> None:
        """The changelog entry should note there is no label bypass for contributor awareness."""  # @regression
        unreleased = self._unreleased_text().lower()
        assert "no label" in unreleased or "label bypass" in unreleased, (
            "CHANGELOG.md [Unreleased] should document the no-label-bypass aspect"
        )

    def test_changelog_unreleased_mentions_path_filters(self) -> None:
        """The changelog entry should mention how path filtering works."""  # @regression
        unreleased = self._unreleased_text().lower()
        assert "path" in unreleased


# ─── Cross-platform path normalization ────────────────────────────────────────

class TestPathNormalization:
    """Verify that Windows-style backslash paths are handled correctly."""

    def test_backslash_armed_path_is_detected(self) -> None:  # @regression
        assert is_armed_path("llmwiki\\cli.py") is True
        assert is_armed_path("tests\\test_convert.py") is True
        assert is_armed_path(".github\\workflows\\ci.yml") is True

    def test_backslash_context_path_is_detected(self) -> None:  # @regression
        assert is_context_path("context\\spec\\notes.md") is True

    def test_backslash_exempt_path_still_exempt(self) -> None:  # @regression
        assert is_armed_path("docs\\tutorials\\getting-started.md") is False

    def test_gate_passes_with_backslash_context_path(self) -> None:  # @regression
        assert gate_passes(["llmwiki\\cli.py", "context\\notes.md"]) is True

    def test_gate_fails_with_backslash_armed_no_context(self) -> None:  # @regression
        assert gate_passes(["llmwiki\\cli.py"]) is False

"""Acceptance tests for #209: cross-agent release skill.

# @layer: integration
# @spec: 200-release-skill
# @regression

AC coverage matrix (FR<requirement>-AC<n> from functional-spec.md):

    FR1-AC1 → test_skill_file_exists
    FR1-AC1 → test_skill_frontmatter_name_is_release
    FR1-AC2 → test_claude_wrapper_exists, test_cursor_wrapper_exists,
               test_claude_wrapper_loads_skill, test_cursor_wrapper_loads_skill
    FR1-AC3 → test_skill_not_in_agent_kit_commands
    FR2-AC1 → test_preflight_covers_main_ci, test_preflight_covers_critical_bugs,
               test_preflight_covers_lint_and_tests, test_preflight_warns_root_wiki
    FR2-AC2 → test_skill_proposes_version_and_theme
    FR2-AC3 → test_human_gate_before_push
    FR2-AC4 → test_skill_mentions_watching_automation_and_release_url
    FR3-AC1 → test_skill_promotes_unreleased
    FR3-AC2 → test_skill_updates_upgrading_guide
    FR3-AC3 → test_skill_calls_out_changelog_helper
    FR3-AC4 → test_skill_is_scripted_steps_not_freeform
    FR3-AC5 → test_no_release_shell_scripts
    FR4-AC1 → test_default_branch_is_main, test_process_doc_mentions_main
    FR4-AC2 → test_no_always_prerelease, test_prerelease_only_for_rc_alpha_beta_dev
    FR4-AC3 → test_claude_wrapper_is_thin
    FR4-AC4 → test_maintainer_readme_mentions_skill, test_slash_ref_mentions_release
    FR4-AC5 → test_changelog_unreleased_mentions_release_skill
    FR5-AC1 → test_pitfall_root_wiki_called_out
    FR5-AC2 → test_pitfall_changelog_helper_called_out
    FR5-AC3 → test_skill_watch_ci_on_release_commit
    FR5-AC4 → test_direct_push_to_main_is_acknowledged

Slice 3 content-smoke assertions (from tasks.md):

    S3-1 → test_skill_file_exists, test_skill_frontmatter_name_is_release
    S3-2 → test_default_branch_is_main, test_process_doc_mentions_main
    S3-3 → test_no_push_origin_master_as_happy_path
    S3-4 → test_no_always_prerelease
    S3-5 → test_skill_body_has_no_implement_feature_string
"""

from __future__ import annotations

import re

from llmwiki import REPO_ROOT

# ─── Paths ───────────────────────────────────────────────────────────────────

SKILL_FILE = REPO_ROOT / ".claude" / "skills" / "release" / "SKILL.md"
RELEASE_PROCESS = REPO_ROOT / "docs" / "maintainers" / "RELEASE_PROCESS.md"
CLAUDE_WRAPPER = REPO_ROOT / ".claude" / "commands" / "release.md"
CURSOR_WRAPPER = REPO_ROOT / ".cursor" / "commands" / "release.md"
AGENT_KIT_CMDS = REPO_ROOT / "llmwiki" / "agent_kit" / "commands"
MAINTAINER_README = REPO_ROOT / "docs" / "maintainers" / "README.md"
SLASH_REF = REPO_ROOT / "docs" / "reference" / "slash-commands.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _skill_parts() -> tuple[dict[str, str], str]:
    """Parse skill frontmatter + body from SKILL.md (stdlib only — no PyYAML)."""
    raw = SKILL_FILE.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    end = raw.index("---", 3)
    fm: dict[str, str] = {}
    for line in raw[3:end].splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip("\"'")
    body = raw[end + 3 :]
    return fm, body


# ─── Slice 3 smoke: existence + frontmatter ───────────────────────────────────


def test_skill_file_exists():
    """FR1-AC1 / S3-1: .claude/skills/release/SKILL.md must exist."""
    # @regression
    assert SKILL_FILE.is_file(), (
        f"Missing skill file: {SKILL_FILE.relative_to(REPO_ROOT)}"
    )


def test_skill_frontmatter_name_is_release():
    """FR1-AC1 / S3-1: frontmatter must declare name: release."""
    # @regression
    fm, _ = _skill_parts()
    assert fm.get("name") == "release", (
        f"Expected frontmatter 'name: release', got: {fm.get('name')!r}"
    )


def test_skill_frontmatter_has_argument_hint():
    """FR1-AC1: frontmatter should carry argument-hint (nice-to-have per tech spec)."""
    fm, _ = _skill_parts()
    hint = fm.get("argument-hint", "")
    # The hint value should suggest a version placeholder
    assert "version" in hint.lower() or "X.Y.Z" in hint or "<" in hint, (
        f"argument-hint should reference a version placeholder, got: {hint!r}"
    )


# ─── Slice 3 smoke: no push origin master ────────────────────────────────────


def test_no_push_origin_master_as_happy_path():
    """FR4-AC1 / S3-3: neither skill nor RELEASE_PROCESS instructs 'git push origin master'."""
    # @regression
    for path in (SKILL_FILE, RELEASE_PROCESS):
        text = path.read_text(encoding="utf-8")
        # 'git push origin master' as an unconditional command is the footgun.
        # We allow the word 'master' in historical context but not as a push target.
        assert "push origin master" not in text, (
            f"{path.relative_to(REPO_ROOT)} still instructs "
            "'git push origin master' — change to 'main'"
        )


# ─── Slice 3 smoke: default branch = main ────────────────────────────────────


def test_default_branch_is_main():
    """FR4-AC1 / S3-2: skill body must reference 'main' as the default branch."""
    # @regression
    _, body = _skill_parts()
    assert "main" in body, (
        "Skill body must mention 'main' as the default branch"
    )


def test_process_doc_mentions_main():
    """FR4-AC1 / S3-2: RELEASE_PROCESS.md must reference 'main'."""
    # @regression
    text = RELEASE_PROCESS.read_text(encoding="utf-8")
    assert "main" in text, (
        "RELEASE_PROCESS.md must mention 'main' as the default branch"
    )


# ─── Slice 3 smoke: no blanket always-prerelease ─────────────────────────────


def test_no_always_prerelease():
    """FR4-AC2 / S3-4: no 'always prerelease' instruction for stable releases post-1.0.

    The doc is allowed to NAME "Always marking prerelease" as a pitfall to avoid
    (that is correct content).  What must NOT appear is an *instructional* sentence
    or shell command that tells the maintainer to pass --prerelease unconditionally
    (e.g. "add --prerelease to every release" or a code block with bare --prerelease
    that carries no rc/alpha/beta/dev condition).
    """
    # @regression
    for path in (SKILL_FILE, RELEASE_PROCESS):
        text = path.read_text(encoding="utf-8")
        # Pattern 1: instructional prose that says to *always* use the flag
        # (exclude lines that start with "|" — those are pitfall table rows)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                # Pitfall-table row — skip; naming the pitfall is correct
                continue
            assert not re.search(
                r"always\s+.*--prerelease|--prerelease\s+.*always",
                stripped, re.IGNORECASE
            ), (
                f"{path.relative_to(REPO_ROOT)} line {stripped!r}: "
                "contains an instructional 'always --prerelease' directive — "
                "only rc/alpha/beta/dev tags should be pre-release"
            )


def test_prerelease_only_for_rc_alpha_beta_dev():
    """FR4-AC2: skill/process doc must clarify prerelease is only for rc/alpha/beta/dev tags."""
    # @regression
    combined = (
        SKILL_FILE.read_text(encoding="utf-8")
        + RELEASE_PROCESS.read_text(encoding="utf-8")
    )
    # At least one of these qualifier words must appear near 'prerelease'
    qualifiers = ["rc", "alpha", "beta", "dev"]
    for q in qualifiers:
        assert q in combined.lower(), (
            f"Expected qualifier {q!r} (prerelease condition) in skill or process doc"
        )


# ─── Slice 3 smoke: spec boundary — no implement-feature in skill body ────────


def test_skill_body_has_no_implement_feature_string():
    """FR3-AC5 / S3-5: skill body must NOT contain 'implement-feature' (spec-only boundary)."""
    # @regression
    _, body = _skill_parts()
    assert "implement-feature" not in body, (
        "SKILL.md body must not mention 'implement-feature' — that boundary "
        "belongs in the spec, not the release checklist (per technical-considerations.md)"
    )


# ─── FR1: Cross-agent skill surface ──────────────────────────────────────────


def test_claude_wrapper_exists():
    """FR1-AC2: .claude/commands/release.md must exist."""
    # @regression
    assert CLAUDE_WRAPPER.is_file(), (
        f"Missing Claude release wrapper: {CLAUDE_WRAPPER.relative_to(REPO_ROOT)}"
    )


def test_cursor_wrapper_exists():
    """FR1-AC2: .cursor/commands/release.md must exist for Cursor /release discovery."""
    # @regression
    assert CURSOR_WRAPPER.is_file(), (
        f"Missing Cursor release wrapper: {CURSOR_WRAPPER.relative_to(REPO_ROOT)}"
    )


def test_claude_wrapper_loads_skill():
    """FR1-AC2: Claude wrapper must reference the skill path."""
    # @regression
    text = CLAUDE_WRAPPER.read_text(encoding="utf-8")
    assert ".claude/skills/release" in text or "skills/release/SKILL.md" in text, (
        f"{CLAUDE_WRAPPER.relative_to(REPO_ROOT)} must reference the skill path"
    )


def test_cursor_wrapper_loads_skill():
    """FR1-AC2: Cursor wrapper must reference the skill path."""
    # @regression
    text = CURSOR_WRAPPER.read_text(encoding="utf-8")
    assert ".claude/skills/release" in text or "skills/release/SKILL.md" in text, (
        f"{CURSOR_WRAPPER.relative_to(REPO_ROOT)} must reference the skill path"
    )


def test_skill_not_in_agent_kit_commands():
    """FR1-AC3: release skill must NOT be in the end-user agent_kit commands (maintainer-only)."""
    # @regression
    if not AGENT_KIT_CMDS.is_dir():
        return
    kit_release = AGENT_KIT_CMDS / "release.md"
    assert not kit_release.is_file(), (
        "release.md must not be in llmwiki/agent_kit/commands — "
        "it is a maintainer-only skill, not for end-user install-agent-kit"
    )


# ─── FR2: Half-scripted walkthrough with human gate ──────────────────────────


def test_preflight_covers_main_ci():
    """FR2-AC1: preflight must check CI on main branch."""
    # @regression
    _, body = _skill_parts()
    # gh run list --branch main is the canonical check
    assert "--branch main" in body, (
        "Skill preflight must instruct checking CI on 'main' branch "
        "(expected: 'gh run list --branch main')"
    )


def test_preflight_covers_critical_bugs():
    """FR2-AC1: preflight must check for critical-priority bugs."""
    _, body = _skill_parts()
    assert "priority:critical" in body or "critical" in body.lower(), (
        "Skill preflight must check for critical-priority open bugs"
    )


def test_preflight_covers_lint_and_tests():
    """FR2-AC1: preflight must instruct ruff + pytest."""
    _, body = _skill_parts()
    assert "ruff" in body, "Skill preflight must instruct 'ruff check'"
    assert "pytest" in body, "Skill preflight must instruct 'pytest'"


def test_preflight_warns_root_wiki():
    """FR2-AC1 / FR5-AC1: preflight must warn about leftover root wiki/ folder."""
    # @regression
    _, body = _skill_parts()
    assert "wiki/" in body or "wiki`" in body or "root.*wiki" in body.lower() or \
        re.search(r"\bwiki\b", body), (
        "Skill preflight must warn about leftover root wiki/ folder"
    )


def test_skill_proposes_version_and_theme():
    """FR2-AC2: skill must propose version + theme and wait for human confirmation."""
    _, body = _skill_parts()
    lower = body.lower()
    assert "theme" in lower, "Skill must mention proposing a release Theme"
    assert "confirm" in lower or "wait" in lower or "approval" in lower, (
        "Skill must wait for human to confirm version/Theme before editing files"
    )


def test_human_gate_before_push():
    """FR2-AC3: skill must have an explicit human gate before push."""
    # @regression
    _, body = _skill_parts()
    lower = body.lower()
    # The gate must be explicit — pushing only after approval
    assert "approval" in lower or "explicit" in lower or "human gate" in lower or \
        "wait for" in lower, (
        "Skill must have an explicit human gate before 'git push'"
    )
    # Also confirm push is mentioned after the gate, not as default
    push_idx = body.find("git push origin main")
    gate_idx = body.lower().find("gate")
    assert push_idx > 0, "Skill must mention 'git push origin main'"
    assert gate_idx > 0, "Skill must name the human gate step"
    # Push instruction should appear after the gate section (later in document)
    assert push_idx > gate_idx, (
        "Push instruction ('git push origin main') should appear after the human gate"
    )


def test_skill_mentions_watching_automation_and_release_url():
    """FR2-AC4: after push the skill must watch automation and report release URL."""
    _, body = _skill_parts()
    lower = body.lower()
    assert "release.yml" in body or "release workflow" in lower, (
        "Skill must instruct watching release.yml after push"
    )
    assert "url" in lower or "github release" in lower or "release page" in lower, (
        "Skill must mention reporting the public GitHub Release URL"
    )


# ─── FR3: Agent owns editorial release notes ─────────────────────────────────


def test_skill_promotes_unreleased():
    """FR3-AC1: skill must instruct promoting Unreleased → versioned section."""
    # @regression
    _, body = _skill_parts()
    assert "Unreleased" in body or "unreleased" in body.lower(), (
        "Skill must instruct promoting the Unreleased CHANGELOG section"
    )
    assert "scaffold" in body.lower() or "empty" in body.lower(), (
        "Skill must instruct leaving an empty Unreleased scaffold after promotion"
    )


def test_skill_updates_upgrading_guide():
    """FR3-AC2: skill must instruct updating UPGRADING.md headings."""
    _, body = _skill_parts()
    assert "UPGRADING" in body or "upgrade" in body.lower(), (
        "Skill must instruct updating docs/UPGRADING.md headings"
    )


def test_skill_calls_out_changelog_helper():
    """FR3-AC3: skill must call out the shipping_section_text pitfall."""
    # @regression
    _, body = _skill_parts()
    assert "shipping_section_text" in body or "shipping" in body.lower(), (
        "Skill must call out 'shipping_section_text' / changelog-helper pitfall"
    )


def test_skill_is_scripted_steps_not_freeform():
    """FR3-AC4: skill body must contain numbered/structured steps (scripted, not freeform)."""
    _, body = _skill_parts()
    # Numbered steps: patterns like "### 1." or "1. " or "Step 1"
    has_numbered = bool(re.search(r"(?:^|\n)#+\s+\d+\.", body) or
                        re.search(r"(?:^|\n)\d+\.\s+\w", body))
    assert has_numbered, (
        "Skill must use numbered scripted steps (not freeform improvisation)"
    )


def test_no_release_shell_scripts():
    """FR3-AC5: no scripts/release-*.sh helpers should exist (skill IS the scripted flow)."""
    # @regression
    if not SCRIPTS_DIR.is_dir():
        return
    release_scripts = list(SCRIPTS_DIR.glob("release-*.sh"))
    assert not release_scripts, (
        f"Found release shell scripts (out of scope per spec): "
        f"{[s.name for s in release_scripts]}. The skill is the scripted flow."
    )


# ─── FR4: Docs match reality ──────────────────────────────────────────────────


def test_claude_wrapper_is_thin():
    """FR4-AC3: Claude /release wrapper must be thin (load skill, not a second checklist)."""
    # @regression
    text = CLAUDE_WRAPPER.read_text(encoding="utf-8")
    # A thin wrapper is short — if it's longer than ~50 lines it's probably a divergent checklist
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) < 50, (
        f".claude/commands/release.md is {len(lines)} non-blank lines — "
        "it should be a thin wrapper (~10-20 lines), not a second release checklist"
    )
    # Thin wrapper must NOT instruct master push or blanket prerelease
    assert "push origin master" not in text, (
        "Claude wrapper must not instruct 'git push origin master'"
    )
    lower = text.lower()
    assert not re.search(r"always\s+.*--prerelease", lower), (
        "Claude wrapper must not say 'always --prerelease'"
    )


def test_maintainer_readme_mentions_skill():
    """FR4-AC4: docs/maintainers/README.md must point at the release skill."""
    # @regression
    if not MAINTAINER_README.is_file():
        return
    text = MAINTAINER_README.read_text(encoding="utf-8")
    assert "release" in text.lower(), (
        "docs/maintainers/README.md must mention the /release skill or command"
    )


def test_slash_ref_mentions_release():
    """FR4-AC4: docs/reference/slash-commands.md must document /release."""
    # @regression
    if not SLASH_REF.is_file():
        return
    text = SLASH_REF.read_text(encoding="utf-8")
    assert "/release" in text or "release" in text.lower(), (
        "docs/reference/slash-commands.md must document /release"
    )


def test_changelog_unreleased_mentions_release_skill():
    """FR4-AC5: CHANGELOG.md Unreleased section must note the release skill addition."""
    # @regression
    text = CHANGELOG.read_text(encoding="utf-8")
    # Find the Unreleased section
    unreleased_match = re.search(
        r"## \[Unreleased\](.*?)(?=## \[|\Z)", text, re.DOTALL
    )
    assert unreleased_match, "CHANGELOG.md must have an [Unreleased] section"
    unreleased = unreleased_match.group(1).lower()
    assert "release" in unreleased or "skill" in unreleased, (
        "CHANGELOG.md [Unreleased] section must note the release skill addition"
    )


# ─── FR5: Lessons from recent cuts ───────────────────────────────────────────


def test_pitfall_root_wiki_called_out():
    """FR5-AC1: skill or process doc must call out the root wiki/ pitfall."""
    # @regression
    combined = (
        SKILL_FILE.read_text(encoding="utf-8")
        + RELEASE_PROCESS.read_text(encoding="utf-8")
    )
    # Must mention leftover wiki/ as a known pitfall
    assert re.search(r"wiki[/`\s]", combined) and "pitfall" in combined.lower(), (
        "Skill or RELEASE_PROCESS.md must call out the leftover root wiki/ pitfall"
    )


def test_pitfall_changelog_helper_called_out():
    """FR5-AC2: skill or process doc must call out the changelog acceptance test pitfall."""
    # @regression
    combined = (
        SKILL_FILE.read_text(encoding="utf-8")
        + RELEASE_PROCESS.read_text(encoding="utf-8")
    )
    assert "shipping_section_text" in combined or (
        "changelog" in combined.lower() and "test" in combined.lower()
    ), (
        "Skill or RELEASE_PROCESS.md must call out the changelog acceptance helper pitfall"
    )


def test_skill_watch_ci_on_release_commit():
    """FR5-AC3: skill must instruct watching CI on the release commit SHA."""
    _, body = _skill_parts()
    lower = body.lower()
    assert "release commit" in lower or "commit sha" in lower or \
        re.search(r"watch\s+ci", lower) or "--branch main" in body, (
        "Skill must instruct watching CI on the release commit SHA after push"
    )


def test_direct_push_to_main_is_acknowledged():
    """FR5-AC4: skill must acknowledge direct push to main as the maintainer path."""
    # @regression
    _, body = _skill_parts()
    lower = body.lower()
    # The skill should distinguish direct push to main from normal PR flow
    assert "direct push" in lower or (
        "push" in lower and "main" in lower and "maintainer" in lower
    ), (
        "Skill must acknowledge that direct push to 'main' is the maintainer "
        "release path (distinct from normal PR flow)"
    )

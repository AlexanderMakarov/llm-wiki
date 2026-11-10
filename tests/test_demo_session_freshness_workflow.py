"""The demo site's session dates must not silently age out between releases.

# @layer: unit
# @spec: 225-demo-release-freshness
# @regression

``demo-session-freshness.yml`` runs on a schedule (every six days at 04:00 UTC)
and on workflow_dispatch. It redates demo sessions to today, builds the site with
``--vault demo``, deploys to GitHub Pages (shared concurrency group with pages.yml),
and asserts the live version afterwards.

Structural text assertions mirror the style of ``tests/test_pages_deploy.py``:
the failure mode is a future edit that quietly drops a trigger, a guard, or a
step, which a substring check catches without importing a YAML parser.
"""

from __future__ import annotations

import re

import pytest

from llmwiki import REPO_ROOT

FRESHNESS_YML = REPO_ROOT / ".github" / "workflows" / "demo-session-freshness.yml"

# Docs that must cross-reference the freshness workflow
RELEASE_PROCESS = REPO_ROOT / "docs" / "maintainers" / "RELEASE_PROCESS.md"
UPTIME_DOC = REPO_ROOT / "docs" / "uptime.md"
GITHUB_PAGES_DOC = REPO_ROOT / "docs" / "deploy" / "github-pages.md"
SKILL_FILE = REPO_ROOT / ".claude" / "skills" / "release" / "SKILL.md"
REFRESH_DEMO_DOC = REPO_ROOT / "docs" / "maintainers" / "REFRESH_DEMO.md"
GENERATOR_SCRIPT = REPO_ROOT / "scripts" / "generate_demo_sessions.py"


@pytest.fixture(scope="module")
def freshness_yml() -> str:
    assert FRESHNESS_YML.is_file(), (
        ".github/workflows/demo-session-freshness.yml is missing — "
        "the demo session freshness gate has no publisher"
    )
    return FRESHNESS_YML.read_text(encoding="utf-8")


# ─── existence ────────────────────────────────────────────────────────


def test_freshness_workflow_file_exists():
    """Workflow file must exist so the freshness gate is active."""
    assert FRESHNESS_YML.is_file(), (
        "demo-session-freshness.yml not found — "
        "the scheduled freshness gate will never run without it"
    )


# ─── triggers ─────────────────────────────────────────────────────────


def test_freshness_workflow_has_cron_schedule(freshness_yml: str):
    """Cron schedule '0 4 */6 * *' must be present so the job runs automatically."""
    assert "0 4 */6 * *" in freshness_yml, (
        "cron '0 4 */6 * *' not found — demo sessions will never be redated without a schedule"
    )


def test_freshness_workflow_has_workflow_dispatch(freshness_yml: str):
    """workflow_dispatch must be present to allow manual triggering."""
    assert "workflow_dispatch:" in freshness_yml, (
        "workflow_dispatch: missing — manual runs are required for recovery and testing"
    )


# ─── session redating ─────────────────────────────────────────────────


def test_freshness_workflow_invokes_generate_demo_sessions(freshness_yml: str):
    """generate_demo_sessions must appear in a run step so sessions get redated."""
    assert "generate_demo_sessions" in freshness_yml, (
        "generate_demo_sessions not found — the workflow won't redate demo sessions"
    )


def test_freshness_workflow_passes_utc_date_to_generator(freshness_yml: str):
    """date -u must be present so the generator uses UTC, not the runner's local time."""
    assert "date -u" in freshness_yml, (
        "'date -u' not found — session dates would be set from the runner's local timezone, not UTC"
    )


# ─── build ────────────────────────────────────────────────────────────


def test_freshness_workflow_builds_with_vault_demo(freshness_yml: str):
    """Build step must use 'llmwiki build' with '--vault demo'."""
    assert "llmwiki build" in freshness_yml, (
        "'llmwiki build' not found — the workflow never compiles the demo site"
    )
    assert "--vault demo" in freshness_yml, (
        "'--vault demo' not found — the build targets the wrong vault"
    )


# ─── deploy ───────────────────────────────────────────────────────────


def test_freshness_workflow_uploads_pages_artifact(freshness_yml: str):
    """upload-pages-artifact must be present to stage the site for Pages."""
    assert "upload-pages-artifact" in freshness_yml, (
        "upload-pages-artifact not found — the built site will never reach GitHub Pages"
    )


def test_freshness_workflow_deploys_pages(freshness_yml: str):
    """deploy-pages action must be present so the site is actually published."""
    assert "deploy-pages" in freshness_yml, (
        "deploy-pages not found — the workflow uploads an artifact but never deploys it"
    )


# ─── post-deploy version check ────────────────────────────────────────


def test_freshness_workflow_checks_live_version_after_deploy(freshness_yml: str):
    """check_live_version must run after deploy-pages in the deploy job."""
    # TEMP (#225 branch dry-run) may comment the whole deploy job so
    # workflow_dispatch on a feature branch can prove redate+build without
    # publishing. Still require the publish+assert path to remain in-file
    # (commented) and in order — restore the active job before merge.
    if "TEMP (#225 branch dry-run)" in freshness_yml:
        assert "deploy-pages" in freshness_yml, (
            "TEMP dry-run must keep deploy-pages in the commented publish path"
        )
        assert "check_live_version" in freshness_yml, (
            "TEMP dry-run must keep check_live_version in the commented publish path"
        )
        assert freshness_yml.find("deploy-pages") < freshness_yml.find("check_live_version"), (
            "check_live_version must still follow deploy-pages in the TEMP-commented path"
        )
        return
    deploy_job = freshness_yml.split("  deploy:", 1)
    assert len(deploy_job) == 2, "freshness workflow has no 'deploy:' job"
    body = deploy_job[1]
    deployed_at = body.find("deploy-pages")
    checked_at = body.find("check_live_version")
    assert deployed_at != -1, "deploy job does not invoke deploy-pages"
    assert checked_at != -1, (
        "check_live_version not found in deploy job — "
        "a green deploy only proves the artifact was accepted, not that the site is fresh"
    )
    assert deployed_at < checked_at, (
        "check_live_version runs before deploy-pages — it would read the previous deploy"
    )


# ─── concurrency ──────────────────────────────────────────────────────


def test_freshness_workflow_uses_pages_concurrency_group(freshness_yml: str):
    """Concurrency group must be 'pages' to share the lock with pages.yml."""
    assert 'group: "pages"' in freshness_yml or "group: 'pages'" in freshness_yml, (
        "concurrency group 'pages' not found — simultaneous freshness and release deploys will race"
    )


# ─── safety guards ────────────────────────────────────────────────────


def test_freshness_workflow_does_not_git_push(freshness_yml: str):
    """No run: step must invoke 'git push' — freshness is Pages-only, no commits."""
    # Extract only the content of run: blocks (inline and multiline) and check
    # none of them contain "git push".
    run_block_pattern = re.compile(r"^\s+run:\s+(.+)", re.MULTILINE)
    # Also capture the pipe-multiline variant (run: |)
    multiline_run_pattern = re.compile(r"^\s+run:\s*\|\s*\n((?:[ \t]+.+\n?)*)", re.MULTILINE)

    run_lines: list[str] = []
    for m in run_block_pattern.finditer(freshness_yml):
        run_lines.append(m.group(1))
    for m in multiline_run_pattern.finditer(freshness_yml):
        run_lines.extend(m.group(1).splitlines())

    violations = [line for line in run_lines if "git push" in line]
    assert not violations, (
        f"run: step(s) invoke 'git push' — freshness must be Pages-only, no commits: {violations}"
    )


def test_freshness_workflow_does_not_invoke_llmwiki_synth(freshness_yml: str):
    """'llmwiki synth' must not appear — freshness skips LLM synthesis steps."""
    run_block_pattern = re.compile(r"^\s+run:\s+(.+)", re.MULTILINE)
    multiline_run_pattern = re.compile(r"^\s+run:\s*\|\s*\n((?:[ \t]+.+\n?)*)", re.MULTILINE)

    run_lines: list[str] = []
    for m in run_block_pattern.finditer(freshness_yml):
        run_lines.append(m.group(1))
    for m in multiline_run_pattern.finditer(freshness_yml):
        run_lines.extend(m.group(1).splitlines())

    violations = [line for line in run_lines if "llmwiki synth" in line]
    assert not violations, (
        f"run: step(s) invoke 'llmwiki synth' — freshness must not run LLM synthesis: {violations}"
    )


def test_freshness_workflow_does_not_invoke_refresh_demo(freshness_yml: str):
    """'refresh_demo.py' must not appear as a run command — that script is not used here."""
    run_block_pattern = re.compile(r"^\s+run:\s+(.+)", re.MULTILINE)
    multiline_run_pattern = re.compile(r"^\s+run:\s*\|\s*\n((?:[ \t]+.+\n?)*)", re.MULTILINE)

    run_lines: list[str] = []
    for m in run_block_pattern.finditer(freshness_yml):
        run_lines.append(m.group(1))
    for m in multiline_run_pattern.finditer(freshness_yml):
        run_lines.extend(m.group(1).splitlines())

    violations = [line for line in run_lines if "refresh_demo" in line]
    assert not violations, (
        f"run: step(s) invoke refresh_demo — that script must not be called here: {violations}"
    )


# ─── checkout safety ──────────────────────────────────────────────────


def test_freshness_workflow_build_job_checkout_does_not_pin_release_tag(freshness_yml: str):
    """The build job's first checkout must not use 'ref:' with a release-tag pattern.

    Pinning to a tag would mean the freshness run builds stale code rather than
    main, defeating the purpose of the workflow.
    """
    build_job_text = freshness_yml.split("  build:", 1)
    assert len(build_job_text) == 2, "freshness workflow has no 'build:' job"
    build_body = build_job_text[1]

    # Grab just the first checkout block within the build job
    # (stop before the deploy job to avoid false positives from the post-deploy checkout)
    deploy_boundary = build_body.find("  deploy:")
    build_section = build_body[:deploy_boundary] if deploy_boundary != -1 else build_body

    first_checkout_end = build_section.find("actions/checkout")
    assert first_checkout_end != -1, "build job has no actions/checkout step"

    # Find the block following that first checkout action
    after_checkout = build_section[first_checkout_end:]
    # The next step starts at the next "      - " marker; grab the checkout block
    next_step = re.search(r"\n      - ", after_checkout[1:])
    checkout_block = after_checkout[: next_step.start() + 1] if next_step else after_checkout

    tag_ref_pattern = re.compile(r"ref:\s*['\"]?v\d", re.IGNORECASE)
    assert not tag_ref_pattern.search(checkout_block), (
        "build job's first checkout pins 'ref:' to a release tag — "
        "freshness should always build from the current default branch"
    )


# ─── docs coverage (#225) ─────────────────────────────────────────────────────
# These tests guard against the docs reverting to a state where the freshness
# workflow is undocumented or described with stale "no separate schedule" claims.


def test_release_process_names_freshness_workflow():
    """RELEASE_PROCESS.md must name demo-session-freshness.yml as the between-release schedule.

    Before #225 the doc was silent about any scheduled session freshness job.
    After #225 the workflow exists and the doc must acknowledge it.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = RELEASE_PROCESS.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        "RELEASE_PROCESS.md must name demo-session-freshness.yml as the "
        "between-release session freshness schedule (#225)"
    )


def test_uptime_doc_names_freshness_workflow():
    """docs/uptime.md must name demo-session-freshness.yml as a Pages publisher.

    The uptime doc describes both publishers of the shared Pages URL.  Omitting
    the freshness schedule leaves operators unaware of the second publisher.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = UPTIME_DOC.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        "docs/uptime.md must document demo-session-freshness.yml as the "
        "scheduled Pages publisher (#225)"
    )


def test_github_pages_doc_names_freshness_workflow():
    """docs/deploy/github-pages.md must name demo-session-freshness.yml as the schedule publisher.

    The pages deploy doc lists all ways the site can be published.  The freshness
    schedule is a third publication path and must be listed alongside tags and
    manual dispatch.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = GITHUB_PAGES_DOC.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        "docs/deploy/github-pages.md must document demo-session-freshness.yml "
        "as the scheduled publisher (#225)"
    )


def test_release_skill_names_freshness_workflow():
    """The release SKILL.md must name demo-session-freshness.yml so an opt-out stays scoped.

    An operator who skips the full demo refresh must still know that the
    Pages-only schedule runs between releases (#225 / FR7).
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = SKILL_FILE.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        ".claude/skills/release/SKILL.md must reference demo-session-freshness.yml "
        "so the release operator knows not to disable the schedule (#225 / FR7)"
    )


# Phrases that would indicate a stale/incorrect claim that no freshness schedule exists.
_STALE_NO_SCHEDULE_PATTERNS = [
    "no separate scheduled freshness",
    "no separate weekly job",
    "no separate freshness workflow",
    "there is no separate scheduled",
    "no scheduled freshness",
]


def test_no_stale_claim_about_no_separate_freshness_schedule():
    """Old stale 'no separate scheduled freshness' claim must not appear in key docs or skill.

    Before #225 the docs might have implied there was no between-release schedule.
    After #225 that claim is wrong and must not reappear in any of these files.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    docs_to_check = {
        "RELEASE_PROCESS.md": RELEASE_PROCESS,
        "uptime.md": UPTIME_DOC,
        "github-pages.md": GITHUB_PAGES_DOC,
        "release SKILL.md": SKILL_FILE,
    }
    for label, path in docs_to_check.items():
        lower = path.read_text(encoding="utf-8").lower()
        for pattern in _STALE_NO_SCHEDULE_PATTERNS:
            assert pattern not in lower, (
                f"{label} contains stale claim {pattern!r} — "
                f"demo-session-freshness.yml IS the separate scheduled freshness "
                f"workflow; that claim must not appear (#225)"
            )


# ─── gap-filling tests for FR2-AC3 / FR4 / FR5-AC3 / FR7-AC1 / FR8 (#225) ───


def test_refresh_demo_doc_names_freshness_workflow():
    """docs/maintainers/REFRESH_DEMO.md must name demo-session-freshness.yml.

    The tech spec (#225) requires updating REFRESH_DEMO.md so maintainers reading
    the "What this does not do" section learn that the between-release schedule
    (not this script) handles session-date sliding on Pages.  Omitting it leaves
    the maintainer believing CI never touches session dates between releases.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = REFRESH_DEMO_DOC.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        "docs/maintainers/REFRESH_DEMO.md must name demo-session-freshness.yml — "
        "maintainers reading the 'What this does not do' section must know the "
        "between-release schedule exists and handles session-date sliding (#225)"
    )


def test_refresh_demo_doc_has_no_stale_no_schedule_claim():
    """docs/maintainers/REFRESH_DEMO.md must not carry a stale 'no schedule' claim.

    The doc previously described CI as never touching sessions; after #225 that is
    wrong.  Stale phrases from _STALE_NO_SCHEDULE_PATTERNS must not appear.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    lower = REFRESH_DEMO_DOC.read_text(encoding="utf-8").lower()
    for pattern in _STALE_NO_SCHEDULE_PATTERNS:
        assert pattern not in lower, (
            f"docs/maintainers/REFRESH_DEMO.md contains stale claim {pattern!r} — "
            f"demo-session-freshness.yml IS the separate freshness schedule; "
            f"that claim must not appear (#225)"
        )


def test_freshness_workflow_concurrency_does_not_cancel_in_progress(freshness_yml: str):
    """Concurrency block must have cancel-in-progress: false (FR5-AC3 / FR7-AC1).

    Pages deploys are serialised by the shared concurrency group.
    Setting cancel-in-progress: false ensures that if a schedule run is queued
    behind a tag deploy (or vice versa), neither run is cancelled — the last
    successful deploy wins rather than a queued job being silently dropped.
    Removing this guard would let a concurrent deploy race kill the prior one,
    leaving visitors with a half-deployed or stale site.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    assert "cancel-in-progress: false" in freshness_yml, (
        "concurrency block must set cancel-in-progress: false — "
        "removing it would let a concurrent release tag deploy cancel an in-flight "
        "freshness run, potentially leaving the site stale (FR5-AC3 / FR7-AC1)"
    )


def test_generator_module_doc_names_freshness_workflow():
    """scripts/generate_demo_sessions.py module docstring must name demo-session-freshness.yml.

    The tech spec (#225) requires the generator's own module doc to state that the
    Pages-only schedule may call it on the runner and that path still never commits.
    Omitting this leaves the script's doc misleading for contributors who read it
    to understand when and where it is invoked.
    """
    # @spec: 225-demo-release-freshness
    # @regression
    text = GENERATOR_SCRIPT.read_text(encoding="utf-8")
    assert "demo-session-freshness.yml" in text, (
        "scripts/generate_demo_sessions.py module doc must name demo-session-freshness.yml — "
        "the tech spec (#225) requires the doc to state that the Pages-only schedule "
        "may call this script on the runner (never commits)"
    )

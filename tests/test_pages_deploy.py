"""The published demo site cannot silently fall behind the package (#213).

# @layer: unit
# @spec: 213-pages-stale-demo
# @regression

The demo sat four releases stale behind green workflow runs: `pages.yml`
deployed on `workflow_dispatch` only, and nothing ever compared the live site
with the code it was supposed to be serving.

Two halves, both offline:

* Static assertions on the workflow YAML — the tag trigger, the retained
  dispatch, and the post-deploy version assert. Text matching in the style of
  ``tests/test_release_pipeline.py``: the failure mode is an edit that quietly
  drops a trigger or a step, which a substring catches.
* Unit and CLI coverage of ``scripts/check_live_version.py``. The helpers are
  pure and the CLI takes ``--manifest-json``, so every exit path is exercised
  against fixtures without touching the network.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT, __version__

PAGES_YML = REPO_ROOT / ".github" / "workflows" / "pages.yml"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_live_version.py"


def _load_checker():
    """Import ``scripts/check_live_version.py`` by path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("check_live_version", CHECK_SCRIPT)
    assert spec is not None and spec.loader is not None, f"cannot load {CHECK_SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pages_yml() -> str:
    assert PAGES_YML.is_file(), ".github/workflows/pages.yml is missing — the demo has no publisher"
    return PAGES_YML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def checker():
    assert CHECK_SCRIPT.is_file(), "scripts/check_live_version.py is missing — pages.yml invokes it post-deploy"
    return _load_checker()


# ─── pages.yml: triggers ──────────────────────────────────────────────


def test_pages_workflow_triggers_on_version_tags(pages_yml: str):
    # The whole of #213: a dispatch-only publisher means the demo only ever
    # updates when a human remembers to press the button.
    assert "tags:" in pages_yml, "pages.yml has no tag trigger — releases will not republish the demo (#213)"
    assert '"v*.*.*"' in pages_yml or "'v*.*.*'" in pages_yml, (
        "pages.yml must republish on v*.*.* tags, matching release.yml"
    )


def test_pages_workflow_keeps_workflow_dispatch(pages_yml: str):
    # Tag pushes are the routine path; dispatch is how a maintainer republishes
    # after a failed or reverted deploy without cutting a version.
    assert "workflow_dispatch:" in pages_yml, "pages.yml dropped workflow_dispatch — manual republish is the recovery path"


def test_pages_workflow_does_not_deploy_on_every_main_push(pages_yml: str):
    # Deliberate (#69): the demo tracks releases, not merges.
    trigger_block = pages_yml.split("permissions:", 1)[0]
    assert "branches:" not in trigger_block, (
        "pages.yml deploys on branch pushes — #69 keeps the demo on releases only; tags are the trigger"
    )


# ─── pages.yml: post-deploy assertion ─────────────────────────────────


def test_pages_deploy_job_asserts_live_version_after_deploying(pages_yml: str):
    deploy_job = pages_yml.split("  deploy:", 1)
    assert len(deploy_job) == 2, "pages.yml has no deploy job"
    body = deploy_job[1]
    deployed_at = body.find("actions/deploy-pages")
    checked_at = body.find("scripts/check_live_version.py")
    assert deployed_at != -1, "pages.yml deploy job no longer runs actions/deploy-pages"
    assert checked_at != -1, (
        "pages.yml deploy job never verifies the published site — a green deploy only proves the artifact was accepted (#213)"
    )
    assert deployed_at < checked_at, (
        "the version check runs before actions/deploy-pages — it would read the previous deploy and pass on a stale site"
    )


def test_pages_post_deploy_check_reads_the_deployed_page_url(pages_yml: str):
    body = pages_yml.split("  deploy:", 1)[1]
    assert "steps.deployment.outputs.page_url" in body, (
        "the post-deploy check must target the URL this run deployed, not a hardcoded site"
    )
    check_line = next(line for line in body.splitlines() if "check_live_version.py" in line)
    assert "${{" not in check_line, (
        "page_url is interpolated straight into the shell — pass it through env: and quote it instead"
    )


def test_pages_post_deploy_check_retries_for_cdn_propagation(pages_yml: str):
    body = pages_yml.split("  deploy:", 1)[1]
    assert "--attempts" in body, (
        "the post-deploy check has no retries — a just-finished deploy needs a moment to reach the CDN, so a single attempt flakes red"
    )


# ─── check_live_version.py: pure helpers ──────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2.1.0", "2.1.0"),
        ("v2.1.0", "2.1.0"),
        ("V2.1.0", "2.1.0"),
        ("  v2.1.0\n", "2.1.0"),
        ("1.5.0rc1", "1.5.0rc1"),
    ],
)
def test_normalise_version_strips_whitespace_and_tag_prefix(checker, raw: str, expected: str):
    assert checker.normalise_version(raw) == expected


@pytest.mark.parametrize(
    ("live", "expected"),
    [
        ("2.1.0", "2.1.0"),
        ("2.1.0", "v2.1.0"),
        ("v2.1.0", "2.1.0"),
        (" 2.1.0 ", "v2.1.0\n"),
    ],
)
def test_versions_match_ignores_tag_prefix_and_whitespace(checker, live: str, expected: str):
    assert checker.versions_match(live, expected) is True


@pytest.mark.parametrize(
    ("live", "expected"),
    [
        ("1.5.0", "2.1.0"),
        ("2.1.0", "2.1.1"),
        ("v1.5.0", "2.1.0"),
        ("2.1.0rc1", "2.1.0"),
        ("", "2.1.0"),
    ],
)
def test_versions_match_rejects_different_versions(checker, live: str, expected: str):
    # The stale demo served 1.5.0 while the package was 2.1.0 — this
    # comparison is the one that had to start returning False.
    assert checker.versions_match(live, expected) is False


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.github.io/llm-wiki/", "https://example.github.io/llm-wiki/manifest.json"),
        ("https://example.github.io/llm-wiki", "https://example.github.io/llm-wiki/manifest.json"),
        (
            "https://example.github.io/llm-wiki/manifest.json",
            "https://example.github.io/llm-wiki/manifest.json",
        ),
        ("  https://example.github.io/llm-wiki/  ", "https://example.github.io/llm-wiki/manifest.json"),
    ],
)
def test_manifest_url_accepts_site_root_or_manifest(checker, url: str, expected: str):
    # `actions/deploy-pages` hands back a page_url ending in "/", while the
    # freshness job pastes the manifest link — both must resolve to one URL.
    assert checker.manifest_url(url) == expected


@pytest.mark.parametrize("url", ["", "   ", "\n"])
def test_manifest_url_rejects_an_empty_url(checker, url: str):
    with pytest.raises(ValueError):
        checker.manifest_url(url)


def test_parse_manifest_version_reads_the_stamped_version(checker):
    payload = json.dumps({"version": "2.1.0", "generated": "2026-09-06"})
    assert checker.parse_manifest_version(payload) == "2.1.0"


def test_parse_manifest_version_strips_whitespace(checker):
    assert checker.parse_manifest_version('{"version": " 2.1.0 "}') == "2.1.0"


@pytest.mark.parametrize(
    "payload",
    [
        "<!DOCTYPE html><html>404</html>",
        "",
        "[1, 2, 3]",
        '"2.1.0"',
        "{}",
        '{"version": ""}',
        '{"version": null}',
        '{"version": 2.1}',
    ],
)
def test_parse_manifest_version_rejects_unreadable_payloads(checker, payload: str):
    # "We cannot tell what is live" must fail loudly. Pages serves the 404 page
    # with a 200 for a missing path, so an HTML body is the realistic case.
    with pytest.raises(checker.ManifestError):
        checker.parse_manifest_version(payload)


def test_package_version_matches_the_installed_package(checker):
    assert checker.package_version() == __version__


def test_package_version_reads_the_checked_out_tree(checker, tmp_path: Path):
    # Read textually, not imported: the freshness workflow installs no deps.
    pkg = tmp_path / "llmwiki"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('__version__ = "9.9.9"\nREPO_ROOT = None\n', encoding="utf-8")
    assert checker.package_version(tmp_path) == "9.9.9"


# ─── check_live_version.py: CLI exit codes ────────────────────────────


def _manifest_file(tmp_path: Path, payload: str) -> str:
    path = tmp_path / "manifest.json"
    path.write_text(payload, encoding="utf-8")
    return str(path)


def test_cli_exits_zero_when_the_live_version_matches(checker, tmp_path: Path):
    manifest = _manifest_file(tmp_path, json.dumps({"version": __version__}))
    assert checker.main(["--manifest-json", manifest]) == checker.EXIT_OK


def test_cli_defaults_expected_to_the_checked_out_version(checker, tmp_path: Path, capsys):
    manifest = _manifest_file(tmp_path, json.dumps({"version": __version__}))
    assert checker.main(["--manifest-json", manifest]) == 0
    assert __version__ in capsys.readouterr().out


def test_cli_exits_nonzero_when_the_site_is_stale(checker, tmp_path: Path, capsys):
    # The #213 reproduction: live 1.5.0, tree 2.1.0.
    manifest = _manifest_file(tmp_path, json.dumps({"version": "1.5.0"}))
    code = checker.main(["--manifest-json", manifest, "--expected", "2.1.0"])
    assert code == checker.EXIT_MISMATCH
    assert code != 0
    err = capsys.readouterr().err
    assert "1.5.0" in err and "2.1.0" in err, "the mismatch message must name both versions"
    assert "213" in err, "the failure should point at the issue that explains what to do about it"


def test_cli_accepts_a_tag_shaped_expected_version(checker, tmp_path: Path):
    manifest = _manifest_file(tmp_path, json.dumps({"version": "1.5.0"}))
    assert checker.main(["--manifest-json", manifest, "--expected", "v1.5.0"]) == checker.EXIT_OK


def test_cli_exits_malformed_on_an_unreadable_manifest(checker, tmp_path: Path):
    # Pages answers a missing path with its 404 page and a 200 status, so this
    # must not be mistaken for "matches" or for "unreachable".
    manifest = _manifest_file(tmp_path, "<html>404: Not Found</html>")
    assert checker.main(["--manifest-json", manifest, "--expected", "2.1.0"]) == checker.EXIT_MALFORMED


def test_cli_exits_malformed_when_the_manifest_has_no_version(checker, tmp_path: Path):
    manifest = _manifest_file(tmp_path, json.dumps({"generated": "2026-09-06"}))
    assert checker.main(["--manifest-json", manifest, "--expected", "2.1.0"]) == checker.EXIT_MALFORMED


def test_cli_exits_unreachable_when_the_manifest_file_is_missing(checker, tmp_path: Path):
    missing = str(tmp_path / "nope.json")
    assert checker.main(["--manifest-json", missing, "--expected", "2.1.0"]) == checker.EXIT_UNREACHABLE


def test_cli_reads_a_manifest_from_stdin(checker, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"version": "2.1.0"})))
    assert checker.main(["--manifest-json", "-", "--expected", "2.1.0"]) == checker.EXIT_OK


def test_cli_requires_a_manifest_source(checker):
    # --url and --manifest-json are mutually exclusive and one is required:
    # a bare invocation must not silently pass.
    with pytest.raises(SystemExit):
        checker.main([])


def test_cli_exit_codes_are_distinct(checker):
    codes = [checker.EXIT_OK, checker.EXIT_MISMATCH, checker.EXIT_UNREACHABLE, checker.EXIT_MALFORMED]
    assert len(set(codes)) == len(codes), "a workflow log has to say *why* the check failed"
    assert checker.EXIT_OK == 0


# ─── check_live_version.py: --url retry loop (CDN propagation) ────────


class _FakeHttpResponse:
    """Minimal urlopen context manager returning a fixed body."""

    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


def _patch_urlopen_sequence(checker, monkeypatch, payloads: list[str | BaseException]):
    """Serve sequential urlopen bodies (or raise) without sleeping between attempts."""
    queue = list(payloads)

    def fake_urlopen(request, timeout=None):  # noqa: ARG001 — mirror urllib signature
        if not queue:
            raise AssertionError("urlopen called more times than payloads provided")
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _FakeHttpResponse(item)

    monkeypatch.setattr(checker.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(checker.time, "sleep", lambda _seconds: None)


def test_cli_url_retries_until_cdn_serves_expected_version(checker, monkeypatch, capsys):
    # Pages often returns 200 with the previous manifest until the CDN flips —
    # the retry budget must cover mismatch, not only fetch failures.
    stale = json.dumps({"version": "1.5.0"})
    fresh = json.dumps({"version": "2.1.0"})
    _patch_urlopen_sequence(checker, monkeypatch, [stale, fresh])
    code = checker.main(
        [
            "--url",
            "https://example.github.io/llm-wiki/",
            "--expected",
            "2.1.0",
            "--attempts",
            "3",
            "--delay",
            "0",
        ]
    )
    assert code == checker.EXIT_OK
    assert "2.1.0" in capsys.readouterr().out


def test_cli_url_exits_mismatch_when_every_attempt_stays_stale(checker, monkeypatch, capsys):
    stale = json.dumps({"version": "1.5.0"})
    _patch_urlopen_sequence(checker, monkeypatch, [stale, stale, stale])
    code = checker.main(
        [
            "--url",
            "https://example.github.io/llm-wiki/manifest.json",
            "--expected",
            "2.1.0",
            "--attempts",
            "3",
            "--delay",
            "0",
        ]
    )
    assert code == checker.EXIT_MISMATCH
    err = capsys.readouterr().err
    assert "1.5.0" in err and "2.1.0" in err


def test_cli_url_retries_malformed_html_then_succeeds(checker, monkeypatch, capsys):
    # Pages serves the 404 HTML page with HTTP 200 for a missing path during
    # propagation — treat that like a soft failure and keep trying.
    html_404 = "<!DOCTYPE html><html>404</html>"
    fresh = json.dumps({"version": "2.1.0"})
    _patch_urlopen_sequence(checker, monkeypatch, [html_404, fresh])
    code = checker.main(
        [
            "--url",
            "https://example.github.io/llm-wiki/",
            "--expected",
            "2.1.0",
            "--attempts",
            "3",
            "--delay",
            "0",
        ]
    )
    assert code == checker.EXIT_OK
    assert "2.1.0" in capsys.readouterr().out

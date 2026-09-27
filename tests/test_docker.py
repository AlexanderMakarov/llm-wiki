"""Tests for Docker setup (v1.1.0, #123)."""

from __future__ import annotations

import re

import pytest

from llmwiki import REPO_ROOT

DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE = REPO_ROOT / "docker-compose.yml"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-publish.yml"
DOCS = REPO_ROOT / "docs" / "deploy" / "docker.md"


# ─── Dockerfile ───────────────────────────────────────────────────────


def test_dockerfile_exists():
    assert DOCKERFILE.is_file()


def test_dockerfile_uses_python_slim_base():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "python:3.12-slim" in text


def test_dockerfile_has_oci_labels():
    text = DOCKERFILE.read_text(encoding="utf-8")
    for label in [
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.source",
        "org.opencontainers.image.licenses",
    ]:
        assert label in text, f"missing OCI label: {label}"


def test_dockerfile_uses_non_root_user():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "USER app" in text
    assert "useradd" in text
    assert "UID 1000" in text or "uid 1000" in text.lower() or "--uid 1000" in text


def test_dockerfile_exposes_no_port():
    """The image runs commands; llmwiki ships no server, so nothing listens."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "EXPOSE" not in text


def test_dockerfile_default_cmd_builds_the_site():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert 'CMD ["build"]' in text


def test_dockerfile_multi_stage_build():
    text = DOCKERFILE.read_text(encoding="utf-8")
    # Builder stage + final runtime stage
    assert "AS builder" in text
    assert "COPY --from=builder" in text


def test_dockerfile_owns_mount_point_as_app_user():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "chown -R app:app /wiki" in text


# ─── docker-compose.yml ───────────────────────────────────────────────


def test_compose_exists():
    assert COMPOSE.is_file()


def test_compose_pulls_ghcr_image():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "image: ghcr.io/alexandermakarov/llm-wiki" in text


def test_compose_has_build_fallback():
    text = COMPOSE.read_text(encoding="utf-8")
    # Fallback build directive so users can build locally if they want
    assert "build:" in text


def test_compose_maps_no_ports():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "ports:" not in text


def test_compose_bind_mounts_user_dirs():
    text = COMPOSE.read_text(encoding="utf-8")
    # Bind-mount raw/, wiki/, site/ so llmwiki reads/writes host data
    assert "./raw:/wiki/raw" in text
    assert "./wiki:/wiki/wiki" in text
    assert "./site:/wiki/site" in text


def test_compose_mounts_examples_readonly():
    text = COMPOSE.read_text(encoding="utf-8")
    # Examples are seed data; mount read-only
    assert "./examples:/wiki/examples:ro" in text


def test_compose_default_command_builds_the_site():
    text = COMPOSE.read_text(encoding="utf-8")
    assert 'command: ["build"]' in text


# ─── Publish workflow ────────────────────────────────────────────────


def test_publish_workflow_exists():
    assert PUBLISH_WORKFLOW.is_file()


def test_publish_triggers_on_version_tags():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v*.*.*"]' in text


def test_publish_has_workflow_dispatch():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text


def test_publish_builds_multi_arch():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    # amd64 + arm64
    assert "linux/amd64" in text
    assert "linux/arm64" in text


def test_publish_requires_packages_write_permission():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "packages: write" in text


def test_publish_uses_gha_cache():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "type=gha" in text


def test_publish_tags_include_latest_only_for_stable():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    # `latest` must NOT apply to rc/alpha/beta/dev pre-releases
    assert "!contains(github.ref, 'rc')" in text
    assert "!contains(github.ref, 'alpha')" in text


def test_publish_logs_into_ghcr():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "ghcr.io" in text
    assert "docker/login-action" in text


# ─── Docs ─────────────────────────────────────────────────────────────


def test_docker_docs_exist():
    assert DOCS.is_file()


def test_docker_docs_cover_pull_mode():
    text = DOCS.read_text(encoding="utf-8")
    assert "docker compose pull" in text


def test_docker_docs_cover_build_mode():
    text = DOCS.read_text(encoding="utf-8")
    assert "docker compose build" in text


def test_docker_docs_list_image_details():
    text = DOCS.read_text(encoding="utf-8")
    assert "Image details" in text
    assert "non-root" in text
    assert "Default CMD:** `build`" in text


def test_docker_docs_tell_the_reader_to_open_the_built_files():
    """No document may tell a reader to start a server to view their wiki."""
    text = DOCS.read_text(encoding="utf-8")
    assert "site/index.html" in text
    assert "llmwiki serve" not in text


def test_docker_docs_list_volumes():
    text = DOCS.read_text(encoding="utf-8")
    assert "./raw" in text
    assert "./wiki" in text
    assert "./site" in text


def test_docker_docs_troubleshooting_section():
    text = DOCS.read_text(encoding="utf-8")
    assert "Troubleshooting" in text


def test_docker_docs_mentions_no_telemetry():
    text = DOCS.read_text(encoding="utf-8")
    assert "no telemetry" in text.lower()


# ─── Publish workflow: least privilege + post-publish proof (#211) ────


def test_publish_grants_no_id_token_permission():
    """No OIDC token: nothing in this workflow signs anything.

    ``id-token: write`` was granted for Cosign keyless signing that was never
    wired up, so it advertised a guarantee the workflow did not provide.
    """
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "id-token:" not in text


def test_publish_does_not_mention_cosign():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "cosign" not in text.lower()


def test_publish_smoke_tests_the_published_image():
    """The workflow must run what it shipped before reporting success."""
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "needs: build-and-push" in text, "no job depends on the publish job"
    assert "docker pull" in text, "the published tag is never pulled back"
    assert re.search(r"docker run\b.*\bversion\b", text), (
        "the published image is never executed to assert its version"
    )
    # A smoke test that can go green while failing proves nothing.
    assert "continue-on-error" not in text


def test_publish_smoke_authenticates_to_ghcr():
    """A GHCR package is private until its first visibility flip (#211).

    Without a login the very first publish from a fork cannot be pulled back,
    so the smoke job fails on an image that is in fact fine.
    """
    smoke = _smoke_job_text()
    assert "docker/login-action" in smoke, "smoke job never logs in to GHCR"
    assert "registry: ghcr.io" in smoke
    assert "${{ secrets.GITHUB_TOKEN }}" in smoke


def test_publish_smoke_drops_package_write():
    """Least privilege: reading a package back needs no write scope."""
    smoke = _smoke_job_text()
    assert re.search(r"^    permissions:$", smoke, re.MULTILINE), (
        "smoke job has no job-level permissions block, so it inherits "
        "the workflow-level `packages: write`"
    )
    assert re.search(r"^      packages: read$", smoke, re.MULTILINE)
    assert not re.search(r"^\s*packages: write$", smoke, re.MULTILINE), (
        "smoke job re-grants `packages: write`"
    )


def test_publish_smoke_compares_the_whole_version_line():
    """`grep -F "1.2"` matches inside "llmwiki 1.20.0" — anchor the check."""
    smoke = _smoke_job_text()
    assert "grep -qF" not in smoke, "substring match: 1.2 would pass against 1.20.0"
    assert '"llmwiki $expected"' in smoke, (
        "the smoke test no longer compares the full `llmwiki <version>` line"
    )


# ─── Dispatch tag override: the build publishes what the smoke pulls ──
#
# The bug this pins (#211 review): `build-and-push` ignored `inputs.tag`, so a
# `workflow_dispatch` published only `latest` while the smoke job pulled the
# override — a tag that run never pushed. Asserting a literal expression
# string cannot catch that; these tests *evaluate* both expressions against
# the three ways this workflow runs and require the sets to line up.


def _smoke_job_text() -> str:
    """Return the ``smoke-published-image`` job block.

    Bounded at the next top-level job so the assertions below keep meaning
    what they say if a job is ever appended after this one.
    """
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    _, _, smoke = text.partition("\n  smoke-published-image:\n")
    assert smoke, "the workflow has no smoke-published-image job"
    return re.split(r"^  \S", smoke, maxsplit=1, flags=re.MULTILINE)[0]


def _meta_tag_rows() -> list[str]:
    """Return the ``docker/metadata-action`` ``tags:`` rows, comments dropped."""
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    _, _, after = text.partition("\n          tags: |\n")
    assert after, "the metadata step declares no tags: block"
    rows: list[str] = []
    for line in after.splitlines():
        if not line.startswith("            "):
            break
        row = line.strip()
        if row and not row.startswith("#"):
            rows.append(row)
    assert rows, "the tags: block is empty"
    return rows


def _smoke_tag_expression() -> str:
    """Return the ``TAG:`` expression the smoke job resolves its image from."""
    match = re.search(r"^          TAG: (.+)$", _smoke_job_text(), re.MULTILINE)
    assert match, "the smoke job does not set a TAG env var"
    return match.group(1).strip()


#: A deliberately narrow model of the GitHub-expression *subset* this workflow
#: uses — string literals, `==`/`!=`, `contains()`, `&&`, `||`, `!` — not a
#: general evaluator. `&&`/`||` do share Python's operand-returning semantics,
#: so the spellings map across, but four divergences are known and only hold
#: because nothing in this workflow exercises them. Check them before
#: extending the workflow's expressions:
#:   1. Precedence of `!`: GitHub binds it tighter than `==`, so `!a == b`
#:      means `(!a) == b`; Python's `not a == b` means `not (a == b)`.
#:      No expression here writes `!x == y`.
#:   2. Case: GitHub compares strings and evaluates `contains()`
#:      case-insensitively; this model is case-sensitive, so a tag
#:      `v2.4.0-RC1` would disable `latest` in reality but not here.
#:   3. Substitution: values are injected through a replacement *function*,
#:      not a template string, so a value containing `\` or `\g` cannot be
#:      reinterpreted as an `re.sub` escape.
#:   4. Literal contamination: the spelling rewrites run over the whole
#:      expression, quoted literals included, so a literal containing `!`,
#:      `&&` or `||` would be mangled. None currently does.
def _gha_eval(expression: str, ctx: dict[str, str]) -> object:
    """Evaluate one ``${{ … }}`` expression against a scenario context."""
    body = expression.strip()
    if body.startswith("${{") and body.endswith("}}"):
        body = body[3:-2]
    body = re.sub(r"contains\(([^,]+),\s*([^)]+)\)", r"(\2 in \1)", body)
    body = body.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
    body = re.sub(r"\bnot =", "!=", body)  # undo `!=` mangled by the line above
    for name, value in ctx.items():
        body = re.sub(rf"\b{re.escape(name)}\b", lambda _m, v=value: repr(v), body)
    assert not re.search(r"\b(github|inputs)\.", body), (
        f"unmodelled context in {expression!r}: {body!r}"
    )
    # Input is a workflow expression from this repository, reduced above to
    # string literals and operators, with builtins removed.
    return eval(body, {"__builtins__": {}}, {})


def _published_tags(ctx: dict[str, str]) -> set[str]:
    """Model the tags ``docker/metadata-action`` would push for a scenario.

    ``type=semver`` rows are aliases of the same released version and are not
    modelled; the contract under test is which *distinct* tags exist at all.
    """
    tags: set[str] = set()
    for row in _meta_tag_rows():
        if row == "type=ref,event=tag":
            if ctx["github.ref"].startswith("refs/tags/"):
                tags.add(ctx["github.ref_name"])
        elif row.startswith("type=raw,"):
            value, _, enable = row[len("type=raw,"):].partition(",enable=")
            assert value.startswith("value="), row
            rendered = value[len("value="):]
            for name, ctx_value in ctx.items():
                rendered = rendered.replace(f"${{{{ {name} }}}}", ctx_value)
            # An assumption about `docker/metadata-action`, not an
            # observation: a disabled row renders as `type=raw,value=,…` and
            # we model that as pushing nothing. If the action ever errored on
            # an empty `value=`, or emitted an empty tag, this model would
            # stay green while every dispatch rebuild broke. Confirm against
            # a real `workflow_dispatch` run once the workflow is on the
            # default branch.
            if not enable or _gha_eval(enable, ctx):
                tags.add(rendered)
        elif not row.startswith("type=semver,"):
            raise AssertionError(f"unmodelled metadata-action row: {row!r}")
    return tags


#: (label, context, the tag the run is expected to publish *and* smoke).
_RUNS = [
    (
        "tag push",
        {
            "github.event_name": "push",
            "github.ref": "refs/tags/v1.2.3",
            "github.ref_name": "v1.2.3",
            "inputs.tag": "",
        },
        "v1.2.3",
    ),
    (
        "dispatch with a tag override",
        {
            "github.event_name": "workflow_dispatch",
            "github.ref": "refs/heads/main",
            "github.ref_name": "main",
            "inputs.tag": "v1.2.3",
        },
        "v1.2.3",
    ),
    (
        # Prereleases are a supported release path (release.yml flips
        # `--prerelease` on these names), and the smoke job's exact-version
        # branch must not claim them: the tag spells `v2.4.0-rc1` while the
        # package reports the PEP 440 `2.4.0rc1`.
        "prerelease tag push",
        {
            "github.event_name": "push",
            "github.ref": "refs/tags/v2.4.0-rc1",
            "github.ref_name": "v2.4.0-rc1",
            "inputs.tag": "",
        },
        "v2.4.0-rc1",
    ),
    (
        "dispatch without a tag override",
        {
            "github.event_name": "workflow_dispatch",
            "github.ref": "refs/heads/main",
            "github.ref_name": "main",
            "inputs.tag": "",
        },
        "latest",
    ),
]


def _run_ctx(label: str) -> dict[str, str]:
    """Return a copy of one named scenario's context."""
    for name, ctx, _expected in _RUNS:
        if name == label:
            return dict(ctx)
    raise AssertionError(f"no such scenario: {label!r}")


@pytest.mark.parametrize(("label", "ctx", "expected"), _RUNS, ids=[r[0] for r in _RUNS])
def test_build_publishes_the_tag_the_smoke_job_pulls(label, ctx, expected):
    """Every way this workflow runs, the smoke job pulls a tag it just pushed."""
    published = _published_tags(ctx)
    smoked = _gha_eval(_smoke_tag_expression(), ctx)

    assert expected in published, (
        f"{label}: build-and-push publishes {sorted(published)}, "
        f"which does not include {expected!r}"
    )
    assert smoked == expected, (
        f"{label}: the smoke job resolves TAG to {smoked!r}, expected {expected!r}"
    )
    assert smoked in published, (
        f"{label}: the smoke job pulls {smoked!r} but the build published "
        f"{sorted(published)} — the job can only go red"
    )


def test_prerelease_tag_does_not_republish_latest():
    """`latest` must keep pointing at the newest *stable* release."""
    ctx = _run_ctx("prerelease tag push")
    assert "latest" not in _published_tags(ctx), (
        "a prerelease tag push also moved `latest`"
    )


def test_smoke_exact_version_check_is_anchored():
    r"""An unanchored `^[0-9]+\.[0-9]+\.[0-9]+` sends `2.4.0-rc1` into the
    exact-match branch, where it is compared against the PEP 440 `2.4.0rc1`
    the image reports — a false red on a perfectly good prerelease."""
    smoke = _smoke_job_text()
    assert r"=~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]" in smoke, (
        "the smoke job's exact-version branch is no longer anchored at `$`"
    )


def test_dispatch_tag_is_validated_before_it_reaches_the_metadata_step():
    """`inputs.tag` lands in a YAML block scalar, where a newline in the
    dispatch input would inject an extra `type=raw` row (#211 review)."""
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    guard = re.search(
        r"if: github\.event_name == 'workflow_dispatch' && inputs\.tag != ''\n"
        r"\s+env:\n\s+TAG: \$\{\{ inputs\.tag \}\}\n"
        r"\s+run: \|\n(?:.*\n)*?.*\[\[ \"\$TAG\" =~ \^\[A-Za-z0-9\]",
        text,
    )
    assert guard, "no step validates the dispatch tag override"
    metadata = text.index("docker/metadata-action")
    assert guard.start() < metadata, (
        "the dispatch tag is validated after it has already been "
        "interpolated into the metadata step"
    )


def test_dispatch_override_does_not_clobber_latest():
    """A rebuild of an old version must not move `latest` onto it."""
    ctx = _run_ctx("dispatch with a tag override")
    assert "latest" not in _published_tags(ctx), (
        "a dispatch that names an explicit tag also republished `latest`"
    )

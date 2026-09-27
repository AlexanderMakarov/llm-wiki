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


def test_publish_dispatch_requires_a_tag():
    """A tag-less dispatch has no version to publish or smoke-test."""
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    dispatch = text.partition("  workflow_dispatch:\n")[2].partition("\npermissions:")[0]
    assert "required: true" in dispatch, (
        "the `tag` dispatch input is optional again — a tag-less dispatch "
        "would publish an empty `type=raw` row"
    )


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


def test_docker_docs_name_the_image_compose_pulls():
    """A reader following the guide must not pull a different image."""
    image = re.search(r"^\s*image:\s*(\S+?)(?::\S+)?$", COMPOSE.read_text(encoding="utf-8"), re.MULTILINE)
    assert image, "docker-compose.yml declares no image:"
    assert image.group(1) in DOCS.read_text(encoding="utf-8")


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
    smoke = _job_text("smoke-published-image")
    assert "docker/login-action" in smoke, "smoke job never logs in to GHCR"
    assert "registry: ghcr.io" in smoke
    assert "${{ secrets.GITHUB_TOKEN }}" in smoke


def test_publish_smoke_drops_package_write():
    """Least privilege: reading a package back needs no write scope."""
    smoke = _job_text("smoke-published-image")
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
    smoke = _job_text("smoke-published-image")
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


def _job_text(job: str) -> str:
    """Return one top-level job block.

    Bounded at the next top-level job so the assertions below keep meaning
    what they say if a job is ever appended after this one.
    """
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    _, _, block = text.partition(f"\n  {job}:\n")
    assert block, f"the workflow has no {job} job"
    return re.split(r"^  \S", block, maxsplit=1, flags=re.MULTILINE)[0]


def _checkout_ref_expression() -> str:
    """Return the git ref the build job checks out before building (#291)."""
    # Any `with:` key may precede `ref:` — comments, blank lines and other
    # settings such as `fetch-depth:`. The repetition cannot run past the
    # step, because a step's `- ` opener matches none of its alternatives.
    match = re.search(
        r"- uses: actions/checkout@\S+\n"
        r"\s+with:\n"
        r"(?:[ \t]*(?:#.*)?\n|[ \t]+[\w-]+:.*\n)*?"
        r"[ \t]+ref: (.+)$",
        _job_text("build-and-push"),
        re.MULTILINE,
    )
    assert match, (
        "build-and-push names no checkout ref, so a workflow_dispatch builds "
        "the branch it ran from and publishes that under the requested tag"
    )
    return match.group(1).strip()


def _tag_name(ref: object) -> object:
    """Reduce a git ref to its tag name, leaving anything else untouched."""
    if isinstance(ref, str) and ref.startswith("refs/tags/"):
        return ref[len("refs/tags/"):]
    return ref


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
    match = re.search(
        r"^          TAG: (.+)$", _job_text("smoke-published-image"), re.MULTILINE
    )
    assert match, "the smoke job does not set a TAG env var"
    return match.group(1).strip()


#: A deliberately narrow model of the GitHub-expression *subset* this workflow
#: uses — string literals, `==`/`!=`, `contains()`, `&&`, `||`, `!` — not a
#: general evaluator, and `format()` is modelled by Python's `str.format`.
#: `&&`/`||` do share Python's operand-returning semantics, so the spellings
#: map across, but five divergences are known and only hold because nothing
#: in this workflow exercises them. Check them before extending the
#: workflow's expressions:
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
#:   5. `format()`: Python's `str.format` accepts more than GitHub's does —
#:      format specs (`{0:>5}`), attribute and index access (`{0.x}`,
#:      `{0[k]}`) — and renders non-string arguments Python's way. Every
#:      call here is a bare positional `{0}` on a string.
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
    # string literals and operators, with builtins removed. `format` is
    # supplied explicitly because GitHub has it and the empty builtins do not.
    globals_ = {"__builtins__": {}, "format": lambda tmpl, *args: tmpl.format(*args)}
    return eval(body, globals_, {})


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
]


def _run_ctx(label: str) -> dict[str, str]:
    """Return a copy of one named scenario's context."""
    for name, ctx, _expected in _RUNS:
        if name == label:
            return dict(ctx)
    raise AssertionError(f"no such scenario: {label!r}")


@pytest.mark.parametrize(("label", "ctx", "expected"), _RUNS, ids=[r[0] for r in _RUNS])
def test_build_checks_out_and_publishes_the_tag_the_smoke_job_pulls(label, ctx, expected):
    """Every way this workflow runs, one tag names the source that is built,
    the tag it is published under, and the image the smoke job pulls back.

    A dispatch that checked out the branch it ran from (#291) satisfies the
    last two and still ships `main`'s code under an old version's tag.
    """
    published = _published_tags(ctx)
    smoked = _gha_eval(_smoke_tag_expression(), ctx)
    built = _gha_eval(_checkout_ref_expression(), ctx)

    assert _tag_name(built) == expected, (
        f"{label}: the build checks out {built!r}, but publishes and smokes "
        f"{expected!r} — the image would carry another commit's code"
    )
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


def test_tag_push_checks_out_the_same_ref_the_default_would_have():
    """Naming a ref must leave the tag-push path alone. The event is not a
    dispatch, so the fallback is `github.ref` — the same *ref* that
    `actions/checkout` resolves when given no `ref:` at all. Only the ref:
    the default also pins `github.sha`, so a tag force-moved between the push
    event and this step is now re-resolved rather than built as pushed."""
    ctx = _run_ctx("tag push")
    ref = _gha_eval(_checkout_ref_expression(), ctx)
    assert ref == ctx["github.ref"], (
        f"a tag push would check out {ref!r}, not {ctx['github.ref']!r} — "
        "naming a ref changed the path that was already correct"
    )


def test_dispatch_checks_out_a_tag_ref_not_a_bare_name():
    """`actions/checkout` resolves an unqualified ref as a *branch* before a
    tag, so a branch sharing a release tag's name would be built and shipped
    under that tag — #291's failure mode with a narrower trigger. The format
    guard does not cover this: it validates the name's shape, not what the
    name resolves to."""
    ctx = _run_ctx("dispatch with a tag override")
    ref = _gha_eval(_checkout_ref_expression(), ctx)
    assert ref == f"refs/tags/{ctx['inputs.tag']}", (
        f"a dispatch checks out {ref!r}, which does not say `tag` — a branch "
        f"named {ctx['inputs.tag']!r} would shadow the tag being rebuilt"
    )


def test_tag_push_moves_latest():
    """`latest` follows the newest release, and only a tag push cuts one."""
    assert "latest" in _published_tags(_run_ctx("tag push"))


def test_smoke_compares_one_exact_version_and_nothing_looser():
    """Only `vMAJOR.MINOR.PATCH` reaches this workflow, so the smoke job has
    exactly one comparison to make. A second, looser branch could only ever
    let a wrong version through."""
    smoke = _job_text("smoke-published-image")
    assert '[ "$actual" != "llmwiki $expected" ]' in smoke, (
        "the smoke job no longer compares the whole `llmwiki <version>` line"
    )
    assert "=~ ^llmwiki" not in smoke, (
        "the smoke job grew a loose version branch again — a tag that cannot "
        "be compared exactly must be rejected by the guard step instead"
    )


def _tag_guard(text: str | None = None) -> re.Match[str]:
    """Return the match for the step that enforces the release tag format.

    Searches the whole workflow unless given one job's text, which is how a
    caller asserts *where in a job* the guard sits.
    """
    if text is None:
        text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    guard = re.search(
        r"- name: Validate the release tag\n"
        r"\s+env:\n\s+TAG: (?P<expr>\$\{\{.+\}\})\n"
        r"\s+run: \|\n(?:.*\n)*?.*\[\[ \"\$TAG\" =~ (?P<regex>\S+) \]\]",
        text,
    )
    assert guard, "no step validates the release tag"
    return guard


def test_tag_guard_enforces_the_single_release_tag_format():
    """`on.push.tags` is a glob, not a regex — `v*.*.*` still matches
    `v2.4.0-rc1`. This step is the enforcement, for both events."""
    pattern = _tag_guard().group("regex")
    assert pattern == r"^v[0-9]+\.[0-9]+\.[0-9]+$", (
        f"the guard regex is {pattern!r}, not the single "
        "vMAJOR.MINOR.PATCH form"
    )
    accept = re.compile(pattern)
    assert accept.search("v2.4.0")
    for rejected in ("v2.4.0-rc1", "v2.4.0rc1", "2.4.0", "v2.4", "latest", "vX.Y.Z"):
        assert not accept.search(rejected), f"the guard admits {rejected!r}"


def test_tag_guard_runs_before_anything_consumes_the_tag():
    """`inputs.tag` lands in a YAML block scalar, where a newline in the
    dispatch input would inject an extra `type=raw` row (#211 review), and in
    the checkout's `ref:`, where a bad value fails with a blunter message
    than the guard's `::error::` (#291).

    Scoped to one job's text: textual order is a proxy for execution order
    only among steps of the same job, so a guard moved out of
    `build-and-push` fails here rather than passing on a file-layout
    coincidence.
    """
    job = _job_text("build-and-push")
    guard = _tag_guard(job).start()
    # `uses:`, not a bare mention: prose above the guard names the steps too.
    for consumer in ("uses: actions/checkout@", "uses: docker/metadata-action"):
        assert guard < job.index(consumer), (
            f"the tag is validated after `{consumer}` has already "
            "interpolated it"
        )


@pytest.mark.parametrize(("label", "_ctx", "expected"), _RUNS, ids=[r[0] for r in _RUNS])
def test_tag_guard_checks_the_tag_the_run_publishes(label, _ctx, expected):
    """Validating some *other* string than the one that gets published would
    leave the publish path unguarded."""
    guarded = _gha_eval(_tag_guard().group("expr"), _run_ctx(label))
    assert guarded == expected, (
        f"{label}: the guard validates {guarded!r}, but the run publishes "
        f"{expected!r}"
    )


def test_dispatch_override_does_not_clobber_latest():
    """A rebuild of an old version must not move `latest` onto it."""
    ctx = _run_ctx("dispatch with a tag override")
    assert "latest" not in _published_tags(ctx), (
        "a dispatch that names an explicit tag also republished `latest`"
    )

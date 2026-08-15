"""The wiki is a static site: nothing runs, nothing is fetched (R12, R13).

# @layer: integration
# @spec: 008-make-product-explain-itself
# @regression

Covers:

* ``serve`` is not a subcommand and the helper scripts are gone.
* The built candidates page reviews without a backend: per-row decisions are
  DOM state and Apply assembles a batch, with no call to any endpoint, and the
  command it prints names a vault.
* Candidate review still runs end to end from the command line.
* ``--local-root`` makes the displayed path a build input, so two builds in
  different environments produce byte-identical output.
* A built site references no script or stylesheet file over ``https://``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import build as build_mod
from llmwiki.cli import build_parser

# A `<link rel="stylesheet">` may still name a web-font *service* endpoint:
# it serves @font-face rules, carries no file extension, and the site falls
# back to the system font stack when it does not load. Any other https host
# on a stylesheet, and any https script at all, breaks "opens offline".
_FONT_SERVICE_HOSTS = frozenset({"fonts.googleapis.com", "fonts.gstatic.com"})

_SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=\"(https://[^\"]+)\"")
_STYLESHEET_HREF_RE = re.compile(r"<link[^>]+href=\"(https://[^\"]+)\"")
_ASSET_FILE_RE = re.compile(r"\.(?:js|css)\b")


# ─── the server is gone ──────────────────────────────────────────────────


def test_serve_is_not_a_subcommand():
    # @regression
    parser = build_parser()
    choices = {
        name
        for action in parser._subparsers._group_actions  # noqa: SLF001
        for name in action.choices
    }
    assert "serve" not in choices
    assert "build" in choices, "sanity: subcommand discovery still works"


def test_serve_cli_invocation_fails():
    proc = subprocess.run(
        [sys.executable, "-m", "llmwiki", "serve"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr


@pytest.mark.parametrize("name", ["serve.sh", "serve.bat", "llmwiki/serve.py"])
def test_serve_helpers_are_gone(name: str):
    assert not (REPO_ROOT / name).exists(), f"{name} still ships"


# ─── candidate review runs on the command line ───────────────────────────


def _candidate(wiki: Path, kind: str, slug: str) -> Path:
    path = wiki / "candidates" / kind / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: {kind[:-1]}\nstatus: candidate\n'
        f"last_updated: 2026-04-17\n---\n\n# {slug}\n\nBlurb about {slug}.\n",
        encoding="utf-8",
    )
    return path


def test_cli_apply_performs_promote_discard_and_merge(tmp_path: Path):
    # @regression
    """The batch shape the page prints still does every review action."""
    wiki = tmp_path / "vault" / "wiki"
    for kind in ("entities", "concepts"):
        (wiki / kind).mkdir(parents=True, exist_ok=True)
    for slug in ("Keep", "Drop", "Dupe", "Target"):
        _candidate(wiki, "entities", slug)

    batch = json.dumps([
        {"action": "promote", "slug": "Target", "kind": "entities"},
        {"action": "promote", "slug": "Keep", "kind": "entities"},
        {"action": "discard", "slug": "Drop", "kind": "entities", "reason": "noise"},
        {"action": "merge", "slug": "Dupe", "into": "Target", "kind": "entities"},
    ])
    proc = subprocess.run(
        [
            sys.executable, "-m", "llmwiki", "candidates", "apply",
            "--actions", "-", "--wiki-dir", str(wiki),
        ],
        input=batch,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert (wiki / "entities" / "Keep.md").is_file()
    assert (wiki / "entities" / "Target.md").is_file()
    assert not (wiki / "candidates" / "entities" / "Drop.md").exists()
    assert not (wiki / "candidates" / "entities" / "Dupe.md").exists()


def test_the_built_candidates_page_reviews_without_a_backend(tmp_path: Path):
    # @regression
    """Decisions are DOM state; only executing them is a command-line step."""
    root = tmp_path / "vault"
    _seed_raw(root)
    for slug in ("Keep", "Dupe"):
        _candidate(root / "wiki", "entities", slug)
    _candidate(root / "wiki", "concepts", "Idea")

    page = (_build_in(root, "/home/alice", "/home/user") / "candidates.html").read_text(
        encoding="utf-8",
    )

    # Reviewing is possible …
    assert page.count("<tr><th>Name</th><th>Description</th><th>Decision</th></tr>") == 2
    assert page.count('class="cand-decision"') == 3
    assert 'id="cand-apply"' in page
    assert "llmwiki candidates apply --vault" in page
    # … and reaches nothing.
    assert "fetch(" not in page
    assert "XMLHttpRequest" not in page
    assert "/api/candidates" not in page


# ─── the displayed local path is a build input ───────────────────────────


def _seed_raw(root: Path) -> tuple[Path, Path]:
    raw = root / "raw"
    sessions = raw / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-04-08T09-00-demo-proj-abc12345.md").write_text(
        """---
title: "Session: local root — 2026-04-08"
type: source
tags: [demo]
date: 2026-04-08
source_file: raw/sessions/2026-04-08T09-00-demo-proj-abc12345.md
sessionId: 8057bbe6-73e8-418f-b439-b4d11bad1ad7
slug: abc12345
project: demo-proj
started: 2026-04-08T09:00:00+00:00
model: claude-sonnet-4-6
cwd: /home/USER/code/demo-proj
description: "Look at /home/USER/code/demo-proj"
---

# Session

```python
print("hi")
```
""",
        encoding="utf-8",
    )
    return raw, sessions


def _build(tmp_path: Path, name: str, home: str, local_root: str | None) -> Path:
    """Build a one-session vault under ``tmp_path/name`` and return its site."""
    root = tmp_path / name
    if not root.exists():
        _seed_raw(root)
    return _build_in(root, home, local_root)


def _build_in(root: Path, home: str, local_root: str | None) -> Path:
    raw = root / "raw"
    sessions = raw / "sessions"
    out = root / "site"
    saved_home = build_mod.Path.home
    build_mod.Path.home = staticmethod(lambda: Path(home))  # type: ignore[assignment]
    saved_now = build_mod._BUILD_NOW
    build_mod._BUILD_NOW = datetime(2026, 4, 8, 9, 0)
    try:
        rc = build_mod.build_site(
            out_dir=out, raw_dir=raw, raw_sessions=sessions,
            wiki_dir=root / "wiki", local_root=local_root,
        )
    finally:
        build_mod.Path.home = saved_home  # type: ignore[assignment]
        build_mod._BUILD_NOW = saved_now
    assert rc == 0
    return out


def _html_bodies(site: Path) -> dict[str, str]:
    return {
        str(p.relative_to(site)): p.read_text(encoding="utf-8")
        for p in sorted(site.rglob("*.html"))
    }


def test_local_root_makes_two_environments_produce_identical_output(tmp_path: Path):
    # @regression
    """One vault, two machines: same flag, same pages."""
    root = tmp_path / "vault"
    _seed_raw(root)

    pages_a = _html_bodies(_build_in(root, "/home/alice", "/home/user"))
    pages_b = _html_bodies(_build_in(root, "/Users/bob", "/home/user"))

    assert set(pages_a) == set(pages_b)
    differing = [name for name in pages_a if pages_a[name] != pages_b[name]]
    assert not differing, f"pages differ between environments: {differing[:5]}"
    assert "/home/user/code/demo-proj" in pages_a["sessions/index.html"]


def test_without_the_flag_two_environments_diverge(tmp_path: Path):
    """The flag is what makes the build reproducible, not luck."""
    root = tmp_path / "vault"
    _seed_raw(root)

    a = _html_bodies(_build_in(root, "/home/alice", None))["sessions/index.html"]
    b = _html_bodies(_build_in(root, "/Users/bob", None))["sessions/index.html"]

    assert "/home/alice/code/demo-proj" in a
    assert "/Users/bob/code/demo-proj" in b


def test_without_the_flag_the_path_follows_the_current_run(tmp_path: Path):
    site = _build(tmp_path, "c", home="/home/alice", local_root=None)
    assert "/home/alice/code/demo-proj" in _html_bodies(site)["sessions/index.html"]


def test_description_prose_is_never_rewritten(tmp_path: Path):
    # @regression
    """Only the cwd field is substituted; free prose is left as imported."""
    site = _build(tmp_path, "d", home="/home/alice", local_root="/home/user")
    assert "Look at /home/USER/code/demo-proj" in _html_bodies(site)["sessions/index.html"]


# ─── nothing is fetched ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_site(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("nofetch")
    return _build(tmp_path, "site", home="/home/alice", local_root="/home/user")


def test_no_https_script_or_stylesheet_file(built_site: Path):
    # @regression
    """Every script and stylesheet the site loads ships with the site.

    Scoped to `<script src>` and `<link href>` — a prose link to a `.js`
    file on a code host is a citation, not something the page loads."""
    offenders: list[str] = []
    for name, body in _html_bodies(built_site).items():
        urls = _SCRIPT_SRC_RE.findall(body) + _STYLESHEET_HREF_RE.findall(body)
        offenders += [f"{name}: {u}" for u in urls if _ASSET_FILE_RE.search(u)]
    assert not offenders, f"remote script/stylesheet files: {offenders[:5]}"


def test_no_https_script_tags_at_all(built_site: Path):
    # @regression
    offenders = [
        f"{name}: {url}"
        for name, body in _html_bodies(built_site).items()
        for url in _SCRIPT_SRC_RE.findall(body)
    ]
    assert not offenders, f"remote <script src>: {offenders[:5]}"


def test_only_the_web_font_service_is_linked_over_https(built_site: Path):
    """Guards the one remaining remote `<link>`: a font service whose
    absence falls back to the system font stack. A new CDN stylesheet
    fails here rather than slipping in unnoticed."""
    hosts = {
        url.split("/")[2]
        for body in _html_bodies(built_site).values()
        for url in _STYLESHEET_HREF_RE.findall(body)
    }
    assert hosts <= _FONT_SERVICE_HOSTS, f"unexpected remote stylesheet hosts: {hosts}"


def test_pages_load_their_data_through_a_script_tag(built_site: Path):
    # @regression
    """`file://` blocks fetch of a same-origin JSON; a <script> src works."""
    index = (built_site / "index.html").read_text(encoding="utf-8")
    assert 'src="llmwiki-state.js"' in index
    assert 'type="module"' not in index


def test_no_page_issues_a_same_origin_fetch(built_site: Path):
    # @regression
    offenders = [
        name for name, body in _html_bodies(built_site).items()
        if re.search(r"fetch\(\s*[\"'`]/", body)
    ]
    assert not offenders, f"same-origin fetch would fail under file://: {offenders[:5]}"

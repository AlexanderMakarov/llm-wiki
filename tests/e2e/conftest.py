"""Shared pytest + Playwright + pytest-bdd harness for llmwiki E2E tests
(v0.4.x · closes #45).

Responsibilities:

* **Build a minimal demo site once per test session** into a tmp
  directory. We monkeypatch `llmwiki.build.RAW_DIR` / `RAW_SESSIONS`
  the same way `tests/test_highlightjs.py` does for its smoke test,
  so the harness never touches the user's real `raw/sessions/`.

* **Expose a `site_root` fixture** holding the built site's directory,
  and a `site_url` fixture holding the matching `file://` prefix.
  Navigation is `page.goto(f"{site_url}/index.html")`, which is exactly
  how a reader opens the site: no socket is opened anywhere in this
  suite, and a page that only works when served fails here.

* **Expose a `desktop_page` / `mobile_page` fixture** that configures
  the Playwright viewport so tests can pick the right layout without
  repeating boilerplate.

* **Ship with a tiny synthetic wiki** — two demo projects, a session
  with fenced code, and enough content to exercise the sessions index,
  the command palette, and the TOC scroll-spy.

Cucumber (via `pytest-bdd`) works alongside plain pytest tests: any
`.feature` file under `tests/e2e/features/` is mounted by the
`test_*.py` scenario binders under `tests/e2e/`. The step definitions
live in `tests/e2e/steps/` and use ordinary Playwright `page` fixtures
so a step can drive the browser, read the DOM, and assert.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from llmwiki import build as build_mod

# ─── synthetic wiki seed ────────────────────────────────────────────────

_DEMO_SESSION_PY = """---
title: "Session: e2e-python-demo — 2026-04-09"
type: source
tags: [claude-code, session-transcript]
date: 2026-04-09
source_file: raw/sessions/e2e-demo/2026-04-09-e2e-python-demo.md
sessionId: e2e-python-000000000000000000000001
slug: e2e-python-demo
project: e2e-demo
started: 2026-04-09T09:00:00+00:00
ended: 2026-04-09T09:45:00+00:00
cwd: /Users/demo/code/e2e-demo
gitBranch: main
permissionMode: default
model: claude-sonnet-4-6
user_messages: 3
tool_calls: 7
tools_used: [Read, Write, Bash]
tool_counts: {"Write": 3, "Read": 2, "Bash": 2}
token_totals: {"input": 2000, "cache_creation": 5000, "cache_read": 15000, "output": 1200}
turn_count: 3
hour_buckets: {"2026-04-09T09": 10}
duration_seconds: 2700
is_subagent: false
---

# Session: e2e-python-demo — 2026-04-09

**Project:** `e2e-demo` · **Branch:** `main` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Scaffolded a tiny FastAPI service for E2E test scaffolding. Added
a health check endpoint and a single route.

## Conversation

### Turn 1 — User

Build a minimal FastAPI app.

### Turn 1 — Assistant

Starting with `main.py`:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello(name: str) -> dict[str, str]:
    return {"greeting": f"Hello, {name}"}
```

The two endpoints exercise the router + path parameter handling.

### Turn 2 — User

Add a test file.

### Turn 2 — Assistant

```python
from fastapi.testclient import TestClient
from main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

Single test that pings the health endpoint.

### Turn 3 — User

Run it.

### Turn 3 — Assistant

**Tools used in this turn:**
- `Bash`: `pytest -q` — exit 0

All green.

## Connections

- [[FastAPI]] — framework
- [[HealthEndpoint]] — concept
"""

_DEMO_SESSION_RUST = """---
title: "Session: e2e-rust-demo — 2026-04-09"
type: source
tags: [claude-code, session-transcript]
date: 2026-04-09
source_file: raw/sessions/e2e-demo-rust/2026-04-09-e2e-rust-demo.md
sessionId: e2e-rust-000000000000000000000001
slug: e2e-rust-demo
project: e2e-demo-rust
started: 2026-04-09T11:00:00+00:00
ended: 2026-04-09T11:30:00+00:00
cwd: /Users/demo/code/e2e-demo-rust
gitBranch: main
permissionMode: default
model: claude-opus-4-6
user_messages: 2
tool_calls: 5
tools_used: [Read, Write, Edit, Bash]
tool_counts: {"Write": 2, "Edit": 2, "Bash": 1}
token_totals: {"input": 1400, "cache_creation": 3200, "cache_read": 8800, "output": 900}
turn_count: 2
hour_buckets: {"2026-04-09T11": 7}
duration_seconds: 1800
is_subagent: false
---

# Session: e2e-rust-demo — 2026-04-09

**Project:** `e2e-demo-rust` · **Branch:** `main` · **Mode:** `default` · **Model:** `claude-opus-4-6`

## Summary

Wrote a small Rust CLI that prints the current timestamp.

## Conversation

### Turn 1 — User

Write a Rust CLI that prints `chrono::Utc::now()`.

### Turn 1 — Assistant

```rust
use chrono::Utc;

fn main() {
    let now = Utc::now();
    println!("{}", now.to_rfc3339());
}
```

That's the entire `src/main.rs`.

### Turn 2 — User

Cargo.toml?

### Turn 2 — Assistant

```toml
[package]
name = "now"
version = "0.1.0"
edition = "2021"

[dependencies]
chrono = "0.4"
```

**Tools used:**
- `Bash`: `cargo run` — exit 0 — printed `2026-04-09T11:29:54+00:00`

## Connections

- [[Rust]]
- [[chrono]]
"""


def _seed_raw(raw_sessions: Path) -> None:
    """Lay out the minimal two-project / two-session fixture under
    ``raw_sessions``. Mirrors the real directory layout so
    `discover_sources` walks it the same way."""
    proj_py = raw_sessions / "e2e-demo"
    proj_rust = raw_sessions / "e2e-demo-rust"
    proj_py.mkdir(parents=True)
    proj_rust.mkdir(parents=True)
    (proj_py / "2026-04-09-e2e-python-demo.md").write_text(
        _DEMO_SESSION_PY, encoding="utf-8"
    )
    (proj_rust / "2026-04-09-e2e-rust-demo.md").write_text(
        _DEMO_SESSION_RUST, encoding="utf-8"
    )


_DEMO_WIKI_INDEX = """# Wiki Index

## Overview (1)
- [Overview](overview.md)

## Entities (2)
- [FastAPI](entities/FastAPI.md) — Python web framework
- [Rust](entities/Rust.md) — systems language

## Concepts (1)
- [HealthEndpoint](concepts/HealthEndpoint.md) — liveness probe route
"""

_DEMO_WIKI_OVERVIEW = """---
title: "Overview"
type: synthesis
tags: []
sources: [e2e-python-demo, e2e-rust-demo]
last_updated: 2026-04-09
---

# Overview

Two demo sessions: a [[FastAPI]] service exposing a [[HealthEndpoint]], and a
[[Rust]] CLI that prints a timestamp.
"""

_DEMO_WIKI_FASTAPI = """---
title: "FastAPI"
type: entity
tags: [python, web]
sources: [e2e-python-demo]
last_updated: 2026-04-09
---

# FastAPI

Python web framework used by the Python demo session.

## Connections
- [[HealthEndpoint]] — the route the demo scaffolded
"""

_DEMO_WIKI_RUST = """---
title: "Rust"
type: entity
tags: [systems]
sources: [e2e-rust-demo]
last_updated: 2026-04-09
---

# Rust

Systems language used by the Rust demo session.

## Connections
- [[FastAPI]] — the other demo project's stack
"""

_DEMO_WIKI_HEALTH = """---
title: "HealthEndpoint"
type: concept
tags: [api]
sources: [e2e-python-demo]
last_updated: 2026-04-09
---

# HealthEndpoint

A route that answers a liveness probe with a fixed payload.

## Connections
- [[FastAPI]] — framework that serves it
"""


def _seed_wiki(wiki_dir: Path) -> None:
    """Lay out a four-page wiki under ``wiki_dir``.

    The homepage links ``graph.html``, and the build emits that page only
    when the wiki it graphs has pages — so the fixture seeds a wiki with
    enough cross-links to yield a non-empty graph. The pages match the
    ``## Connections`` wikilinks in the seeded sessions above.
    """
    (wiki_dir / "entities").mkdir(parents=True)
    (wiki_dir / "concepts").mkdir(parents=True)
    (wiki_dir / "index.md").write_text(_DEMO_WIKI_INDEX, encoding="utf-8")
    (wiki_dir / "overview.md").write_text(_DEMO_WIKI_OVERVIEW, encoding="utf-8")
    (wiki_dir / "entities" / "FastAPI.md").write_text(_DEMO_WIKI_FASTAPI, encoding="utf-8")
    (wiki_dir / "entities" / "Rust.md").write_text(_DEMO_WIKI_RUST, encoding="utf-8")
    (wiki_dir / "concepts" / "HealthEndpoint.md").write_text(_DEMO_WIKI_HEALTH, encoding="utf-8")


# ─── fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def site_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the E2E demo site once per test session and return the
    path to the generated `site/` directory.

    The builder is imported lazily + monkeypatched so it never reads
    the user's real `raw/sessions/`. This fixture is session-scoped
    so all scenarios share a single built site — a full rebuild per
    scenario would make E2E unusable."""

    workspace = tmp_path_factory.mktemp("llmwiki_e2e")
    raw = workspace / "raw"
    raw_sessions = raw / "sessions"
    wiki = workspace / "wiki"
    _seed_raw(raw_sessions)
    _seed_wiki(wiki)

    original_raw_dir = build_mod.RAW_DIR
    original_raw_sessions = build_mod.RAW_SESSIONS
    build_mod.RAW_DIR = raw
    build_mod.RAW_SESSIONS = raw_sessions
    try:
        out = workspace / "site"
        rc = build_mod.build_site(out_dir=out, synthesize=False, wiki_dir=wiki)
        assert rc == 0, f"build_site returned {rc}"
    finally:
        build_mod.RAW_DIR = original_raw_dir
        build_mod.RAW_SESSIONS = original_raw_sessions
    return out


@pytest.fixture(scope="session")
def site_url(site_root: Path) -> str:
    """`file://` prefix for every `page.goto(...)` call — the address a
    reader uses when they double-click `index.html`.

    Returned without a trailing slash so call sites read
    `f"{site_url}/index.html"`. There is no directory index behind a
    `file://` URL, so every path must name a file.
    """
    return site_root.as_uri().rstrip("/")


@pytest.fixture(scope="session")
def site_has(site_root: Path) -> Callable[[str], bool]:
    """Predicate over site paths: ``site_has("/graph.html")``.

    Whether a page is part of the build is a fact about the output
    directory, so tests that skip on an absent page ask the filesystem.
    """

    def _has(path: str) -> bool:
        return (site_root / path.lstrip("/")).is_file()

    return _has


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object], browser_name: str) -> dict[str, object]:
    """Override the default pytest-playwright context args so the
    browser permissions include clipboard access (needed for the
    copy-as-markdown test). Merges with the upstream defaults.

    #636: clipboard-read / clipboard-write are chromium-only permission
    names — Firefox + WebKit raise `Unknown permission` if they're
    granted. Only set the permission list when running on chromium so
    the cross-browser smoke matrix can run without monkey-patching.
    """
    args: dict[str, object] = {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
    }
    if browser_name == "chromium":
        args["permissions"] = ["clipboard-read", "clipboard-write"]
    return args


@pytest.fixture()
def desktop_page(page):  # type: ignore[no-untyped-def]
    """Alias for `page` at desktop viewport. Playwright's default
    viewport from `browser_context_args` above is already 1280×800."""
    return page


@pytest.fixture()
def mobile_page(page):  # type: ignore[no-untyped-def]
    """Shrink the viewport to mobile (iPhone SE-ish) so scenarios
    that assert on `.mobile-bottom-nav` behavior run against the
    right media query."""
    page.set_viewport_size({"width": 375, "height": 667})
    return page


@pytest.fixture(autouse=True)
def _attach_console_listener(page):  # type: ignore[no-untyped-def]
    """Record every `console.error` and page-level error onto the
    `page` object so the "browser console has no errors" step can
    assert against a per-scenario buffer.

    Scoped per-test (function scope) so errors don't leak across
    scenarios. Uses a simple attribute to avoid monkeypatching the
    Playwright Page class."""
    errors: list[str] = []
    page._llmwiki_console_errors = errors  # type: ignore[attr-defined]

    def _on_console(msg) -> None:  # type: ignore[no-untyped-def]
        if msg.type == "error":
            errors.append(msg.text)

    def _on_pageerror(exc) -> None:  # type: ignore[no-untyped-def]
        errors.append(str(exc))

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    yield
    # Listeners auto-detach when the page closes at end-of-test.


# Make sure pytest-bdd can find step definitions. The import triggers
# registration via the `@given` / `@when` / `@then` decorators. We do
# this unconditionally (no try/except) so a broken import fails loudly
# at collection time rather than producing confusing
# "Step definition is not found" errors inside scenarios.
from tests.e2e.steps import ui_steps  # noqa: F401,E402

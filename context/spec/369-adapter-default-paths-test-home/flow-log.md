# Flow log — #369 lazy adapter defaults + session-store guard

## fix-bug #369 — scope (2026-11-06)

- Issue: [#369](https://github.com/AlexanderMakarov/llm-wiki/issues/369) — session adapters froze `Path.home()` at import, so tests with a per-run `HOME` sandbox still scanned the developer's real agent stores.
- Product: classmethods (`default_roots()`, `default_session_store_path()`, …) resolve defaults at use time; `tests/session_store_guard.py` blocks `open` / `os.scandir` / `sqlite3.connect` under real-home session prefixes; `tests/test_cross_platform_paths.py` uses current `Path.home()`.
- Docs: `docs/adapter-authoring.md`, CONTRIBUTING cross-platform path rule; CHANGELOG under `[Unreleased]`.

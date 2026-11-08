# Flow log — #369 lazy adapter defaults + session-store guard

## fix-bug #369 — scope (2026-11-06)

- Issue: [#369](https://github.com/AlexanderMakarov/llm-wiki/issues/369) — session adapters froze `Path.home()` at import, so tests with a per-run `HOME` sandbox still scanned the developer's real agent stores.
- Product: classmethods (`default_roots()`, `default_session_store_path()`, …) resolve defaults at use time; `tests/session_store_guard.py` blocks `open` / `os.scandir` / `sqlite3.connect` under real-home session prefixes; `tests/test_cross_platform_paths.py` uses current `Path.home()`.
- Docs: `docs/adapter-authoring.md`, CONTRIBUTING cross-platform path rule; CHANGELOG under `[Unreleased]`.

## workspace (2026-11-07)

- Pushed `fix/369-adapter-default-paths-lazy-home` to `origin` (`2c570cf`); primary checkout `MAIN` on `main`.
- Worktree: `.claude/worktrees/fix-369-adapter-default-paths-lazy-home` on branch `fix/369-adapter-default-paths-lazy-home`; throwaway vault `.worktree-vault/` + worktree `config.json`.

## verify + bugbot follow-ups (2026-11-07)

- Contrib `session_store_path` properties re-resolve `default_*()` when config does not override roots/vault/export paths; `discover_*` walks `session_store_path`, not cached `self.roots`.
- `session_store_guard` also wraps `os.stat` / `os.lstat` (probes under real-home session prefixes fail).
- Stale `DEFAULT_ROOTS` comment on OpenClaw/Codex removed.
- Next: full `pytest` (no pipe), local review (`review.md`), commit-push + PR.

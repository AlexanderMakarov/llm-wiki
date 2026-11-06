# #224 — install-agent-kit chained `.bak` files

When a customised kit file is overwritten more than once, the installer must not reuse `<name>.bak` if it already holds a prior rescue copy — the second backup lands at `<name>.bak.1`, `<name>.bak.2`, … If the file about to be overwritten already matches the existing `.bak` bytes, no new backup file is written (idempotent re-install). Product change: `llmwiki/install_agent_kit.py`; docs: `docs/reference/cli.md`, `CHANGELOG.md`.

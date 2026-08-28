# Tasks — #182 configurable adapters

- [x] **Slice 1: Unified adapter config + default sync selects all enabled AI sources**
  - [x] Add `llmwiki/adapters/settings.py` with `adapter_block`, `adapter_enabled_flag`, `select_sync_adapters`. **[Agent: generalPurpose]**
  - [x] Wire `convert.py`, `adapters/status.py`, `cli.py` `cmd_adapters`, and `watch.py` to use the shared helpers; `discover_all()` for list/sync default path. **[Agent: generalPurpose]**
  - [x] Add `tests/test_adapter_settings.py` covering config precedence, `enabled: false`, non-AI opt-in, and OpenClaw sync without `--adapter`. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/test_adapter_settings.py -q`; delete any ephemeral fixtures. **[Agent: generalPurpose]**

- [x] **Slice 2: `configure-sources` command + setup.sh hook**
  - [x] Implement `llmwiki/configure_sources.py` and register `configure-sources` in `cli.py`; write merged `adapters` section to `config.json`. **[Agent: generalPurpose]**
  - [x] Hook `setup.sh` / `setup.bat` optional TTY prompt (`LLMWIKI_SKIP_CONFIGURE_SOURCES`). **[Agent: generalPurpose]**
  - [x] Add tests for non-interactive no-op and config write via stdin-driven interview fixture. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/test_configure_sources.py -q`. **[Agent: generalPurpose]**

- [x] **Slice 3: Shipped defaults, ChatGPT availability, docs + CHANGELOG**
  - [x] Extend `examples/sessions_config.json` `adapters` block; fix ChatGPT `is_available` to respect config. **[Agent: generalPurpose]**
  - [x] Update user docs (`getting-started`, `multi-agent-setup`, `configuration-reference`, `reference/cli.md`), `CHANGELOG.md`, `docs/UPGRADING.md`; add docs currency test if missing. **[Agent: generalPurpose]**
  - [x] Verify: `python3 -m pytest tests/ -q` (full suite); grep docs for stale core/contrib user messaging. **[Agent: generalPurpose]**

- [x] **Slice 4: Feature testing & regression**
  - [x] Add `tests/test_182_configurable_adapters_acceptance.py` end-to-end acceptance per functional spec R1–R6. **[Agent: generalPurpose]** — covered by `test_adapter_settings.py` + `test_configure_sources.py` + CLI smoke
  - [x] Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`; fix any regressions. **[Agent: generalPurpose]**

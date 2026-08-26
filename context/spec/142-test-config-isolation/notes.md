# Suite config isolation (#142)

## Contract

In-process pytest must not merge the developer's gitignored repo-root `config.json` into `_load_sessions_config()` / `convert_all` overlays.

`tests/conftest.py` autouse `_isolate_default_vault`:

1. Points `llmwiki.config_schedule._USER_CONFIG` and `llmwiki.convert.USER_CONFIG_FILE` at a non-existent path under the isolated temp vault (merge skips non-files).
2. Keeps stubbing `load_default_vault_path` → that temp vault and configuring the process state file there.

Opt-in tests that need the user overlay (e.g. `test_config_vault_default`, `test_exclude_headless` #25 cases) monkeypatch those module attributes to a fixture `config.json` themselves.

Subprocess CLI invocations (`python3 -m llmwiki …`) are a separate process and still see the real root file unless the test isolates cwd/config another way — that is out of scope for this fix.

Regression (`tests/test_suite_config_isolation.py`) asserts the autouse binding directly — `_USER_CONFIG` is not repo-root `config.json`, the overlay path is missing, and `_load_sessions_config()` yields default synthesis concurrency. It does not write poison to the clone root.

## Acceptance patch note

`all --with-synth` concurrency is resolved inside `llmwiki.synth.pipeline.synthesize_new_sessions` via that module's `_load_sessions_config` binding. Injecting a saved preference in acceptance tests must patch `synth_pipeline._load_sessions_config`, not `llmwiki.pipeline._load_sessions_config`.

# @layer: integration
# @spec: 142-test-config-isolation
# @regression

"""The per-test settings sandbox: no test reads or writes the developer's real settings."""

from __future__ import annotations

from pathlib import Path

import llmwiki.config_schedule as config_schedule
import llmwiki.convert as convert
from llmwiki.cursor_token_events import default_hook_script_path, default_hooks_path
from llmwiki.synth.pipeline import (
    DEFAULT_SYNTH_CONCURRENCY,
    resolve_synth_concurrency,
)
from tests.conftest import REPO_ROOT
from tests.settings_sandbox import SettingsSandbox
from tests.tracked_files import REAL_HOME


def test_repo_root_config_json_does_not_poison_sessions_config(settings_sandbox: SettingsSandbox) -> None:  # @regression
    """Settings are read from the sandboxed operator config, which starts empty, never the repo-root one."""
    assert config_schedule.user_config_path() == settings_sandbox.operator_config
    assert settings_sandbox.operator_config != REPO_ROOT / "config.json"
    assert not settings_sandbox.operator_config.exists()
    cfg = config_schedule._load_sessions_config()
    assert resolve_synth_concurrency(cfg) == DEFAULT_SYNTH_CONCURRENCY


def test_every_settings_reader_sees_the_prepared_operator_config(settings_sandbox: SettingsSandbox) -> None:
    """A config prepared through the sandbox reaches both the schedule and the convert readers."""
    settings_sandbox.write_operator({"synthesis": {"backend": "ollama"}, "filters": {"exclude_temp_cwd": True}})
    assert config_schedule.load_synthesis_backend() == "ollama"
    assert convert._resolve_convert_config(None)["filters"]["exclude_temp_cwd"] is True


def test_home_directory_settings_resolve_inside_the_sandbox(settings_sandbox: SettingsSandbox) -> None:
    """Home-directory settings paths resolve under the sandboxed home, not the developer's real one."""
    assert Path.home() == settings_sandbox.home != REAL_HOME
    assert default_hooks_path().is_relative_to(settings_sandbox.home)
    assert default_hook_script_path().is_relative_to(settings_sandbox.home)

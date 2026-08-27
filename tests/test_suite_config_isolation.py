# @layer: integration
# @spec: 142-test-config-isolation
# @regression

"""Regression: in-process tests must not merge repo-root config.json (#142)."""

from __future__ import annotations

import llmwiki.config_schedule as config_schedule
from llmwiki.synth.pipeline import (
    DEFAULT_SYNTH_CONCURRENCY,
    resolve_synth_concurrency,
)
from tests.conftest import REPO_ROOT


def test_repo_root_config_json_does_not_poison_sessions_config() -> None:  # @regression
    """Autouse isolates _USER_CONFIG away from repo-root config.json."""
    assert config_schedule._USER_CONFIG != REPO_ROOT / "config.json"
    assert not config_schedule._USER_CONFIG.is_file()
    cfg = config_schedule._load_sessions_config()
    assert resolve_synth_concurrency(cfg) == DEFAULT_SYNTH_CONCURRENCY

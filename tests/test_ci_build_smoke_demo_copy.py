"""CI build-smoke must not stamp tracked demo/llmwiki-state (#255)."""

from __future__ import annotations

from llmwiki import REPO_ROOT

CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_build_smoke_copies_demo_before_build() -> None:
    """After demo state is tracked, smoke build must use a vault copy.

    ``llmwiki build`` stamps ``ops.last_build_at`` into the vault's
    ``llmwiki-state.json``. Building ``--vault demo`` would dirtify the
    checkout and fail the working-tree-clean gate in the same job.
    """
    text = CI.read_text(encoding="utf-8")
    assert "ci-demo-vault" in text
    assert "cp -a demo ./ci-demo-vault" in text
    assert "--vault ./ci-demo-vault" in text
    # The smoke step must not build the tracked checkout path.
    for line in text.splitlines():
        stripped = line.strip()
        if "llmwiki build" not in stripped:
            continue
        if "ci-demo-vault" in stripped or "perf-site" in stripped:
            continue
        assert "--vault demo" not in stripped, (
            f"lint-and-test smoke must not build tracked demo/: {stripped!r}"
        )

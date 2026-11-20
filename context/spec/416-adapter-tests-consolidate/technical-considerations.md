# Technical Specification: Mirror adapter unit tests under tests/adapters/

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

One PR creates `tests/adapters/` mirroring `llmwiki/adapters/` concerns (shared/core modules at the package root; contrib per-adapter modules under `tests/adapters/contrib/` when that mapping is clear), moves the bounded flat adapter unit-test batch into that tree (same workflow as #280 → `tests/cli/`, #315 → `tests/render/`, #316 → `tests/mcp/`), merges exact-duplicate contract cases / drops vacuous asserts only when clearly non-protective, keeps per-adapter enable/sync contracts as explicit named tests, extends quality-gate / CODING_STANDARDS mentions, and leaves product adapter behaviour untouched. No product behaviour change; 87% unit coverage floor unchanged.

Follow the #316 MCP convention: **no ticket-only `tests/adapters/__init__.py`** — pytest collects `test_*.py` under the directory without a package init; layout gates assert the directory has `test_*.py` modules (and optionally that `contrib/` has modules when used). Prefer `from tests._paths import REPO_ROOT` (or existing shared helpers) over fragile `Path(__file__).parents[N]` after the move.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Inclusion criteria (approved — batch option 1)

**In batch (move into `tests/adapters/`):**

| Current path | Target under `tests/adapters/` |
|---|---|
| `test_adapters.py` | `test_registry.py` |
| `test_adapter_config.py` | `test_config.py` |
| `test_adapter_settings.py` | `test_settings.py` |
| `test_adapter_is_available_unified.py` | `test_is_available.py` |
| `test_adapter_is_headless_contract.py` | `test_is_headless_contract.py` |
| `test_adapter_exclude_headless_slice3.py` | `test_exclude_headless.py` |
| `test_adapter_tag.py` | `test_tag.py` |
| `test_adapter_graduation.py` | `test_graduation.py` |
| `test_no_phantom_adapters.py` | `test_no_phantoms.py` |
| `test_chatgpt_adapter.py` | `contrib/test_chatgpt.py` |
| `test_copilot_adapters.py` | `contrib/test_copilot.py` |
| `test_cursor_ide_adapter.py` | `contrib/test_cursor_ide.py` |
| `test_openclaw_cursor_cli_adapters.py` | `contrib/test_openclaw_cursor_cli.py` |
| `test_opencode_adapter.py` | `contrib/test_opencode.py` |

**Stay put (this PR):** `test_182_configurable_adapters_acceptance.py`; `test_180_exclude_headless_acceptance.py`; `test_watch_adapters.py`; `test_docs_adapter_currency.py`; non-adapter modules; Playwright/e2e; product code under `llmwiki/adapters/`.

### 2.2 Package layout

```
tests/adapters/
  test_registry.py
  test_config.py
  test_settings.py
  test_is_available.py
  test_is_headless_contract.py
  test_exclude_headless.py
  test_tag.py
  test_graduation.py
  test_no_phantoms.py
  contrib/
    test_chatgpt.py
    test_copilot.py
    test_cursor_ide.py
    test_openclaw_cursor_cli.py
    test_opencode.py
```

No `tests/adapters/__init__.py` / no nested ticket-only init under `contrib/` unless a real shared helper requires a package. Align module names with concerns, not issue numbers. Issue/spec links in module docstrings / `# @spec:`.

**Path fixes:** any `Path(__file__).parent…` that assumed `tests/` depth must be rechecked after nesting under `tests/adapters/` or `tests/adapters/contrib/` (chatgpt fixture path writes under `parent.parent` today — under `contrib/` that becomes wrong). Prefer `tests._paths.REPO_ROOT` or `tmp_path`.

### 2.3 Hygiene rules (batch-only)

- Search before merge; one protective check per behaviour when two modules assert the **same** outcome (watch overlaps between `test_graduation` Cursor contract vs `contrib/test_cursor_ide`, and between `test_is_headless_contract` vs `test_exclude_headless` / per-adapter headless cases — keep registry-wide contract + slice-specific behaviour; drop only exact duplicates).
- Keep per-adapter enable/sync / registry / availability / headless contracts as **explicit** named tests (ticket non-negotiable).
- Delete vacuous / tautology / import-path-only asserts only when clearly non-protective; do not delete to hit a count target.
- One-sentence behaviour docstring per test or parametrize group touched.
- Grep and update docstring / docs / acceptance pointers that hardcode old flat paths (`tests/test_*adapter*.py`, etc.). Historical CHANGELOG path mentions stay.
- Extend `tests/test_quality_gates.py` + `docs/CODING_STANDARDS.md` to name `tests/adapters/` like `tests/cli/` / `tests/render/` / `tests/mcp/`. Layout gate: directory exists with `test_*.py` (and `contrib/` has `test_*.py` if that subtree is used). Do **not** add a hard-coded inventory of migrated filenames (CODING_STANDARDS: tests assert product behaviour, not the edit).
- AWOS notes under `context/spec/416-adapter-tests-consolidate/`; CHANGELOG only if contributor-visible — prefer editing the existing Unreleased testing/standards / mirror-layout bullets to add #317 / `tests/adapters/` rather than a separate “adapters tests moved” entry.

### 2.4 Out of product code

No changes to `llmwiki/adapters/` behaviour — tests and contributor docs/gates only.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** pytest collection of `tests/`; `test_quality_gates`; CODING_STANDARDS; docs under `docs/adapters/` that cite flat test paths; acceptance modules that mention old paths.
- **Potential Risks & Mitigations:**
  - Broken relative paths after nesting under `contrib/` → grep `Path(__file__)` / `parents[` in moved files; use `REPO_ROOT` or `tmp_path`.
  - Coverage dip from over-deletion → delete only vacuous/exact-duplicate; full `--cov` before push.
  - Losing enable/sync/headless contracts in a merge → keep those tests named and present.
  - Oversized PR → batch is bounded to the table in §2.1; do not pull stay-put modules.
  - Cross-test string refs to old module names → grep and update.

---

## 4. Testing Strategy

- `ruff check llmwiki tests scripts`
- `python3 -m pytest tests/adapters/ -q`
- `python3 -m pytest tests/ -q`
- `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (≥87%)
- `python3 -m pytest tests/test_quality_gates.py -q`

No new harness; no Playwright move; no mutation tooling.

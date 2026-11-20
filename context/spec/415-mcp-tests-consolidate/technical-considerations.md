# Technical Specification: Mirror MCP unit tests under tests/mcp/

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

One PR creates `tests/mcp/` mirroring `llmwiki/mcp/` concerns, moves the bounded flat `tests/test_mcp_*.py` batch into that tree (same workflow as #280 → `tests/cli/` and #315 → `tests/render/`), merges exact-duplicate cases / drops vacuous asserts only when clearly non-protective, keeps timeout / lock / add-as-CLI-proxy contracts as explicit named tests, extends quality-gate / CODING_STANDARDS mentions, and leaves product MCP wire behaviour untouched. No product behaviour change; 87% unit coverage floor unchanged.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Inclusion criteria (approved)

**In batch (move into `tests/mcp/`):**

| Current path | Target under `tests/mcp/` |
|---|---|
| `test_mcp_protocol.py` | `test_protocol.py` |
| `test_mcp_enhanced.py` | `test_tools.py` |
| `test_mcp_safety.py` | `test_safety.py` |
| `test_mcp_byte_cap.py` | `test_byte_cap.py` |
| `test_mcp_read_page_allowlist.py` | `test_read_page_allowlist.py` |
| `test_mcp_lint_parity.py` | `test_lint_parity.py` |
| `test_mcp_caller_attribution.py` | `test_caller_attribution.py` |
| `test_mcp_usage.py` | `test_usage.py` |
| `test_mcp_wiki_add.py` | `test_wiki_add.py` (timeout / lock stay here) |
| `test_mcp_add_cli_proxy.py` | `test_add_cli_proxy.py` (proxy acceptance stays here) |

**Stay put (this PR):** non-MCP modules; Playwright/e2e; adapters / synth / other package mirrors (#317, #318); product code under `llmwiki/mcp/`.

### 2.2 Package layout

```
tests/mcp/
  test_*.py            # consolidated modules as above
```

No ticket-only `tests/mcp/__init__.py` — pytest collects `test_*.py` under the directory without a package init; quality gates assert the directory has modules. Use shared `from tests._paths import REPO_ROOT` (`tests/_paths.py` already resolves repo root via `parents[1]`). Do **not** add a nested `tests/mcp/_paths.py` unless a second shared helper is required. Align module names with concerns, not issue numbers. Issue/spec links in module docstrings / `# @spec:`.

**Path fix required:** `test_mcp_protocol.py` currently uses `Path(__file__).resolve().parent.parent` for repo root — under `tests/mcp/` that becomes wrong; switch to `tests._paths.REPO_ROOT` (or `parents[2]`).

### 2.3 Hygiene rules (batch-only)

- Search before merge; one protective check per behaviour when two modules assert the **same** outcome (especially overlapping default-build / synth-opt-in slices between `wiki_add` and `add_cli_proxy`).
- Keep timeout/poll, lock-holder, and CLI-proxy acceptance contracts as **explicit** named tests (ticket non-negotiable).
- Delete vacuous / tautology / import-path-only asserts only when clearly non-protective; do not delete to hit a count target.
- One-sentence behaviour docstring per test or parametrize group touched.
- Grep and update docstring / acceptance pointers that hardcode old flat paths (`tests/test_102_acceptance.py`, `tests/test_150_acceptance.py`, etc.). Historical CHANGELOG path mentions stay.
- Extend `tests/test_quality_gates.py` + `docs/CODING_STANDARDS.md` to name `tests/mcp/` like `tests/cli/` / `tests/render/`.
- AWOS notes under `context/spec/415-mcp-tests-consolidate/`; CHANGELOG only if contributor-visible (prefer editing an existing Unreleased testing/standards bullet if one already covers mirror layout).

### 2.4 Out of product code

No changes to `llmwiki/mcp/` behaviour — tests and contributor docs/gates only.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** pytest collection of `tests/`; `test_quality_gates`; CODING_STANDARDS; acceptance modules / specs that cite `tests/test_mcp_*.py` paths.
- **Potential Risks & Mitigations:**
  - Broken `REPO_ROOT` in protocol subprocess tests → use `tests._paths.REPO_ROOT`; grep `parents[` in moved files.
  - Coverage dip from over-deletion → delete only vacuous/exact-duplicate; full `--cov` before push.
  - Losing timeout/lock/proxy contracts in a merge → keep those tests named and present under `test_wiki_add.py` / `test_add_cli_proxy.py`.
  - Oversized PR → batch is already bounded to the ten `test_mcp_*` modules; do not pull in unrelated flat tests.
  - Cross-test string refs to old module names → grep and update.

---

## 4. Testing Strategy

- `ruff check llmwiki tests scripts`
- `python3 -m pytest tests/mcp/ -q`
- `python3 -m pytest tests/ -q`
- `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (≥87%)
- `python3 -m pytest tests/test_quality_gates.py -q`

No new harness; no Playwright move; no mutation tooling.

# Technical Specification: Product principles and maintainer doc clarity

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov
- **Approval notes (2026-09-08):** Operator approved after rebase onto fresh `origin/main` (includes #237 command-surface parity).

---

## 1. High-Level Technical Approach

Docs-only change on branch `feat/docs-product-principles`. No Python package behavior changes. PyPI long description continues to come from `README.md` (`pyproject.toml` `readme = "README.md"`). New evergreen principles live under `docs/maintainers/`. Brand canonical path moves from `docs/design/` to `docs/maintainers/`; update live links + `tests/test_brand_system_doc.py` path assertions. Soften one DECLINED reason. Touch `context/` (this spec + a short product note) for the product-PR gate.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Documentation layout

| Action | Path |
|---|---|
| Create | `docs/maintainers/principles.md` — intentions; link to `DECLINED.md`; no personal metrics; no essay paste |
| Move | `docs/design/brand-system.md` → `docs/maintainers/brand-system.md`; delete empty `docs/design/` |
| Edit | `README.md` — problem lede; What you get bullet for documents; richer `add` examples in The loop; docs table row for principles |
| Edit | `docs/architecture.md` — short pointer to principles near the Karpathy-layer intro |
| Edit | `docs/index.md` — link principles (and brand under maintainers if indexed) |
| Edit | `docs/getting-started.md` — subsection on adding a document (file / URL / PDF / folder) |
| Edit | `docs/reference/ui.md`, `reader-shell.md`, `reader-api.md` — brand path `../maintainers/brand-system.md` |
| Edit | `docs/maintainers/README.md` — table rows for `principles.md` and `brand-system.md` |
| Edit | `docs/maintainers/DECLINED.md` — qmd dependency reason: drop `3.9+` / any pinned Python version; keep stdlib + no Node |
| Edit | `CHANGELOG.md` `[Unreleased]` — Added/Changed bullets + release-note lines |
| Edit | `tests/test_brand_system_doc.py` — `BRAND_DOC` path + assertion strings |
| Edit | `context/product/` note or architecture cross-link as needed for CI product-PR filter (spec dir alone may suffice if path filter counts `context/spec/`; if CI requires `context/product/`, add a one-line roadmap or architecture note) |

### Brand typography wording

Replace “first-class system support on all three major OSes” with: preferred faces Inter / JetBrains Mono, with documented system fallback stacks; fonts may need installing; still never bundle font files in the package. Do **not** change `llmwiki/build.py` Google Fonts links in this PR.

### Principles content (source of truth for copy)

Distill from the operator-approved outline only:

1. Boundary problem (cross-tool / cross-project session memory)
2. Cheap by default (static site, on-demand stdio MCP, markdown files, no vector DB)
3. Measure then strip (synthesis context trim as method; no private token stats)
4. Sessions + documents (`llmwiki add` as scriptable intake)
5. Human candidate gate; contradictions kept side by side
6. Analytics as product signal (retrievals-per-page as idea only)
7. See also: `DECLINED.md`

### Explicit non-edits

- `CONTRIBUTING.md` — no article link; no principles section required this PR
- `docs/maintainers/TRIAGE.md`, triage slash command, maintainer slash-command list — unchanged
- Demo `raw/docs/**` historical citations of `docs/design/` — leave for demo refresh
- No `docs/essays/`

### Markdown conventions

One paragraph per line (no hard-wrap). Placeholders only for paths/usernames.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** PyPI description regenerates on next publish from README; until then PyPI stays stale relative to git. Brand test fails if path move incomplete. Link-check / CI greps may flag absolute personal paths — avoid them.
- **Potential Risks & Mitigations:** Broken relative links after the brand move — grep `docs/design` and update live docs + test. Over-copying essay voice into principles — keep short bullets. Accidental personal metrics — review diff before commit.

---

## 4. Testing Strategy

- Update and run `tests/test_brand_system_doc.py` (path + any string assertions about OS support if present).
- `ruff check llmwiki tests scripts` (expect no Python logic changes beyond the test path).
- `python3 -m pytest tests/ -q` with focus on brand doc tests; full suite before push.
- Manual: open README + principles + getting-started + brand path; confirm DECLINED qmd entry has no version pin; confirm TRIAGE still mentions `/triage-issue` (intentionally unchanged).

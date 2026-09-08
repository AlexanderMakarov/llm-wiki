# Tasks: Product principles and maintainer doc clarity

Spec: `227-product-principles-docs`. Worktree root only. Vault writes only to `$WT/.worktree-vault` if needed (not required for this docs change).

Agents: docs/layout → `general-purpose` (no hired docs agent); verification → `testing-expert`.

---

- [ ] **Slice 1: Principles page + DECLINED version wording**
  - [ ] Create `docs/maintainers/principles.md` per tech outline; link `DECLINED.md`; no personal vault metrics; no essay paste. Soften DECLINED qmd-dependency reason to drop any pinned Python version (e.g. `3.9+`). Add table rows in `docs/maintainers/README.md` for `principles.md` (and leave brand row for Slice 2 if brand not moved yet — or add both rows when Slice 2 lands). Link principles from `docs/architecture.md` and `docs/index.md`. **[Agent: general-purpose]**
  - [ ] Verify: principles file exists; contains human gate / cheap-to-run / documents+sessions; links to DECLINED; DECLINED qmd entry has no `3.9` / version pin; architecture + index link principles; `rg` for personal essay metrics (732 sessions, 7.5B, etc.) returns nothing in new/edited docs. Clean any ephemeral files. **[Agent: testing-expert]**

- [ ] **Slice 2: Brand system under maintainers**
  - [ ] Move `docs/design/brand-system.md` → `docs/maintainers/brand-system.md`; remove empty `docs/design/`. Fix typography claim (Inter / JetBrains Mono preferred with fallbacks; not preinstalled on all OSes; still no bundled font files). Update live links in `docs/reference/ui.md`, `reader-shell.md`, `reader-api.md`, `docs/maintainers/README.md`. Update `tests/test_brand_system_doc.py` path + assertion strings. Do not change `llmwiki/build.py` Google Fonts. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_brand_system_doc.py -q` green; no live docs link to `docs/design/brand-system.md`; brand doc lacks “first-class system support on all three major OSes”. Clean ephemeral files. **[Agent: testing-expert]**

- [ ] **Slice 3: README / PyPI fold + getting-started add**
  - [ ] Elevate document add on README (problem lede for cross-tool memory; What you get bullet; richer `llmwiki add` examples for file/URL/PDF/folder in The loop; docs table link to principles). Add getting-started subsection for adding a document. No article URL in CONTRIBUTING; no personal metrics. **[Agent: general-purpose]**
  - [ ] Verify: README mentions add for documents with multi-kind examples; getting-started has add section; CONTRIBUTING has no article link; no personal vault stats. Clean ephemeral files. **[Agent: testing-expert]**

- [ ] **Slice 4: CHANGELOG**
  - [ ] Add `[Unreleased]` entries (Added principles; Changed brand path + font honesty; Changed DECLINED Python wording; Changed README/getting-started) with release-note bullets. **[Agent: general-purpose]**
  - [ ] Verify: Unreleased section lists this work; no personal paths/usernames. **[Agent: testing-expert]**

- [ ] **Slice 5: Feature Testing & Regression**
  - [ ] Run full `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` from worktree; confirm acceptance criteria from functional-spec R1–R5, R6 (DECLINED), R7 (CHANGELOG + context/spec present). Annotate any new tests with `@spec` / `@regression` only if added. **[Agent: testing-expert]**

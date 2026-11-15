# Technical Specification: Delete dishonest uptime monitoring guide

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Delete `docs/uptime.md`. Retarget every in-repo link that pointed at it to `docs/deploy/github-pages.md` (and keep `docs/maintainers/RELEASE_PROCESS.md` self-contained for the two Pages publishers). Drop CI/doc-contract assertions that require `docs/uptime.md` to exist. Remove the mirrored demo raw + wiki source for that guide and prune catalog / entity links that only existed for it. Add a `CHANGELOG.md` *Removed* bullet under `[Unreleased]`.

No product code, no new workflow file, no Actions version bumps in this change.

## 2. Proposed Solution & Implementation Plan (The "How")

### Docs

- **Delete:** `docs/uptime.md`.
- **Retarget links:**
  - `docs/deploy/github-pages.md` — remove `(see [uptime.md](../uptime.md))`; the Step 4 publisher list and post-deploy verify sections already carry the “up vs current” material.
  - `docs/maintainers/RELEASE_PROCESS.md` — drop the `docs/uptime.md` link; keep the `github-pages.md` link (and the in-page publisher bullets).
- **Do not** invent a replacement uptime.yml or badge snippet.

### Demo corpus

- Delete `demo/raw/docs/uptime/uptime-monitoring.md` (and empty `uptime/` dir if left empty).
- Delete `demo/wiki/sources/uptime/2026-09-28-uptime-monitoring.md` (and empty dir).
- Update `demo/wiki/index.md` to remove the Uptime Monitoring catalog row.
- Drop `[[2026-09-28-uptime-monitoring]]` (and related `sources:` slug if present) from `demo/wiki/candidates/entities/LLM Wiki.md` where it only cites that source.
- Update `demo/llmwiki-state.json` key for `docs::uptime/uptime-monitoring.md` if present (remove that entry).
- Fix `demo/raw/docs/deploy-github-pages/deploying-to-github-pages-01.md` link away from `uptime.md`; while editing that sentence, remove the stale “no separate scheduled freshness workflow” claim so it does not contradict `#225` / `demo-session-freshness.yml` (point readers at the Pages deploy doc’s publisher list instead).

### Tests / contracts

- In `tests/test_demo_session_freshness_workflow.py`:
  - Remove `UPTIME_DOC` and `test_uptime_doc_names_freshness_workflow`.
  - Remove `uptime.md` from `test_no_stale_claim_about_no_separate_freshness_schedule`’s `docs_to_check` map.
  - Leave `test_github_pages_doc_names_freshness_workflow` and `RELEASE_PROCESS` / skill / REFRESH_DEMO contracts intact — those docs remain the source of truth.

### Changelog

- Under `## [Unreleased]` → `### Removed`: one bullet that the uptime monitoring guide was deleted because it documented a non-existent workflow (`#288`), with a one-line release note.

### Explicitly not in this PR

- Upgrading `actions/*` / other marketplace actions for Node 20→24 deprecation warnings — separate `chore` issue/PR (CONTRIBUTING one-concern; not acceptance criteria for #288).

## 3. Impact and Risk Analysis

- **System Dependencies:** Static docs, demo vault fixtures, and one pytest module that greps doc text. No CLI/runtime behaviour.
- **Potential Risks & Mitigations:**
  - Broken external bookmarks to `docs/uptime.md` — accepted; honesty over preserving a false page. In-repo links must be grepped clean.
  - Losing unique “what to monitor / external services / incident” prose that lived only in uptime.md — accepted under option 2; deploy troubleshooting already covers stale-after-deploy. Do not re-home the fake workflow YAML.
  - Demo state / index drift leaving orphans — prune index, wiki source, state key, and entity wikilink in the same change; run the freshness workflow test file + a path-existence grep.

## 4. Testing Strategy

- `pytest tests/test_demo_session_freshness_workflow.py -q` must pass after removing uptime contracts.
- Repo grep: no remaining references to `docs/uptime.md` or `uptime.yml` badge in tracked docs (historical `context/spec/**` mentions of the old file are fine as delivery records).
- Confirm `docs/uptime.md` and demo uptime raw/wiki paths are absent on the branch.

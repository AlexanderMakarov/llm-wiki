# Technical Specification: Pages-only demo session freshness (#225)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Add a scheduled GitHub Actions publisher beside the existing tag/dispatch Pages path. The new job checks out **`main`** (current generator scripts + committed `demo/`), slides synthetic demo **session** calendar fields forward with `generate_demo_sessions.py --today` (UTC), builds the static demo site, and deploys to the **same** GitHub Pages site. It never commits, never runs synth/LLM, never refreshes demo docs or usage fixtures. Release-time `pages.yml` still publishes the committed demo from the version tag.

**Locked decisions:** cron `0 4 */6 * *` (max gap ~7 days; shorter gaps OK) · checkout **`main`** (Option 1) · separate workflow file · docs corrected in the same PR · shared `pages` concurrency kept as cheap insurance only.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Workflows

| Piece | Responsibility |
|---|---|
| `.github/workflows/pages.yml` | Unchanged intent: `v*.*.*` tag + `workflow_dispatch` build **committed** `demo/` as-of that ref → deploy → version assert vs that ref’s `__version__` |
| **New** `.github/workflows/demo-session-freshness.yml` | Schedule path: checkout **`main`** → session redate → reconcile → build → deploy → version assert vs **`main`’s** `__version__`; **no** git write; **no** synth |
| Shared | `permissions`: `contents: read`, `pages: write`, `id-token: write`; `concurrency.group: pages`, `cancel-in-progress: false`; environment `github-pages` |

### Schedule

```text
cron: '0 4 */6 * *'   # 04:00 UTC on day-of-month 1, 7, 13, 19, 25
```

- Typical interval: **6 days**.
- **Max** interval: **~7 days** (25 → next month’s 1 after a 31-day month).
- Shorter gaps after short months are acceptable.
- Also allow `workflow_dispatch` for maintainer dry runs.

### Session redate (no LLM)

On the runner, after checkout of `main`:

1. `python3 scripts/generate_demo_sessions.py --today "$(date -u +%F)"` — offline; in-place by slug; writes `demo/`, `demo/.demo-sessions-date`, `tests/fixtures/demo_search_terms.json`; runs offline `migrate source-page-paths`. Non-zero exit fails the job.
2. `python3 scripts/reconcile_synth_state_from_wiki.py --vault demo` (existing Pages step; no LLM).
3. `python -m llmwiki build --vault demo --out ./site --local-root /home/user`
4. `.nojekyll` → upload Pages artifact → `deploy-pages`
5. `python3 scripts/check_live_version.py --url "$PAGE_URL" …` against the checked-out **`main`** tree’s `llmwiki.__version__`

**Hard ban on this path:** `llmwiki synth`, LLM/API credentials, `refresh_demo.py`, `git push` / commit / PR creation.

### Checkout = `main` (Option 1) — version implication

- Freshness job always uses the **current** `generate_demo_sessions.py` and migrate code on `main`, avoiding “last release’s stale generator” skew.
- Live demo **`manifest.json` version** after a schedule deploy follows **`main`’s `__version__`**, which may be **ahead of the last PyPI/tag release** until the next cut.
- Functional FR6 is interpreted as: schedule must not invent a random version; it publishes whatever version `main` currently declares, and tag deploys still assert the tagged release version. Docs must state this split explicitly (release tag vs between-release `main` freshness publish).

### Generator confidence before relying on schedule

- Extend/keep tests so `generate_demo_sessions.py --today` is proven offline, rehomes source pages, and yields a buildable demo (existing `tests/test_generate_demo_sessions.py` + any thin age/helper coverage needed).
- Same PR must not ship a schedule that calls a generator the test suite does not cover for the write path used in CI.

### Docs / skill (must correct — not leave stale)

Update text that currently claims there is no scheduled freshness / CI never regenerates sessions:

- `docs/maintainers/RELEASE_PROCESS.md`
- `docs/uptime.md`
- `docs/deploy/github-pages.md`
- `docs/maintainers/REFRESH_DEMO.md`
- `.claude/skills/release/SKILL.md`
- `scripts/generate_demo_sessions.py` module doc (Pages-only schedule may redate on the runner; still never commits)

Document the split:

- **Release / tag `pages.yml`:** committed full demo (sessions + docs + synth + usage as today); version = that tag.
- **Schedule `demo-session-freshness.yml`:** from `main`, sessions-only date slide → Pages; no git write; no synth; no docs/usage regen; version = `main`’s `__version__`.

### CHANGELOG / AWOS

- `CHANGELOG.md` `[Unreleased]` — maintainer-facing demo Pages freshness schedule.
- Spec dir `context/spec/225-demo-release-freshness/` ships with the PR (workflows touch AWOS context gate).

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| Stale generator on last tag | **Avoided** by checking out `main` |
| Live version ahead of last PyPI release between cuts | Documented; tag deploy still pins released version when cutting |
| Cron month-boundary gap up to ~7 days | Accepted by product |
| Overlap with tag deploy | Unlikely at 04:00 UTC; keep shared `concurrency.group: pages` only |
| Wiki body dates lag after migrate-without-synth | Accepted (sessions-only / no synth in CI) |
| Runner dirties `demo/` + search fixture files | Never commit; discard workspace |
| Schedule fails | Prior Pages deploy remains; failed Actions run visible |
| Broken generator on `main` | Tests + verify write path before merge |

**Dependencies:** `generate_demo_sessions.py`, `migrate_source_page_paths`, existing Pages actions, `check_live_version.py`, `reconcile_synth_state_from_wiki.py`.

---

## 4. Testing Strategy

- Workflow contract tests (extend `tests/test_pages_deploy.py` or add `tests/test_demo_session_freshness_workflow.py`): file exists; cron `0 4 */6 * *`; `workflow_dispatch`; steps include `generate_demo_sessions`, build, deploy; **no** `git push` / `synth`; concurrency `pages`; checkout is default/`main` (no release-tag-only ref for the freshness job).
- Generator: extend `tests/test_generate_demo_sessions.py` as needed for the CI write path (offline, rehome, non-zero on migrate errors).
- No live network Pages assert in unit tests; rely on workflow contract + existing `check_live_version` unit coverage if any.

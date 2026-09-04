# Technical Specification: Cross-agent release skill

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Add a **maintainer-only** skill at `.claude/skills/release/SKILL.md` as the **scripted release cut**: a step-by-step procedure the agent executes (preflight → bump → editorial → commit/tag → human gate → push → watch automation). Claude’s existing `.claude/commands/release.md` becomes a thin `/release <version>` wrapper that loads that skill. Cursor already reads `.claude/skills/` (no duplicate under `.cursor/skills/`). Add a thin `.cursor/commands/release.md` so Cursor has an explicit `/release` slash entry. Rewrite `docs/maintainers/RELEASE_PROCESS.md` to match current automation (`main`, tag → `release.yml`, human push gate). No new Python package code; no agent-kit packaging. Mechanical steps are commands the skill lists (`gh`, `pytest`, `ruff`, `git`) — not a separate `scripts/release-*.sh` tree (those remain out of scope unless a later decision adds them).

---

## 2. Proposed Solution & Implementation Plan

### Skill (canonical)

| Path | Role |
|---|---|
| `.claude/skills/release/SKILL.md` | Agent-agnostic checklist; `name: release`, `description` with triggers (`/release`, “cut a release”, “tag vX.Y.Z”), optional `argument-hint: "<version>"` |

Body structure (mirror `gha-diagnosis` / `project-maintainer` tone):

1. Load `docs/maintainers/RELEASE_PROCESS.md` first; skill may be slightly more operational than the doc but must not contradict it.
2. **Preflight:** `gh run list --branch main`, `gh issue list --label priority:critical --state open`, `ruff check llmwiki tests scripts`, `python3 -m pytest tests/ -q` (warn/rename aside if root gitignored `wiki/` exists — do not delete user data without asking), `python3 -m llmwiki --version` after bump.
3. **Version bump files:** `llmwiki/__init__.py` `__version__`, `pyproject.toml` `version`, README version badge (keep current badge color/URL style).
4. **Editorial (agent judgment):** promote `CHANGELOG.md` `[Unreleased]` → `## [X.Y.Z] — YYYY-MM-DD` + Theme; empty Unreleased scaffold; rename/compact `docs/UPGRADING.md` Unreleased headings; ensure `tests/changelog_notes.shipping_section_text` still finds older shipping bullets (helper already searches all versioned sections — do not regress).
5. **Commit + tag locally:** conventional `release(vX.Y.Z): …` message; `git tag vX.Y.Z`.
6. **Human gate:** stop; show `git show` / version / Theme; push `origin main` + tag **only after explicit approval**.
7. **Post-push:** watch `release.yml` on the tag; report GitHub Release URL; note PyPI skipped unless `PYPI_PUBLISHING=true`; watch CI on the release commit SHA.
8. **Hard rules (in the skill body):** no force-push; no amend after tag; no unattended publish (always wait for explicit human approval before `git push` of `main` + tag).

**Spec-only (not skill body):** `/implement-feature` must not auto-invoke release — keep that boundary in this doc and the functional spec’s Out-of-Scope; do not put an “do not invoke from implement-feature” line in `SKILL.md` (obvious to maintainers and noise in the cut checklist).

### Wrappers

| Path | Role |
|---|---|
| `.claude/commands/release.md` | Thin: Usage `/release <version>`; “follow `.claude/skills/release/SKILL.md` and `RELEASE_PROCESS.md`”; pass `$ARGUMENTS` as version. Remove divergent stale steps (master, always `--prerelease`, manual `gh release create` as the happy path). |
| `.cursor/commands/release.md` | Same thin wrapper for Cursor slash discovery (optional but in-scope for FR1 “Claude + Cursor can invoke `/release`”). |

Keep `release` in `tests/test_slash_cli_parity.py` governance / `NON_WRAPPER_SLASHES` lists (already present).

### Docs

Update in the same PR (current tense):

- `docs/maintainers/RELEASE_PROCESS.md` — `main` not `master`; tag push triggers `.github/workflows/release.yml` (GitHub Release + Sigstore; PyPI if enabled); prerelease only for tags matching rc/alpha/beta/dev; drop “always `--prerelease` until 1.0” as the default path now that we are past 1.0/2.x; human approval before push; pitfalls appendix (root `wiki/`, changelog helper).
- `docs/maintainers/README.md` — `/release` loads the skill.
- `docs/reference/slash-commands.md` — `/release` blurb matches skill (no “always invent a second create”).
- `CHANGELOG.md` Unreleased — Added/Changed for the skill + process doc fix.
- Brief pointer in `docs/reference/cli.md` contributor-only note if it still implies slash-only release with no skill.

`AGENTS.md` / `CLAUDE.md` vault schemas: **do not** document maintainer release skill there (they are product vault schemas, not contribution guides). **Required:** a short pointer under `docs/maintainers/` (README and/or `RELEASE_PROCESS.md` intro) that the canonical cut instructions live in `.claude/skills/release/SKILL.md` and are invoked as `/release` (Claude/Cursor wrappers).

### Codex / other agents

No new installer path. Existing `llmwiki` skill installer already mirrors `.claude/skills/*` → `.codex/skills` / `.agents/skills` when someone runs install against this checkout’s skills tree. Document in the skill “Available wherever `.claude/skills/release` is installed (Cursor/Claude read that tree; Codex via skill install).”

### Out of package surface

- Not under `llmwiki/agent_kit/`
- Not under `.cursor/skills/` (would duplicate; Cursor reads `.claude/skills/`)

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| Skill and `RELEASE_PROCESS.md` drift again | Thin wrappers; skill says process doc is canonical for checklist order; PR updates both together |
| Accidental unattended push | Explicit human-gate step; never script push |
| Acceptance tests fail after emptying Unreleased | Skill + process doc call out `shipping_section_text`; do not narrow that helper |
| Cursor users never see `/release` | Add `.cursor/commands/release.md` |
| Skill mistaken for end-user kit | Frontmatter description “maintainer / cutting a tagged llmwiki release”; docs say contributor-only |

**System dependencies:** GitHub Actions `release.yml`, `gh`, existing pytest/ruff gates. No runtime product code change.

---

## 4. Testing Strategy

- **Docs / packaging:** extend or add a small test that `.claude/skills/release/SKILL.md` exists and frontmatter has `name: release`; keep slash parity (`release` still under `.claude/commands/`).
- **Content smoke:** assert skill or `RELEASE_PROCESS.md` mentions `main` and does **not** instruct `git push origin master` as the happy path; assert no “always `--prerelease`” for every release after 1.0 (or equivalent stale phrase removed).
- **Manual:** dry-run reading the skill against the v2.1.0 checklist in review (no second live tag in this PR).
- No E2E that pushes tags.

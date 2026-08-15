---
name: verification-rules
load: always
applies_to: "**/*"
---

# Verification rules (always loaded)

Before marking anything as done, verify it per the rules below. These map to the parent framework's "Verification Iron Law: no claims without fresh evidence."

## Code changes

Before marking a code PR as done:

- [ ] `python3 -m llmwiki --version` prints the version
- [ ] `python3 -m llmwiki adapters` lists the expected adapters
- [ ] All tests pass: `python3 -m pytest tests/ -q`
- [ ] Privacy grep returns zero: `grep -r "<your_username>" site/ wiki/`
- [ ] CI is green on the PR
- [ ] The file you touched has at least one test (or is justifiably untestable — say why in the PR)
- [ ] No new runtime deps added without updating `README.md` and `docs/configuration.md`

## Adapter additions

Before marking a new adapter as done:

- [ ] Subclasses `BaseAdapter`
- [ ] Registered with `@register("<name>")`
- [ ] `SUPPORTED_SCHEMA_VERSIONS` is set
- [ ] Fixture exists under `tests/fixtures/<adapter>/`
- [ ] Snapshot test exists under `tests/snapshots/<adapter>/`
- [ ] Graceful degradation test: passing an unknown record type does not crash
- [ ] `docs/adapters/<name>.md` exists
- [ ] README and CHANGELOG updated

## Wiki page additions

Before marking a wiki ingest as done:

- [ ] Source page written with full frontmatter
- [ ] `wiki/index.md` updated
- [ ] `wiki/overview.md` updated if warranted (substantial new info only)
- [ ] Relevant entity pages created/updated
- [ ] Relevant concept pages created/updated
- [ ] At least one `[[wikilink]]` under `## Connections`
- [ ] Contradictions recorded, not silently overwritten
- [ ] Entry appended to `wiki/log.md`

## Documentation changes

Before marking a docs PR as done:

- [ ] Every internal link resolves (`python3 -m llmwiki lint-docs` or grep)
- [ ] Every code snippet in the docs runs unchanged
- [ ] Every file path referenced in docs exists in the repo
- [ ] README badges render (no broken shields.io URLs)
- [ ] Every external link returns HTTP 200 (spot-check)

## Release verification (Phase 6)

Before tagging a release:

- [ ] `setup.sh` runs clean on a fresh `git clone`
- [ ] `build.sh` succeeds on an empty `raw/`
- [ ] `site/index.html` opens from disk with no console errors
- [ ] Every page listed in `index.html` exists in `site/`
- [ ] Copy-as-markdown button copies correct text
- [ ] Cmd+K opens the command palette
- [ ] `/` focuses the search bar
- [ ] Dark mode toggle persists across reloads
- [ ] `grep -r "<your_username>" site/` returns zero
- [ ] `git tag v<version>` is signed (optional for 0.x)
- [ ] CHANGELOG has the new version at the top
- [ ] `docs/roadmap.md` shows the items moved from `[ ]` to `[x]`

## Stale-context guard

When re-verifying any claim:

- If the last verification was more than **7 days ago**, re-verify from source rather than trusting memory.
- If the underlying agent schema changed (Claude Code version bump, Codex CLI release), re-run the fixture snapshot tests and update `SUPPORTED_SCHEMA_VERSIONS`.
- If a referenced URL returns 404, mark the reference as broken in `docs/roadmap.md` and open an issue.

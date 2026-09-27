# Flow log — #211 docker-identity-refs

## fetch-bug / resume-detection / workspace
- BUG_ID: 211 — "docs: Docker guide points at the upstream clone URL and image instead of ours"
- SPEC_NAME: 211-docker-identity-refs (orphan fix-as-spec — no owning functional-spec)
- Branch: fix/211-docker-identity-refs
- Worktree: .claude/worktrees/fix-211-docker-identity-refs (throwaway vault at .worktree-vault, gitignored)
- Entry: issue OPEN, no PR, no prior flow-log
- Sibling issues: #210 (PyPI, merged — its `tests/test_install_docs_match_packaging.py` is the precedent), #212 (Homebrew tap, open)
- Next: diagnose

## diagnose
Root cause is fork inheritance: this repository is a fork of an upstream project and every
reference to a *project artifact* (clone URL, registry image, OCI provenance, marketplace
publisher, package metadata, demo URL) was inherited pointing at the upstream owner.

Why CI never caught it: `link-check.yml` (lychee) tests **liveness**, and every upstream
reference resolves — `github.com/Pratiyush/llm-wiki` is a real repo, `ghcr.io/pratiyush/llm-wiki`
is a real image. A reachable-but-foreign reference is worse than a 404: it silently succeeds
and runs somebody else's software.

Measured inventory (tracked files, `git grep`):
- 27 `github.com/Pratiyush/…` refs across 45 files outside `demo/`
- 2 `github.com/nicobailey/…` refs — a **third** owner, in `integrations/vscode/package.json`
  and `integrations/obsidian/manifest.json`. `integrations/vscode/package.json` names two
  different foreign owners in one file (`publisher: pratiyush`, `repository: nicobailey/llm-wiki`).
- 32 files under `demo/`, including `<upstream-maintainer-email>` — a real third-party email address
  published on the live demo site.

Not all of it is inert text. Live defects found:
- `llmwiki/docs_pages.py:238` `_DEFAULT_GITHUB_REPO = "Pratiyush/llm-wiki"` — the runtime
  fallback when config and `git remote` detection both fail, so an affected user's generated
  site links into upstream's blob URLs.
- `Dockerfile` OCI `source` / `authors` — machine-read provenance; registries and scanners
  report the published image as originating upstream.
- `.github/workflows/docker-publish.yml` grants `id-token: write` for Cosign with no signing
  step, and never executes the image it ships.

Parts of the filed issue are already stale (fixed by the #210 sweep): the clone URL in
`docs/deploy/docker.md:22` is correct, and the guide's "Build locally" section already uses
`docker compose build`. Only `docker-compose.yml`'s **header comment** still advertises the
non-existent `docker-compose.build.yml`.

Live probes (2026-09-26):
- `ghcr.io/alexandermakarov/llm-wiki` — public, anonymous pull lists through `v2.3.0`. No setup needed.
- `alexandermakarov.github.io/llm-wiki` — HTTP 200. No setup needed.
- `github.com/AlexanderMakarov/homebrew-tap` — **404**. Blocks the Homebrew surface (#212).
- `docs/uptime.md` documents `.github/workflows/uptime.yml`, which **does not exist**. Pre-existing, out of scope.

## classify
- **Conformance** — orphan fix-as-spec, no `functional-spec.md` to amend. No documented behavior
  is being changed: every edit moves a reference from wrong-owner to right-owner, and the
  OIDC removal deletes a capability the workflow never exercised.
- Not divergence: nothing in `context/` specifies the upstream owner as intended.

## decisions (operator, this run)
1. **Cosign** — drop `id-token: write` and the Cosign comment; no signing. Rationale: least
   privilege, and stop advertising a guarantee the workflow does not provide. Signing can be
   added deliberately later.
2. **Homebrew** — leave the tap *functionally* for #212 (`docs/deploy/homebrew-setup.md`,
   `homebrew/llmwiki.rb`, `scripts/bump-homebrew-formula.sh`,
   `.github/workflows/homebrew-bump.yml`, `tests/test_homebrew_tap.py`), because our tap does
   not exist yet and repointing the install commands would document a 404 under our own name.
   What this PR does touch: the doc gains a "not yet available" banner, and the formula's two
   caveat URLs follow the sweep (the rest of `homebrew/llmwiki.rb` already named us on `main`).
   The identity test carries a `#212`-tagged exemption; after the delta review it lists exactly
   one path — `docs/deploy/homebrew-setup.md`, the only file that fails the new "Homebrew tap
   owner" surface row. The other four either already name us or mention upstream's tap only to
   warn against pushing to it. #212 deletes the exemption rather than adding a parallel check.
3. **Package authors** — `pyproject.toml` `authors` becomes Alexander Makarov alone, so PyPI's
   author contact for `llm-wiki-plus` is the person who maintains it. Upstream credit stays in
   `LICENSE` (both copyright lines) and the README acknowledgements.
4. **`demo/` corpus** — mechanically rewritten in this PR (32 files), which also removes the
   published third-party email. Accepted trade-off: `demo/raw/` is nominally generated-immutable,
   and the synthesized `demo/wiki/` pages are not re-derived from the rewritten raw input.
- Test file name: `tests/test_docker_refs_are_ours.py`, verbatim from the issue's acceptance
  criteria, structured as a per-surface table so #212 / `action.yml` extend it (#211 comment).

## Next: fix + regression-test

## fix / regression-test / verify-criteria
- Sweep applied across 76 files: every clone URL, registry image, OCI label, package manifest, marketplace publisher, Pages host and demo-corpus reference now names this repository.
- A **third** foreign owner was found during the sweep (`nicobailey`, in `integrations/vscode/package.json` and `integrations/obsidian/manifest.json`); `integrations/vscode/package.json` named two different foreign owners in one file.
- Live defect fixed: `llmwiki/docs_pages.py` `_DEFAULT_GITHUB_REPO` (runtime fallback that baked upstream blob URLs into an affected user's generated site).
- `.github/workflows/docker-publish.yml`: `id-token: write` + Cosign comment removed (no signing step existed); new `smoke-published-image` job pulls and executes the published image; `workflow_dispatch`'s `tag` input, previously declared and never read, is now wired through `metadata-action` so the tag the build publishes is the tag the smoke job pulls.
- New `tests/test_docker_refs_are_ours.py`: per-surface table (GHCR image, GitHub repo URL, Pages host, integration manifest, Homebrew tap owner), owner derived from `pyproject.toml` `[project.urls] Repository`, non-vacuity guards, and a fragment-assembled email guard from which `context/` is deliberately NOT exempt.
- Evidence: real image built (`docker compose build`) and run (`docker run … version` → `llmwiki 2.3.0`); OCI labels verified on the built image; demo site rendered (353 pages) and grepped — residual foreign refs only in README attribution and the Homebrew doc.
- Verified the distributed artifact carries the MIT notice: `…/llm_wiki_plus-2.3.0.dist-info/licenses/LICENSE` inside the image retains both copyright lines.

## local-review (two passes)
- Pass 1 — Request changes, 3 Blockers / 10 Nits. Blockers: a third-party email written into this flow-log while documenting its removal; the smoke job pulling a tag `build-and-push` never published on `workflow_dispatch`; one-concern-per-PR. 11 findings applied; the PR-split finding resolved as a PR-body justification per operator.
- Pass 2 (delta, covering everything the first pass could not see) — Comment, 0 Blockers / 14 Nits, all applied. Highest value: an unanchored semver regex that would have false-redded any prerelease release (PEP 440 normalises `v2.4.0-rc1` → `2.4.0rc1`); `HOMEBREW_EXEMPT_212` empirically exempting *nothing*, with a CHANGELOG sentence claiming otherwise; raw `${{ inputs.tag }}` interpolation into the `tags:` block; and the guard's single vacuous-pass path (a regressed `Repository` URL would make every assertion pass).
- `_SESSION_LOCAL_BASENAME_PREFIXES`, introduced mid-review to generalise a removed literal, was then shown to be unreachable — the generic bare-`.md` rule matches every input it could — and removed. The net change to `llmwiki/docs_pages.py` is 5 insertions / 4 deletions.
- Review files are session-only and gitignored; never committed.

## operator decisions (late)
- Vulnerability reports move to GitHub private vulnerability reporting (feature enabled on the repository this run; verified `{"enabled": true}`). `SECURITY.md` no longer publishes a personal email and states explicitly that a public issue must not be used. `CODE_OF_CONDUCT.md` keeps the GitHub profile link.
- Upstream credit retained where MIT requires it and where it belongs: `LICENSE` (both copyright lines), README acknowledgements, CHANGELOG history.

## Next: commit-push → remote gates → merge

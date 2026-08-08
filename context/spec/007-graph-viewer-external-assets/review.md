# Code review — #127 external graph viewer assets

**Reviewer:** checklist half of local dual review (`REVIEW_CHECKLIST.md` + `ARCHITECTURE.md` + `DECLINED.md` + `CONTRIBUTING.md` + `SECURITY.md`)
**Branch:** `feat/127-graph-viewer-external-js`
**Scope reviewed:** `git diff origin/main...HEAD` (1 commit, spec only) **plus all uncommitted working-tree changes** — 22 modified files and 4 untracked additions (`llmwiki/render/graph_viewer.py`, `llmwiki/vendor/{NOTICE,vis-network.min.js}`, `tests/test_127_acceptance.py`).

**Verdict: REQUEST CHANGES** — 3 blockers, 2 majors, 5 nits.

The engineering core of this change is genuinely good: the JS extraction is provably faithful, the vendored bundle is provably the authentic upstream artifact, docs are updated in five places, and the whole suite is green. What blocks it is a packaging boundary the repo has never crossed before — the vendored `.js` never reaches an installed copy of the package, so `llmwiki graph` and `llmwiki build` crash for every user who installed via pip, Homebrew, or Docker. That is a shipped-product outage, not a style question, and it is invisible to the test suite by construction.

---

## What I verified (and what passed)

These are worth recording because they retire the risks the spec itself flagged as the scary ones.

- **The extracted JS is a faithful move, not a rewrite.** I pulled the old inline viewer `<script>` block from `origin/main:llmwiki/graph.py` and compared it token-by-token against `GRAPH_VIEWER_JS` after normalising away comments, `'use strict';`, and the relocated `const GRAPH = …` stub. The two are **identical**. FR1 ("same Knowledge Graph experience") is structurally guaranteed rather than merely asserted — there is no behavioural drift to hunt for.
- **The vendored bundle is authentic upstream 9.1.9.** `origin/main` pinned `integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"`. Recomputing SHA-384 over `llmwiki/vendor/vis-network.min.js` yields exactly that value. The committed blob is byte-for-byte the file the CDN was serving under SRI, so nothing hostile was substituted during vendoring. (SHA-256 for the record: `f53f833ddb9bf97efe856bb0637d4fe88f39e39999c7e94a4b8afc8de8a1a2e5`.)
- **Lint and tests are green.** `ruff check llmwiki tests scripts` passes clean. `python3 -m pytest tests/ -q` exits `0` with 3869 tests collected and no failures or errors.
- **The README test badge is accurate.** It claims 3869 passing; collection confirms exactly 3869.
- **No CDN residue, no telemetry, no network at build time.** The only remaining `unpkg`/CDN mentions in the tree are prose in `docs/reference/ui.md` explaining that unpkg is *no longer* used. No new runtime Python dependency; `graph.py` adds only `shutil` from stdlib. Localhost binding untouched. No analytics.
- **`DECLINED.md` conflict check: clean.** Nothing in the declined log covers vendoring browser assets or externalising the viewer script.
- **AWOS `context/` rule satisfied.** The change touches `llmwiki/`, `tests/`, and `docs/reference/`, and `context/spec/007-graph-viewer-external-assets/` changes alongside it.
- **Emitted artifacts stay out of git.** `.gitignore` already covers `site/` and `graph/`, so the per-build copies of `vis-network.min.js` cannot be accidentally committed.

---

## Blockers

### B1 — The vendored asset is not in the wheel; `llmwiki graph` and `llmwiki build` crash for every installed user

`llmwiki/graph.py` resolves the bundle relative to the installed package:

```python
VIS_NETWORK_VENDOR = Path(__file__).resolve().parent / "vendor" / "vis-network.min.js"
```

and `write_html()` copies it unconditionally. But `pyproject.toml` declares:

```toml
[tool.setuptools.packages.find]
include = ["llmwiki*"]

[tool.setuptools.package-data]
llmwiki = ["py.typed"]
```

`packages.find` only discovers importable packages, and `llmwiki/vendor/` has no `__init__.py`, so it is not a package. `package-data` lists only `py.typed`. There is no `MANIFEST.in`. The result is that the file is silently dropped from the distribution.

I confirmed this empirically rather than by reading the config. Building the wheel and listing its contents shows `llmwiki/render/graph_viewer.py` present (it is a `.py` inside a real package) and **no `llmwiki/vendor/` entry at all**. Installing that wheel into a clean venv and running the command against a two-page throwaway vault reproduces a hard crash:

```
File ".../site-packages/llmwiki/graph.py", line 670, in write_html
  shutil.copy2(VIS_NETWORK_VENDOR, out_path.parent / "vis-network.min.js")
FileNotFoundError: [Errno 2] No such file or directory:
  '.../site-packages/llmwiki/vendor/vis-network.min.js'
```

Impact is total for the affected population: `write_html()` is the shared writer on both emission paths, so `llmwiki graph` and the graph step of `llmwiki build` both die, and they die *after* `graph.json` is written — leaving a half-produced output directory. Everyone installing from PyPI, Homebrew, or the Docker image is affected. Only contributors running from a source checkout are spared, which is precisely why this is invisible to CI.

**Why the test suite cannot catch this:** every test imports `llmwiki` from the repo working tree, where `llmwiki/vendor/vis-network.min.js` exists on disk. `tests/test_127_acceptance.py::test_vendored_vis_network_is_a_real_js_bundle` asserts `VIS_NETWORK_VENDOR.is_file()` and passes for exactly that reason. The suite verifies the file exists *in the repo* and never verifies it survives packaging. A green CI run says nothing about the shipped artifact here.

**Fix:** declare the asset as package data, e.g. `llmwiki = ["py.typed", "vendor/*.js", "vendor/NOTICE"]`. Then add a regression test that fails without it — the cheapest durable form is a test that builds a wheel (or inspects `importlib.resources`) and asserts the vendor file is present, so the next contributor who adds a non-`.py` asset gets caught by the same net. Consider `importlib.resources.files("llmwiki")` for the runtime lookup instead of `__file__` arithmetic, which also makes the dependency on packaging explicit at the call site.

### B2 — A missing or unreadable vendor asset takes down the whole build instead of degrading

Independent of B1, the copy is unguarded:

```python
shutil.copy2(VIS_NETWORK_VENDOR, out_path.parent / "vis-network.min.js")
```

`REVIEW_CHECKLIST.md` (Code quality → error handling) requires that "build never crashes on a single bad file", and this is the graph step of a whole-site build aborting on one missing asset. The irony is that the correct degraded behaviour is already implemented and already tested: the viewer checks `if (typeof vis === 'undefined')` and shows `#offline-notice`, and this PR even improved that notice to name the two companion files. The Python side should let that path do its job — wrap the copy, warn on failure, and still emit a usable `graph.html` that explains itself — rather than turning a cosmetic degradation into a stack trace.

I am calling this separately from B1 because fixing the packaging alone leaves the fragility in place for every other way the file can go missing (a partial install, a stripped Docker layer, a read-only or full filesystem, an aggressive packager). Both need fixing; B2 is the defence in depth that keeps B1's failure mode from ever being fatal again.

### B3 — The implementation is uncommitted; the only commit on the branch is `docs:`

`git log origin/main..HEAD` contains exactly one commit, `docs: add spec for #127 external graph viewer assets`, and its diff is the four spec files. Every line of implementation, every test change, the new viewer module, and the 676 kB vendor blob are **uncommitted working-tree state**. As the branch stands, a PR opened from it would contain the spec and nothing else.

This trips the Meta section of the checklist in three ways, and the Meta section is blocker-tier by the checklist's own rule. The conventional-commit title on the eventual code commit still has to be chosen and is not `docs:` — given the CHANGELOG files this under `### Changed`, `refactor:` or `feat:` is the honest prefix. "CI is green" cannot be satisfied, because CI has never seen this code. And the AWOS `context/` path-filter check evaluates committed paths, so it is not meaningfully exercised yet either.

Nothing here is a criticism of the code; it is a gate that has to close before the other Meta items can be assessed at all. Commit the work, push, and let the required checks run on the real head SHA.

---

## Majors

### M1 — Vendoring removed the supply-chain control from #571 and put nothing in its place

`origin/main` carried an explicit, commented hardening: vis-network pinned to `@9.1.9` with a SHA-384 SRI hash, with instructions for regenerating it on upgrade, added under #571 / `#ui-h14` precisely so "a malicious or accidental upstream change can't ship code to every visitor of the site". This PR removes it, and `tests/test_ui_a11y_bundle_473.py` now asserts the opposite — that `integrity="sha384-` is *absent* from the template.

Dropping SRI for a same-origin local file is correct on its own terms; SRI protects a network fetch, and there is no longer a fetch. But the control it replaced has no successor. The repo now carries an opaque 676 kB minified blob that is copied verbatim into every user's published `site/`, and **nothing anywhere verifies its contents**. The closest thing is `test_vendored_vis_network_is_a_real_js_bundle`, which only checks the file is ≥ 100 kB and contains the substring `Network` — a placeholder check that any large file mentioning "Network" satisfies. A future edit to that blob, whether a bad merge, a careless "quick patch", or something deliberate, ships to every reader of every built site with zero detection, and it is not realistically reviewable by eye in a PR diff.

`SECURITY.md` puts supply-chain squarely in scope, and its out-of-scope carve-out does not cover this: it exempts "security of third-party tools this project integrates with (`qmd`, `highlight.js`, …)", but llmwiki no longer merely integrates with vis-network — it *redistributes* it.

**Fix:** record the hash in `llmwiki/vendor/NOTICE` (the SHA-384 above is already known-good and matches the retired SRI value) and add a test that recomputes `hashlib.sha384(VIS_NETWORK_VENDOR.read_bytes())` and asserts the match. That is a handful of lines, it restores the #571 guarantee in the form appropriate to a local file, it makes upgrades deliberate rather than accidental, and it gives a reviewer something checkable in place of an unreadable diff.

### M2 — `docs/maintainers/ARCHITECTURE.md` now contradicts what shipped

Two statements in the maintainer one-pager are falsified by this change and were not updated:

- The L3 row still describes the viewer as "Browser-side JS baked into `build.py`", PR surface "inline JS string inside `build.py`". That is exactly the pattern this PR replaces for the graph.
- Under "What must NEVER land in a PR": "**New runtime dependencies** — stdlib + `markdown` only. Viewer may load from a CDN (highlight.js). **Anything else gets rejected.**"

The second one matters more than a stale table row. I do not read this PR as violating the dependency rule in spirit — vis-network was already a viewer dependency on `main`, and this relocates it rather than introducing it, which is a net reduction in third-party network exposure. But the written rule permits exactly one mechanism for third-party browser code (CDN) and rejects everything else, and a new `llmwiki/vendor/` distribution category now exists that the rule does not describe. The next contributor reads the governing doc and concludes that what just landed is forbidden — or, worse, cites it as precedent for vendoring something the maintainers would not want.

`REVIEW_CHECKLIST.md` requires docs updated for any architectural change, and this is one: it introduces a new asset class, a new packaging obligation (see B1), and a new emission contract for both build paths. Update the L3 row, and amend the dependency bullet to name vendored browser assets as an accepted category with its conditions — pinned version, attribution, integrity hash, and packaging declared. `CONTRIBUTING.md` line 26 carries the same CDN-only phrasing and deserves the same touch.

---

## Nits

1. **Size-budget headroom is thin.** `GRAPH_VIEWER_JS` is 29,008 bytes against the 32,000-byte budget — 2,992 bytes, about 9%. FR5's guardrail works as designed, but the CHANGELOG's own history shows the previous ceiling being nudged from 41 kB to 43.5 kB before #127 forced the extraction. Worth a line in the module docstring naming the intended next move (split the panel/context-menu code into a second asset) so the next contributor to hit the wall reaches for that instead of the number.
2. **Dead variable carried over.** `llmwiki/render/graph_viewer.py:17` declares `const root = document.documentElement;` and nothing reads it — the other `root` matches in the file are the `colors.root` key and the `--g-node-root` CSS variable. It was already dead on `main` (the #456 comment above it explains the handler that used to use it was removed), but the checklist asks that a PR touching code sweep now-unreferenced helpers, and this PR moves the line wholesale. One-line deletion.
3. **Unrelated drive-by in the README badge.** The test badge goes 3279 → 3869. The number is correct — I verified 3869 collected — but +590 tests is not this PR's doing; it is a stale badge on `main` being opportunistically corrected. Harmless, though it is the kind of thing "one concern per PR" is aimed at, and it makes the diff look like this branch added 590 tests. Either split it out or note it explicitly in the PR body.
4. **License text is referenced rather than included.** `llmwiki/vendor/NOTICE` ends with "Copyright notices and full license texts are available in the upstream repository", which is the weakest form of compliance. In practice the situation is better than that sentence suggests: the minified bundle preserves its own `@license` banner carrying both copyright lines (Almende B.V. 2011-2017, visjs contributors 2017-2019) and the Apache-2.0/MIT dual-license declaration, so attribution does travel with the redistributed file. The residual gap is the verbatim permission-notice text that MIT asks be included in copies. Dropping a `LICENSE-vis-network.txt` next to the NOTICE and pointing at it closes it cheaply.
5. **No `.gitattributes` for the vendored blob.** A 676 kB minified file with no `linguist-vendored` / `-diff` marking will skew the repo's language statistics and expand in diffs and in `git log -p`. Adding `llmwiki/vendor/*.min.js linguist-vendored -diff` keeps it out of the way.

---

## Checklist summary

| Section | Result |
|---|---|
| Meta | **Blocked** — B3 (implementation uncommitted; sole commit is `docs:`; CI has never run on this code) |
| Layer boundaries | Pass with a doc gap — no new Python runtime dep, L0 untouched, clean L2/L3 split; **M2** (ARCHITECTURE.md not updated for the new vendored-asset category) |
| Security + privacy | **M1** — #571 SRI control removed with no integrity successor. No real session data, no personal paths, no telemetry, no build-time network, localhost binding untouched. Redaction and XSS surfaces not touched (GRAPH JSON embedding unchanged). |
| Code quality | **Blocked** — B2 (unguarded `shutil.copy2` aborts the build); nit 2 (dead `root`). Docstrings and type hints on the new module are fine; ruff clean. |
| Tests | Pass with a gap — 3869 green, faithful repointing of nine graph test modules from `HTML_TEMPLATE` to `GRAPH_VIEWER_JS`, good AC-coverage matrix in `test_127_acceptance.py`, all fixtures on `tmp_path`. Gap: no packaging test, which is why B1 slipped through. |
| Docs | Pass except **M2** — CHANGELOG entry under `[Unreleased] → Changed`, plus `docs/reference/ui.md`, `docs/reference/cli.md`, `specs/graph.md`, and `.github/synthetic-failure-template.md` all correctly updated. |
| Build + runtime smoke | **Blocked** — B1 reproduced against a pip-installed wheel. |
| `DECLINED.md` | No conflict. |

## Recommended path to green

1. Add `vendor/*.js` and `vendor/NOTICE` to `[tool.setuptools.package-data]`, plus a packaging regression test (B1).
2. Guard the copy so a missing asset warns and falls through to the existing offline notice instead of aborting the build (B2).
3. Record the SHA-384 in `NOTICE` and assert it in a test, restoring the #571 guarantee (M1).
4. Update the L3 row and the dependency bullet in `ARCHITECTURE.md`, and the matching line in `CONTRIBUTING.md` (M2).
5. Commit under a `refactor:` or `feat:` conventional title, push, and confirm the required checks pass on the head SHA (B3).

Nits 1-5 are non-blocking and can ride along or follow up.

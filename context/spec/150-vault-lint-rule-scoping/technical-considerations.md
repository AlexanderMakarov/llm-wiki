# Technical Specification: Per-vault quality-check scoping

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (Approved)
- **Status:** Completed
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Five changes, only one of which is the feature #150 literally asks for:

1. **A vault-scoped settings file** — `<vault>/llmwiki.json` — carrying `lint.disabled_rules`. Read at the CLI border, never by rule modules.
2. **`link_integrity` learns the harvest threshold.** `DEFAULT_MIN_REFS` moves to a neutral module so both the harvester and the rule read one definition, and the per-target reference count is computed by one shared helper so the producer and the checker cannot drift.
3. **Threshold plumbing** — `lint --min-refs`, `all --min-refs`, and the `all` pipeline passing it to `run_harvest` instead of hardcoding the stock value.
4. **Reporting honesty** — lint returns *what it skipped* alongside *what it found*, and both CLI paths render through one shared reporter instead of two copies of the same print block.
5. **One answer for people and agents** — the MCP `wiki_lint` tool stops reimplementing lint privately and reports exactly what the CLI reports.

Plus two contained precision fixes to `contradiction_detection`, the demo's settings file, the CI gate flip, and the documentation defect the enforced gate surfaced.

The guiding constraint: **rules stay pure.** A rule receives pages and options and returns issues. Nothing under `llmwiki/lint/rules/` reads a config file, touches the filesystem for settings, or knows a vault exists.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Vault settings file

**Path:** `<vault-root>/llmwiki.json`, a sibling of the existing per-vault `llmwiki-state.json`.

Deliberately *not* the clone's `config.json`: that file is gitignored, describes how this install behaves, and is merged over `examples/sessions_config.json`. A vault's opt-out list is a property of the wiki and must travel with it — the demo's must be committed. Deliberately not hidden under `.llmwiki/` either: a committed file a reviewer is meant to read should be visible.

**Shape** — both forms accepted, normalised to `dict[str, str]`:

| Form | Example | Normalises to |
| --- | --- | --- |
| List | `{"lint": {"disabled_rules": ["content_freshness"]}}` | `{"content_freshness": ""}` |
| Object | `{"lint": {"disabled_rules": {"content_freshness": "reason"}}}` | unchanged |

**Resolution order** for which file to read:
1. `--wiki-dir` given explicitly → `<wiki_dir>.parent / "llmwiki.json"`
2. otherwise → `_content_root(args) / "llmwiki.json"`

**New module:** `llmwiki/vault_settings.py`

| Function | Responsibility |
| --- | --- |
| `load_vault_settings(root) -> dict` | Read + parse; missing file → `{}` |
| `disabled_lint_rules(settings) -> dict[str, str]` | Extract + normalise both accepted forms |

Malformed JSON is a hard error (exit 2), not a silent `{}`. A vault whose settings file cannot be parsed must not be reported as clean — same reasoning as R3.

### 2.2 One definition of the significance threshold

`llmwiki/candidates_harvest.py` currently imports `_norm_slug` from `llmwiki.lint.rules.link_integrity`. If `llmwiki/lint/` imported `DEFAULT_MIN_REFS` back from `candidates_harvest`, that is a circular import.

**Resolution:** new dependency-free `llmwiki/thresholds.py` holding `DEFAULT_MIN_REFS = 3`. `candidates_harvest` re-exports it, so existing importers (`cli.py`, `pipeline.py`) are unaffected.

### 2.3 Shared reference counting

The producer and the checker must count references identically or the rule reintroduces the very drift it exists to remove. Extract from `harvest_targets`:

```
count_source_refs(texts_by_rel) -> dict[str, set[str]]
```

Pure — takes page text keyed by relative path, returns target → set of pages naming it. Counted **once per page**; repeated mentions in one document are one signal. `harvest_targets` calls it after reading `wiki/sources/**`; `LinkIntegrity` calls it over the source pages already in memory.

**Only counting is shared — resolution is not, and deliberately so.** The two have opposite and correct rules:

| | `harvest_targets` | `link_integrity` |
| --- | --- | --- |
| `candidates/` | does **not** resolve — so evidence keeps refreshing on each run | **resolves** — a pending stub is a real page |
| `archive/` | **resolves** — an archived stub is the dismissal ledger (#140) | not loaded — a link to a discarded page reads as broken on purpose |

Sharing resolution would break one of them. This asymmetry is intentional and must survive review.

### 2.4 Passing options to rules

`run_all` constructs each rule with `rule_cls()` and calls `rule.run(pages)`. Existing rule signatures are `run(self, pages, *, llm_callback=None)`, so passing a new `min_refs=` keyword would raise `TypeError` in 16 of 17 rules — and the runner converts rule exceptions into **error-severity issues**, which would turn a clean vault into 16 errors.

**Resolution:** a frozen options object set on the instance, not a new call argument.

```
@dataclass(frozen=True)
class LintOptions:
    min_refs: int = DEFAULT_MIN_REFS
```

`LintRule` declares `options: LintOptions = LintOptions()` as a class attribute, so every rule always has one. The runner sets `rule.options = options` before `run`. No rule signature changes; `LinkIntegrity` reads `self.options.min_refs`.

### 2.5 `link_integrity` becomes threshold-aware

Resolution logic is unchanged. One new gate before recording an issue, keyed on how many **source** pages name the target (counts from §2.3, over `pages` whose relative path is under `sources/`):

| Source references | Interpretation | Verdict |
| --- | --- | --- |
| `0` | Harvest never saw the name — it was never a decision, nothing was ever going to materialise it | **reported at every threshold** |
| `1 … min_refs - 1` | Harvest saw it and deliberately declined | not reported |
| `>= min_refs` | Harvest should have materialised it | **reported** |

**The zero case is load-bearing.** Excusing everything below the threshold would make a reference that *nothing* names unreportable at any threshold, `--min-refs 1` included — silently deleting a whole class of genuine finding while appearing to satisfy "lower the threshold and everything comes back". Measured: 0 such links on the demo, 1 on a 717-page vault (`entities/AmeriaBank.md → [[Banking-APIs]]`), i.e. rare enough to miss in review and real enough to matter.

This also keeps the rule in step with the harvester rather than departing from it: harvest's decision domain is exactly the source-named targets, so the rule excuses only inside that domain and never outside it.

Measured effect: demo `120 → 0` at the stock threshold; live 717-page vault `650 → 256`, the 256 being genuine gaps.

### 2.6 Runner returns what it skipped

`run_all` returns `list[issue]` and has ~20 call sites in tests plus `pipeline.py`. Changing its return type is gratuitous churn.

**Resolution:** add a richer entry point; leave `run_all` as a thin wrapper over it.

```
@dataclass(frozen=True)
class LintOutcome:
    issues: list[dict]
    skipped: dict[str, str]      # rule name → reason ("" when none given)
    ran: list[str]

run_lint(pages, *, selected=None, disabled=None, options=None) -> LintOutcome
run_all(pages, *, selected=None, **_) -> list[dict]     # delegates, returns .issues
```

`disabled` names validated against `REGISTRY`, raising the existing `UnknownRuleError` — R3 reuses the machinery `--rules` already has.

**Findings must be ordered deterministically.** Several rules iterate a `set` — `LinkIntegrity` walks `wikilink_targets(text)`, which returns one — so with `PYTHONHASHSEED` randomised, two processes emit the same findings in different order. Measured on a four-target fixture: five distinct payload hashes across five seeds. This predates #150, but §2.10 makes it load-bearing: the MCP server and the CLI are *different processes*, so a payload diff between them can show reordered `issues` for an unchanged vault, and R9's "the same report" would be false on a technicality.

`run_lint` therefore sorts each rule's issues by `(page, message)` before extending the result. Sorting **within** each rule, not globally, preserves the `REGISTRY` enumeration order that `llmwiki/lint/rules/__init__.py` documents as deliberate ("any test or downstream consumer that relied on enumeration order continues to see the same sequence"). One place, every rule fixed, no rule module touched.

### 2.7 One reporter, two callers

`cmd_lint` (cli.py:702) and `_run_lint_step` (pipeline.py:90) contain the same ~20-line print block. Adding skipped-rule output would make it three copies.

**New module:** `llmwiki/lint/report.py`

| Function | Responsibility |
| --- | --- |
| `render_text(outcome, total_pages) -> str` | Scan line, counts, skipped block, per-rule findings |
| `render_json(outcome, total_pages) -> dict` | Adds `disabled_rules` to the existing payload |

Skipped rules are printed **whether or not any issue was found** (R2). When `len(skipped) == len(REGISTRY)`, the reporter states that nothing was checked rather than printing a clean summary.

### 2.8 CLI surface

| Command | Change |
| --- | --- |
| `lint` | `--min-refs N` (default `DEFAULT_MIN_REFS`); `--fail-on-warnings` alongside the existing `--fail-on-errors` |
| `all` | `--min-refs N` — the parser never defined it, so the threshold was unreachable on this path |

`pipeline.py:309` passes the resolved threshold to `run_harvest` instead of the hardcoded constant.

**Ordering bug to fix while here:** `cmd_lint` returns on `--fail-on-errors` *before* calling `_apply_default_vault(args)` and recording `last_lint_run_at`, so a failing lint never records its run. The new `--fail-on-warnings` must not inherit that; compute the exit code last.

### 2.9 `contradiction_detection` precision

Both fixes verified against the demo's real text plus a regression case:

| Demo page | Cause | Fix |
| --- | --- | --- |
| `cli-reference-07` | "…claims that **could** conflict with prior wiki entries" — `_AFFIRMATIVE_CUE_RE` fires; `rather than` is not a negator | Add modal hypotheticals `could\|would\|might\|may` to `_NEGATOR_RE` |
| `configuration-reference-01` | "**None evident.**" — `evident` absent from `_NONE_SYNONYMS` | Add `evident` |

Verified unchanged: the genuine `01-installation` finding stays flagged, and a crafted section opening `"None in the summary. However, this page contradicts prior guidance…"` stays flagged.

### 2.10 MCP reports what the CLI reports

`tool_wiki_lint` (`llmwiki/mcp/server.py:989`) is a private reimplementation. It resolves the vault correctly — `REPO_ROOT` there is `resolve_content_root()`, not the git clone — but everything after that is its own:

| | CLI `lint` | MCP `wiki_lint` today |
| --- | --- | --- |
| Checks run | 17 registered rules | 2, hand-rolled |
| Broken link | `_norm_slug` + anchor-stripped match | exact `target in {p.stem}` → **over-reports** |
| Orphan | inbound wikilinks **and** catalog markdown links; skips `SYSTEM_PAGE_SLUGS` | inbound wikilinks only; skips `index/overview/log` → **over-reports** |
| Severity / threshold / opt-outs | yes | none |

Its advertised description already promises "orphan pages, broken wikilinks, **contradictions, and stale summaries**" — two of which it has never implemented. The description is not aspirational, it is wrong, and folding onto the registry makes it true rather than requiring it be walked back.

`tests/test_archive_cold_storage.py:272` already asserts the two agree about discarded slugs, so parity is an existing project principle this extends rather than invents.

**Change:** `tool_wiki_lint` calls `load_pages` + `run_lint` with the same vault settings and `LintOptions` the CLI resolves, and returns `render_json(...)` — the identical payload `lint --json` produces. Optional tool arguments `rules` and `min_refs` mirror the CLI flags. `fail_on_*` has no MCP analogue (there is no exit code) and is not added.

**This is a breaking change to the tool's output contract.** Keys `orphans` / `orphan_count` / `broken_links` / `broken_link_count` are replaced by `summary` / `issues` / `disabled_rules` / `total_pages`. That is the point — "behaves exactly as the CLI" is not achievable while keeping a second shape — but it must be announced in `CHANGELOG.md` and `docs/UPGRADING.md`, which already references `wiki_lint`.

### 2.11 Demo, CI, and the surfaced defect

| File | Change |
| --- | --- |
| `demo/llmwiki.json` | **New, committed.** Disables `content_freshness` only, with a reason. No threshold override — the demo runs at stock settings |
| `.github/workflows/wiki-checks.yml` | `--fail-on-warnings` added; replace the comment explaining why `--strict` is withheld |
| `docs/tutorials/01-installation.md:26` | `# expect 3.9 or newer` → 3.12, agreeing with line 10 and `pyproject.toml:10` `requires-python = ">=3.12"` |
| `docs/configuration-reference.md` | New section for `llmwiki.json` — both accepted shapes, the caution, the threshold's effect on cross-reference findings; `lint` flags alongside the existing `all` flag table |
| `llmwiki/mcp/server.py` tool description | Rewrite to describe what it now actually runs |
| `CHANGELOG.md`, `docs/UPGRADING.md` | Announce the `wiki_lint` payload change (§2.10) |

---

## 3. Impact and Risk Analysis

### System Dependencies

- **`llmwiki/lint/`** — new options + outcome types; 17 rule modules keep their signatures.
- **`llmwiki/candidates_harvest.py`** — counting extracted; threshold re-exported. Behaviour must be identical.
- **`llmwiki/pipeline.py`** — lint reporting and harvest threshold.
- **MCP `wiki_lint`** — rewritten onto the shared registry (§2.10). Breaking payload change; existing MCP tests (`tests/test_v02.py:157`, `tests/test_archive_cold_storage.py:272`) assert the old shape and must be updated to the new one.
- **`scripts/refresh_demo.py`** — prints the lint report; will now show skipped rules.
- **No new runtime dependencies.** Stdlib only, per architecture §1.

### Potential Risks & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Passing a new kwarg to rules turns every rule into an error-severity issue via the runner's exception handler | **High** | §2.4 — options on the instance, no signature change. A test asserts all registered rules run clean under the new runner |
| Shared counting changes harvest behaviour | **High** | Pure extraction, no logic change; existing harvest tests must pass untouched, plus a test asserting rule and harvester agree on the same corpus |
| Circular import via the shared threshold | Medium | §2.2 neutral module; import-order test |
| Threshold-aware rule hides a genuinely broken link | Medium | Below-threshold links are *by design* unmaterialized; a test pins that lowering `--min-refs` to 1 restores every finding, so nothing is unreachable |
| Enforcing warnings makes the demo gate brittle for unrelated PRs | Medium | Demo runs at stock settings with one opt-out; the gate is `demo/`-path-filtered already |
| A vault silences a check and forgets | Medium | R2 — skipped rules always printed |
| MCP payload change breaks an agent consuming `orphan_count` / `broken_links` | Medium | Announced in `CHANGELOG.md` + `docs/UPGRADING.md`; the replacement payload is the CLI's, already documented. Keeping both shapes would defeat the parity requirement |
| MCP now runs 17 rules instead of 2 on every call | Low | Same corpus the CLI already walks in one pass; `tests/test_lint_perf.py` covers rule-suite cost |
| `--fail-on-warnings` inherits the early-return bug and stops recording runs | Low | §2.8 — exit code computed last |

### Explicitly not addressed

**Site readability.** An unmaterialized cross-reference is, after this change, correctly not a lint finding — but a reader clicking `[[Ollama]]` on the site still arrives nowhere, even though `topics.py` already builds a topic page for many such names. Resolving wikilinks against topic pages is its own issue.

---

## 4. Testing Strategy

Existing suite is `pytest`, run as `python3 -m pytest tests/ -q`; lint rules are covered by `tests/test_lint_rules.py`.

**Unit**
- `vault_settings`: missing file, both accepted shapes, malformed JSON → exit 2, unknown rule name → `UnknownRuleError`.
- `LintOptions` / `run_lint`: `skipped` populated with reasons; `run_all` back-compat; **every registered rule runs clean under the new runner** (guards the §2.4 risk).
- `link_integrity`: below-threshold target not reported; at-threshold target reported; `--min-refs 1` restores all findings; candidates resolve; archive links stay broken.
- `contradiction_detection`: the two demo strings become filler; the genuine finding and the `"None … However, contradicts …"` regression stay flagged.
- `count_source_refs`: once-per-page counting; rule and harvester agree on one corpus.

**Integration (CLI, against a temp vault — never the operator's live vault)**
- `lint --fail-on-warnings` exits non-zero on a warning-only vault, zero on a clean one, zero when the offending rule is disabled.
- Disabled rules appear in text output and in `--json` `disabled_rules`.
- All rules disabled → "nothing was checked", not a clean report.
- `all --min-refs N` reaches `run_harvest`; equals the standalone `synth --min-refs N` result.
- A failing lint still records `last_lint_run_at`.

**MCP parity (§2.10)**
- `tool_wiki_lint({})` and `lint --json` return the **same payload** for the same vault — the central parity assertion.
- Vault opt-outs and `min_refs` honoured through the MCP path; `disabled_rules` present in the response.
- `rules` / `min_refs` tool arguments behave as the CLI flags do; an unknown rule name errors rather than returning a clean report.
- Existing MCP tests updated to the new shape, including the archived-slug agreement test.
- The tool's advertised description matches the checks actually run.

**Acceptance (R8)**
- `lint --vault demo --fail-on-errors --fail-on-warnings` exits 0 on the committed demo.
- Output names `content_freshness` as skipped with its reason.
- Seeding a demo copy with an above-threshold unmaterialized target makes the gate fail.
- Freezing the clock past 90 days keeps the demo passing.
- The three Python-version statements agree.

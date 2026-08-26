# Tasks: Offline migrate-topic-kinds (#174)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** In Progress

---

- [ ] **Slice 1: Core migration library**
  - [ ] Implement `llmwiki/migrate_topic_kinds.py`: kind map (entities/concepts/candidates, ambiguous skip), Connections-only stamping, `run_migration` / `print_report`, vault-root stamped JSON on successful non-dry-run. No synth backend imports. Verify with focused unit tests in `tests/test_migrate_topic_kinds.py` covering rewrite flip, ambiguous skip, byte-identical already-kinded lines, candidates as kind source, dry-run no writes. **[Agent: generalPurpose]**

- [ ] **Slice 2: CLI + reference docs**
  - [ ] Wire `migrate-topic-kinds` in `llmwiki/cli.py` (`cmd_migrate_topic_kinds` + subparser), add `docs/reference/cli.md` section, and a CLI parse/dry-run test. **[Agent: generalPurpose]**

- [ ] **Slice 3: Upgrade docs + CHANGELOG**
  - [ ] Document trade-off in `docs/UPGRADING.md` beside #147; add `CHANGELOG.md` Unreleased entry + release-note bullet. **[Agent: generalPurpose]**

- [ ] **Slice 4: Feature testing & regression**
  - [ ] Expand/confirm acceptance coverage in `tests/test_migrate_topic_kinds.py` against FR1–FR7; run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_migrate_topic_kinds.py tests/e2e/test_cli_smoke.py -q` (or full suite if smoke lists migrate commands). Annotate with `@spec` where the project already does. **[Agent: testing-expert]**

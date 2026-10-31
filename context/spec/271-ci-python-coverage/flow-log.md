# Flow log — ci: Python line+branch coverage (#271)

## [2026-10-31] implement | #271 branch coverage + CI artifact

- Completed the visibility gap left after #280: `branch = true` in `pyproject.toml`, CI `--cov-branch` + `coverage.xml` artifact, docs in CONTRIBUTING §Testing and `docs/CODING_STANDARDS.md`.
- Regression gate unchanged: **87% line** floor only; branch reported, not gated.
- Next: commit-push → PR with `Closes #271` → remote gates → merge.

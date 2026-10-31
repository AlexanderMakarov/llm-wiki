# Flow log — ci: Python line+branch coverage (#271)

## [2026-10-31] implement | #271 branch coverage + CI artifact

- Completed the visibility gap left after #280: CI `--cov-branch`, `coverage.xml` + `coverage.json` artifacts, `scripts/check_unit_coverage.py` line gate at 87%.
- Regression gate: **87% line** only; branch reported in CI log/XML, not a separate fail threshold.
- Next: commit-push → PR with `Closes #271` → remote gates → merge.

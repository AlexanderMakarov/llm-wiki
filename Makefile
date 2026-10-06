# Maintainer helpers (not part of the PyPI package).
# Override the readiness label: make loop-ready-issue-herdr LABEL=agent-ready

.PHONY: loop-ready-issue-herdr loop-ready-issue-herdr-dry-run

LABEL ?=

loop-ready-issue-herdr:
	@test -n "$(LABEL)" || (echo "LABEL is required, e.g. make loop-ready-issue-herdr LABEL=self-heal" >&2; exit 2)
	python3 scripts/loop_ready_issue_herdr.py --label "$(LABEL)"

loop-ready-issue-herdr-dry-run:
	@test -n "$(LABEL)" || (echo "LABEL is required, e.g. make loop-ready-issue-herdr-dry-run LABEL=self-heal" >&2; exit 2)
	python3 scripts/loop_ready_issue_herdr.py --label "$(LABEL)" --dry-run

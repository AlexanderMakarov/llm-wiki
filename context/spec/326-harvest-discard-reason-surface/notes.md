# Notes — #146 harvest discard reason surface (spec 326)

## Product delivery

Remaining #146 scope after #282: near-match pending candidates stay in the review queue and surface the prior free-text dismissal reason on both `candidates list` and `site/candidates.html`.

Storage rewrite that enables that: one archive ledger at `wiki/archive/candidates/dismissals.json` (dismissals + merges). New discard/merge upsert the ledger only — no new sibling `*.reason.txt`. Legacy reason files remain import input via `llmwiki migrate dismissal-ledger` (and auto-rebuild when the ledger file is missing). Empty reason displays as `(discarded without explanation)`.

Docs + CHANGELOG + UPGRADING updated in Slice 4 of `tasks.md`.

---
title: "Lint Rules"
type: concept
status: candidate
tags: []
sources: [2026-09-08-configuration-reference-07, 2026-08-23-lint-rule-severities, 2026-08-23-lint-rule-severities, 2026-09-08-cli-reference-04]
last_updated: 2026-09-08
---

# Lint Rules

the 17 wiki quality rules; names match `## <rule>` headings and CLI reference

## Key Facts

- `disabled_rules` only turns rules off entirely; severity cannot be re-graded per wiki. [[2026-09-08-configuration-reference-07]]
- 17 rules categorized into error (4), warning (9), and informational (4) levels [[2026-08-23-lint-rule-severities]]
- `--json` includes `ran` so partial `--rules` runs are not mistaken for full scans. [[2026-09-08-cli-reference-04]]

## Connections

Named by 4 source page(s), which is the evidence that
justified this candidate:

- [[2026-09-08-configuration-reference-07]]
- [[2026-08-23-lint-rule-severities]]
- [[2026-08-23-lint-rule-severities]]
- [[2026-09-08-cli-reference-04]]

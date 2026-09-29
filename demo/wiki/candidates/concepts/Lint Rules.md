---
title: "Lint Rules"
type: concept
status: candidate
tags: []
sources: [2026-09-28-command-cheatsheet-01, 2026-09-28-configuration-reference-02, 2026-09-28-configuration-reference-07, 2026-09-28-feature-matrix-every-feature-across-the-15-prior-implementations-02, 2026-09-12-lint-rule-severities, 2026-09-27-wikilink-resolution, 2026-09-28-cli-reference-05, 2026-09-28-cli-reference-06, 2026-09-28-cli-reference-11, 2026-09-28-cli-reference-12, 2026-09-28-cli-reference-16, 2026-09-28-cli-reference-17, 2026-09-28-page-kinds-01, 2026-09-28-page-kinds-03, 2026-09-28-slash-commands-reference-01, 2026-09-28-slash-commands-reference-02, 2026-09-28-ui-reference-01, 2026-09-28-docs-style-guide, 2026-09-28-00-quickstart-walkthrough, 2026-09-28-08-synthesize-wiki-pages-with-ollama, 2026-09-28-upgrade-guide-02, 2026-09-28-upgrade-guide-07, 2026-09-28-upgrade-guide-08]
last_updated: 2026-09-29
---

# Lint Rules

the 17 wiki quality rules; names match `## <rule>` headings and CLI reference

## Key Facts

- `disabled_rules` only turns rules off entirely; severity cannot be re-graded per wiki. [[2026-09-28-configuration-reference-07]]
- 17 rules categorized into error (4), warning (9), and informational (4) levels [[2026-09-12-lint-rule-severities]]
- `--json` includes `ran` so partial `--rules` runs are not mistaken for full scans. [[2026-09-28-cli-reference-04]]

## Connections

Named by 23 source page(s), which is the evidence that
justified this candidate:

- [[2026-09-28-command-cheatsheet-01]]
- [[2026-09-28-configuration-reference-02]]
- [[2026-09-28-configuration-reference-07]]
- [[2026-09-28-feature-matrix-every-feature-across-the-15-prior-implementations-02]]
- [[2026-09-12-lint-rule-severities]]
- [[2026-09-27-wikilink-resolution]]
- [[2026-09-28-cli-reference-05]]
- [[2026-09-28-cli-reference-06]]
- [[2026-09-28-cli-reference-11]]
- [[2026-09-28-cli-reference-12]]
- [[2026-09-28-cli-reference-16]]
- [[2026-09-28-cli-reference-17]]
- [[2026-09-28-page-kinds-01]]
- [[2026-09-28-page-kinds-03]]
- [[2026-09-28-slash-commands-reference-01]]
- [[2026-09-28-slash-commands-reference-02]]
- [[2026-09-28-ui-reference-01]]
- [[2026-09-28-docs-style-guide]]
- [[2026-09-28-00-quickstart-walkthrough]]
- [[2026-09-28-08-synthesize-wiki-pages-with-ollama]]
- [[2026-09-28-upgrade-guide-02]]
- [[2026-09-28-upgrade-guide-07]]
- [[2026-09-28-upgrade-guide-08]]

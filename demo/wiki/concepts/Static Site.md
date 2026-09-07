---
title: "Static Site"
type: concept
status: reviewed
tags: []
sources: [2026-07-24-topic-graph-sparsity, 2026-08-22-lint-rule-severities, 2026-08-28-static-site-offline, 2026-09-01-project-page-aggregation, 2026-09-04-search-index-chunks]
last_updated: 2026-09-07
---

# Static Site

the build process that selects and generates the appropriate graph

## Key Facts

- The build output explicitly logs which graph was chosen and the threshold that triggered selection [[2026-07-24-topic-graph-sparsity]]
- Vendored graph library and inlined page data eliminated external dependencies that previously prevented file:// access [[2026-08-28-static-site-offline]]
- Project stub pages are generated during the build process as part of static site generation [[2026-09-01-project-page-aggregation]]

## Connections

Named by 5 source page(s), which is the evidence that
justified this candidate:

- [[2026-07-24-topic-graph-sparsity]]
- [[2026-08-22-lint-rule-severities]]
- [[2026-08-28-static-site-offline]]
- [[2026-09-01-project-page-aggregation]]
- [[2026-09-04-search-index-chunks]]

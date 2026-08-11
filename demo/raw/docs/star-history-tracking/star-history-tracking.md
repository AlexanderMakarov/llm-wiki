---
title: "Star History Tracking"
slug: star-history-tracking
project: star-history-tracking
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/star-history.md"
content_sha256: e906b4b3c3e0db82df52d84574f6a761811654cc2d883f7d0b9da89cc09cbda5
---

# Star History Tracking

Track GitHub star growth over time to understand adoption velocity and
the impact of launches, blog posts, and awesome-list submissions.

## star-history.com chart

Embed a live chart on any page:

**Interactive link:**

```
https://star-history.com/#Pratiyush/llm-wiki&Date
```

**Embeddable image (for blog posts):**

```markdown
[![Star History Chart](https://api.star-history.com/svg?repos=Pratiyush/llm-wiki&type=Date)](https://star-history.com/#Pratiyush/llm-wiki&Date)
```

**For the README:**

```markdown
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Pratiyush/llm-wiki&type=Date)](https://star-history.com/#Pratiyush/llm-wiki&Date)
```

Add this section to the README once the repo has 50+ stars (before that
the chart is too sparse to be meaningful).

## README badge

Add a live star-count badge to the badge row:

```markdown
[![GitHub stars](https://img.shields.io/github/stars/Pratiyush/llm-wiki?style=flat&color=7C3AED)](https://github.com/Pratiyush/llm-wiki/stargazers)
```

This uses shields.io and updates automatically. The `color=7C3AED`
matches the llmwiki accent purple.

## Comparing with related projects

star-history.com supports multi-repo charts. Useful for competitive
positioning:

```
https://star-history.com/#Pratiyush/llm-wiki&mem0ai/mem0&nichochar/hivemind&Date
```

## Monthly check-in template

Copy this template into a GitHub Discussion or internal doc once a month
to track growth alongside project activity.

```markdown
## Star history check-in — YYYY-MM

### Numbers
- Stars at start of month: ___
- Stars at end of month: ___
- Net new stars: ___
- Growth rate: ___%

### Traffic sources (from GitHub Insights > Traffic)
- Top referrers: ___
- Unique visitors: ___
- Unique cloners: ___

### Correlations
- Blog posts published: ___
- Awesome-list PRs merged: ___
- HN / Reddit / Twitter mentions: ___
- New releases shipped: ___

### Notes
- What drove the biggest spike this month?
- Any negative trends to investigate?
- Action items for next month:
```

## Automation options

### GitHub Actions (monthly snapshot)

Create a scheduled workflow that logs the current star count to a file
or GitHub Discussion:

```yaml
name: Star snapshot
on:
  schedule:
    - cron: '0 9 1 * *'  # 9 AM UTC on the 1st of each month
jobs:
  snapshot:
    runs-on: ubuntu-latest
    steps:
      - name: Get star count
        run: |
          STARS=$(gh api repos/Pratiyush/llm-wiki --jq '.stargazers_count')
          echo "$(date +%Y-%m-%d): $STARS stars" >> star-history.log
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Third-party services

- **star-history.com** — free chart embedding, no auth required
- **ossinsight.io** — deeper analytics (contributors, issues, PRs)
- **repobeats.axiom.co** — embeddable activity widget

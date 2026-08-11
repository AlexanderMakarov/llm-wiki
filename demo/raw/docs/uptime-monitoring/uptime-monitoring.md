---
title: "Uptime Monitoring"
slug: uptime-monitoring
project: uptime-monitoring
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/uptime.md"
content_sha256: f912a69432e3410b09c51771b26f4e3c26dd8177a2afa72811d418dfe84ee792
---

# Uptime Monitoring

Monitor the llmwiki demo site availability with a simple GitHub Actions
workflow and README badge.

## GitHub Actions scheduled workflow

This workflow runs every 6 hours, curls the demo site, and fails
(sending a notification) if the site is down.

Create `.github/workflows/uptime.yml`:

```yaml
name: Uptime check
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch: {}      # Manual trigger

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check demo site
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            https://pratiyush.github.io/llm-wiki/)
          echo "HTTP status: $STATUS"
          if [ "$STATUS" -ne 200 ]; then
            echo "::error::Demo site returned HTTP $STATUS"
            exit 1
          fi

      - name: Check sitemap
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            https://pratiyush.github.io/llm-wiki/sitemap.xml)
          echo "Sitemap HTTP status: $STATUS"
          if [ "$STATUS" -ne 200 ]; then
            echo "::warning::Sitemap returned HTTP $STATUS"
          fi

      - name: Check llms.txt
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            https://pratiyush.github.io/llm-wiki/llms.txt)
          echo "llms.txt HTTP status: $STATUS"
          if [ "$STATUS" -ne 200 ]; then
            echo "::warning::llms.txt returned HTTP $STATUS"
          fi
```

GitHub sends email notifications on workflow failures by default. For
Slack/Discord notifications, add a step that posts to a webhook on
failure.

### Notification on failure

Add this step after the checks to post to Slack on failure:

```yaml
      - name: Notify on failure
        if: failure()
        run: |
          curl -X POST "${{ secrets.SLACK_WEBHOOK_URL }}" \
            -H 'Content-type: application/json' \
            -d '{"text":"llmwiki demo site is DOWN. Check: https://github.com/Pratiyush/llm-wiki/actions/workflows/uptime.yml"}'
```

## Simple cron job (self-hosted)

If you deploy to your own server instead of GitHub Pages, run a cron
job locally:

```bash
# Add to crontab -e
0 */6 * * * curl -sf https://wiki.example.com/ > /dev/null || \
  echo "llmwiki site is down" | mail -s "Uptime alert" you@example.com
```

## README badge

Add an uptime badge using the GitHub Actions workflow status:

```markdown
[![Uptime](https://github.com/Pratiyush/llm-wiki/actions/workflows/uptime.yml/badge.svg)](https://github.com/Pratiyush/llm-wiki/actions/workflows/uptime.yml)
```

This badge reflects the most recent workflow run. Green means the last
check passed; red means the site was unreachable.

## What to monitor

| Endpoint | Why |
|---|---|
| `/` (home page) | Core site availability |
| `/sitemap.xml` | SEO health -- search engines rely on this |
| `/llms.txt` | AI agent discoverability |
| `/search-index.json` | Search functionality depends on this |
| `/sessions/` (any session) | Content rendering works end-to-end |

## Monitoring services (free tier)

If you want more sophisticated monitoring than a cron job:

| Service | Free tier | Notes |
|---|---|---|
| [UptimeRobot](https://uptimerobot.com) | 50 monitors, 5-min interval | Email + Slack alerts |
| [Pingdom](https://www.pingdom.com) | 1 monitor | SMS + email alerts |
| [Freshping](https://www.freshworks.com/website-monitoring/) | 50 monitors, 1-min interval | Status page included |
| [GitHub Actions](https://github.com/features/actions) | 2,000 min/month | Already set up above |

For a personal project, the GitHub Actions approach is sufficient and
requires no external accounts.

## Incident response

When the uptime check fails:

1. Check GitHub Pages status at [githubstatus.com](https://www.githubstatus.com/)
   -- if Pages is down globally, wait for GitHub to resolve it
2. Check the latest `pages.yml` workflow run -- a build failure means
   the site was not deployed
3. Verify the `CNAME` record if using a custom domain -- DNS changes
   can take up to 24 hours
4. Check the repo settings under **Pages** -- ensure the source branch
   and directory are correct

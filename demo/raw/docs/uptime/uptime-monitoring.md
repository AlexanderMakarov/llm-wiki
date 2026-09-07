---
title: "Uptime Monitoring"
slug: uptime-monitoring
project: uptime
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/uptime.md"
content_sha256: 0b4c5d28623514285cdc4f2c78247a062468f87ddf32ddedb6d23996af137ecc
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

## Version freshness (a reachable site can still be wrong)

An uptime check answers "is the site up", which is not the same question as "is the site current". The llmwiki demo once served a four-release-old build behind entirely green checks: every URL returned 200, and nothing compared what was published with what had been released (#213).

`llmwiki build` writes `site/manifest.json` with the `__version__` of the build that produced it, so the deployed site carries its own version. `scripts/check_live_version.py` reads it back and compares:

```bash
# against __version__ in the checked-out tree
python3 scripts/check_live_version.py --url https://<username>.github.io/<repo-name>/

# against an explicit version (a leading "v" is stripped, so tags work)
python3 scripts/check_live_version.py --url https://<username>.github.io/<repo-name>/ --expected v2.1.0
```

Pass either the site root or the `manifest.json` URL — the script appends the filename when it is missing. Exit codes are distinct so a failing job says which problem it hit:

| Exit | Meaning |
|---|---|
| 0 | Live version matches the expected version |
| 1 | Mismatch — the site is stale (or ahead of) the code |
| 2 | Unreachable — the manifest could not be fetched |
| 3 | Malformed — the response was not JSON, or carried no `version` |

`.github/workflows/pages.yml` calls it right after `actions/deploy-pages`, so a deploy that does not actually reach the live URL turns the run red instead of green. That post-deploy assert is the only automated freshness gate: version tags (and manual dispatch) republish the demo, and the check confirms the live site matches the commit that was just published. There is no separate weekly job — a skipped or cancelled Pages run is caught by watching the release checklist, not by a cron.

A red post-deploy check is not an outage: the site is up, it is just not serving this build yet (or at all). Re-run **Actions → Deploy demo site to GitHub Pages**, or fix `__version__` / the tag and cut again — do not treat it as an HTTP outage.

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
| `/manifest.json` | Which build is live — reachable is not the same as current |
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

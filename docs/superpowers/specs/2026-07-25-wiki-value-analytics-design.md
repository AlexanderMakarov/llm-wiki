# Wiki value analytics (#52)

**Status:** implemented · **Date:** 2026-07-25 · **Branch:** `feat/wiki-value-analytics-52`

## Goal

Make the static-site Analytics page answer usage-led value questions: retrieval payoff, answer rate, reads vs writes, sessions vs docs mix, caller reach (Tier 1), top/dead pages, and a stored daily trend with two series (MCP calls + best-effort wiki-using sessions).

## Locked decisions

- Surface: Analytics page only (`llmwiki usage` CLI unchanged)
- Sessions vs docs: page-count corpus mix + `wiki_read_page` read mix (no USD split)
- Lead with usage; USD from `synth.estimate` is a muted secondary line
- Daily MCP series persists in `usage/daily.json`; session-adoption days recomputed each build
- Dual chart: MCP calls/day + wiki-using sessions/day
- Unknown attribution is tolerable and shown honestly
- Top/dead pages use retained (non-compacted) telemetry only

## Implementation map

| Piece | Location |
|---|---|
| Daily persistence + value aggregates | `llmwiki/usage.py` |
| Session adoption detector | `llmwiki/wiki_adoption.py` |
| Analytics render | `llmwiki/build.py` (`render_wiki_value_section`, `render_wiki_value_daily_chart`) |
| Styles | `llmwiki/render/css.py` |

## Out of scope

- CLI value report parity
- Tier 2 feedback tool
- Expanding Cursor converter `tools_used` beyond body best-effort
- Persisting per-page retrieval history across compact
- USD split sessions vs docs

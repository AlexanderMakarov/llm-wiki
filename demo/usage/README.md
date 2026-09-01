# Demo MCP usage

Fixture telemetry under `usage/` for the Pages demo Analytics widgets (MCP heatmaps, per-tool table, heaviest project).

Synthetic only — no personal vault queries. Queries mention the demo product docs and projects (`llm-wiki`, `demo-todo-api`, …).

The committed JSONL and `daily.json` keep pre-#196 tool names (July/August dates). Regenerate with `python3 scripts/generate_demo_usage.py` when you want a fresh fixture on the six-tool surface — that script writes JSONL and folds `daily.json` via `refresh_daily()`.

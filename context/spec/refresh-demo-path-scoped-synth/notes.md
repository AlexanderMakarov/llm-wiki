# refresh_demo path-scoped synth

## Problem

`scripts/refresh_demo.py` planned only changed product docs, then called `llmwiki synth --vault demo --docs-only` with no `--path`. That flag means every pending document under `raw/docs/`, so a 12-doc release refresh could queue 100+ pages and hit provider rate limits (v2.2.0 cut).

## Fix

After `add`/`remove`, build synth argv via `synth_argv_for_added_docs`: `synth --docs-only` plus repeatable `--path raw/docs/<slug>/…` for each slug the plan added. Remove-only plans skip synth and skip `synth --check`.

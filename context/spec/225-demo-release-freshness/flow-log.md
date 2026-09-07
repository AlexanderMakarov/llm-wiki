# Flow log — #225 demo release freshness (docs reminder slice)

## docs reminder (2026-09-06)
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/225 — full automated gate still open
- This change: release checklist / skill / script docs so maintainers cannot forget regenerate-before-tag; README CI Python claim fixed (stale 3.12+3.13)
- Automated stale-session CI gate left for the issue acceptance criteria

## wiki-checks shallow clone (2026-09-07)

- Symptom: after committing `demo/.demo-source-rev`, Wiki checks failed on `refresh_demo.py --dry-run` with `fatal: bad object` / `bad revision` because `actions/checkout` default depth-1 cannot resolve the recorded parent SHA or release tag.
- Fix: `.github/workflows/wiki-checks.yml` sets `fetch-depth: 0` so the dry-run plan can resolve the recorded rev. Pin `.demo-source-rev` to the v2.2.0 demo commit SHA (`5952316…`).

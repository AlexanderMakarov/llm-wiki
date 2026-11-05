# Flow log amendment — drop build-time topic pruning (2026-11-04)

Product owner direction: hollow curated pages belong out of the vault (especially demo), not hidden at render time.

## Shipped in this amendment

- Removed `prune_empty_isolated_topics` from the build path; Graph / Topics / search share the full topic graph node list.
- Added `hollow_curated_pages` lint (warning) via `llmwiki/topics_health.py`.
- Demo: removed empty entity pages `Python`, `SQLite`; index `Entities (7)`.
- Home Knowledge card: Candidates · Entities · Concepts · Other (graph counts; href Topics index).
- Split `tests/test_248_acceptance.py` → `tests/test_curated_topics_*.py`, `tests/test_hollow_curated_pages.py`.

## Follow-up

- GitHub issue for remaining pipeline vs graph metric alignment (self-heal / bug labels).

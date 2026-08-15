Scaffold an empty llmwiki — create `raw/`, `wiki/`, `site/` directories and seed `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`.

Usage: /wiki-init

Steps:

1. Run:
   ```bash
   python3 -m llmwiki init
   ```
2. Report what was created.
3. Suggest the user's next step: `/wiki-sync` to ingest session transcripts, or `/wiki-ingest raw/<path>` to ingest a specific source.

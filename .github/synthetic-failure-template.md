# Synthetic monitoring failure

The nightly synthetic monitoring workflow (`.github/workflows/synthetic.yml`) failed while walking a freshly built demo site opened as files.

## Possible causes

- The build itself emitted a broken or incomplete site — check the most recent `pages.yml` run for the same corpus.
- A page asked for a file the build did not emit, so it loads only where something answers requests for it.
- Third-party failure on the one accepted outbound link (fonts.googleapis.com) or on axe-core. highlight.js and vis-network ship beside the pages (#127) and are not CDN-loaded.
- A browser update changed default behaviour for one of the tested features.

## Debug

- Download the `synthetic-report` artifact from the failed workflow run for an HTML report with screenshots + traces.
- Re-run the workflow manually via "Run workflow" on the workflow page to confirm the failure isn't transient.

## Triage

If the built demo is broken, file a fresh issue describing the user impact and link the failed workflow run. Resolve this tracking issue once the underlying cause is fixed.

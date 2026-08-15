Synthesize `wiki/sources/<slug>.md` pages from raw session transcripts and harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only behaviour.

Wraps: `python3 -m llmwiki synth`

Usage: `/wiki-synth` (preferred) or `/wiki-synthesize` (deprecated alias). Claude translates natural-language phrasing into flags.

## Natural-language → flags

| You say | Runs |
|---|---|
| "just show me what it would cost" | `python3 -m llmwiki synth --estimate` |
| "check the backend is reachable" | `python3 -m llmwiki synth --check` |
| "force re-synthesize everything" | `python3 -m llmwiki synth --force` |
| "sources only, no candidates" | `python3 -m llmwiki synth --sources-only` |
| "candidates only" | `python3 -m llmwiki synth --candidates-only` |

## Expected output

First run on a fresh corpus (dummy backend):

```
Backend: DummySynthesizer
Scanned 785, new 785, synthesized 785, skipped 0
Candidates: N stub(s) at --min-refs 3 → …/wiki/candidates
```

Re-run on unchanged tree:

```
Backend: DummySynthesizer
Scanned 785, new 0, synthesized 0, skipped 0
Candidates: N stub(s) at --min-refs 3 → …/wiki/candidates
```

## When to use

- After `/wiki-sync` produces new `raw/sessions/*.md` files and you want their `wiki/sources/*.md` counterparts (and candidates) immediately.
- After updating the prompt template under `wiki/prompts/source_page.md` — pair with `--force` to re-synthesize everything using the new prompt.
- After switching synthesis backends (`dummy` → `ollama` → api).

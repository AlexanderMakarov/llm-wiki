---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 3/3: Phase 6.5 — Self-Demo (NEW))"
slug: llmwiki-framework-building-an-agent-native-dev-tool-03
project: llmwiki-framework-building-an-agent-native-dev-tool
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/framework.md"
content_sha256: eaa0b1b799c976996e7f4c0abe139ab99b35aae734b1fa67f0b35a8648668fa7
---

> Part 3 of 3 of **llmwiki Framework — Building an Agent-Native Dev Tool** — Phase 6.5 — Self-Demo (NEW).

## Phase 6.5 — Self-Demo (NEW)

**llmwiki's killer demo is its own repo.**

Every dev tool that produces browsable output should publish its own dev history as the demo. The pattern:

1. **On tag push**, CI:
   a. Runs the tool against the author's own session transcripts (stored as an encrypted test corpus OR synthetic fixtures)
   b. Builds the HTML site to `site/`
   c. Publishes to GitHub Pages
2. The GitHub Pages URL becomes the README's demo link.
3. Every release updates the demo automatically.
4. Visitors SEE the exact output they'd get. No screenshots, no "look here's what it looks like on my machine".

For **privacy reasons**, llmwiki's self-demo uses a **synthetic corpus** under `demo/`, not the author's real session history. The fixtures are hand-curated, cover all UI states (short sessions, long sessions, sub-agents, code blocks, tool calls, errors), and are committed to the repo.

### Gate to Phase 7

Self-demo is closed when:
- [x] `demo/raw/sessions/` has 10+ representative sessions
- [ ] `.github/workflows/pages.yml` builds and publishes on tag push
- [ ] The README's demo link is a working URL

---

## Phase 7 — Grow

Same as parent. Platform strategies for a dev tool:

| Platform | Angle |
|---|---|
| Reddit r/ClaudeAI | "I built a local tool that turns all your Claude Code sessions into a Karpathy-style wiki" |
| Reddit r/programming | "Self-hosted knowledge base from your AI coding sessions, no servers needed" |
| Hacker News | "Show HN: llmwiki — Turn your coding agent session history into a searchable wiki" |
| X/Twitter | Thread: screenshot → demo URL → install command → link |
| Dev.to | Long-form: "I have 278 Claude Code sessions. I built this to browse them." |
| LinkedIn | "Learning from your own work" framing |

---

## Phase 7.5 — Living Knowledge (NEW)

**The wiki built during development IS a growth engine.** Publish it.

- The author's own `wiki/` (synthetic or hand-curated) becomes a public knowledge base at `https://pratiyush.github.io/llmwiki/wiki/`.
- Every release refreshes the public wiki with new insights, decisions, and patterns extracted from dev sessions.
- Visitors who land on the demo can also browse the **living documentation of how the tool is built** — a form of meta-transparency that doubles as SEO.

### Operational rules

1. **No real PII.** Use the same synthetic corpus as Phase 6.5 Self-Demo.
2. **Opt-in.** The `pages.yml` workflow only publishes to Pages when a tag is pushed, not on every commit.
3. **The public wiki and the release notes cross-link.** Every release's changelog links to the relevant wiki page.
4. **Feedback loop.** Community feedback on wiki pages (via GitHub Issues) feeds back into the framework.

---

## Phase 8 — Maintain

Same as parent plus agent-specific additions:

### Monthly checklist

- [ ] Check Claude Code / Codex CLI release notes for schema changes
- [ ] Re-run test fixtures against latest CLI version
- [ ] Update `SUPPORTED_SCHEMA_VERSIONS` if compatibility confirmed
- [ ] Bump CHANGELOG
- [ ] Re-run pre-launch QA checklist
- [ ] Review open issues labelled `adapter:*`

### Schema-change response playbook

When an agent ships a new `.jsonl` schema:

1. Create a fresh fixture from a real (redacted) session
2. Run the converter; note any crashes or data-loss
3. If graceful degradation works: add the version to `SUPPORTED_SCHEMA_VERSIONS`, commit the fixture, done
4. If not: open an issue, tag `adapter:<agent>`, block the release until fixed
5. If the change is breaking: ship a new adapter file (`claude_code_v3.py`) alongside the old one, route by version

---

## Dogfooding Meta-Loop (cross-cutting)

**llmwiki tracks its own development with llmwiki.**

- Every dev session on llmwiki is already being captured by Claude Code.
- `./sync.sh` pulls those sessions into `raw/sessions/llmwiki/`.
- The author runs `./build.sh` and reads the output to validate the tool on its own dev history.
- Insights (bugs, UX issues, missing features) get extracted into `tasks.md`.
- The loop closes: the tool's own output drives the tool's own backlog.

This is only possible because the tool is self-referential by design — it's a dev tool that browses dev sessions, built during dev sessions.

---

## Summary of extensions over the parent framework

| Phase / Rule | Added | What it gives you |
|---|---|---|
| 1.75 Agent Survey | ✅ | Predictable adapter compatibility tracking |
| 5.25 Adapter Flow | ✅ | Community can extend the tool without the author's intervention |
| 6.5 Self-Demo | ✅ | Zero-effort landing-page demo from CI |
| 7.5 Living Knowledge | ✅ | The dev wiki doubles as marketing + meta-documentation |
| Schema-Versioning rules | ✅ | Graceful degradation when upstream agents change format |
| Privacy-First rules | ✅ | No telemetry, no network, no PII by default |
| Performance Budget | ✅ | Budget-enforced build pipeline |
| Dogfooding Meta-Loop | ✅ | Tool improves itself from its own output |

None of these violate the parent framework; they extend it with patterns specific to **agent-native dev tools** — a category that the parent framework's `Curated Lists / Libraries / Marketplaces / Dev Tools` typology didn't cover.

Future projects in this category (a Cursor wiki, a Cline session browser, a multi-agent unified viewer) should inherit this document and extend it further.

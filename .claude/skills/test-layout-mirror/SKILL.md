---
name: test-layout-mirror
description: >-
  How to plan and verify a tests/ mirror of an llmwiki/ package (CLI, render, MCP, adapters, synth, …) without shipping refactor-proving pytest. Use whenever consolidating flat tests/test_<area>_*.py into tests/<area>/, writing AWOS tasks.md / tech for a layout migration, extending test_quality_gates.py for a new mirror, or reviewing a “tests under tests/X/” ticket — even if the user only says “move the tests” or “same as #280/#316”. Prefer this skill over inventing new quality-gate inventory asserts.
---

# Test layout mirror (llmwiki)

## Why this exists

Agents repeatedly added pytest that only checks which `tests/*.py` files exist after a move (glob flat prefixes, stay-put allow-lists, “assert originals are gone”). That violates CODING_STANDARDS / CLAUDE.md / AGENTS.md. The recurring **instruction** was not the standards docs — they already forbid it — but **Slice 4 wording in AWOS `tasks.md`** that said “optionally assert flat `tests/test_*_*.py` originals are gone” (first written in `415-mcp-tests-consolidate/tasks.md`, then copied into later tickets). Specific task text beat the general agent rule.

## When writing `tasks.md` / tech for a mirror pass

**Allowed quality-gate work**

- DOC assert: `docs/CODING_STANDARDS.md` *names* `tests/<pkg>/`
- Layout gate: `tests/<pkg>/` exists and contains at least one `test_*.py` (package helper if `__init__.py` is intentional; dir helper if no ticket-only init — match sibling mirrors)

**Forbidden (do not write into tasks, do not implement)**

- “Assert flat originals are gone”
- Hard-coded frozensets / allow-lists of stay-put or migrated filenames
- Globbing `tests/test_<prefix>*.py` and comparing to an inventory
- Pytest whose only failure mode is “someone added a legitimately rooted `test_<prefix>_….py` later”

Stay-put modules belong in the **technical-considerations stay-put table** and in **human review**, not in the suite.

## When acting as testing-expert

If `tasks.md` still contains the forbidden phrase, **refuse that clause**, implement only DOC + directory-has-modules gates, and report the refusal so the task line can be fixed. CODING_STANDARDS wins over a bad task copy-paste.

## Copy-paste template (Slice 4 nested task)

```text
Prefer extending tests/test_quality_gates.py invariants for tests/<pkg>/ layout
(package/dir has test_*.py modules + CODING_STANDARDS DOC mention only —
never assert that named flat originals are gone or inventory filenames)
over inventing product behaviour tests for this layout-only migration.
```

## Related

- `docs/CODING_STANDARDS.md` — “Tests assert product behaviour, not the edit” + “Layout-migration tasks must not ask for flat-gone inventory asserts”
- `.claude/agents/testing-expert.md` — `tasks.md` cannot override the no-inventory rule
- Good precedent: `416-adapter-tests-consolidate/tasks.md` (no flat-gone phrase)
- Bad precedent (now errata’d): old `415-mcp-tests-consolidate/tasks.md` Slice 4 wording

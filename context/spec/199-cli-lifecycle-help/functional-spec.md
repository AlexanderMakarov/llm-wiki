# Functional Specification: CLI help as a lifecycle map

- **Roadmap Item:** CLI help as a lifecycle map (#112); remove dead commands; wrap migrations under one `migrate`
- **Status:** Approved
- **Author:** Aleksandr Makarov
- **Issue:** [#112](https://github.com/AlexanderMakarov/llm-wiki/issues/112)
- **Date:** 2026-09-03

## 1. Overview and Rationale (The "Why")

Someone who types `llmwiki --help` today sees a long historical list. It does not say what to run first, what comes next, or which names are leftover. Issue numbers and jargon leak into the text. One-time migrations sit next to daily commands as if they were equals. A retired command and a deprecated alias still look like real options. Each migration is also its own top-level command, so the list grows every time a vault format changes.

Desired outcome: **help teaches the wiki loop**; **dead names are gone**; **all migrations live under one `migrate` command** that you inspect before you apply. New migrations are added there, not as new top-level commands. Guides that still tell people to type `synthesize` or `consolidate-topics` are rewritten so they teach the current loop.

Success:

- Top-level help groups commands so the daily loop is obvious.
- Each remaining command’s own help is enough to know what it is for, when to run it, what usually comes before/after, and what it deliberately does not do.
- `synthesize` and `consolidate-topics` no longer appear or run.
- There is a single `migrate` command; `migrate` / `migrate --list` lists migrations; applying one is an explicit choice.
- Contributor instructions (including the vault schema files agents read) say: add a new migration to this wrapper, never as a separate command.
- Tutorials and other user guides do not tell anyone to run the removed names.

## 2. Functional Requirements (The "What")

### R1 — Top-level help is a map, not a dump

- **As a** new user, **I want** `llmwiki --help` to show commands in lifecycle groups with a loop reminder, **so that** I know the order of work without a separate guide.
  - **Acceptance Criteria:**
    - [ ] `llmwiki --help` (and `python3 -m llmwiki --help`) lists commands under these headings, not one unsorted list:

      | Group | Commands |
      |---|---|
      | **Start here** | `init`, `configure-sources`, `install-agent-kit` |
      | **Daily loop** (this order) | `sync`, `add`, `synth`, `candidates`, `build` |
      | **Run the loop for me** | `all`, `watch`, `install-automation` |
      | **Look around** | `lint`, `query`, `trace`, `graph`, `adapters`, `usage`, `version` |
      | **Take things out** | `remove` |
      | **Rare — one-time** | `migrate`, `queue` |

    - [ ] Help ends with a canonical-loop reminder: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`). It states that `synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh.
    - [ ] No top-level help line contains a GitHub issue number.
    - [ ] One-line summaries are imperative and outcome-oriented. Jargon is defined in the same line if it appears.
    - [ ] Every remaining top-level command appears in exactly one group. There are no `migrate-*` top-level names.

### R2 — Each command’s own help is a real explanation

- **As a** user who has picked a command, **I want** `llmwiki <command> --help` to explain it in full, **so that** I do not need a second document to know when to use it.
  - **Acceptance Criteria:**
    - [ ] Every remaining command’s `--help` includes readable prose covering: what it does; where it sits in the loop; what it deliberately does not do; and, if it is rare, that fact in the opening paragraph.
    - [ ] Flag descriptions drop issue numbers and unexplained jargon (define “adapter” in the same help if the word is used).
    - [ ] `synth --help` states that candidate review normally follows, then `build`.
    - [ ] `candidates --help` states it runs after `synth`, and that rebuilding the site after review keeps the Candidates page in sync (unless the user opts out of rebuild on batch apply).
    - [ ] `queue --help` explains this is the internal task list when work is deferred (add a document, sync sessions, summarise, rebuild), and that most people never need it if they run `sync` / `synth` / `build` / `all` themselves.
    - [ ] `all --help` states it is the full pipeline in one invocation, and which stages can be skipped.
    - [ ] `migrate --help` is the home of migration help (see R4): how to list, how to run one by name, that nothing is applied until a name is chosen, and that new migrations are added here rather than as new commands.

### R3 — Dead commands are removed; guides that taught them are rewritten

- **As a** user, **I want** only commands that still do useful work, **so that** I do not run leftovers — and **as a** reader of a tutorial, **I want** the commands in the walkthrough to match what `--help` lists.
  - **Acceptance Criteria:**
    - [ ] `llmwiki --help` does not list `synthesize` or `consolidate-topics`.
    - [ ] `llmwiki synthesize …` and `llmwiki consolidate-topics …` fail as unknown commands. They do not do the old work.
    - [ ] Changelog and upgrade notes say: use `synth` instead of `synthesize` (`synthesize` was sources-only by default); summarisation prepares known names — do not run `consolidate-topics`.
    - [ ] Every user-facing tutorial, cheatsheet, slash-command page, and similar walkthrough that still tells the reader to run `synthesize` or `consolidate-topics` is rewritten to the current names and loop (`synth`, and harvest/review instead of consolidate-topics). Historical changelog entries may still mention the old names.

### R4 — One `migrate` command lists and runs migrations

- **As a** user with an existing vault after an upgrade, **I want** one place to see which migrations exist and to run the one I need, **so that** I never mistake a one-time rewrite for a daily command.
  - **Acceptance Criteria:**
    - [ ] Top-level `migrate-state`, `migrate-raw-redaction`, `migrate-tools-used`, `migrate-page-kinds`, `migrate-topic-kinds`, and `migrate-broken-provenance` are gone (`--help` does not list them; typing them is an unknown command).
    - [ ] `llmwiki migrate` with no extra arguments, and `llmwiki migrate --list`, print the same catalog: each migration’s short name, a one-line purpose, and when you would apply it. Nothing in the vault is changed by listing.
    - [ ] Applying a migration requires naming it, e.g. `llmwiki migrate <name> …` with that migration’s own flags (vault path, dry-run, and so on — same capabilities as today’s separate commands). A missing or unknown name does not apply anything; it fails and points the user at the list.
    - [ ] There is no “run every migration” default. Listing is not applying.
    - [ ] `llmwiki migrate --help` explains listing vs applying, that these are rare one-time repairs, and shows how to get the list.
    - [ ] Upgrade notes map each old command to `migrate <name>` (for example `migrate-raw-redaction` → `migrate raw-redaction`).
    - [ ] The six current migrations remain available under this wrapper (same user-visible jobs as today, new invocation shape).

### R5 — New migrations go in the wrapper, not as new commands

- **As a** contributor (human or agent) adding a vault repair, **I want** the project instructions to say “register it under `migrate`”, **so that** `--help` does not grow another top-level name.
  - **Acceptance Criteria:**
    - [ ] The packaged agent/vault schema files (`AGENTS.md`, `CLAUDE.md`) and the contributor-facing command reference (or equivalent “how to extend the CLI” note) state: add a new migration as an entry of `migrate`, not as a new top-level command.
    - [ ] A reviewer following those files would not add `llmwiki migrate-something-new` as its own command.

### R6 — Documentation matches the terminal

- **As a** reader of the command reference, **I want** the same grouping, command set, and `migrate` catalog as live help.
  - **Acceptance Criteria:**
    - [ ] The CLI reference lists the same top-level commands as `--help`, in the same groups. Removed names appear only as a short “removed / renamed” note if needed.
    - [ ] The `migrate` section documents listing and each named migration.
    - [ ] Automated “every live command is documented” checks still pass and do not require the removed top-level names.

## 3. Scope and Boundaries

### In-Scope

- Grouped, rewritten top-level and per-command help.
- Removal of `synthesize` and `consolidate-topics`.
- Collapse of `migrate-*` into `migrate` (list + run-by-name).
- Updates to CLI reference, changelog, upgrade notes, cheatsheet, slash-command docs, **tutorials that still teach the old names**, and agent/contributor schema files for the “add migrations here” rule.
- Tests for grouping, no issue numbers in top-level help, unknown old names, `migrate` list vs apply, and doc/CLI parity.

### Out-of-Scope

- Changing what remaining commands do, except as needed to delete old names and route migrations through `migrate`.
- Removing `queue`.
- Auto-detecting which migrations a given vault still “needs” (the list is the catalog of available migrations, not a doctor-style pending report). That stays with #110 if at all.
- Adding `doctor` or `serve`.
- A single flag that applies every migration in one shot.
- Rewriting changelog history; only current tutorials/guides that instruct the user to run dead names.

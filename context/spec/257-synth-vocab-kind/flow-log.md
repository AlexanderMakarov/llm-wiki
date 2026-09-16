# Flow log — 257-synth-vocab-kind

## fetch-ticket / resume-detection / workspace
- **Ticket:** [#257](https://github.com/AlexanderMakarov/llm-wiki/issues/257) open; labels bug + important; no prior merged PR for this work.
- **Branch / worktree:** `feat/257-synth-vocab-kind` @ `.claude/worktrees/feat-257-synth-vocab-kind`; throwaway vault `.worktree-vault` via worktree `config.json`.
- **Author:** Alexander Makarov (GitHub display name).
- **Next:** specs (`/awos:spec` gate).

## specs (functional — approved)
- **Produced:** `context/spec/257-synth-vocab-kind/functional-spec.md` (Status: Approved; user lgtm).
- **Decisions:** Kind fallback = prefer page filing when known-names lacks kind (option 1). #264 complementary; out of scope with compatibility note.
- **Next:** `/awos:tech` gate.

## specs (technical — approved)
- **Produced:** `context/spec/257-synth-vocab-kind/technical-considerations.md` (Status: Approved).
- **Decisions:** Source-vs-source kind fights stay harvest/job-1 (majority / one cache kind); #257 inject = cache → unique page filing → omit (option 1). #264 out of scope.
- **Next:** tasks → commit-specs → implement.

## specs (tasks)
- **Produced:** `context/spec/257-synth-vocab-kind/tasks.md` — 3 slices (shared map+inject; prompt+docs; regression). Agents: generalPurpose / testing-expert.
- **Next:** commit specs, then `/awos:implement`.

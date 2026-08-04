# Flow log — 002-ci-refactor-ci (#116)

## fetch-ticket
- Issue #116 open: chore CI — Node 20 deprecation, Python 3.12-only, drop Claude-in-CI
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/116
- Next: workspace

## resume-detection
- No prior spec for #116; no PR; issue open
- Next: workspace

## workspace
- Stashed unrelated #102 WIP (`wip: #102 drop entity_type taxonomy — parked for feat/116`)
- Branch: `feat/116-ci-refactor-ci` from `origin/main` @ 67ebbf6
- Next: specs (/awos:spec)

## specs — functional
- Approved functional-spec.md → `context/spec/002-ci-refactor-ci/functional-spec.md`
- Decisions: latest action majors; gitleaks verify-then-bump (OK for personal acct); one PR A+B+C; secret deletion = grep + PR note
- Next: /awos:tech

## specs — technical
- Approved technical-considerations.md
- Next: /awos:tasks then implement

## specs — tasks
- Approved tasks.md (skip Feature Testing)
- Next: commit-specs then /awos:implement

# Phase A — merge commit or full-message marker (2026-11-06)

Phase A passes when either signal holds on the main checkout: the closing PR's merge commit (SHA from the last GitHub poll) is an ancestor of local `HEAD` (`git merge-base --is-ancestor`), or one of the last 10 commits names the ticket — any whole `#N` token in its subject, or a closing keyword (`Closes` / `Fixes` / `Resolves #N`) in its body. A bare `#N` in a body is usually a cross-reference (`Relevant to #N` on a partial PR) and would pass Phase A before this ticket's delivery was pulled, so it does not count. This replaces `#N` in `git log -n 10 --oneline` from `phase-a-no-porcelain.md` and the marker rule in `advance-wait-redesign.md`.

Rationale: a delivery whose commit carried `Closes #N` only in its body, merged by GitHub as `Merge pull request #PR from …`, never showed `#N` under `--oneline`, so the driver waited in Phase A forever although the issue was closed, merged and green. The merge-commit check does not depend on commit-message wording or on the 10-commit window; the message check remains the fallback before the first successful GitHub poll.

`--skip-issue N` no longer requires `--label` — it only writes the skip file. Normal runs still reject a missing `--label` (exit 2).

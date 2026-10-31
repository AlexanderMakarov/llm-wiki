# Functional Specification: Automation never fails silently

- **Roadmap Item:** GitHub issue [#374](https://github.com/AlexanderMakarov/llm-wiki/issues/374) — surface failed or missed scheduled runs on Home
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

The daily scheduled run is what turns a user's agent sessions into wiki knowledge without them having to think about it. Users trust it to keep working, and they only look at the site's Home page to see how things stand.

Today a scheduled run can fail every day for days while Home looks healthy. In the incident behind this change, the AI backend used for summarizing stopped being found after a routine update of that backend. For four days each run collected new sessions, skipped summarizing, rebuilt the site and ended in failure. Home showed a current "Last sync" time, no warning anywhere, and a "Last synth" time that stopped moving — hidden inside a collapsed section. The only real signal was a log file the user never opens. The same happened earlier when a single document could not be summarized: every run failed, nothing on Home said so.

Home already has a red note for wiki lint errors, tucked under the pipeline tables. Failures of the scheduled run itself have no place at all.

**Desired outcome:** Home has one place for every error — a single red banner at the top. If a scheduled run did not finish cleanly, did not happen at all, or the wiki has lint errors, the user sees it there the next time they open the site, with each problem labelled by the exact part that failed and whether that part failed entirely or only partly, and enough detail to know where to look. Each problem goes away once it is fixed.

**Success measure:** a failed or missed scheduled run is visible on Home within one page refresh after it happens, no run failure goes unshown, and the user never has to look in more than one place on Home to find out what is broken.

---

## 2. Functional Requirements (The "What")

### 2.1 One red error banner at the top of Home

Home has exactly one place for errors: a red banner above all other Home content. It collects every current problem — failed parts of the latest scheduled run, an overdue scheduled run (2.4), and wiki lint errors — as separate entries in the same banner. When there are no current problems, there is no banner.

The existing red lint note under the pipeline tables moves into this banner as its "Lint" entry and no longer appears on its own. A lint entry appears under the same conditions the lint note appears today, and shows the same findings. The full lint report stays where it is today, in the "Linter output" section.

- **Acceptance Criteria:**
  - [ ] Given a scheduled run whose summarizing failed and a wiki with lint errors, when the user opens Home, then one red banner at the very top shows a "Synth" entry and a "Lint" entry, and no separate red lint note appears under the pipeline tables.
  - [ ] Given a wiki with lint errors and a clean scheduled run, when the user opens Home, then the red banner at the top shows only a "Lint" entry with the same findings the lint note used to show.
  - [ ] Given a clean scheduled run, no overdue run and no lint errors, when the user opens Home, then no red banner is shown.

### 2.2 Each entry says exactly what failed and how much of it

Every entry in the banner starts with the part that failed — "Sync" (collecting new sessions), "Synth" (summarizing sources into wiki pages), "Build" (rebuilding the site), "Lint" (wiki checks), or "Schedule" (the scheduled run itself) — followed by whether that part failed **entirely** or **partly**:

- **Entirely** — the part could not do its job at all. Examples: "Synth — did not run: backend claude-cli is not available"; "Build — failed"; "Schedule — overdue".
- **Partly** — the part ran, but some of its items failed. The entry says how many of how many, and which. Examples: "Synth — 1 of 7 sources failed"; "Sync — 1 of 4 session sources failed (Cursor)"; "Synth — stopped at the AI provider's usage limit after 5 of 12 sources".

Each entry also shows when it happened, the first lines of the error message (longer messages end with "…"), and where the full log is. All entries are red, whether the part failed entirely or partly.

When the run as a whole ended in failure but no single part reported an error, the banner still shows an entry saying the run failed, with when and the log location.

- **Acceptance Criteria:**
  - [ ] Given a scheduled run where summarizing could not start because the AI backend was not found, when the user opens Home, then the banner shows a "Synth" entry saying it did not run, with the run's date and time, the "backend … is not available" message, and the log file location.
  - [ ] Given a scheduled run where 6 of 7 sources were summarized and 1 failed, when the user opens Home, then the "Synth" entry says 1 of 7 sources failed, names that source, and shows its error.
  - [ ] Given a scheduled run where summarizing stopped at the AI provider's usage limit, when the user opens Home, then the "Synth" entry says it stopped at the usage limit and how many sources it finished out of how many.
  - [ ] Given a scheduled run where collecting sessions failed for one of several session sources and rebuilding the site failed, when the user opens Home, then the banner shows a "Sync" entry saying which session source failed out of how many, and a "Build" entry saying the build failed.
  - [ ] Given a scheduled run with a very long error message, when the user opens Home, then that entry shows only the first lines followed by "…".
  - [ ] Given a scheduled run that ended in failure without any part reporting an error, when the user opens Home, then the banner shows an entry saying the run failed, with when and the log location.

### 2.3 The banner appears even when the site rebuild is the part that failed

The user must see the banner without having to rebuild the site themselves. Refreshing an already-built Home page in the browser is enough to show a new problem, including a failure of the rebuild itself.

- **Acceptance Criteria:**
  - [ ] Given a site built earlier and a later scheduled run whose rebuild step failed, when the user refreshes Home in the browser, then the red banner shows a "Build" entry with its error.
  - [ ] Given a site built earlier and a later scheduled run whose summarizing failed, when the user refreshes Home without anything rebuilding the site, then the red banner shows the "Synth" entry.

### 2.4 Entries clear when the problem is fixed

An entry disappears from the banner as soon as that part next finishes cleanly — whether in the next scheduled run or when the user runs that same part by hand after fixing the cause (a lint entry clears when lint next passes, as today). Parts that still fail stay listed. When no entries remain, the banner is gone. A partial or trial run (for example summarizing a single chosen file, a cost estimate, or a "can the backend be reached" check) does not clear anything, because it did not do the whole part. No site rebuild is needed: refreshing Home shows the change.

- **Acceptance Criteria:**
  - [ ] Given a banner with only a "Synth" entry, when the next scheduled run finishes cleanly and the user refreshes Home, then the banner is gone.
  - [ ] Given a banner with only a "Synth" entry, when the user fixes the cause, runs summarizing by hand and it finishes without errors, then after refreshing Home the banner is gone.
  - [ ] Given a banner with "Sync" and "Build" entries, when a run finishes with collecting sessions clean but the rebuild still failing, then after refreshing Home only the "Build" entry remains.
  - [ ] Given a banner with "Synth" and "Lint" entries, when summarizing next finishes cleanly but lint still finds errors, then after refreshing Home only the "Lint" entry remains.
  - [ ] Given a banner with a "Synth" entry, when the user runs only a cost estimate, a backend check, or summarizes one chosen file, then after refreshing Home the "Synth" entry is still shown.

### 2.5 A scheduled run that did not happen is also shown

When the scheduled job is set up but no scheduled run has happened for longer than one schedule interval plus two hours (for a daily 09:00 schedule: nothing by 11:00 the next day), the banner shows a "Schedule — overdue" entry with when the last scheduled run happened and when the next one was expected. This covers a job that was switched off, a computer that was off or asleep, and a run that crashed before it could record anything. Runs the user starts by hand do not count as scheduled runs for this check. When no scheduled job is set up, this entry is not shown. A later scheduled run clears it.

- **Acceptance Criteria:**
  - [ ] Given a daily 09:00 schedule whose last scheduled run was two days ago, when the user opens Home, then the banner shows a "Schedule — overdue" entry with the last run's date and time and the expected time.
  - [ ] Given a daily 09:00 schedule whose last scheduled run was at 09:00 today, when the user opens Home at 10:00 the next day, then no "Schedule" entry is shown.
  - [ ] Given a daily schedule whose last scheduled run was two days ago, when the user only runs steps by hand today, then the "Schedule — overdue" entry is still shown.
  - [ ] Given no scheduled job is set up, when the user opens Home, then no "Schedule" entry is shown.

### 2.6 Every program the scheduled run depends on keeps being found, and a missing one is reported

The scheduled run relies on programs outside this tool: the program that runs the scheduled job itself, and whichever AI backend summarizes sources — the Claude command-line program, the Cursor agent program, or a local model server. Many of these update themselves, often by swapping the installed version behind a stable launcher.

- Setting up the scheduled job never records a program location that stops working when that program updates itself; it records the stable launcher the user would run, not the version currently behind it.
- A program the scheduled run looks up by name is found by the scheduled job the same way it is found when the user runs the step by hand, so a program that works from the user's terminal also works in the scheduled run.
- When a needed program cannot be found or reached during a scheduled run, the banner shows an entry for the part that needed it, saying it did not run, naming the program and how to fix it (for example where to set its location). The health check command reports the same problem with the same repair.
- When the program that runs the scheduled job itself is missing, so no run can start, the "Schedule — overdue" entry (2.5) shows it, and the health check names the missing program.

- **Acceptance Criteria:**
  - [ ] Given the Claude program is installed behind its usual self-updating launcher, when the user sets up the scheduled job with the Claude backend and Claude then updates itself and removes its previous version, then the next scheduled run summarizes normally.
  - [ ] Given the Cursor agent backend is chosen and the Cursor agent program runs from the user's terminal, when the next scheduled run happens, then it summarizes normally.
  - [ ] Given a saved location for the AI backend program that no longer exists, when the next scheduled run happens, then the banner shows a "Synth" entry saying it did not run, naming that program and how to fix its location, and the health check reports the same with the repair steps.
  - [ ] Given the local model server is chosen and is not running, when the next scheduled run happens, then the banner shows a "Synth" entry saying it did not run because the server could not be reached, with how to start it or switch backend.
  - [ ] Given the program that runs the scheduled job was removed, when the expected run time plus two hours passes, then the banner shows a "Schedule — overdue" entry, and the health check names the missing program.

---

## 3. Scope and Boundaries

### In-Scope

- One red error banner at the top of Home holding every current problem: failed parts of the latest scheduled run (Sync, Synth, Build, or the run as a whole), an overdue scheduled run, and wiki lint errors.
- Moving the existing red lint note into that banner (same findings, same conditions); the full lint report stays in "Linter output".
- Each entry naming the exact part that failed and whether it failed entirely or partly (how many of how many, and which).
- The banner showing up after a browser refresh, without a site rebuild, including when the rebuild itself failed.
- Clearing each entry when that part next finishes cleanly, scheduled or by hand.
- A "Schedule — overdue" entry when the scheduled run has not happened for longer than one interval plus two hours.
- Every outside program the scheduled run depends on (the job's own runner and every AI backend) being found across that program's updates, and a missing or unreachable one being reported in the banner and by the health check.

### Out-of-Scope

- Notifications outside the site (email, desktop pop-ups, chat messages).
- Changes to which lint findings fail lint or to the lint failure policy.
- Automatically repairing a broken setup; the banner reports and points to the fix.
- A history of past runs on Home; only the latest outcome per part is shown.
- A setting to change the two-hour grace for the overdue entry.
- All other roadmap items.

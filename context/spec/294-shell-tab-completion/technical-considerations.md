# Technical Specification: Shell TAB Completion for llmwiki Commands

- **Functional Specification:** [functional-spec.md](functional-spec.md)
- **Status:** Completed
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

The completion line is plain text that the shell reads at startup and runs with its own builtins: bash `complete`/`compgen`, zsh `compdef`/`_arguments`. The command names are written into the line as literals, so no Python runs at TAB time or at shell startup.

The line is built by one small stdlib helper module that reads the top-level command names from `build_parser()`. Two things use that helper:

- **`setup.sh`** calls it once, via `python3 -c`, to write or refresh the line in the rc file.
- **The docs drift test** checks that the line printed in the docs is exactly what the helper produces today.

There is no new CLI subcommand and no completion-script file.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Component breakdown

| Path | Responsibility |
|---|---|
| `llmwiki/shell_completion.py` (new) | `command_names() -> list[str]`: the keys of the root subparser's `choices`, in registration order. `completion_line(shell: Literal["bash","zsh"]) -> str`: the one-line snippet, ending in the marker comment `# llmwiki-completion`. `install_rc_line(rc: Path, shell) -> Literal["added","updated","unchanged"]`: removes every existing line containing the marker, appends the current line, and creates the file if it's missing. Every other byte of the file stays as it was. |
| `setup.sh` | New optional step, next to the existing configure-sources / automation prompts. It runs only when `[ -t 0 ]` and `LLMWIKI_SKIP_COMPLETION != 1`. It picks the rc file from `basename "$SHELL"` (`bash` → `~/.bashrc`, `zsh` → `~/.zshrc`). Any other shell gets the bash line printed with no file changed. It prompts `Add llmwiki TAB completion to <file>? [Y/n]` and, on yes, calls `install_rc_line` and prints `added`, `updated` or `unchanged` with the path. |
| `docs/getting-started.md` | New **Shell completion** section: the bash and zsh lines (copied from the helper's output), what setup does, and the skip variable. |
| `docs/reference/cli.md` | A one-sentence pointer from *Top-level* to that section. |
| `CHANGELOG.md` | `[Unreleased]` → *Added* entry. |

### Line contracts (shape, not final text)

- **bash:** a function `_llmwiki_complete` that fills `COMPREPLY` from `compgen -W "<names>"` only when `COMP_CWORD == 1`, registered with `complete -o default -F _llmwiki_complete llmwiki`.
- **zsh:** makes sure `compinit` is loaded if `compdef` is missing, then registers a function using `_arguments '1:command:(<names>)' '*::arg:_files'` through `compdef … llmwiki`.
- Both lines end in `# llmwiki-completion`, the marker `install_rc_line` uses to find and replace the line.

### Logic

- **Refresh on re-run (FR4):** delete all marker lines, then append one fresh line. Duplicates are impossible, and a new release's commands get picked up.
- **Name order:** registration order from the parser, which is stable. The shell sorts the displayed list anyway.

---

## 3. Impact and Risk Analysis

- **Dependencies:** reads `build_parser()` internals (`_SubParsersAction.choices`, a private argparse attribute). This has been stable since Python 3.2, and the tests exercise it on every run.
- **Risk: setup edits user dotfiles.** Mitigations: only after an explicit prompt, only on a TTY, a skip variable, touching only lines with the marker, and printing the file path.
- **Risk: zsh without `compinit`.** The guard runs it. On oh-my-zsh and similar setups it's already loaded, so nothing changes.
- **Risk: the docs line goes stale when a command is added.** The drift test fails in CI.
- **Risk: running `python3 -m llmwiki` doesn't complete.** By design, only the `llmwiki` entry point completes. This is documented.
- **Windows / `setup.ps1`:** untouched, out of scope.

---

## 4. Testing Strategy

`tests/test_shell_completion.py`:

- `command_names()` equals the root subparser's choices. A spot check that `sync`, `synth` and `migrate` are present also guards against an empty result.
- `install_rc_line`: a missing file → created, `added`; an existing file with other content → content preserved byte for byte, one marker line; run twice → `unchanged`, still one line; a stale marker line with an old list → replaced, `updated`.
- **Real bash behavior:** run `bash -c` with the line sourced and `COMP_WORDS`/`COMP_CWORD` set, then check: `llmwiki sy` → `sync synth`; `llmwiki ` → all names; `llmwiki sync ` → no command names.
- **Real zsh behavior:** a smoke test that the line parses (`zsh -n`), skipped when zsh isn't installed.
- **Docs drift:** `completion_line("bash")` and `completion_line("zsh")` both appear verbatim in `docs/getting-started.md`.
- **`setup.sh` step:** run the new block with `HOME=<tmp>`, `SHELL=/bin/bash` and piped `y` input, forcing the TTY branch through a test-only hook or by factoring the step into a sourced function. Check the tmp `.bashrc`. Also check non-TTY → no change, and `LLMWIKI_SKIP_COMPLETION=1` → no change.

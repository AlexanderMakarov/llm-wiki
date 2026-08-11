# Windows setup

llmwiki ships Windows `.bat` files alongside the Unix shell scripts. Most things just work. This doc covers the Windows-specific gotchas.

## Prerequisites

- **Python ≥ 3.12** — install from [python.org](https://www.python.org/downloads/windows/) or the Microsoft Store. Make sure "Add Python to PATH" is checked.
- **Git** — install from [git-scm.com](https://git-scm.com/download/win).
- **Claude Code for Windows** — optional but recommended.

## Install

Open a fresh **Command Prompt** or **PowerShell** window after installing Python (to pick up the new PATH).

```cmd
git clone https://github.com/AlexanderMakarov/llm-wiki.git
cd llm-wiki
python -m venv .venv && .venv\Scripts\activate
setup.bat
```

If `setup.bat` says "python is required but was not found", close and re-open your terminal. If that doesn't fix it, your Python install didn't set PATH — reinstall with the PATH checkbox enabled.

> Like the Unix flow, your transcripts/wiki/site live in an external **vault**, not the clone. After `setup.bat`, follow [getting-started.md](getting-started.md#2-create-a-vault-and-point-configjson-at-it) to create a vault directory and point `config.json` `vault.default_path` at it.

## Running commands

Same as macOS / Linux, but with `.bat`:

```cmd
sync.bat
build.bat
```

Or run the Python module directly:

```cmd
python -m llmwiki sync
python -m llmwiki build
```

Note: on Windows the command is `python`, not `python3`. The `.bat` files use `python`.

## Paths

Windows paths use backslashes (`C:\Users\...`) but Claude Code on Windows stores sessions at a Unix-looking path:

```
C:\Users\<you>\.claude\projects\<project>\<uuid>.jsonl
```

llmwiki handles this automatically. You don't need to do anything.

## Redaction of Windows paths

The default redaction config covers `/Users/<you>/` and `/home/<you>/` (Unix), but not `C:\Users\<you>\`. Add this to your `config.json`:

```jsonc
{
  "redaction": {
    "real_username": "<YOUR_WINDOWS_USERNAME>",
    "extra_patterns": [
      "C:\\\\Users\\\\<YOUR_WINDOWS_USERNAME>\\\\[^\\\"]*",
      // ... (keep the defaults too)
    ]
  }
}
```

Replace `<YOUR_WINDOWS_USERNAME>` with your actual Windows username. Note the quadruple backslashes — JSON string escaping + regex escaping.

## Line endings

Git on Windows defaults to converting line endings (`core.autocrlf=true`). This is usually fine, but if you ever see weird markdown rendering, check with:

```cmd
git config core.autocrlf
```

Recommended setting for this repo:

```cmd
git config core.autocrlf input
```

## PowerShell execution policy

If PowerShell complains "cannot be loaded because running scripts is disabled on this system" when you try to run `setup.bat`, run this once as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Opening the site

The built site is plain files — nothing needs to be running.

```cmd
start site\index.html
```

## Known limitations

- **No SessionStart hook yet.** The hook syntax for Windows is different and the install.bat doesn't set it up automatically. You can still add it manually by editing `%USERPROFILE%\.claude\settings.json`.
- **No GPG signing setup.** llmwiki doesn't require signed commits for contributions, but if you want them on Windows, install Git for Windows with the GPG support option.
- **Emoji in terminal output** may render as boxes. This is a Windows terminal font issue — everything still works, it just looks odd.

## Getting help

If you hit a Windows-specific issue, open a [bug report](https://github.com/Pratiyush/llm-wiki/issues/new?template=bug_report.md) with the `windows` label.

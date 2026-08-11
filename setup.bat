@echo off
REM llmwiki — one-click installer for Windows.
REM Usage: setup.bat
REM Idempotent — safe to re-run.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==^> llmwiki setup
echo     root: %cd%

REM 1. Python check
where python >nul 2>&1
if errorlevel 1 (
  echo error: python is required but was not found in PATH
  exit /b 1
)
for /f "delims=" %%v in ('python -c "import sys; print(\".\".join(map(str, sys.version_info[:2])))"') do set PY_VER=%%v
echo     python: !PY_VER!

REM 2. Check for markdown
python -c "import markdown" 2>nul
if errorlevel 1 (
  echo ==^> installing python 'markdown' (required)
  python -m pip install --user --quiet markdown
)

REM 3. Syntax highlighting (v0.5): highlight.js loads from CDN at view time,
REM    so there is no longer an optional Python dep to install here.

REM 4. Scaffold raw/ wiki/ site/ — but only into a configured vault.
REM #29: never grow personal data (raw/ wiki/ site/) inside the git clone.
set "VAULT_PATH="
for /f "delims=" %%p in ('python -c "import json;from pathlib import Path;c=Path('config.json');print(((json.loads(c.read_text(encoding='utf-8')).get('vault') or {}).get('default_path') or '') if c.exists() else '')" 2^>nul') do set "VAULT_PATH=%%p"
if defined VAULT_PATH (
  echo ==^> scaffolding into vault: !VAULT_PATH!
  python -m llmwiki init
) else (
  echo.
  echo ==^> no vault configured ^(config.json vault.default_path is unset^).
  echo     Skipping scaffold so raw/ wiki/ site/ do NOT grow inside this git clone.
  echo     Create a vault, point config.json at it, then run: python -m llmwiki init
  echo     See docs\getting-started.md section 2.
)

REM 5. Show available adapters
python -m llmwiki adapters

REM 6. First sync (dry-run)
echo.
echo ==^> dry-run of first sync:
python -m llmwiki sync --dry-run

REM 7. Git hooks — ruff on pushed Python files only
git rev-parse --git-dir >nul 2>&1
if not errorlevel 1 (
  echo.
  echo ==^> wiring git hooks ^(.githooks^)
  git config core.hooksPath .githooks
) else (
  echo.
  echo     ^(not a git checkout — skipping hook wiring^)
)

echo.
echo ================================================================
echo   Setup complete.
echo ================================================================
echo.
echo Next steps:
echo   sync.bat                    ^-^- convert new sessions to markdown
echo   build.bat                   ^-^- generate the static HTML site
echo   start site\index.html       ^-^- browse the site ^-^- plain files, nothing to run

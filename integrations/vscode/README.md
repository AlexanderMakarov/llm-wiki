# llm-wiki VS Code Extension

A minimal VS Code extension that integrates with your local llm-wiki instance.

## Features

- **Open llm-wiki** -- opens the built site (`site/index.html`) in your browser
- **Sync Sessions** -- runs `python3 -m llmwiki sync` from the workspace root
- **Build Site** -- runs `python3 -m llmwiki build`
- **Wiki Pages sidebar** -- tree view of all wiki pages grouped by section (sources, entities, concepts, syntheses)

## Prerequisites

- An llm-wiki project in your VS Code workspace (must contain `wiki/index.md`)
- Python 3.12+ with `llmwiki` installed (`pip install -e .` from the repo root)

## Build & Install

```bash
cd integrations/vscode
npm install
npm run compile
```

To test in VS Code:

1. Open this folder in VS Code
2. Press F5 to launch the Extension Development Host
3. Open a workspace that contains an llm-wiki project

To package as a `.vsix`:

```bash
npx @vscode/vsce package
```

## Configuration

| Setting | Default | Description |
|---|---|---|
| `llmwiki.pythonPath` | `python3` | Path to the Python interpreter |

## Development

```bash
npm run watch    # recompile on save
npm run lint     # run eslint
```

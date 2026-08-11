#!/usr/bin/env bash
# Demo recording script for asciinema
# Simulates a user running the full llm-wiki workflow
# Usage: asciinema rec demo.cast --command "bash scripts/demo-record.sh" --cols 100 --rows 30

set -e
cd "$(dirname "$0")/.."

# Helper: type commands slowly for visual effect
type_cmd() {
    echo ""
    echo -n "$ "
    for (( i=0; i<${#1}; i++ )); do
        echo -n "${1:$i:1}"
        sleep 0.04
    done
    echo ""
    sleep 0.3
}

pause() { sleep "${1:-1.5}"; }

clear
echo "╔══════════════════════════════════════════════════════╗"
echo "║  llm-wiki — Turn AI coding sessions into a wiki     ║"
echo "║  github.com/Pratiyush/llm-wiki                      ║"
echo "╚══════════════════════════════════════════════════════╝"
pause 2

# 1. Version + adapters
type_cmd "llmwiki --version"
python3 -m llmwiki --version
pause

type_cmd "llmwiki adapters"
python3 -m llmwiki adapters
pause 2

# 2. Sync sessions
type_cmd "llmwiki sync --vault demo --dry-run"
python3 -m llmwiki sync --vault demo --dry-run
pause 2

# 3. Build the site
type_cmd "llmwiki build --vault demo"
python3 -m llmwiki build --vault demo 2>&1
pause 2

# 4. Show what was generated
type_cmd "ls demo/site/ | head -15"
ls demo/site/ | head -15
pause

type_cmd "echo \"Total HTML pages:\" && find demo/site -name '*.html' | wc -l"
echo "Total HTML pages:" && find demo/site -name '*.html' | wc -l
pause

# 5. Show exports
type_cmd "head -20 demo/site/llms.txt"
head -20 demo/site/llms.txt
pause 2

# 6. Show project breakdown
type_cmd "ls demo/raw/sessions/ | head -10"
ls demo/raw/sessions/ | head -10
pause

# 7. v1.1 — Preview API cost before synthesis (#50)
type_cmd "llmwiki synthesize --vault demo --estimate"
python3 -m llmwiki synthesize --vault demo --estimate 2>&1 | head -12
pause 2

# 8. v1.1 — List candidate pages awaiting human review (#51)
type_cmd "llmwiki candidates list --vault demo"
python3 -m llmwiki candidates list --vault demo 2>&1 || echo "  (no candidates pending)"
pause 2

# 9. Open the site
type_cmd "open demo/site/index.html"
echo "→ The built site is plain files under demo/site/"
pause 2

# 10. Wrap up
type_cmd "# Open demo/site/index.html to explore your wiki!"
echo "Features: heatmap, token stats, tool charts, model directory,"
echo "          search (Cmd+K), dark mode, AI exports (llms.txt, JSON-LD),"
echo "          interactive graph (Graph tab), candidates workflow,"
echo "          Ollama-ready synthesis pipeline."
pause 2

echo ""
echo "★ Star the repo: github.com/Pratiyush/llm-wiki"
echo "★ Live demo: pratiyush.github.io/llm-wiki"
pause 2

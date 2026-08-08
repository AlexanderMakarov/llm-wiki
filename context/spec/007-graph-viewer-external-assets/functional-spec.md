# Functional Specification: External graph viewer assets for the static site

- **Roadmap Item:** GitHub Issue #127 — move the Knowledge Graph viewer script out of the page itself; expanded here to also ship the canvas library with the site so the graph works offline
- **Status:** Approved
- **Author:** Auto (implement-feature run for #127)

---

## 1. Overview and Rationale (The "Why")

People browse their wiki Knowledge Graph as part of the built static site — including by opening pages from disk. Today the graph page carries a large block of page-specific script inside every copy of that page, which makes the page heavier and ties every new graph feature to growing that one page. Separately, the drawing library is fetched from the public internet, so a fully offline or disk-opened visit often shows an empty canvas with a failure notice.

This change makes the graph page load its own script and drawing library as ordinary companion files next to the page. Readers get the same graph experience as today, whether they open the built files from disk or through a plain web host, including with no network. Success: the graph still searches, filters, clusters, and navigates as before; it no longer depends on an in-page script bloat pattern or an online-only library load for everyday static use.

---

## 2. Functional Requirements (The "What")

- **FR1 — Same Knowledge Graph experience**
  As a wiki reader, when I open the Knowledge Graph page after this change, I still see and use the same controls and behaviors I had before (search, layout density, cluster toggle, side panel, context actions, theme via the site nav).
  - **Acceptance Criteria:**
    - [ ] Given a built site with a non-empty wiki, when I open the Knowledge Graph page, then the graph canvas, legend, stats, and header controls all appear and work as they did immediately before this change.
    - [ ] Given I use search, layout density, clustering, and a node’s context actions, when I compare to the previous behavior, then results and available actions match (no new controls required; none removed).

- **FR2 — Works when opening built files from disk**
  As a reader, I can open the built Knowledge Graph HTML from disk (double-click / file open) and still use the graph without a local app server.
  - **Acceptance Criteria:**
    - [ ] Given a freshly built site on disk and no product local server, when I open the Knowledge Graph HTML file from the filesystem, then the graph draws and interactive controls respond.
    - [ ] Given that same disk open with network disabled, when the page finishes loading, then the graph still draws (no reliance on downloading the canvas library from the public internet).

- **FR3 — Works when opening the same built files over a plain web host**
  As a reader, when I open the same built files through any ordinary static host or simple file server (not the product’s edit/API server), the graph works the same way.
  - **Acceptance Criteria:**
    - [ ] Given the built site served only as static files over HTTP, when I open the Knowledge Graph page, then behavior matches the disk-open case for drawing and controls.

- **FR4 — Both build paths produce a working graph page**
  As a maintainer, when I regenerate the graph alone or rebuild the whole site, the Knowledge Graph page and its companion assets are both produced and usable.
  - **Acceptance Criteria:**
    - [ ] Given I run the standalone graph command, when it finishes, then opening its Knowledge Graph HTML (from disk) shows a working graph.
    - [ ] Given I run a full site build, when it finishes, then the site’s Knowledge Graph page shows a working graph with the same companion assets available beside it.

- **FR5 — Contributor guardrail on graph viewer growth**
  As a contributor, I am stopped from quietly ballooning the graph viewer’s main script without a deliberate decision.
  - **Acceptance Criteria:**
    - [ ] Given the automatic tests for the graph viewer, when the extracted viewer script exceeds the agreed size budget, then the test suite fails with a message that points contributors to externalize or trim rather than silently raising the ceiling without discussion.

- **FR6 — Release notes**
  The unreleased changelog records the user-visible effect (static/offline graph assets).
  - **Acceptance Criteria:**
    - [ ] Given the project’s unreleased changelog section, when this work lands, then there is an entry describing that the Knowledge Graph loads from companion assets and works offline from the built site.

---

## 3. Scope and Boundaries

### In-Scope

- External companion script for the Knowledge Graph viewer (no behavior change)
- Shipping the canvas drawing library next to the page so disk open and offline use work
- Standalone graph generation and full site build both emit the needed files
- Automated size guardrail on the extracted viewer script
- Changelog entry under Unreleased

### Out-of-Scope

- Changes to how the product local server’s APIs or edit features work (static site only)
- Redesign of the Knowledge Graph UI or new graph analytics features
- Vendoring or changing other CDN scripts on the rest of the site (for example syntax highlighting)
- Other roadmap items and open issues unrelated to #127

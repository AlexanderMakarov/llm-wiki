# `llmwiki add` CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `llmwiki add <url|file|folder>...` converts sources to Markdown, writes them to `raw/docs/` in kbbuilder-compatible layout, then batch-synthesizes and rebuilds the site.

**Architecture:** Three new modules — `llmwiki/slugs.py` (shared title/slug derivation, fixes kbbuilder#7 cases), `llmwiki/htmlmd.py` (stdlib HTML→Markdown fallback), `llmwiki/add_doc.py` (SSRF-guarded fetch, 3-layer URL pipeline, file/folder conversion, section chunker, raw-doc writer, batch orchestrator) — plus `cmd_add` wiring in `cli.py`. Post-steps reuse the existing `synthesize_new_sessions` and `build_site` entry points in-process.

**Tech Stack:** Python stdlib only for required paths (`urllib.request`, `html.parser`, `ipaddress`, `unicodedata`). Optional: `trafilatura` + `markitdown` (new `[add]` extra), `playwright` (existing `[e2e]` extra) — all import-guarded.

**Spec:** `docs/superpowers/specs/2026-07-04-llmwiki-add-design.md` (approved). Read it before starting a task.

## Global Constraints

- Python floor: `requires-python >=3.9` — no `match`, no `X | Y` in annotations at runtime (use `from __future__ import annotations`), no 3.10+ stdlib APIs.
- Ruff: line-length 120, rules `E,F,I,B,UP` (E501/E402 ignored). Run `ruff check llmwiki tests` before each commit.
- Tests MUST be offline: no network, no LLM, no playwright. All I/O seams injectable.
- Run tests with `env -u LLMWIKI_ROOT python3 -m pytest ...` — a set `LLMWIKI_ROOT` breaks the suite on this machine.
- NEVER resurrect a `[pdf]` extra in pyproject — deliberately pruned. The new extra is named `add`.
- `raw/` is immutable: the writer must never overwrite an existing file — suffix `-2`, `-3`, … on the doc slug.
- Frontmatter must be byte-compatible with kbbuilder `makeRawDocWriter` (`src/wiki-worker.ts:91-100`): keys in order `title, slug, project, type, tags, date, source`; `title`/`source` JSON-quoted; tags inline list starting `[wiki-add, raw-doc`.
- Commit messages: conventional style (`feat(add): ...`), NO `Claude-Session:`/claude.ai link lines, no `Co-Authored-By`.
- House style: module docstring with issue ref, lazy imports inside `cmd_*` functions, `print(..., file=sys.stderr)` + return `2` for usage errors, `1` for runtime failures.

---

### Task 1: `llmwiki/slugs.py` — shared title/slug derivation

**Files:**
- Create: `llmwiki/slugs.py`
- Test: `tests/test_slugs.py`

**Interfaces:**
- Produces (used by Tasks 6–8):
  - `slugify(text: str, max_len: int = 80) -> str` — kebab ASCII slug, `""` when nothing survives.
  - `strip_site_suffix(title: str) -> str` — drops one trailing `" - Site"`/`" | Site"`/`" — Site"` segment; collapses `"X - X"` to `"X"`.
  - `first_heading(markdown: str) -> str` — first `#`–`######` heading text, fence-aware, `""` if none.
  - `title_from_url(url: str) -> str` — last meaningful path segment (dashes→spaces), else hostname.
  - `derive_title(*, explicit: str | None, markdown: str, html_title: str | None, url: str | None, path_name: str | None) -> str` — preference chain from the spec; never returns `""` for a non-empty input.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for llmwiki.slugs — shared slug/title derivation (issue #16, kbbuilder#7)."""

from __future__ import annotations

from llmwiki.slugs import (
    derive_title,
    first_heading,
    slugify,
    strip_site_suffix,
    title_from_url,
)


# ── slugify ──────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_accents_folded():
    assert slugify("Café Über naïve") == "cafe-uber-naive"


def test_slugify_cyrillic_transliterated():
    # kbbuilder#7: "Получение или замена биометрического загранпаспорта"
    # must NOT collapse to '' (the old literal-'document' failure).
    s = slugify("Получение загранпаспорта РФ в Армении")
    assert s == "poluchenie-zagranpasporta-rf-v-armenii"


def test_slugify_empty_returns_empty():
    # Caller falls to the next title candidate — slugify never invents 'document'.
    assert slugify("†‡•") == ""


def test_slugify_caps_at_80_chars_no_trailing_dash():
    s = slugify("word " * 40)
    assert len(s) <= 80
    assert not s.endswith("-")


def test_slugify_output_is_site_safe():
    # raw_docs_site._SAFE_SEG_RE requires ^[A-Za-z0-9._-]+$ — anything else
    # is silently invisible to the site build.
    import re
    s = slugify("Weird 「title」 withّ marks — and stuff")
    assert re.fullmatch(r"[a-z0-9-]+", s)


# ── strip_site_suffix ────────────────────────────────────────────────

def test_strip_site_suffix_dash():
    assert strip_site_suffix("Getting Started - MyLib Docs") == "Getting Started"


def test_strip_site_suffix_pipe():
    assert strip_site_suffix("Pricing | Acme") == "Pricing"


def test_strip_site_suffix_emdash():
    assert strip_site_suffix("Guide — ReadTheDocs") == "Guide"


def test_strip_site_suffix_repeated_word_collapses():
    # kbbuilder#7: docs.openclaw.ai titles itself "OpenClaw - OpenClaw".
    assert strip_site_suffix("OpenClaw - OpenClaw") == "OpenClaw"


def test_strip_site_suffix_no_separator_untouched():
    assert strip_site_suffix("Plain Title") == "Plain Title"


def test_strip_site_suffix_keeps_head_when_tail_longer():
    # Don't strip when the "suffix" is the real content.
    assert strip_site_suffix("FAQ - Frequently Asked Questions about Billing") \
        == "FAQ - Frequently Asked Questions about Billing"


# ── first_heading ────────────────────────────────────────────────────

def test_first_heading_simple():
    assert first_heading("intro\n\n# Real Title\n\nbody") == "Real Title"


def test_first_heading_skips_fenced_hash():
    md = "```sh\n# not a heading\n```\n\n## Actual\n"
    assert first_heading(md) == "Actual"


def test_first_heading_none():
    assert first_heading("no headings here") == ""


# ── title_from_url ───────────────────────────────────────────────────

def test_title_from_url_path_segment():
    assert title_from_url("https://ex.com/docs/getting-started.html") == "getting started"


def test_title_from_url_skips_index():
    assert title_from_url("https://ex.com/guide/index.html") == "guide"


def test_title_from_url_host_fallback():
    assert title_from_url("https://docs.openclaw.ai/") == "docs.openclaw.ai"


# ── derive_title ─────────────────────────────────────────────────────

def test_derive_title_prefers_explicit():
    assert derive_title(explicit="My Title", markdown="# Other", html_title="X",
                        url="https://e.com/a", path_name=None) == "My Title"


def test_derive_title_markdown_heading_beats_html_title():
    assert derive_title(explicit=None, markdown="# From Heading",
                        html_title="From <title> - Site", url="https://e.com/a",
                        path_name=None) == "From Heading"


def test_derive_title_html_title_suffix_stripped():
    assert derive_title(explicit=None, markdown="no headings",
                        html_title="Page - SiteName", url="https://e.com/a",
                        path_name=None) == "Page"


def test_derive_title_boilerplate_heading_falls_to_url():
    # kbbuilder#7: 'Source: External' boilerplate must not win over URL segments.
    t = derive_title(explicit=None, markdown="# Source: External\n\nbody",
                     html_title=None, url="https://ex.com/real-doc-name", path_name=None)
    assert t == "real doc name"


def test_derive_title_path_name():
    assert derive_title(explicit=None, markdown="", html_title=None, url=None,
                        path_name="notes.txt") == "notes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_slugs.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'llmwiki.slugs'`

- [ ] **Step 3: Implement `llmwiki/slugs.py`**

```python
"""Shared slug + title derivation for added documents (issue #16).

Canonical implementation of the slug rules that kbbuilder's async
add-doc worker (kbbuilder#7) converges on: prefer real content headings,
strip site-name suffixes, transliterate Cyrillic instead of collapsing
to a junk fallback, and emit only site-safe ASCII
(subset of raw_docs_site._SAFE_SEG_RE).
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Russian → Latin. Enough for the observed failure case (kbbuilder#7:
# Russian document titles slugging to ''); other scripts fall through
# NFKD folding and, if nothing survives, the caller's next candidate.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_BOILERPLATE_HEADINGS = frozenset({"source: external", "document", "untitled", "home"})

# "X - Site", "X | Site", "X — Site" (spaces required so hyphenated words survive)
_SUFFIX_SEP = re.compile(r"\s+[-|—–]\s+")

_INDEXISH = frozenset({"index", "index.html", "index.htm", "index.php", "default.aspx"})


def slugify(text: str, max_len: int = 80) -> str:
    """Kebab-case ASCII slug. Returns '' when nothing survives —
    callers fall to their next title candidate, never a junk literal."""
    s = text.lower()
    s = "".join(_CYRILLIC.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def strip_site_suffix(title: str) -> str:
    """Drop one trailing site-name segment ("X - Site" → "X"); collapse
    exact repeats ("OpenClaw - OpenClaw" → "OpenClaw")."""
    parts = _SUFFIX_SEP.split(title)
    if len(parts) < 2:
        return title.strip()
    head, tail = " - ".join(parts[:-1]).strip(), parts[-1].strip()
    if head.lower() == tail.lower():
        return head
    # Only strip when the tail looks like a short site name, not content.
    if tail and len(tail) <= len(head):
        return head
    return title.strip()


def first_heading(markdown: str) -> str:
    """First markdown heading, skipping '#' lines inside code fences."""
    fence = None
    for line in markdown.split("\n"):
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is not None:
            continue
        h = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if h:
            return h.group(1).strip()
    return ""


def title_from_url(url: str) -> str:
    """Last meaningful URL path segment (dashes/underscores → spaces),
    else the hostname."""
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s and s.lower() not in _INDEXISH]
    for seg in reversed(segments):
        seg = re.sub(r"\.[a-z0-9]{1,5}$", "", seg, flags=re.IGNORECASE)  # drop extension
        cleaned = seg.replace("-", " ").replace("_", " ").strip()
        if cleaned and not cleaned.isdigit():
            return cleaned
    return parsed.hostname or url


def derive_title(
    *,
    explicit: "str | None",
    markdown: str,
    html_title: "str | None",
    url: "str | None",
    path_name: "str | None",
) -> str:
    """Spec preference chain: --title → first real MD heading → cleaned
    HTML <title> → URL path segments → filename stem → hostname."""
    if explicit and explicit.strip():
        return explicit.strip()
    heading = first_heading(markdown)
    if heading and heading.lower() not in _BOILERPLATE_HEADINGS and slugify(heading):
        return heading
    if html_title:
        cleaned = strip_site_suffix(html_title)
        if cleaned and slugify(cleaned):
            return cleaned
    if url:
        t = title_from_url(url)
        if t and slugify(t):
            return t
    if path_name:
        stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", path_name)
        if stem:
            return stem
    # Absolute last resort — heading/html_title even if boilerplate, then raw input.
    return heading or (html_title or "").strip() or (url or path_name or "").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_slugs.py -q`
Expected: all PASS. Also run `ruff check llmwiki/slugs.py tests/test_slugs.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/slugs.py tests/test_slugs.py
git commit -m "feat(add): shared slug/title derivation module (#16, kbbuilder#7 cases)"
```

---

### Task 2: `llmwiki/htmlmd.py` — stdlib HTML→Markdown fallback

**Files:**
- Create: `llmwiki/htmlmd.py`
- Test: `tests/test_htmlmd.py`

**Interfaces:**
- Produces (used by Task 6): `html_to_markdown(html: str) -> tuple[str, str]` — `(title, markdown)`. Title is the raw `<title>` text (`""` if absent) — suffix-stripping happens in `slugs.derive_title`, not here.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for llmwiki.htmlmd — stdlib HTML→Markdown converter (issue #16)."""

from __future__ import annotations

from llmwiki.htmlmd import html_to_markdown

PAGE = """<!doctype html>
<html><head><title>Sample Page - ExampleSite</title>
<style>body { color: red }</style>
<script>alert("nope")</script>
</head><body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<header><h1>Site Banner</h1></header>
<article>
  <h1>Real Article Title</h1>
  <p>First paragraph with <strong>bold</strong> and <em>italic</em> and
     an <a href="https://ex.com/link">anchor</a>.</p>
  <h2>Section &amp; Details</h2>
  <ul><li>alpha</li><li>beta</li></ul>
  <ol><li>one</li><li>two</li></ol>
  <pre><code>x = 1
y = 2</code></pre>
  <p>Inline <code>code()</code> too.</p>
</article>
<footer>© 2026 Example</footer>
</body></html>"""


def test_title_extracted():
    title, _ = html_to_markdown(PAGE)
    assert title == "Sample Page - ExampleSite"


def test_article_preferred_over_chrome():
    _, md = html_to_markdown(PAGE)
    assert "Real Article Title" in md
    assert "Site Banner" not in md      # <header> outside article dropped
    assert "About" not in md            # nav dropped
    assert "© 2026" not in md           # footer dropped
    assert "alert(" not in md           # script dropped
    assert "color: red" not in md       # style dropped


def test_block_conversions():
    _, md = html_to_markdown(PAGE)
    assert "# Real Article Title" in md
    assert "## Section & Details" in md          # entity decoded
    assert "- alpha" in md and "- beta" in md
    assert "1. one" in md and "2. two" in md
    assert "[anchor](https://ex.com/link)" in md
    assert "**bold**" in md and "*italic*" in md
    assert "`code()`" in md
    assert "```\nx = 1\ny = 2\n```" in md


def test_no_article_falls_back_to_body():
    html = "<html><head><title>T</title></head><body><p>hello world</p></body></html>"
    _, md = html_to_markdown(html)
    assert "hello world" in md


def test_whitespace_collapsed():
    _, md = html_to_markdown(PAGE)
    assert "\n\n\n" not in md
    assert not md.startswith("\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_htmlmd.py -q`
Expected: `ModuleNotFoundError: No module named 'llmwiki.htmlmd'`

- [ ] **Step 3: Implement `llmwiki/htmlmd.py`**

```python
"""Stdlib HTML → Markdown converter (issue #16).

Zero-dependency floor of the `llmwiki add` URL pipeline. trafilatura
(the `[add]` extra — also pullmd's base extraction library) supersedes
this when installed; this converter keeps a bare install functional.

Readability-lite: when the page has an <article> or <main> subtree,
only content inside it is emitted; site chrome (nav/header/footer/
aside) and non-content (script/style/template/noscript/svg) are always
dropped.
"""

from __future__ import annotations

from html.parser import HTMLParser

_SKIP = {"script", "style", "template", "noscript", "svg", "iframe",
         "nav", "header", "footer", "aside", "form", "button"}
_CONTENT_ROOTS = ("article", "main")
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_PARA_BREAK = {"p", "div", "section", "table", "tr", "blockquote", "figure"}


class _MdBuilder(HTMLParser):
    """Event-driven converter. convert_charrefs=True (default) makes
    handle_data receive already-unescaped text."""

    def __init__(self, content_root: "str | None"):
        super().__init__()
        self.content_root = content_root
        self.in_content = content_root is None
        self._content_depth = 0
        self.out: list[str] = []
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._pre_depth = 0
        self._list_stack: list["int | None"] = []  # None=ul, int=next ol number
        self._href: "str | None" = None
        self._link_text: list[str] = []

    # ── tag handling ────────────────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
            return
        if tag in _SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if self.content_root and tag == self.content_root:
            self.in_content = True
            self._content_depth += 1
            return
        if not self.in_content:
            return
        if tag in _HEADINGS:
            self.out.append("\n\n" + "#" * _HEADINGS[tag] + " ")
        elif tag == "pre":
            self._pre_depth += 1
            self.out.append("\n\n```\n")
        elif tag == "code":
            if not self._pre_depth:
                self.out.append("`")
        elif tag in ("ul", "ol"):
            self._list_stack.append(1 if tag == "ol" else None)
            self.out.append("\n")
        elif tag == "li":
            marker = "- "
            if self._list_stack and self._list_stack[-1] is not None:
                marker = f"{self._list_stack[-1]}. "
                self._list_stack[-1] += 1
            self.out.append("\n" + marker)
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._link_text = []
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "br":
            self.out.append("\n")
        elif tag in _PARA_BREAK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            return
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if self.content_root and tag == self.content_root:
            self._content_depth -= 1
            if self._content_depth <= 0:
                self.in_content = False
            return
        if not self.in_content:
            return
        if tag in _HEADINGS or tag in _PARA_BREAK or tag == "li":
            self.out.append("\n")
        elif tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            self.out.append("\n```\n\n")
        elif tag == "code":
            if not self._pre_depth:
                self.out.append("`")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self.out.append("\n")
        elif tag == "a":
            text = "".join(self._link_text).strip()
            if self._href and text:
                self.out.append(f"[{text}]({self._href})")
            elif text:
                self.out.append(text)
            self._href = None
            self._link_text = []
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")

    # ── text ────────────────────────────────────────────────────────
    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._skip_depth or not self.in_content:
            return
        if self._href is not None:
            self._link_text.append(data)
            return
        if self._pre_depth:
            self.out.append(data)
        else:
            self.out.append(" ".join(data.split()) and " ".join(data.split()) or "")
            # keep single spaces between inline fragments
            if data and data[-1].isspace():
                self.out.append(" ")


def html_to_markdown(html: str) -> "tuple[str, str]":
    """Convert HTML to (title, markdown). Prefers an <article>/<main>
    subtree when one exists; otherwise converts the whole body."""
    lower = html.lower()
    root = next((r for r in _CONTENT_ROOTS if f"<{r}" in lower), None)
    builder = _MdBuilder(root)
    builder.feed(html)
    raw = "".join(builder.out)
    lines = [ln.rstrip() for ln in raw.split("\n")]
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return builder.title.strip(), text.strip()
```

- [ ] **Step 4: Run tests, iterate until green**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_htmlmd.py -q`
Expected: all PASS. (Inline-whitespace joining is the usual trouble spot — fix `handle_data` spacing if `**bold**` assertions fail, but keep tests as written; they encode the required output.)
Then `ruff check llmwiki/htmlmd.py tests/test_htmlmd.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/htmlmd.py tests/test_htmlmd.py
git commit -m "feat(add): stdlib HTML-to-Markdown fallback converter (#16)"
```

---

### Task 3: `add_doc.py` part 1 — SSRF guard + guarded fetch

**Files:**
- Create: `llmwiki/add_doc.py`
- Test: `tests/test_add_doc.py` (new file; later tasks append to it)

**Interfaces:**
- Produces (used by Tasks 6–8):
  - `class FetchResult` (dataclass): `url: str`, `status: int`, `content_type: str`, `headers: dict[str, str]`, `body: str`.
  - `assert_public_url(url: str) -> None` — raises `AddError` on non-http(s) schemes or any address resolving non-globally.
  - `guarded_fetch(url: str, headers: dict[str, str], timeout: int = 30) -> FetchResult` — manual redirects ≤5 hops, re-validating each hop.
  - `class AddError(Exception)` — single user-facing error type for the module.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests** (create `tests/test_add_doc.py`)

```python
"""Tests for llmwiki.add_doc — llmwiki add pipeline (issue #16). Offline only."""

from __future__ import annotations

import pytest

from llmwiki.add_doc import AddError, assert_public_url


# ── SSRF guard (port of kbbuilder wiki-convert.ts assertPublicUrl) ──

@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "gopher://example.com",
])
def test_blocked_schemes(url):
    with pytest.raises(AddError, match="scheme"):
        assert_public_url(url)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://10.1.2.3/x",
    "http://192.168.1.1/x",
    "http://172.16.0.1/x",
    "http://169.254.169.254/latest/meta-data",   # cloud metadata
    "http://100.64.0.1/x",                        # CGNAT / tailnet
    "http://0.0.0.0/x",
    "http://[::1]/x",
    "http://[::ffff:127.0.0.1]/x",                # v4-mapped loopback
    "http://[64:ff9b::7f00:1]/x",                 # NAT64 loopback
    "http://[fe80::1]/x",
    "http://[fd00::1]/x",                          # unique-local
])
def test_blocked_addresses(url):
    with pytest.raises(AddError, match="non-public|resolve"):
        assert_public_url(url)


def test_public_ip_literal_allowed():
    assert_public_url("https://1.1.1.1/")  # must not raise


def test_invalid_url_rejected():
    with pytest.raises(AddError):
        assert_public_url("not a url at all")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: `ModuleNotFoundError: No module named 'llmwiki.add_doc'`

- [ ] **Step 3: Implement the guard + fetch in `llmwiki/add_doc.py`**

```python
"""`llmwiki add` — universal document intake (issue #16).

Converts URLs / files / folders to Markdown and lands them under
raw/docs/ in the exact layout kbbuilder's async add-doc worker
produces (dir per doc, section-aware chunks), so a machine running
both never sees format drift. Spec:
docs/superpowers/specs/2026-07-04-llmwiki-add-design.md

Security posture ported from kbbuilder src/wiki-convert.ts: SSRF
egress guard (scheme + every resolved address + every redirect hop)
and a sensitive-path denylist for local reads.
"""

from __future__ import annotations

import ipaddress
import re as _re  # aliased: `re` is shadowed by hot loop locals in later sections
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin


class AddError(Exception):
    """User-facing failure adding one source (bad URL, blocked address,
    unreadable path, missing optional converter)."""


# ── SSRF egress guard ────────────────────────────────────────────────
# `llmwiki add <url>` fetches from the local machine; kbbuilder may
# later shell out to it with queue-supplied URLs, so an internal URL
# could reach cloud metadata (169.254.169.254), localhost services, or
# tailnet hosts (100.64/10). Validate scheme + every resolved address,
# and re-validate across redirect hops.

# NAT64 well-known prefix — embedded IPv4 must itself be public.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _is_blocked(addr: "ipaddress.IPv4Address | ipaddress.IPv6Address") -> bool:
    if isinstance(addr, ipaddress.IPv6Address):
        mapped = addr.ipv4_mapped
        if mapped is not None:
            return _is_blocked(mapped)
        if addr in _NAT64:
            embedded = ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
            return _is_blocked(embedded)
    # is_global is False for private/loopback/link-local/CGNAT(100.64/10)/
    # unique-local/unspecified/reserved; multicast is excluded explicitly
    # for older Pythons where ff00::/8 slips through is_global.
    return not addr.is_global or addr.is_multicast


def assert_public_url(raw: str) -> None:
    """Raise AddError unless `raw` is an http(s) URL whose host resolves
    only to public addresses."""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise AddError(f"blocked URL scheme {parsed.scheme!r} (only http/https allowed): {raw}")
    host = parsed.hostname
    if not host:
        raise AddError(f"invalid URL: {raw}")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise AddError(f"could not resolve host {host}: {exc}") from exc
    if not infos:
        raise AddError(f"could not resolve host: {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked(ip):
            raise AddError(f"refusing to fetch non-public address {ip} for host {host}")


@dataclass
class FetchResult:
    url: str                    # final URL after redirects
    status: int
    content_type: str
    headers: "dict[str, str]" = field(default_factory=dict)
    body: str = ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None  # surface 3xx as HTTPError so we can re-validate the hop


_OPENER = urllib.request.build_opener(_NoRedirect)


def guarded_fetch(url: str, headers: "dict[str, str]", timeout: int = 30) -> FetchResult:
    """Fetch with manual redirect handling (≤5 hops), re-validating every
    hop against the SSRF guard. Returns non-2xx statuses as FetchResult
    (callers decide on retries) rather than raising."""
    current = url
    for _hop in range(5):
        assert_public_url(current)
        req = urllib.request.Request(current, headers=headers)
        try:
            resp = _OPENER.open(req, timeout=timeout)
        except urllib.error.HTTPError as err:
            if err.code in (301, 302, 303, 307, 308):
                loc = err.headers.get("Location")
                if not loc:
                    raise AddError(f"redirect ({err.code}) without Location from {current}") from err
                current = urljoin(current, loc)
                continue
            body = err.read().decode("utf-8", errors="replace") if err.fp else ""
            return FetchResult(url=current, status=err.code,
                               content_type=err.headers.get("Content-Type", ""),
                               headers=dict(err.headers.items()), body=body)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise AddError(f"fetch failed for {current}: {exc}") from exc
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return FetchResult(url=current, status=resp.status,
                           content_type=ctype, headers=dict(resp.headers.items()),
                           body=raw.decode(charset, errors="replace"))
    raise AddError(f"too many redirects fetching {url}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: all PASS (guard tests resolve only IP literals — no real DNS/network; the hostname-based case is `1.1.1.1` which getaddrinfo answers locally).
`ruff check llmwiki/add_doc.py tests/test_add_doc.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/add_doc.py tests/test_add_doc.py
git commit -m "feat(add): SSRF-guarded fetcher with redirect revalidation (#16)"
```

---

### Task 4: `add_doc.py` part 2 — section-aware chunker

**Files:**
- Modify: `llmwiki/add_doc.py` (append)
- Test: `tests/test_add_doc.py` (append)

**Interfaces:**
- Produces (used by Task 7):
  - `class MarkdownChunk` (dataclass): `index: int` (1-based), `total: int`, `heading: str`, `body: str` (newline-terminated).
  - `chunk_markdown_by_sections(markdown: str, max_chars: int = 7000, heading_levels: tuple[int, ...] = (1, 2)) -> list[MarkdownChunk]`
  - Module constant `DEFAULT_CHUNK_MAX_CHARS = 7000`.
- Consumes: nothing new.

- [ ] **Step 1: Append failing tests to `tests/test_add_doc.py`**

```python
# ── section chunker (port of kbbuilder chunkMarkdownBySections) ──────

from llmwiki.add_doc import DEFAULT_CHUNK_MAX_CHARS, chunk_markdown_by_sections


def test_chunk_small_doc_single_chunk():
    chunks = chunk_markdown_by_sections("# T\n\nshort body\n")
    assert len(chunks) == 1
    assert chunks[0].index == 1 and chunks[0].total == 1
    assert chunks[0].heading == "T"
    assert chunks[0].body.endswith("\n")


def test_chunk_splits_on_headings_not_hard_chars():
    # Two ~600-char sections with max_chars=1000: must split at the
    # heading boundary (section-aware), not at char 1000.
    sec = "## S{n}\n\n" + "x" * 590 + "\n\n"
    md = sec.replace("{n}", "1") + sec.replace("{n}", "2")
    chunks = chunk_markdown_by_sections(md, max_chars=1000)
    assert len(chunks) == 2
    assert chunks[0].body.startswith("## S1")
    assert chunks[1].body.startswith("## S2")
    assert chunks[0].heading == "S1" and chunks[1].heading == "S2"


def test_chunk_packs_sections_greedily():
    md = "".join(f"## S{i}\n\ntext {i}\n\n" for i in range(6))
    chunks = chunk_markdown_by_sections(md, max_chars=10_000)
    assert len(chunks) == 1  # all six fit in one budget


def test_chunk_fence_aware():
    md = "## Real\n\n```sh\n# comment not heading\n" + "y" * 300 + "\n```\n\n## Next\n\nz\n"
    chunks = chunk_markdown_by_sections(md, max_chars=250)
    # The fenced '# comment' must never start a chunk.
    assert all(not c.body.startswith("# comment") for c in chunks)


def test_chunk_oversized_section_paragraph_split():
    md = "## Big\n\n" + "\n\n".join("para " + "w" * 80 for _ in range(10))
    chunks = chunk_markdown_by_sections(md, max_chars=300)
    assert len(chunks) > 1
    assert all(len(c.body) <= 300 + 1 for c in chunks)


def test_chunk_indices_and_total():
    md = "".join(f"# H{i}\n\n" + "b" * 500 + "\n\n" for i in range(4))
    chunks = chunk_markdown_by_sections(md, max_chars=600)
    assert [c.index for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(c.total == len(chunks) for c in chunks)


def test_default_cap_is_7000():
    # 7000 keeps each chunk inside the agent-delegate synthesizer's
    # raw_body[:8000] prompt embed with frontmatter+breadcrumb headroom.
    assert DEFAULT_CHUNK_MAX_CHARS == 7000
```

- [ ] **Step 2: Run to verify failure**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: `ImportError: cannot import name 'chunk_markdown_by_sections'`

- [ ] **Step 3: Append the chunker to `llmwiki/add_doc.py`**

```python
# ── section chunking (port of kbbuilder chunkMarkdownBySections) ─────
# Synthesis distills ONE input file into ONE wiki page per pass. A large
# document overflows the model context in that single pass, so we split
# by section at WRITE time — each chunk becomes one synthesis input that
# fits. 7000 chars keeps a chunk inside the agent-delegate synthesizer's
# raw_body[:8000] prompt embed (llmwiki/synth/agent_delegate.py) with
# headroom for frontmatter + breadcrumb. The cap is soft: splits happen
# at heading, then paragraph boundaries; a hard slice only ever hits a
# single paragraph longer than the whole budget.

DEFAULT_CHUNK_MAX_CHARS = 7000

_FENCE_RE = _re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass
class MarkdownChunk:
    index: int          # 1-based position within the document
    total: int
    heading: str        # first heading inside the chunk ('' if none)
    body: str           # verbatim slice, newline-terminated


def _first_heading_line(body: str) -> str:
    fence = None
    for line in body.split("\n"):
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is not None:
            continue
        h = _re.match(r"^#{1,6}\s+(.*)$", line.lstrip())
        if h:
            return h.group(1).strip()
    return ""


def _split_sections(text: str, levels: "tuple[int, ...]") -> "list[str]":
    lines = text.split("\n")
    sections: "list[str]" = []
    buf: "list[str]" = []
    fence = None
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
        h = _re.match(r"^(#{1,6})\s", line)
        if fence is None and h and len(h.group(1)) in levels and buf:
            sections.append("\n".join(buf) + "\n")
            buf = []
        buf.append(line)
    if buf:
        sections.append("\n".join(buf) + "\n")
    return sections


def _split_oversized(section: str, max_chars: int) -> "list[str]":
    paras = _re.split(r"\n{2,}", section)
    out: "list[str]" = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            out.append(cur.rstrip("\n") + "\n")
        cur = ""

    for p in paras:
        if len(p) > max_chars:
            flush()
            for i in range(0, len(p), max_chars):
                piece = p[i:i + max_chars].strip()
                if piece:
                    out.append(piece + "\n")
            continue
        if cur and len(cur) + len(p) + 2 > max_chars:
            flush()
        cur += ("\n\n" if cur else "") + p
    flush()
    return out


def chunk_markdown_by_sections(
    markdown: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    heading_levels: "tuple[int, ...]" = (1, 2),
) -> "list[MarkdownChunk]":
    """Split a Markdown document into section-aligned chunks ≤ max_chars.
    Sections pack greedily; an oversized section splits on blank-line
    paragraph boundaries, hard-slicing only as a last resort. Heading
    detection is fence-aware. A document within budget returns whole."""
    text = markdown.replace("\r\n", "\n")
    sections = _split_sections(text, heading_levels)
    bodies: "list[str]" = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            bodies.append(cur.rstrip("\n") + "\n")
        cur = ""

    for sec in sections:
        if len(sec) > max_chars:
            flush()
            bodies.extend(_split_oversized(sec, max_chars))
            continue
        if cur and len(cur) + len(sec) > max_chars:
            flush()
        cur += sec
    flush()

    if not bodies:
        body = text.strip()
        if not body:
            return []
        return [MarkdownChunk(1, 1, _first_heading_line(body), body + "\n")]
    total = len(bodies)
    return [MarkdownChunk(i + 1, total, _first_heading_line(b), b) for i, b in enumerate(bodies)]
```

(Note: `dataclass` is already imported at the top of the module from Task 3.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: all PASS. `ruff check llmwiki/add_doc.py` — clean (`_re` was already imported at the top in Task 3).

- [ ] **Step 5: Commit**

```bash
git add llmwiki/add_doc.py tests/test_add_doc.py
git commit -m "feat(add): section-aware markdown chunker, kbbuilder parity (#16)"
```

---

### Task 5: `add_doc.py` part 3 — file/folder conversion + path safety

**Files:**
- Modify: `llmwiki/add_doc.py` (append)
- Test: `tests/test_add_doc.py` (append)

**Interfaces:**
- Produces (used by Tasks 7–8):
  - `class ConvertedDoc` (dataclass): `title: str`, `markdown: str`, `source_label: str`, `html_title: str | None = None`, `url: str | None = None`, `path_name: str | None = None`, `warnings: list[str] = field(default_factory=list)`.
  - `assert_readable_path(value: str) -> Path` — traversal/sensitive-path guard, returns resolved path.
  - `convert_path(value: str, note: str | None = None) -> ConvertedDoc` — file or folder → one doc.
- Consumes: nothing new. (`derive_title` is applied later, in the Task 7 writer — `ConvertedDoc.title` here is the *provisional* title, filename/URL-based.)

- [ ] **Step 1: Append failing tests**

```python
# ── file/folder conversion + path safety ─────────────────────────────

from pathlib import Path

from llmwiki.add_doc import ConvertedDoc, assert_readable_path, convert_path


def test_reject_dotdot_segments(tmp_path):
    with pytest.raises(AddError, match=r"\.\."):
        assert_readable_path(str(tmp_path / ".." / "x"))


def test_reject_missing_path(tmp_path):
    with pytest.raises(AddError, match="resolve|exist"):
        assert_readable_path(str(tmp_path / "nope.md"))


@pytest.mark.parametrize("name", [".env", ".env.local", "id_rsa", "server.pem", "credentials.json"])
def test_reject_sensitive_paths(tmp_path, name):
    p = tmp_path / name
    p.write_text("secret")
    with pytest.raises(AddError, match="sensitive"):
        assert_readable_path(str(p))


def test_md_file_passthrough(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# My Notes\n\ncontent here\n")
    doc = convert_path(str(p))
    assert isinstance(doc, ConvertedDoc)
    assert doc.markdown.strip().startswith("# My Notes")
    assert doc.source_label == str(p.resolve())
    assert doc.path_name == "notes.md"


def test_text_file_fenced(tmp_path):
    p = tmp_path / "script.py"
    p.write_text("print('hi')\n")
    doc = convert_path(str(p))
    assert "```py" in doc.markdown
    assert "print('hi')" in doc.markdown


def test_note_prepended(tmp_path):
    p = tmp_path / "n.md"
    p.write_text("body\n")
    doc = convert_path(str(p), note="check this later")
    assert doc.markdown.startswith("> check this later\n\n")


def test_pdf_without_markitdown_errors(tmp_path, monkeypatch):
    import llmwiki.add_doc as m
    monkeypatch.setattr(m, "_markitdown_convert", None)
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(AddError, match=r"llm-notebook\[add\]"):
        convert_path(str(p))


def test_folder_walk(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\nalpha\n")
    (tmp_path / "b.py").write_text("x = 1\n")
    (tmp_path / ".hidden.md").write_text("nope")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("gamma\n")
    (tmp_path / "sub" / "binary.bin").write_bytes(b"\x00\x01")
    doc = convert_path(str(tmp_path))
    assert "## a.md" in doc.markdown
    assert "## b.py" in doc.markdown
    assert "## c.txt" in doc.markdown
    assert "nope" not in doc.markdown          # dotfile skipped
    assert "binary.bin" not in doc.markdown    # non-textual skipped
    assert doc.path_name == tmp_path.name


def test_folder_skips_symlinks(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# escaped\n")
    inner = tmp_path / "docs"
    inner.mkdir()
    (inner / "real.md").write_text("# real\n")
    (inner / "link.md").symlink_to(outside)
    doc = convert_path(str(inner))
    assert "real" in doc.markdown
    assert "escaped" not in doc.markdown
```

- [ ] **Step 2: Run to verify failure**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: `ImportError: cannot import name 'ConvertedDoc'`

- [ ] **Step 3: Append conversion code to `llmwiki/add_doc.py`**

Add `from pathlib import Path` to the top imports. Then append:

```python
# ── local file / folder conversion ───────────────────────────────────

TEXTUAL_EXT = {
    ".md", ".markdown", ".txt", ".rst", ".org",
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java", ".c", ".h", ".cpp",
    ".json", ".yaml", ".yml", ".toml", ".sh", ".sql", ".html", ".css",
}

# Extensions markitdown converts that are worth supporting; anything
# else binary is refused with a clear message.
_MARKITDOWN_EXT = {".pdf", ".docx", ".pptx", ".xlsx", ".epub"}

# Paths that almost always hold secrets — never ingest, ever.
# Port of kbbuilder SENSITIVE_PATH_PATTERNS (wiki-convert.ts).
_SENSITIVE_RES = [
    _re.compile(r"(^|[\\/])\.env(\.[^\\/]*)?$", _re.I),
    _re.compile(r"(^|[\\/])\.ssh([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.aws([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.gnupg([\\/]|$)", _re.I),
    _re.compile(r"(^|[\\/])\.netrc$", _re.I),
    _re.compile(r"(^|[\\/])id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$", _re.I),
    _re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$", _re.I),
    _re.compile(r"(^|[\\/])(credentials|secret|secrets)(\.[^\\/]*)?$", _re.I),
    _re.compile(r"(^|[\\/])shadow$", _re.I),
]


def _is_sensitive(path: str) -> bool:
    return any(rx.search(path) for rx in _SENSITIVE_RES)


try:  # optional [add] extra — used for PDF/docx/pptx/xlsx/epub
    from markitdown import MarkItDown as _MarkItDown

    def _markitdown_convert(path: Path) -> str:
        return _MarkItDown().convert(str(path)).text_content
except ImportError:  # pragma: no cover — exercised via monkeypatch in tests
    _markitdown_convert = None


@dataclass
class ConvertedDoc:
    """One source converted to markdown, before slug/title finalization."""
    title: str                       # provisional (filename/URL); finalized by the writer
    markdown: str
    source_label: str                # original URL or absolute path, for frontmatter
    html_title: "str | None" = None  # <title> when the source was an HTML page
    url: "str | None" = None
    path_name: "str | None" = None   # filename/dirname for title fallback
    warnings: "list[str]" = field(default_factory=list)


def assert_readable_path(value: str) -> Path:
    """Path-traversal / secret-read guard. Rejects literal '..' segments,
    resolves symlinks, and refuses known-sensitive paths. Returns the
    resolved path. (No allowlist roots: the CLI runs as the user who
    typed the path — unlike kbbuilder's queue-driven worker.)"""
    if ".." in _re.split(r"[\\/]", value):
        raise AddError(f'path must not contain ".." segments: {value}')
    try:
        real = Path(value).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AddError(f"cannot resolve path: {value}") from exc
    if _is_sensitive(str(real)) or _is_sensitive(value):
        raise AddError(f"refusing to read sensitive path: {value}")
    return real


def _fence_code(text: str, ext: str) -> str:
    lang = ext.lstrip(".")
    return f"```{lang}\n" + text.replace("```", "`​``").rstrip() + "\n```"


def _note_header(note: "str | None") -> str:
    return f"> {note.strip()}\n\n" if note and note.strip() else ""


def _walk_folder(dir_path: Path, depth: int = 0) -> str:
    """Concatenate a folder's textual files as '## name' sections.
    Depth-capped, sorted, dotfiles/node_modules skipped, symlinks never
    followed (they can escape the directory), sensitive paths skipped."""
    if depth > 6:
        return ""
    out: "list[str]" = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: p.name):
        if entry.name.startswith(".") or entry.name == "node_modules":
            continue
        if entry.is_symlink():
            continue
        if _is_sensitive(str(entry)):
            continue
        if entry.is_dir():
            nested = _walk_folder(entry, depth + 1)
            if nested:
                out.append(nested)
        elif entry.is_file() and entry.suffix.lower() in TEXTUAL_EXT:
            text = entry.read_text(encoding="utf-8", errors="replace")
            ext = entry.suffix.lower()
            body = text.strip() if ext in (".md", ".markdown") else _fence_code(text, ext)
            out.append(f"## {entry.name}\n\n{body}\n")
    return "\n".join(p for p in out if p)


def convert_path(value: str, note: "str | None" = None) -> ConvertedDoc:
    """Convert a local file or folder to one markdown document."""
    real = assert_readable_path(value)
    label = str(real)
    if real.is_dir():
        title = real.name
        body = _walk_folder(real)
        markdown = _note_header(note) + f"# {title}\n\n" + body
        return ConvertedDoc(title=title, markdown=markdown, source_label=label,
                            path_name=real.name)
    ext = real.suffix.lower()
    if ext in (".md", ".markdown"):
        text = real.read_text(encoding="utf-8", errors="replace")
        return ConvertedDoc(title=real.stem, markdown=_note_header(note) + text.strip() + "\n",
                            source_label=label, path_name=real.name)
    if ext in _MARKITDOWN_EXT:
        if _markitdown_convert is None:
            raise AddError(
                f"converting {ext} needs markitdown — install the optional extra: "
                "pip install 'llm-notebook[add]'"
            )
        text = _markitdown_convert(real)
        return ConvertedDoc(title=real.stem, markdown=_note_header(note) + text.strip() + "\n",
                            source_label=label, path_name=real.name)
    # Any other extension: treat as text, fenced as code.
    text = real.read_text(encoding="utf-8", errors="replace")
    body = _fence_code(text, ext or ".txt")
    markdown = _note_header(note) + f"# {real.name}\n\n" + body + "\n"
    return ConvertedDoc(title=real.stem, markdown=markdown, source_label=label,
                        path_name=real.name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: all PASS. `ruff check llmwiki/add_doc.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/add_doc.py tests/test_add_doc.py
git commit -m "feat(add): file/folder conversion with sensitive-path guard (#16)"
```

---

### Task 6: `add_doc.py` part 4 — layered URL pipeline

**Files:**
- Modify: `llmwiki/add_doc.py` (append)
- Test: `tests/test_add_doc.py` (append)

**Interfaces:**
- Produces (used by Tasks 7–8):
  - `convert_url(url: str, note: str | None = None, *, fetch=None, renderer=None, render: str = "auto") -> ConvertedDoc`
    - `fetch`: `Callable[[str, dict[str, str]], FetchResult]` — defaults to `guarded_fetch`; injected fetchers are trusted (no SSRF re-check), matching kbbuilder's `fetchFn` test seam.
    - `renderer`: `Callable[[str], str] | None` — returns rendered HTML; default resolves playwright lazily, `None` when unavailable.
    - `render`: `"auto" | "force" | "never"`.
  - `AGENT_UA`, `BROWSER_UA`, `CHALLENGE_MARKERS` module constants.
- Consumes: `html_to_markdown` (Task 2), `FetchResult`/`guarded_fetch`/`AddError` (Task 3), `ConvertedDoc`/`_note_header` (Task 5).

- [ ] **Step 1: Append failing tests**

```python
# ── layered URL pipeline ─────────────────────────────────────────────

from llmwiki.add_doc import FetchResult, convert_url

HTML_DOC = ("<html><head><title>Doc - Site</title></head><body><article>"
            "<h1>Doc Title</h1>" + "<p>real paragraph content here.</p>" * 30
            + "</article></body></html>")


def _fetcher(responses):
    """Stub fetch: pops canned FetchResults; records requested headers."""
    calls = []

    def fetch(url, headers):
        calls.append({"url": url, "headers": dict(headers)})
        return responses.pop(0)

    fetch.calls = calls
    return fetch


def test_layer1_markdown_negotiation_short_circuits():
    fetch = _fetcher([FetchResult(url="https://ex.com/a", status=200,
                                  content_type="text/markdown; charset=utf-8",
                                  body="# Served MD\n\nbody\n")])
    doc = convert_url("https://ex.com/a", fetch=fetch)
    assert doc.markdown.rstrip().endswith("body")
    assert "# Served MD" in doc.markdown
    # The first request must ask for markdown (Cloudflare Markdown for Agents).
    accept = fetch.calls[0]["headers"]["Accept"]
    assert accept.startswith("text/markdown")


def test_layer2_html_converted():
    fetch = _fetcher([FetchResult(url="https://ex.com/b", status=200,
                                  content_type="text/html", body=HTML_DOC)])
    doc = convert_url("https://ex.com/b", fetch=fetch)
    assert "Doc Title" in doc.markdown
    assert doc.html_title == "Doc - Site"
    assert doc.url == "https://ex.com/b"
    assert doc.source_label == "https://ex.com/b"


def test_403_retries_with_browser_ua():
    fetch = _fetcher([
        FetchResult(url="https://ex.com/c", status=403, content_type="text/html", body="denied"),
        FetchResult(url="https://ex.com/c", status=200, content_type="text/html", body=HTML_DOC),
    ])
    doc = convert_url("https://ex.com/c", fetch=fetch)
    assert "Doc Title" in doc.markdown
    ua1 = fetch.calls[0]["headers"]["User-Agent"]
    ua2 = fetch.calls[1]["headers"]["User-Agent"]
    assert "llmwiki" in ua1
    assert "Mozilla" in ua2


def test_challenge_page_escalates_to_renderer():
    challenge = "<html><body>Just a moment... Enable JavaScript</body></html>"
    fetch = _fetcher([
        FetchResult(url="https://ex.com/d", status=200, content_type="text/html", body=challenge),
        FetchResult(url="https://ex.com/d", status=200, content_type="text/html", body=challenge),
    ])
    rendered = {}

    def renderer(url):
        rendered["url"] = url
        return HTML_DOC

    doc = convert_url("https://ex.com/d", fetch=fetch, renderer=renderer)
    assert rendered["url"] == "https://ex.com/d"
    assert "Doc Title" in doc.markdown


def test_thin_page_without_renderer_warns():
    # A real SPA shell: all the bytes are script, the body has no text.
    thin = ("<html><head><title>SPA</title><script>" + "x" * 30000
            + "</script></head><body><div id=root></div></body></html>")
    fetch = _fetcher([
        FetchResult(url="https://ex.com/e", status=200, content_type="text/html", body=thin),
        FetchResult(url="https://ex.com/e", status=200, content_type="text/html", body=thin),
    ])
    doc = convert_url("https://ex.com/e", fetch=fetch, renderer=None)
    assert doc.warnings, "expected a shell-capture warning"
    assert any("render" in w.lower() or "javascript" in w.lower() for w in doc.warnings)


def test_render_never_skips_renderer():
    challenge = "<html><body>Enable JavaScript to continue</body></html>"
    fetch = _fetcher([
        FetchResult(url="https://ex.com/f", status=200, content_type="text/html", body=challenge),
        FetchResult(url="https://ex.com/f", status=200, content_type="text/html", body=challenge),
    ])

    def renderer(url):  # pragma: no cover — must not be called
        raise AssertionError("renderer must not run with render='never'")

    doc = convert_url("https://ex.com/f", fetch=fetch, renderer=renderer, render="never")
    assert doc.warnings


def test_http_error_raises():
    fetch = _fetcher([FetchResult(url="https://ex.com/g", status=404,
                                  content_type="text/html", body="nope"),
                      FetchResult(url="https://ex.com/g", status=404,
                                  content_type="text/html", body="nope")])
    with pytest.raises(AddError, match="404"):
        convert_url("https://ex.com/g", fetch=fetch)


def test_plain_text_response_passthrough():
    fetch = _fetcher([FetchResult(url="https://ex.com/h", status=200,
                                  content_type="text/plain",
                                  body="just plain text content, long enough to pass the gate. " * 10)])
    doc = convert_url("https://ex.com/h", fetch=fetch)
    assert "just plain text content" in doc.markdown
```

- [ ] **Step 2: Run to verify failure**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: `ImportError: cannot import name 'convert_url'`

- [ ] **Step 3: Append the URL pipeline to `llmwiki/add_doc.py`**

Add to top imports: `from llmwiki import __version__` and `from llmwiki.htmlmd import html_to_markdown`.

```python
# ── layered URL pipeline ─────────────────────────────────────────────
# Layer 1: content negotiation — Accept: text/markdown unlocks
#   Cloudflare "Markdown for Agents" / Read the Docs served markdown.
# Layer 2: static HTML extraction — trafilatura when installed (pullmd's
#   base extraction library; [add] extra), stdlib htmlmd otherwise.
# Quality gate: thin/challenge output ⇒ the page is JS-rendered or
#   bot-walled ⇒ Layer 3.
# Layer 3: headless render via playwright when importable ([e2e] extra).

AGENT_UA = f"llmwiki-add/{__version__} (+https://github.com/AlexanderMakarov/llm-wiki)"
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CHALLENGE_MARKERS = ("just a moment", "enable javascript", "checking your browser",
                     "attention required", "verify you are human")

_MIN_TEXT_CHARS = 200


def _looks_challenged(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in CHALLENGE_MARKERS)


def _quality_ok(text: str, html: str) -> bool:
    if _looks_challenged(text):
        return False
    stripped = text.strip()
    if len(stripped) < _MIN_TEXT_CHARS:
        return False
    if len(html) > 20_000 and len(stripped) < len(html) // 100:
        return False
    return True


def _extract_html(html: str) -> "tuple[str, str]":
    """(title, markdown) via trafilatura when available, stdlib otherwise."""
    try:
        import trafilatura
    except ImportError:
        return html_to_markdown(html)
    md = trafilatura.extract(html, output_format="markdown",
                             include_links=True, include_formatting=True)
    title = ""
    try:
        meta = trafilatura.extract_metadata(html)
        title = (meta.title or "") if meta else ""
    except Exception:  # noqa: BLE001 — metadata is best-effort
        pass
    if not md:
        return html_to_markdown(html)
    return title, md


def _default_renderer() -> "object | None":
    """Playwright-backed renderer, or None when playwright is absent."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    def render(url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=BROWSER_UA)
                page.goto(url, wait_until="networkidle", timeout=60_000)
                return page.content()
            finally:
                browser.close()

    return render


_RENDER_HINT = ("content may be a JS shell — install the render layer: "
                "pip install 'llm-notebook[e2e]' && playwright install chromium, "
                "or re-run with --render")


def convert_url(
    url: str,
    note: "str | None" = None,
    *,
    fetch=None,
    renderer=None,
    render: str = "auto",
) -> ConvertedDoc:
    """Convert a URL to one markdown document via the layered pipeline."""
    do_fetch = fetch or guarded_fetch
    headers = {"Accept": "text/markdown, text/html;q=0.9, */*;q=0.5",
               "User-Agent": AGENT_UA}
    resp = do_fetch(url, headers)

    # Anti-bot posture: honest agent headers first (unlocks markdown
    # negotiation); one retry with a browser UA on 403 / challenge body.
    if resp.status == 403 or (resp.status == 200 and _looks_challenged(resp.body)):
        headers = dict(headers)
        headers["User-Agent"] = BROWSER_UA
        resp = do_fetch(url, headers)

    if resp.status != 200:
        raise AddError(f"fetch {url} failed: HTTP {resp.status}")

    ctype = resp.content_type.lower()
    header = f"> Source: <{url}>\n\n"
    warnings: "list[str]" = []

    if ctype.startswith("text/markdown"):
        saved = resp.headers.get("x-markdown-tokens")
        if saved:
            warnings.append(f"server-side markdown: ~{saved} tokens "
                            f"(original ~{resp.headers.get('x-original-tokens', '?')})")
        body = resp.body.strip()
        return ConvertedDoc(title="", markdown=_note_header(note) + header + body + "\n",
                            source_label=url, url=url,
                            warnings=warnings)

    is_html = "html" in ctype or _re.match(r"^\s*<(!doctype|html)", resp.body, _re.I)
    if not is_html:
        body = resp.body.strip()
        return ConvertedDoc(title="", markdown=_note_header(note) + header + body + "\n",
                            source_label=url, url=url)

    html = resp.body
    title, md = _extract_html(html)

    needs_render = render == "force" or (render == "auto" and not _quality_ok(md, html))
    if needs_render and render != "never":
        active_renderer = renderer if renderer is not None else _default_renderer()
        if active_renderer is not None:
            rendered_html = active_renderer(url)
            r_title, r_md = _extract_html(rendered_html)
            if len(r_md.strip()) > len(md.strip()):
                title, md = (r_title or title), r_md
            if not _quality_ok(md, rendered_html):
                warnings.append(_RENDER_HINT)
        else:
            warnings.append(_RENDER_HINT)
    elif not _quality_ok(md, html):
        warnings.append(_RENDER_HINT)

    return ConvertedDoc(title="", markdown=_note_header(note) + header + md.strip() + "\n",
                        source_label=url, url=url, html_title=title or None,
                        warnings=warnings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: all PASS. Note `test_render_never_skips_renderer` also proves `render="never"` never even constructs the default renderer. `ruff check llmwiki/add_doc.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/add_doc.py tests/test_add_doc.py
git commit -m "feat(add): layered URL pipeline - markdown negotiation, extraction, render escalation (#16)"
```

---

### Task 7: `add_doc.py` part 5 — raw-doc writer + batch orchestrator

**Files:**
- Modify: `llmwiki/add_doc.py` (append)
- Test: `tests/test_add_doc.py` (append)

**Interfaces:**
- Produces (used by Task 8):
  - `write_raw_doc(doc: ConvertedDoc, docs_dir: Path, *, explicit_title: str | None = None, project: str | None = None, extra_tags: tuple[str, ...] = (), today: str | None = None, chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS) -> list[Path]`
  - `add_sources(sources: list[str], docs_dir: Path, *, title: str | None = None, project: str | None = None, tags: tuple[str, ...] = (), note: str | None = None, render: str = "auto", dry_run: bool = False, fetch=None, renderer=None, today: str | None = None) -> dict` — returns `{"written": list[Path], "titles": list[str], "warnings": list[str], "errors": list[str]}`. Converts + writes every source; does NOT synthesize/build (that stays in `cmd_add`, Task 8).
- Consumes: `slugify`/`derive_title` (Task 1), `chunk_markdown_by_sections`/`MarkdownChunk` (Task 4), `ConvertedDoc`/`convert_path` (Task 5), `convert_url` (Task 6).

- [ ] **Step 1: Append failing tests**

```python
# ── raw-doc writer + orchestrator ────────────────────────────────────

from llmwiki.add_doc import add_sources, write_raw_doc


def _doc(markdown="# Doc Title\n\nbody\n", **kw):
    defaults = dict(title="", source_label="/tmp/x.md", path_name="x.md")
    defaults.update(kw)
    return ConvertedDoc(markdown=markdown, **defaults)


def test_write_single_chunk_layout_and_frontmatter(tmp_path):
    paths = write_raw_doc(_doc(), tmp_path, today="2026-07-04")
    assert paths == [tmp_path / "doc-title" / "doc-title.md"]
    text = paths[0].read_text()
    # Byte-compatible with kbbuilder makeRawDocWriter (wiki-worker.ts:91-100).
    assert text.startswith(
        '---\n'
        'title: "Doc Title"\n'
        'slug: doc-title\n'
        'project: doc-title\n'
        'type: source\n'
        'tags: [wiki-add, raw-doc]\n'
        'date: 2026-07-04\n'
        'source: "/tmp/x.md"\n'
        '---\n\n'
    )
    assert text.rstrip().endswith("body")


def test_write_multi_chunk_names_titles_breadcrumbs(tmp_path):
    md = "".join(f"## Sec{i}\n\n" + "x" * 900 + "\n\n" for i in range(4))
    paths = write_raw_doc(_doc(markdown="# Big Doc\n\n" + md), tmp_path,
                          today="2026-07-04", chunk_max_chars=1000)
    assert len(paths) > 1
    assert paths[0].name == "big-doc-01.md"
    first = paths[0].read_text()
    assert 'title: "Big Doc (part 1/' in first
    assert "> Part 1 of" in first
    assert "slug: big-doc-01" in first
    assert "project: big-doc" in first


def test_write_never_overwrites_suffixes_slug(tmp_path):
    p1 = write_raw_doc(_doc(), tmp_path, today="2026-07-04")
    p2 = write_raw_doc(_doc(), tmp_path, today="2026-07-04")
    assert p1 != p2
    assert p2 == [tmp_path / "doc-title-2" / "doc-title-2.md"]
    p3 = write_raw_doc(_doc(), tmp_path, today="2026-07-04")
    assert p3 == [tmp_path / "doc-title-3" / "doc-title-3.md"]
    assert p1[0].read_text() == p2[0].read_text().replace("doc-title-2", "doc-title")


def test_write_explicit_project_collides_on_file_level(tmp_path):
    write_raw_doc(_doc(), tmp_path, project="shared", today="2026-07-04")
    p2 = write_raw_doc(_doc(), tmp_path, project="shared", today="2026-07-04")
    assert p2 == [tmp_path / "shared" / "doc-title-2.md"]


def test_write_extra_tags(tmp_path):
    paths = write_raw_doc(_doc(), tmp_path, extra_tags=("research",), today="2026-07-04")
    assert "tags: [wiki-add, raw-doc, research]" in paths[0].read_text()


def test_write_explicit_title_wins(tmp_path):
    paths = write_raw_doc(_doc(), tmp_path, explicit_title="Custom Name", today="2026-07-04")
    assert paths[0].parent.name == "custom-name"
    assert 'title: "Custom Name"' in paths[0].read_text()


def test_add_sources_batch_mixed_success_and_failure(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("# In File\n\ncontent\n")
    docs = tmp_path / "docs"
    result = add_sources([str(src), str(tmp_path / "missing.md")], docs,
                         today="2026-07-04")
    assert len(result["written"]) == 1
    assert result["titles"] == ["In File"]
    assert len(result["errors"]) == 1
    assert "missing.md" in result["errors"][0]
    assert (docs / "in-file" / "in-file.md").exists()


def test_add_sources_dry_run_writes_nothing(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("# In File\n\ncontent\n")
    docs = tmp_path / "docs"
    result = add_sources([str(src)], docs, dry_run=True, today="2026-07-04")
    assert result["titles"] == ["In File"]
    assert not docs.exists()


def test_add_sources_url_routed_to_convert_url(tmp_path):
    fetch = _fetcher([FetchResult(url="https://ex.com/p", status=200,
                                  content_type="text/html", body=HTML_DOC)])
    docs = tmp_path / "docs"
    result = add_sources(["https://ex.com/p"], docs, fetch=fetch, today="2026-07-04")
    assert result["titles"] == ["Doc Title"]
    written = result["written"][0].read_text()
    assert 'source: "https://ex.com/p"' in written


def test_written_doc_flows_through_synth_pipeline(tmp_path):
    """End-to-end with the EXISTING synthesis pipeline (DummySynthesizer):
    the written raw doc must produce a wiki/sources page."""
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import synthesize_new_sessions

    docs = tmp_path / "raw" / "docs"
    src = tmp_path / "in.md"
    src.write_text("# Flow Doc\n\nSome real content to summarize.\n")
    add_sources([str(src)], docs, today="2026-07-04")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",       # empty — docs only
        docs_dir=docs,
        wiki_sources_dir=tmp_path / "wiki" / "sources",
        state_file=tmp_path / "state.json",
        log_path=tmp_path / "log.md",
    )
    assert summary["errors"] == []
    assert summary["synthesized"] == 1
    pages = list((tmp_path / "wiki" / "sources").rglob("*.md"))
    assert len(pages) == 1
    assert "flow-doc" in pages[0].name
```

- [ ] **Step 2: Run to verify failure**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py -q`
Expected: `ImportError: cannot import name 'add_sources'`

- [ ] **Step 3: Append writer + orchestrator to `llmwiki/add_doc.py`**

Add to top imports: `import json` and `from datetime import date` and `from llmwiki.slugs import derive_title, slugify`.

```python
# ── raw-doc writer (byte-compatible with kbbuilder makeRawDocWriter) ─

def _dedupe(base: str, exists) -> str:
    """First of base, base-2, base-3, … for which exists() is False."""
    if not exists(base):
        return base
    n = 2
    while exists(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"


def _frontmatter(title: str, slug: str, project: str, tags: "tuple[str, ...]",
                 today: str, source: str) -> str:
    tag_list = ", ".join(("wiki-add", "raw-doc") + tags)
    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"slug: {slug}\n"
        f"project: {project}\n"
        "type: source\n"
        f"tags: [{tag_list}]\n"
        f"date: {today}\n"
        f"source: {json.dumps(source, ensure_ascii=False)}\n"
        "---\n\n"
    )


def write_raw_doc(
    doc: ConvertedDoc,
    docs_dir: Path,
    *,
    explicit_title: "str | None" = None,
    project: "str | None" = None,
    extra_tags: "tuple[str, ...]" = (),
    today: "str | None" = None,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> "list[Path]":
    """Write one converted doc under raw/docs/<project>/, chunked by
    section when large. Never overwrites (raw/ immutability): the doc
    slug is suffixed -2, -3, … on collision. Returns written paths."""
    title = derive_title(explicit=explicit_title, markdown=doc.markdown,
                         html_title=doc.html_title, url=doc.url,
                         path_name=doc.path_name)
    base_slug = slugify(title) or "untitled"
    day = today or date.today().isoformat()
    chunks = chunk_markdown_by_sections(doc.markdown, max_chars=chunk_max_chars)
    if not chunks:
        raise AddError(f"nothing to write for {doc.source_label} (empty document)")
    multi = len(chunks) > 1

    def file_names(slug: str) -> "list[str]":
        if not multi:
            return [f"{slug}.md"]
        return [f"{slug}-{c.index:02d}.md" for c in chunks]

    if project:
        proj = slugify(project) or project
        target = docs_dir / proj
        slug = _dedupe(base_slug,
                       lambda s: any((target / n).exists() for n in file_names(s)))
    else:
        slug = _dedupe(base_slug, lambda s: (docs_dir / s).exists())
        proj = slug
        target = docs_dir / proj

    target.mkdir(parents=True, exist_ok=True)
    written: "list[Path]" = []
    for c in chunks:
        chunk_slug = f"{slug}-{c.index:02d}" if multi else slug
        sub = c.heading if (c.heading and c.heading != title) else ""
        if multi:
            chunk_title = f"{title} (part {c.index}/{c.total}" + (f": {sub}" if sub else "") + ")"
            breadcrumb = f"> Part {c.index} of {c.total} of **{title}**" + (f" — {sub}" if sub else "") + ".\n\n"
        else:
            chunk_title, breadcrumb = title, ""
        fm = _frontmatter(chunk_title, chunk_slug, proj, extra_tags, day, doc.source_label)
        path = target / f"{chunk_slug}.md"
        if path.exists():  # belt-and-braces: raw/ is immutable
            raise AddError(f"refusing to overwrite existing raw file {path}")
        path.write_text(fm + breadcrumb + c.body, encoding="utf-8")
        written.append(path)
    return written


def add_sources(
    sources: "list[str]",
    docs_dir: Path,
    *,
    title: "str | None" = None,
    project: "str | None" = None,
    tags: "tuple[str, ...]" = (),
    note: "str | None" = None,
    render: str = "auto",
    dry_run: bool = False,
    fetch=None,
    renderer=None,
    today: "str | None" = None,
) -> dict:
    """Convert + write a batch of sources. Post-steps (synthesize/build)
    are the CLI's job — this function only lands raw docs. Per-source
    failures are collected, not fatal: the rest of the batch lands."""
    written: "list[Path]" = []
    titles: "list[str]" = []
    warnings: "list[str]" = []
    errors: "list[str]" = []
    for src in sources:
        try:
            if _re.match(r"^https?://", src):
                doc = convert_url(src, note, fetch=fetch, renderer=renderer, render=render)
            else:
                doc = convert_path(src, note)
            final_title = derive_title(explicit=title, markdown=doc.markdown,
                                       html_title=doc.html_title, url=doc.url,
                                       path_name=doc.path_name)
            titles.append(final_title)
            warnings.extend(f"{src}: {w}" for w in doc.warnings)
            if dry_run:
                chunks = chunk_markdown_by_sections(doc.markdown)
                slug = slugify(final_title) or "untitled"
                proj = slugify(project) if project else slug
                names = ([f"{slug}.md"] if len(chunks) <= 1
                         else [f"{slug}-{c.index:02d}.md" for c in chunks])
                warnings.append(f"{src}: dry-run — would write "
                                f"{', '.join(str(docs_dir / proj / n) for n in names)}")
                continue
            written.extend(write_raw_doc(doc, docs_dir, explicit_title=title,
                                         project=project, extra_tags=tags, today=today))
        except AddError as exc:
            errors.append(f"{src}: {exc}")
    return {"written": written, "titles": titles, "warnings": warnings, "errors": errors}
```

- [ ] **Step 4: Run the whole module's tests**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_add_doc.py tests/test_slugs.py tests/test_htmlmd.py -q`
Expected: all PASS — including `test_written_doc_flows_through_synth_pipeline`, which proves compatibility with the real synthesis pipeline. `ruff check llmwiki tests` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/add_doc.py tests/test_add_doc.py
git commit -m "feat(add): raw-doc writer with collision suffixing + batch orchestrator (#16)"
```

---

### Task 8: CLI wiring — `cmd_add`, `llm-wiki-add` entry point, README

**Files:**
- Modify: `llmwiki/cli.py` (new `cmd_add`, subparser registration in `build_parser()`, `main_add`, `_add_vault_arg` role dict, module docstring subcommand list)
- Modify: `pyproject.toml` (`[project.scripts]` + `[project.optional-dependencies]`)
- Modify: `README.md` (CLI reference block)
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `add_sources` (Task 7), `synthesize_new_sessions`/`resolve_backend` (existing), `build_site` (existing).
- Produces: `llmwiki add` subcommand; `main_add(argv: list[str] | None = None) -> int` console entry.

- [ ] **Step 1: Append failing tests to `tests/test_cli.py`**

```python
def test_add_dry_run_local_md(tmp_path):
    src = tmp_path / "sample.md"
    src.write_text("# Sample Doc\n\nsome content\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--dry-run", str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Sample Doc" in r.stdout
    assert "dry-run" in r.stdout


def test_add_requires_source():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


def test_add_title_with_multiple_sources_rejected(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("# A\n"); b.write_text("# B\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--title", "T", "--dry-run",
         str(a), str(b)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "--title" in r.stderr


def test_llm_wiki_add_entry_point(tmp_path):
    src = tmp_path / "sample.md"
    src.write_text("# Entry Point Doc\n\ncontent\n")
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; from llmwiki.cli import main_add; sys.exit(main_add())",
         "--dry-run", str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Entry Point Doc" in r.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_cli.py -q`
Expected: the three `add` tests FAIL (`invalid choice: 'add'`); `main_add` import error. Also run `env -u LLMWIKI_ROOT python3 -m pytest tests/test_cli_doc_parity.py -q` — currently PASSES (README not yet touched); it must STILL pass after Step 3's README edit.

- [ ] **Step 3: Implement CLI wiring**

3a. In `llmwiki/cli.py`, extend `_add_vault_arg`'s role help dict (llmwiki/cli.py:692-708) with an `"add"` key:

```python
            "add": "(#16) Vault-overlay mode: write the converted document "
                   "under the vault's raw/docs/ and run synthesize/build "
                   "against the vault.",
```

3b. Add `cmd_add` after `cmd_synthesize` (~line 576):

```python
def cmd_add(args: argparse.Namespace) -> int:
    """Add documents to the wiki: convert to Markdown, land under
    raw/docs/ (kbbuilder-compatible layout), then batch synthesize +
    rebuild the site (issue #16).

    Sources may be URLs, files, or folders, freely mixed. Conversion
    and writing happen per source; synthesis and build run ONCE for
    the whole batch. --no-synthesize / --no-build opt out.
    """
    _apply_default_vault(args)
    from llmwiki.add_doc import add_sources

    if args.title and len(args.sources) > 1:
        print("error: --title needs a single source (got "
              f"{len(args.sources)})", file=sys.stderr)
        return 2

    docs_dir = REPO_ROOT / "raw" / "docs"
    vault_root = None
    if getattr(args, "vault", None):
        from llmwiki.vault import resolve_vault
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        vault_root = vault.root
        docs_dir = vault_root / "raw" / "docs"

    render = "auto"
    if args.render:
        render = "force"
    elif args.no_render:
        render = "never"

    result = add_sources(
        list(args.sources), docs_dir,
        title=args.title, project=args.project, tags=tuple(args.tag or ()),
        note=args.note, render=render, dry_run=args.dry_run,
    )

    for title in result["titles"]:
        print(f"  + {title}")
    for w in result["warnings"]:
        print(f"  ~ {w}")
    for e in result["errors"]:
        print(f"  ! {e}", file=sys.stderr)
    if args.dry_run:
        return 2 if result["errors"] else 0
    print(f"  wrote {len(result['written'])} file(s) under {docs_dir}")

    failed = bool(result["errors"])
    if not result["written"]:
        return 2 if failed else 0

    # Post-steps run once for the whole batch. Failures here never
    # un-land written docs (kbbuilder add-doc precedent): the next
    # sync/build picks them up.
    if not args.no_synthesize:
        from llmwiki.config_schedule import _load_sessions_config
        from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions
        backend = resolve_backend(_load_sessions_config())
        print(f"Synthesizing with backend: {backend.name}")
        raw_dir = wiki_sources_dir = state_file = None
        if vault_root:
            raw_dir = vault_root / "raw" / "sessions"
            wiki_sources_dir = vault_root / "wiki" / "sources"
            state_file = vault_root / ".llmwiki-synth-state.json"
        summary = synthesize_new_sessions(
            backend=backend, raw_dir=raw_dir,
            wiki_sources_dir=wiki_sources_dir, state_file=state_file,
        )
        print(f"  synthesized {summary['synthesized']}, skipped {summary['skipped']}")
        if summary["errors"]:
            for err in summary["errors"]:
                print(f"  ! {err}", file=sys.stderr)
            failed = True

    if not args.no_build:
        from llmwiki.build import build_site, RAW_SESSIONS, RAW_DIR
        raw_sessions, raw_dir_b = RAW_SESSIONS, RAW_DIR
        wiki_dir = REPO_ROOT / "wiki"
        out_dir = REPO_ROOT / "site"
        if vault_root:
            raw_dir_b = vault_root / "raw"
            raw_sessions = raw_dir_b / "sessions"
            wiki_dir = vault_root / "wiki"
            out_dir = vault_root / "site"
        code = build_site(out_dir=out_dir, raw_sessions=raw_sessions,
                          raw_dir=raw_dir_b, wiki_dir=wiki_dir)
        if code:
            failed = True

    # Observability: same grep-parseable format as sync/synthesize.
    from datetime import date as _date
    log_path = (vault_root or REPO_ROOT) / "wiki" / "log.md"
    if log_path.parent.is_dir():
        day = _date.today().isoformat()
        with log_path.open("a", encoding="utf-8") as fh:
            for t in result["titles"]:
                fh.write(f"\n## [{day}] add | {t}\n")

    return 2 if failed else 0
```

3c. Register the subparser in `build_parser()` (after the `synthesize` block, before `consolidate-topics`):

```python
    add_p = sub.add_parser(
        "add",
        help="Add documents to the wiki: URL, file, or folder → raw/docs/ + synthesize + build (#16)",
    )
    add_p.add_argument("sources", nargs="+", metavar="SOURCE",
                       help="URL (http/https), file, or folder. Repeatable.")
    add_p.add_argument("--title", default=None,
                       help="Override title derivation (single source only)")
    add_p.add_argument("--project", default=None,
                       help="Group under raw/docs/<PROJECT>/ instead of the doc's own slug")
    add_p.add_argument("--tag", action="append", default=None, metavar="TAG",
                       help="Extra frontmatter tag (repeatable)")
    add_p.add_argument("--note", default=None,
                       help="Blockquote note prepended to the document body")
    add_p.add_argument("--no-synthesize", action="store_true",
                       help="Skip the post-add synthesis pass")
    add_p.add_argument("--no-build", action="store_true",
                       help="Skip the post-add site rebuild")
    render_group = add_p.add_mutually_exclusive_group()
    render_group.add_argument("--render", action="store_true",
                              help="Force the headless-browser layer for URLs (needs playwright)")
    render_group.add_argument("--no-render", action="store_true",
                              help="Never use the headless-browser layer")
    add_p.add_argument("--dry-run", action="store_true",
                       help="Convert and report, write nothing, run nothing")
    _add_vault_arg(add_p, role="add")
    add_p.set_defaults(func=cmd_add)
```

3d. Add `main_add` next to `main()` at the bottom of `cli.py`:

```python
def main_add(argv: "list[str] | None" = None) -> int:
    """Console entry for `llm-wiki-add` — `llmwiki add` with less typing."""
    import sys as _sys
    return main(["add", *(_sys.argv[1:] if argv is None else argv)])
```

3e. Update the module docstring subcommand list at the top of `cli.py` — insert after the `sync` line:

```
    add               Add documents: URL, file, or folder → raw/docs/ + synthesize + build
```

3f. `pyproject.toml` — extend scripts and extras:

```toml
[project.scripts]
llmwiki = "llmwiki.cli:main"
llm-wiki-add = "llmwiki.cli:main_add"
```

and under `[project.optional-dependencies]` (after `graph`):

```toml
# `llmwiki add` quality upgrades (#16): trafilatura is pullmd's base
# extraction library (static HTML → markdown); markitdown converts
# PDF/docx/pptx/xlsx/epub. The stdlib fallback keeps a bare install
# working without either. (This is NOT the old [pdf] extra — that one
# stays removed.)
add = [
    "trafilatura>=2.0.0",
    "markitdown>=0.1.2",
]
```

3g. README `## CLI reference` block — insert after the `llmwiki sync` line:

```bash
llmwiki add <url|file|folder>... [--vault PATH] [--no-synthesize] [--no-build]
```

(`test_cli_doc_parity.py` parses `llmwiki <name>` lines in this block against registered subparsers — the name `add` must match.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u LLMWIKI_ROOT python3 -m pytest tests/test_cli.py tests/test_cli_doc_parity.py tests/test_slash_cli_parity.py -q`
Expected: all PASS.
Then the full suite: `env -u LLMWIKI_ROOT python3 -m pytest -q` — no regressions.
`ruff check llmwiki tests` — clean.

- [ ] **Step 5: Commit**

```bash
git add llmwiki/cli.py pyproject.toml README.md tests/test_cli.py
git commit -m "feat(cli): llmwiki add subcommand + llm-wiki-add entry point (#16)"
```

---

### Task 9: Docs, changelog, typo fix, end-to-end verification

**Files:**
- Modify: `CHANGELOG.md` (new entry at top, matching existing entry style)
- Modify: `docs/architecture.md` (intake path mention)
- Modify: `README.md` (short "Adding documents" section after the CLI reference)
- Modify: `CLAUDE.md:204` (drive-by typo: "impolemented" → "implemented")

**Interfaces:** none — documentation only.

- [ ] **Step 1: CHANGELOG entry**

Read the top of `CHANGELOG.md` and copy the exact heading style of the latest entry. Content:

```markdown
- **`llmwiki add <url|file|folder>...`** (#16): synchronous local document intake.
  Converts sources to Markdown (Cloudflare `Accept: text/markdown` negotiation →
  trafilatura/stdlib extraction → optional playwright render), writes
  `raw/docs/<slug>/<slug>[-NN].md` in the kbbuilder-compatible chunked layout,
  then batch-synthesizes and rebuilds the site. New `llm-wiki-add` console script
  and `[add]` optional extra (`trafilatura`, `markitdown`).
```

- [ ] **Step 2: README "Adding documents" section**

Insert after the CLI-reference block's closing paragraph (`Shell shortcuts: ...`):

```markdown
## Adding documents

`llmwiki add` drops any URL, file, or folder into the wiki:

```bash
llmwiki add https://blog.example.com/post ./notes.md ./research-folder
llm-wiki-add https://docs.example.com/guide   # same thing, shorter
```

URLs are fetched with `Accept: text/markdown` first — sites behind Cloudflare's
[Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
return ready-made Markdown. HTML pages are extracted with
[trafilatura](https://trafilatura.readthedocs.io/) when installed
(`pip install 'llm-notebook[add]'`, which also enables PDF/docx via markitdown)
and a stdlib converter otherwise. JavaScript-rendered pages escalate to a headless
browser when playwright is available (`pip install 'llm-notebook[e2e]'`).

Documents land under `raw/docs/<slug>/`, split at section boundaries into
~7k-char chunks. The separation is deliberate: each chunk becomes one synthesis
input that fits the model's context window, so one huge page can't overload or
OOM a synthesis pass — splits happen at `#`/`##` headings (never mid-sentence,
not a hard 7000-char slice). After writing, one synthesis pass and one site
build run for the whole batch (`--no-synthesize` / `--no-build` to skip).
`raw/` stays immutable: re-adding a document never overwrites — the slug gets
a `-2`, `-3`, … suffix.
```

- [ ] **Step 3: `docs/architecture.md`**

Find the intake/dataflow description (around the line mentioning `raw/docs/**` / wiki-add documents, `docs/architecture.md:103`) and add one sentence:

```markdown
Documents enter `raw/docs/` either via kbbuilder's async `wiki-add` worker or
synchronously via `llmwiki add` (`llmwiki/add_doc.py`, #16) — both produce the
same dir-per-doc, section-chunked layout.
```

- [ ] **Step 4: CLAUDE.md typo fix**

In `CLAUDE.md` line 204: `change impolemented` → `change implemented`.

- [ ] **Step 5: Full verification**

```bash
env -u LLMWIKI_ROOT python3 -m pytest -q          # full suite green
ruff check llmwiki tests                           # clean
env -u LLMWIKI_ROOT python3 -m llmwiki add --help  # renders all flags
```

Manual end-to-end (real repo, no network): create a scratch md file and run
`env -u LLMWIKI_ROOT python3 -m llmwiki add --dry-run /tmp/claude-scratch-sample.md` —
prints the derived title + would-write path, exits 0.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md README.md docs/architecture.md CLAUDE.md
git commit -m "docs(add): changelog, README adding-documents section, architecture note (#16)"
```

---

## Post-plan (not tasks — PR checklist)

- Push `feat/add-cli` via HTTPS + `gh` (SSH push is denied on this machine).
- PR to `AlexanderMakarov/llm-wiki` `main`, title `feat(cli): llmwiki add — universal document intake (#16)`, body: summary, design/spec link, test evidence, `Closes #16`. NO claude.ai session links.
- Comment on kbbuilder#7 pointing at `llmwiki/slugs.py` as the convergence target.

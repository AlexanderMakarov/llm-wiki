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

_SKIP = {
    "script",
    "style",
    "template",
    "noscript",
    "svg",
    "iframe",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
}
_CONTENT_ROOTS = ("article", "main")
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_PARA_BREAK = {"p", "div", "section", "table", "tr", "blockquote", "figure"}


class _MdBuilder(HTMLParser):
    """Event-driven converter. convert_charrefs=True (default) makes
    handle_data receive already-unescaped text."""

    def __init__(self, content_root: str | None):
        super().__init__()
        self.content_root = content_root
        self.in_content = content_root is None
        self._entered_root = False
        self._content_depth = 0
        self.out: list[str] = []
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._pre_depth = 0
        self._list_stack: list[int | None] = []  # None=ul, int=next ol number
        self._href: str | None = None
        self._link_text: list[str] = []

    # ── output helpers ─────────────────────────────────────────────
    def _emit(self, marker: str) -> None:
        """Write an inline formatting marker (**, *, `) to whichever buffer
        is currently active — the link-text buffer while inside an <a>,
        otherwise the main output. Keeps `<a><strong>text</strong></a>`
        from splitting the markers away from the link they belong to."""
        if self._href is not None:
            self._link_text.append(marker)
        else:
            self.out.append(marker)

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
            self._entered_root = True
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
                self._emit("`")
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
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
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
                self._emit("`")
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
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")

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
            return
        # Inline text between tags: collapse internal runs of whitespace to
        # a single space, but preserve a leading/trailing space when the
        # original had one — that's what keeps "word <a>anchor</a>." from
        # gluing onto the previous/next word once tags are stripped out.
        collapsed = " ".join(data.split())
        if not collapsed:
            if data:
                # whitespace-only fragment between two elements: keep one
                # separating space so adjacent inline elements don't merge.
                self.out.append(" ")
            return
        if data[:1].isspace():
            collapsed = " " + collapsed
        if data[-1:].isspace():
            collapsed = collapsed + " "
        self.out.append(collapsed)


def html_to_markdown(html: str) -> tuple[str, str]:
    """Convert HTML to (title, markdown). Prefers an <article>/<main>
    subtree when one exists; otherwise converts the whole body."""
    lower = html.lower()
    root = next((r for r in _CONTENT_ROOTS if f"<{r}" in lower), None)
    builder = _MdBuilder(root)
    builder.feed(html)
    if root is not None and not builder._entered_root:
        # The assumed content root was a false positive (e.g. "<article>"
        # only appeared inside a comment or string, never as a real start
        # tag) — re-parse the whole document instead of losing everything.
        builder = _MdBuilder(None)
        builder.feed(html)
    raw = "".join(builder.out)
    lines = [ln.rstrip() for ln in raw.split("\n")]
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return builder.title.strip(), text.strip()

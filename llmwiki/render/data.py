"""Build-emitted runtime data files for the static site (#20).

The viewer needs its search payloads at runtime. Fetching them is not an
option when the site is opened straight from disk: browsers refuse
``fetch``/XHR against ``file://`` URLs, which used to leave search silently
empty. Subresource *execution* is not restricted the same way, so every
payload is emitted a second time as a ``.js`` file that assigns itself into
``window.llmwikiData``; the client injects a ``<script src>`` and reads it
back out. One code path covers both ``http://`` and ``file://``.

The ``.json`` originals stay on disk — they are the documented reader-API
surface (``docs/reference/reader-api.md``) that external tools consume.
"""

from __future__ import annotations

import json
from pathlib import Path

#: U+2028 / U+2029 are legal inside JSON strings but were illegal inside JS
#: string literals until ES2019. Escaping them costs nothing, keeps the
#: decoded value identical, and avoids an obscure parse error on old engines.
_JS_SIDECAR_ESCAPES = {" ": "\\u2028", " ": "\\u2029"}


def write_js_sidecar(json_path: Path, key: str, payload: str) -> Path:
    """Emit ``json_path`` a second time as executable JS. Returns its path.

    ``payload`` is the already-serialised JSON text, reused verbatim so the
    sidecar can never drift from the ``.json`` it shadows. ``key`` is the name
    the client looks the payload up under in ``window.llmwikiData``.
    """
    for char, escape in _JS_SIDECAR_ESCAPES.items():
        payload = payload.replace(char, escape)
    js_path = json_path.with_suffix(".js")
    # Chunks load in arbitrary order, so every sidecar seeds the namespace
    # itself rather than assuming another file got there first.
    js_path.write_text(
        "window.llmwikiData = window.llmwikiData || {};\n"
        f"window.llmwikiData[{json.dumps(key)}] = {payload};\n",
        encoding="utf-8",
    )
    return js_path

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

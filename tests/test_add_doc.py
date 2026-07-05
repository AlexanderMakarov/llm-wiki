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


# ── file/folder conversion + path safety ─────────────────────────────

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

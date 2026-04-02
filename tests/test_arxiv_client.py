"""Tests for tools/arxiv_client.py."""

import pytest

from tools.arxiv_client import (
    ArxivPaper,
    _parse_arxiv_id,
    looks_like_arxiv_id,
    metadata_to_dict,
)

# ── Normalisation ────────────────────────────────────────────────────────────────

class TestParseArxivId:
    @pytest.mark.parametrize("raw,expected", [
        ("2301.12345",        "2301.12345"),
        ("2301.12345v2",      "2301.12345"),
        ("2301.12345v10",     "2301.12345"),
        ("id:2301.12345",     "2301.12345"),
        ("cs/0601001",        "cs/0601001"),
        ("cs/0601001v3",      "cs/0601001"),
        ("https://arxiv.org/abs/2301.12345",     "2301.12345"),
        ("https://arxiv.org/abs/2301.12345v2",  "2301.12345"),
        ("https://arxiv.org/pdf/2301.12345.pdf", "2301.12345"),
        ("  2301.12345  ",    "2301.12345"),
        ("2301.12345.pdf",    "2301.12345"),
    ])
    def test_parses_all_formats(self, raw, expected):
        assert _parse_arxiv_id(raw) == expected


class TestLooksLikeArxivId:
    @pytest.mark.parametrize("valid", [
        "2301.12345", "2301.1", "cs/0601001", "hep-th/9901001",
    ])
    def test_valid_ids(self, valid):
        assert looks_like_arxiv_id(valid) is True

    @pytest.mark.parametrize("invalid", [
        "not-an-id", "12345", "2301.123456", "", "   ",
    ])
    def test_invalid_ids(self, invalid):
        assert looks_like_arxiv_id(invalid) is False


# ── Metadata dict conversion ────────────────────────────────────────────────────

class TestMetadataToDict:
    def test_roundtrip_fields(self):
        paper = ArxivPaper(
            arxiv_id="2301.12345",
            title="Test Title",
            authors=["Alice", "Bob"],
            abstract="Test abstract.",
            published="2023-01-15",
            updated="2023-01-20",
            categories=["cs.CL"],
            pdf_url="https://arxiv.org/pdf/2301.12345.pdf",
            abs_url="https://arxiv.org/abs/2301.12345",
            first_author="Alice",
            year=2023,
        )
        d = metadata_to_dict(paper)
        assert d["arxiv_id"] == "2301.12345"
        assert d["title"] == "Test Title"
        assert d["authors"] == ["Alice", "Bob"]
        assert d["first_author"] == "Alice"
        assert d["year"] == 2023


# ── Fetch with mocking ─────────────────────────────────────────────────────────

ATOM_ENTRY = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v1</id>
    <title>A Test Paper on LLMs</title>
    <summary>This paper studies quantization of large language models.</summary>
    <published>2023-01-15T00:00:00Z</published>
    <updated>2023-01-20T00:00:00Z</updated>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
    <link href="https://arxiv.org/pdf/2301.12345v1" title="pdf"/>
  </entry>
</feed>"""


@pytest.fixture
def mock_urlopen(requests_mock):
    requests_mock.register_uri(
        "GET", "https://export.arxiv.org/api/query", content=ATOM_ENTRY
    )


class TestFetchMetadata:
    def test_returns_paper_on_success(self, requests_mock):
        requests_mock.register_uri(
            "GET", "https://export.arxiv.org/api/query", content=ATOM_ENTRY
        )
        from tools.arxiv_client import fetch_metadata
        paper = fetch_metadata("2301.12345")
        assert paper is not None
        assert paper.arxiv_id == "2301.12345"
        assert paper.title == "A Test Paper on LLMs"
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert "cs.CL" in paper.categories
        assert paper.first_author == "Alice Smith"
        assert paper.year == 2023

    def test_returns_none_for_not_found(self, requests_mock):
        requests_mock.register_uri(
            "GET", "https://export.arxiv.org/api/query",
            content=b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv API response</title>
</feed>""",
        )
        from tools.arxiv_client import fetch_metadata
        paper = fetch_metadata("9999.99999")
        assert paper is None


class TestSearch:
    def test_parses_feed(self, requests_mock):
        requests_mock.register_uri(
            "GET", "https://export.arxiv.org/api/query", content=ATOM_ENTRY
        )
        from tools.arxiv_client import search
        results = search("id:2301.12345")
        assert len(results) == 1
        assert results[0].arxiv_id == "2301.12345"


class TestDownloadPaper:
    def test_skips_existing_file(self, tmp_path):
        existing = tmp_path / "2301.12345.pdf"
        existing.write_bytes(b"%PDF-1.4 fake")
        from tools.arxiv_client import download_paper
        result = download_paper("2301.12345", output_dir=tmp_path)
        assert result.skipped is True
        assert result.size_kb > 0

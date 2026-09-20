import math

from bench import (
    BENCHMARK_CASES,
    HeadingChunker,
    LexicalHashEmbedder,
    build_chunk_documents,
    parse_policy_file,
)


def test_parse_policy_file_separates_front_matter_and_body(tmp_path):
    path = tmp_path / "policy.md"
    path.write_text(
        "---\ndoc_id: policy\naudience: buyer\n---\n\n# Tiêu đề\n\nNội dung.",
        encoding="utf-8",
    )
    metadata, body = parse_policy_file(path)
    assert metadata == {"doc_id": "policy", "audience": "buyer"}
    assert body.startswith("# Tiêu đề")
    assert "doc_id:" not in body


def test_heading_chunker_keeps_heading_with_section():
    text = "# Chính sách\nMở đầu.\n\n## Thời hạn\nMười lăm ngày."
    chunks = HeadingChunker(max_chars=100).chunk(text)
    assert chunks == ["# Chính sách\nMở đầu.", "## Thời hạn\nMười lăm ngày."]


def test_lexical_hash_embedder_is_deterministic_and_normalized():
    embedder = LexicalHashEmbedder(dim=64)
    first = embedder("Hoàn tiền qua Ví ShopeePay")
    second = embedder("  hoàn TIỀN qua ví ShopeePay  ")
    assert first == second
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_chunk_documents_keep_source_identity_and_strategy():
    metadata = {"doc_id": "return-window", "audience": "buyer"}
    docs = build_chunk_documents(
        metadata,
        "# Thời hạn\nMười lăm ngày.",
        "heading",
        HeadingChunker(max_chars=100),
    )
    assert len(docs) == 1
    assert docs[0].id == "return-window#heading#0"
    assert docs[0].metadata["doc_id"] == "return-window"
    assert docs[0].metadata["strategy"] == "heading"


def test_benchmark_defines_exactly_five_cases_and_one_filter_case():
    assert len(BENCHMARK_CASES) == 5
    assert all(
        {"query", "gold_doc_id", "evidence_terms"} <= case.keys()
        for case in BENCHMARK_CASES
    )
    assert any(case.get("metadata_filter") == {"audience": "seller"} for case in BENCHMARK_CASES)

import math

import bench
import src
from src import embeddings

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


def test_benchmark_runs_four_distinct_chunking_strategies(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "OUTPUT_PATH", tmp_path / "benchmark.txt")

    evaluations = bench.run_benchmark(embedding_fn=LexicalHashEmbedder(dim=64))

    assert [evaluation["name"] for evaluation in evaluations] == [
        "fixed_size",
        "recursive",
        "heading",
        "sentence",
    ]


def test_openrouter_embedder_batches_documents_and_caches_queries():
    assert hasattr(embeddings, "OpenRouterEmbedder")
    OpenRouterEmbedder = embeddings.OpenRouterEmbedder
    requests = []

    def fake_transport(url, headers, payload, timeout):
        requests.append((url, headers, payload, timeout))
        inputs = payload["input"]
        if isinstance(inputs, str):
            inputs = [inputs]
        return {
            "object": "list",
            "model": payload["model"],
            "data": [
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": [index + 1.0, 0.5],
                }
                for index, _ in enumerate(inputs)
            ],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        }

    embedder = OpenRouterEmbedder(api_key="test-key", transport=fake_transport)

    assert embedder.embed_documents(["doc one", "doc two"]) == [
        [1.0, 0.5],
        [2.0, 0.5],
    ]
    assert embedder.embed_query("question") == [1.0, 0.5]
    assert embedder.embed_query("question") == [1.0, 0.5]

    assert len(requests) == 2
    assert requests[0][0] == "https://openrouter.ai/api/v1/embeddings"
    assert requests[0][1]["Authorization"] == "Bearer test-key"
    assert requests[0][2] == {
        "model": "nvidia/nemotron-3-embed-1b:free",
        "input": ["doc one", "doc two"],
        "encoding_format": "float",
        "input_type": "search_document",
    }
    assert requests[1][2]["input_type"] == "search_query"


def test_benchmark_embedder_selection_is_explicit_and_key_safe():
    assert hasattr(bench, "create_benchmark_embedder")
    lexical = bench.create_benchmark_embedder(provider="lexical", api_key=None)
    semantic = bench.create_benchmark_embedder(
        provider="openrouter", api_key="test-key"
    )

    assert isinstance(lexical, LexicalHashEmbedder)
    assert isinstance(semantic, embeddings.OpenRouterEmbedder)


def test_benchmark_result_lines_do_not_end_with_whitespace():
    line = bench._result_line(
        1,
        {
            "score": 0.5,
            "content": "x" * 149 + " " + "tail",
            "metadata": {"doc_id": "policy"},
        },
    )

    assert line == line.rstrip()


def test_openrouter_embedder_is_available_from_public_package_api():
    assert src.OpenRouterEmbedder is embeddings.OpenRouterEmbedder

import main as app_main

from src.chunking import RecursiveChunker, SentenceChunker
from src.agent import KnowledgeBaseAgent
from src.models import Document
from src.store import EmbeddingStore


def test_sentence_chunker_preserves_terminal_punctuation():
    chunks = SentenceChunker(max_sentences_per_chunk=1).chunk("Một. Hai! Ba?")
    assert chunks == ["Một.", "Hai!", "Ba?"]


def test_sentence_chunker_ignores_whitespace_only_text():
    assert SentenceChunker().chunk("   \n\t") == []


def test_recursive_chunker_merges_small_adjacent_lines():
    chunks = RecursiveChunker(chunk_size=12).chunk("aa\nbb\ncc\ndd")
    assert chunks == ["aa\nbb\ncc\ndd"]


def test_recursive_chunker_hard_splits_without_separators():
    chunks = RecursiveChunker(separators=[], chunk_size=4).chunk("abcdefghij")
    assert chunks == ["abcd", "efgh", "ij"]


def _axis_embed(text: str) -> list[float]:
    return {"query": [1.0, 0.0], "near": [1.0, 0.0], "far": [0.0, 1.0]}[text]


def test_store_copies_metadata_and_hides_embeddings():
    metadata = {"audience": "buyer"}
    store = EmbeddingStore(embedding_fn=_axis_embed)
    store.add_documents([Document("doc", "near", metadata)])
    metadata["audience"] = "seller"
    result = store.search("query", top_k=1)[0]
    assert result["metadata"] == {"audience": "buyer", "doc_id": "doc"}
    assert "embedding" not in result


def test_filter_is_applied_before_top_k():
    store = EmbeddingStore(embedding_fn=_axis_embed)
    store.add_documents(
        [
            Document("seller", "near", {"audience": "seller"}),
            Document("buyer", "far", {"audience": "buyer"}),
        ]
    )
    result = store.search_with_filter(
        "query", top_k=1, metadata_filter={"audience": "buyer"}
    )
    assert [item["id"] for item in result] == ["buyer"]


def test_filter_with_no_matches_returns_empty_list():
    store = EmbeddingStore(embedding_fn=_axis_embed)
    store.add_documents([Document("doc", "near", {"audience": "buyer"})])
    assert (
        store.search_with_filter(
            "query", metadata_filter={"audience": "seller"}
        )
        == []
    )


def test_store_uses_batch_document_and_query_embedding_interfaces():
    class BatchEmbedder:
        def __init__(self):
            self.document_batches = []
            self.queries = []

        def __call__(self, text):
            raise AssertionError("single-text fallback must not be used")

        def embed_documents(self, texts):
            self.document_batches.append(list(texts))
            return [[1.0, 0.0], [0.0, 1.0]]

        def embed_query(self, text):
            self.queries.append(text)
            return [1.0, 0.0]

    embedder = BatchEmbedder()
    store = EmbeddingStore(embedding_fn=embedder)
    store.add_documents(
        [Document("first", "alpha", {}), Document("second", "beta", {})]
    )

    assert [item["id"] for item in store.search("question", top_k=2)] == [
        "first",
        "second",
    ]
    assert embedder.document_batches == [["alpha", "beta"]]
    assert embedder.queries == ["question"]


def test_agent_does_not_call_llm_for_empty_store():
    calls = []
    agent = KnowledgeBaseAgent(
        EmbeddingStore(), lambda prompt: calls.append(prompt) or "x"
    )
    answer = agent.answer("Câu hỏi")
    assert calls == []
    assert "không tìm thấy" in answer.lower()


def test_agent_prompt_numbers_context_and_requires_grounding():
    store = EmbeddingStore(embedding_fn=lambda text: [1.0])
    store.add_documents(
        [
            Document(
                "chunk-1",
                "Bằng chứng",
                {"source": "policy.md", "doc_id": "policy"},
            )
        ]
    )
    prompts = []
    agent = KnowledgeBaseAgent(
        store, lambda prompt: prompts.append(prompt) or "Trả lời"
    )
    assert agent.answer("Quy định là gì?", top_k=1) == "Trả lời"
    assert "[1]" in prompts[0]
    assert "policy.md" in prompts[0]
    assert "chỉ" in prompts[0].lower()


def test_configure_utf8_output_reconfigures_stream():
    calls = []

    class Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    app_main.configure_utf8_output(Stream())
    assert calls == [{"encoding": "utf-8", "errors": "replace"}]

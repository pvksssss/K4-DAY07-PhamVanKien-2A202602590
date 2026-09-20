from src.chunking import RecursiveChunker, SentenceChunker
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

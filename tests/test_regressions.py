from src.chunking import RecursiveChunker, SentenceChunker


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

# Complete Lab 07 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a complete, evidence-backed Lab 07 submission with passing core code, a traceable Shopee Vietnam return-and-refund policy corpus, a reproducible five-query benchmark, and completed reports.

**Architecture:** Keep the starter public APIs and implement the required behavior with a deterministic in-memory vector store. Build a separate benchmark pipeline that parses policy Markdown, applies three chunking strategies, ranks chunks with a dependency-free lexical hashing embedder, and writes evidence consumed by the reports and work log.

**Tech Stack:** Python 3.11, pytest, standard library, python-dotenv, Markdown/YAML-style front matter, CSV.

**Spec:** `docs/superpowers/specs/2026-09-20-complete-lab-07-design.md`

## Global Constraints

- Preserve all existing public function and method signatures in `src/`.
- Required code and tests must run without ChromaDB, neural-model packages, API keys, or network access.
- Use only public official Shopee Vietnam pages for corpus provenance; do not bypass robots.txt, authentication, CAPTCHA, or access controls.
- Corpus documents are concise Vietnamese paraphrases with source URLs, not copied full pages.
- Use exactly five benchmark questions and include at least one `audience` filter A/B run.
- Do not invent teammate names, group participation, test output, benchmark output, or policy facts.
- Update `THUC_HIEN.md` after every verified task with files, commands, results, and remaining work.

## Review Focus

1. Empty and whitespace-only text must not create meaningless chunks or division-by-zero errors; Task 1 adds explicit tests.
2. Recursive splitting must both hard-split oversized text and merge small adjacent pieces; Task 1 adds explicit tests.
3. Caller metadata must not be mutated and stored embeddings must not leak through search results; Task 2 adds explicit tests.
4. Metadata filtering must happen before top-k ranking, including no-filter and no-match cases; Task 2 adds explicit tests.
5. An empty knowledge base must not invoke the LLM, while a non-empty prompt must expose numbered, traceable sources; Task 3 adds explicit tests.

---

### Task 1: Establish baseline and implement chunking

**Files:**
- Modify: `src/chunking.py`
- Create: `tests/test_regressions.py`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: existing constructors for `FixedSizeChunker`, `SentenceChunker`, and `RecursiveChunker`.
- Produces: `SentenceChunker.chunk(text: str) -> list[str]`, `RecursiveChunker.chunk(text: str) -> list[str]`, `RecursiveChunker._split(current_text: str, remaining_separators: list[str]) -> list[str]`, `compute_similarity(vec_a, vec_b) -> float`, and `ChunkingStrategyComparator.compare(text, chunk_size) -> dict`.

- [ ] **Step 1: Run and record the red baseline**

Run: `pytest tests/ -v`

Expected: failures caused by the starter `NotImplementedError` branches. Copy the exact pass/fail counts into `THUC_HIEN.md`.

- [ ] **Step 2: Add focused failing chunking regressions**

Append these tests to `tests/test_regressions.py`:

```python
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
```

- [ ] **Step 3: Verify the new tests fail for the intended missing behavior**

Run: `pytest tests/test_regressions.py -v`

Expected: all four tests fail because `SentenceChunker` and `RecursiveChunker` raise `NotImplementedError`.

- [ ] **Step 4: Implement the minimal chunking behavior**

In `src/chunking.py`, use a punctuation-preserving boundary regex for sentences, group sentences by the configured maximum, implement recursive separator descent with hard splitting, then merge adjacent pieces while their joined length stays at or below `chunk_size`. Implement cosine similarity with zero-norm protection and return comparator entries with exact keys and zero-safe averages.

- [ ] **Step 5: Verify focused and starter chunking tests**

Run: `pytest tests/test_regressions.py tests/test_solution.py -k "Chunker or Similarity or Compare or sentence_chunker or recursive_chunker" -v`

Expected: every selected test passes.

- [ ] **Step 6: Update the work log and commit**

Record the commands and exact counts in `THUC_HIEN.md`, then run:

```powershell
git add -- src/chunking.py tests/test_regressions.py THUC_HIEN.md
git commit -m "feat: implement chunking and similarity"
```

### Task 2: Implement the in-memory embedding store

**Files:**
- Modify: `src/store.py`
- Modify: `tests/test_regressions.py`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: `Document`, injected `Callable[[str], list[float]]`, and `_dot`.
- Produces: normalized internal records and the existing `add_documents`, `search`, `get_collection_size`, `search_with_filter`, and `delete_document` methods.

- [ ] **Step 1: Add failing store regressions**

Append:

```python
from src.models import Document
from src.store import EmbeddingStore


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
    store.add_documents([
        Document("seller", "near", {"audience": "seller"}),
        Document("buyer", "far", {"audience": "buyer"}),
    ])
    result = store.search_with_filter(
        "query", top_k=1, metadata_filter={"audience": "buyer"}
    )
    assert [item["id"] for item in result] == ["buyer"]


def test_filter_with_no_matches_returns_empty_list():
    store = EmbeddingStore(embedding_fn=_axis_embed)
    store.add_documents([Document("doc", "near", {"audience": "buyer"})])
    assert store.search_with_filter(
        "query", metadata_filter={"audience": "seller"}
    ) == []
```

- [ ] **Step 2: Verify store regressions fail**

Run: `pytest tests/test_regressions.py -k "store or filter" -v`

Expected: failures at `EmbeddingStore.add_documents` because it is not implemented.

- [ ] **Step 3: Implement one shared in-memory record and ranking path**

Force `_use_chroma` to remain `False`. `_make_record` copies metadata, supplies `doc_id`, embeds content, and assigns a stable internal ID. `_search_records` embeds the query, calculates `_dot`, sorts descending, limits non-negative `top_k`, and returns copies without `embedding`. Public search methods select candidate records and delegate to this helper. Deletion rebuilds `_store` without matching `doc_id` records and returns whether its size changed.

- [ ] **Step 4: Verify all store tests**

Run: `pytest tests/test_regressions.py tests/test_solution.py -k "store or filter or delete or collection or search" -v`

Expected: every selected test passes.

- [ ] **Step 5: Update the work log and commit**

```powershell
git add -- src/store.py tests/test_regressions.py THUC_HIEN.md
git commit -m "feat: implement in-memory embedding store"
```

### Task 3: Implement the grounded knowledge-base agent

**Files:**
- Modify: `src/agent.py`
- Modify: `tests/test_regressions.py`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: `EmbeddingStore.search(question, top_k)` results containing `content` and `metadata`.
- Produces: `KnowledgeBaseAgent.answer(question: str, top_k: int = 3) -> str`.

- [ ] **Step 1: Add failing agent regressions**

Append:

```python
from src.agent import KnowledgeBaseAgent


def test_agent_does_not_call_llm_for_empty_store():
    calls = []
    agent = KnowledgeBaseAgent(EmbeddingStore(), lambda prompt: calls.append(prompt) or "x")
    answer = agent.answer("Câu hỏi")
    assert calls == []
    assert "không tìm thấy" in answer.lower()


def test_agent_prompt_numbers_context_and_requires_grounding():
    store = EmbeddingStore(embedding_fn=lambda text: [1.0])
    store.add_documents([
        Document("chunk-1", "Bằng chứng", {"source": "policy.md", "doc_id": "policy"})
    ])
    prompts = []
    agent = KnowledgeBaseAgent(store, lambda prompt: prompts.append(prompt) or "Trả lời")
    assert agent.answer("Quy định là gì?", top_k=1) == "Trả lời"
    assert "[1]" in prompts[0]
    assert "policy.md" in prompts[0]
    assert "chỉ" in prompts[0].lower()
```

- [ ] **Step 2: Verify agent regressions fail**

Run: `pytest tests/test_regressions.py -k "agent" -v`

Expected: failure because `KnowledgeBaseAgent` does not retain dependencies and `answer` raises `NotImplementedError`.

- [ ] **Step 3: Implement retrieval, prompt construction, and empty-store behavior**

Store `store` and `llm_fn` in `__init__`. In `answer`, retrieve results; if none, return a Vietnamese no-information message. Otherwise create `[n] Nguồn: ...` blocks, include the question, require answers only from context with citations, and return `llm_fn(prompt)`.

- [ ] **Step 4: Run agent tests and full core suite**

Run: `pytest tests/ -v`

Expected: all starter and regression tests pass.

- [ ] **Step 5: Run the manual application**

Run: `python main.py "Chunking là gì?"`

Expected: exit code 0, documents loaded, search results printed, and a non-empty demo-agent answer.

- [ ] **Step 6: Update the work log and commit**

```powershell
git add -- src/agent.py tests/test_regressions.py THUC_HIEN.md
git commit -m "feat: implement grounded knowledge agent"
```

### Task 4: Build and audit the return-and-refund policy corpus

**Files:**
- Create: `data/shopee-return-refund/return-eligibility.md`
- Create: `data/shopee-return-refund/return-window.md`
- Create: `data/shopee-return-refund/return-evidence.md`
- Create: `data/shopee-return-refund/return-shipping-and-packaging.md`
- Create: `data/shopee-return-refund/refund-methods-and-time.md`
- Create: `data/shopee-return-refund/seller-return-refund-obligations.md`
- Create: `data/shopee-return-refund/sources.csv`
- Create: `tests/test_submission_assets.py`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: official public Shopee Vietnam policy pages verified on the collection date.
- Produces: six Markdown files with parseable front matter and a one-to-one CSV inventory.

- [ ] **Step 1: Add a failing corpus audit test**

Create `tests/test_submission_assets.py` with a small standard-library front-matter parser and assertions that exactly six Markdown files exist, required keys are non-empty, `doc_id == path.stem`, IDs are unique, audiences include `buyer` and `seller`, every `source_url` uses HTTPS on an official Shopee Vietnam domain, and CSV IDs exactly equal document IDs.

- [ ] **Step 2: Verify the audit fails because the corpus is absent**

Run: `pytest tests/test_submission_assets.py -v`

Expected: failure reporting that `data/shopee-return-refund` or its six documents do not exist.

- [ ] **Step 3: Verify six official source pages**

Search current official Shopee Vietnam help/policy pages for the six named return/refund topics: eligibility, request window, evidence, return shipping/packaging, refund methods/timing, and seller obligations. Record direct canonical page URLs, visible update/effective dates when stated, and concise facts needed for the five benchmark answers. Reject search-result URLs, third-party summaries, inaccessible pages, and pages whose automated access is disallowed.

- [ ] **Step 4: Write clean Vietnamese policy documents and inventory**

Each file starts with the required front matter and contains focused headings, conditions, exceptions, deadlines, and procedures supported by its source. Use `document_version: "not-stated"` when the official page gives no version. Add one matching CSV row per document with `license_or_permission=public-source`.

- [ ] **Step 5: Run the corpus audit**

Run: `pytest tests/test_submission_assets.py -v`

Expected: all corpus-audit tests pass.

- [ ] **Step 6: Update the work log and commit**

```powershell
git add -- data/shopee-return-refund tests/test_submission_assets.py THUC_HIEN.md
git commit -m "data: add Shopee return and refund corpus"
```

### Task 5: Implement the reproducible benchmark

**Files:**
- Create: `bench.py`
- Create: `tests/test_benchmark.py`
- Create: `ket_qua_benchmark.txt`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: `data/shopee-return-refund/*.md`, `Document`, `EmbeddingStore`, `FixedSizeChunker`, and `RecursiveChunker`.
- Produces: `parse_policy_file(path)`, `HeadingChunker.chunk(text)`, `LexicalHashEmbedder.__call__(text)`, benchmark result dictionaries, and deterministic text output.

- [ ] **Step 1: Add failing benchmark unit tests**

Create tests that assert: front matter and body are separated; heading chunks retain each heading with its section; lexical embeddings are normalized and give identical vectors for identical normalized text; chunk documents retain original `doc_id` and strategy metadata; exactly five benchmark cases exist; and one case declares an `audience` filter.

- [ ] **Step 2: Verify benchmark tests fail because `bench.py` is absent**

Run: `pytest tests/test_benchmark.py -v`

Expected: collection error `ModuleNotFoundError: No module named 'bench'`.

- [ ] **Step 3: Implement benchmark components**

Use only the standard library and project APIs. Tokenize lowercase Unicode words, hash tokens into a fixed vector, count signed buckets, and normalize the vector. Parse simple scalar front-matter values, build fixed/recursive/heading chunks, and add chunk-level metadata. Define five questions with `query`, `gold_doc_id`, `evidence_terms`, and optional filter. Score by the first rank whose normalized content contains every evidence term.

- [ ] **Step 4: Implement deterministic output generation**

For each strategy, print configuration, chunk count, average length, each question's top three ranks with score/doc/chunk preview, evidence rank, and total `/10`. Run the filter-designated question with and without filtering. Select a genuine zero/one-point case as failure analysis; if all cases score two, report the smallest score margin and its retrieval risk instead of fabricating failure.

- [ ] **Step 5: Verify benchmark unit tests and generate evidence**

Run: `pytest tests/test_benchmark.py -v`

Then run: `python bench.py`

Expected: tests pass, command exits 0, and `ket_qua_benchmark.txt` contains three strategies, five questions, an A/B filter section, totals, and failure/risk analysis.

- [ ] **Step 6: Update the work log and commit**

```powershell
git add -- bench.py tests/test_benchmark.py ket_qua_benchmark.txt THUC_HIEN.md
git commit -m "feat: add retrieval strategy benchmark"
```

### Task 6: Complete the individual and repository experiment reports

**Files:**
- Modify: `report/REPORT_CANHAN.md`
- Modify: `report/REPORT_NHOM.md`
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: fresh pytest output, corpus inventory, and `ket_qua_benchmark.txt`.
- Produces: completed reports with no template prompts or invented claims.

- [ ] **Step 1: Capture similarity measurements and fresh verification data**

Run a deterministic Python snippet using five declared vector pairs through `compute_similarity`, then run `pytest tests/ -v`. Save exact values and counts for the reports.

- [ ] **Step 2: Complete `REPORT_CANHAN.md`**

Fill student identity, warm-up calculations, algorithm explanations, exact test output, five similarity predictions/measurements, the chosen personal heading-based strategy, five retrieval results, limitations, and lessons. The 10,000-character calculations must show 23 chunks at overlap 50 and 25 chunks at overlap 100.

- [ ] **Step 3: Complete `REPORT_NHOM.md` as an honest repository experiment**

Identify this as a single-person submission with three experimental configurations, list all six documents and metadata, include exact strategy metrics, the same five questions/gold answers, filter A/B findings, failure analysis, and demo talking points. Do not attribute configurations to nonexistent teammates.

- [ ] **Step 4: Scan for unfilled template text**

Run a repository search over both reports for bracket prompts, blank score markers, `Viết`, `Dán`, and unchecked governance boxes. Resolve every real template remnant while preserving literal code notation.

- [ ] **Step 5: Update the work log and commit**

```powershell
git add -- report/REPORT_CANHAN.md report/REPORT_NHOM.md THUC_HIEN.md
git commit -m "docs: complete Lab 07 reports"
```

### Task 7: Final verification and submission audit

**Files:**
- Modify: `THUC_HIEN.md`

**Interfaces:**
- Consumes: all repository deliverables.
- Produces: final verification evidence and an accurate completion checklist.

- [ ] **Step 1: Run the complete automated suite**

Run: `pytest tests/ -v`

Expected: zero failures, including starter, regression, corpus, and benchmark tests.

- [ ] **Step 2: Run both executable workflows from a clean invocation**

Run:

```powershell
python main.py "Chunking là gì?"
python bench.py
```

Expected: both exit 0 and the second command deterministically regenerates `ket_qua_benchmark.txt`.

- [ ] **Step 3: Audit implementation and repository hygiene**

Search `src/` for `TODO`, `NotImplementedError`, and bare `pass`; inspect `git status --short`; verify `.env` and `.venv` are not tracked; verify `sources.csv` and all required deliverables exist.

- [ ] **Step 4: Reconcile reports and log against evidence**

Check every reported test count, benchmark score, chunk count, source URL, and checklist item against fresh command output. Correct stale values before making completion claims.

- [ ] **Step 5: Record final evidence and commit**

Write the exact commands, exit codes, counts, remaining limitations, and final deliverable list in `THUC_HIEN.md`, then run:

```powershell
git add -- THUC_HIEN.md ket_qua_benchmark.txt report/REPORT_CANHAN.md report/REPORT_NHOM.md
git commit -m "chore: record final Lab 07 verification"
```

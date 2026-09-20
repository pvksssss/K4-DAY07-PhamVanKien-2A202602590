# Complete Lab 07 Design

## Objective

Turn the starter repository into a complete, reproducible Lab 07 submission for Phạm Văn Kiên (`2A202602590`). The finished repository must implement the required chunking, vector-store, and RAG-agent behavior; include a traceable public e-commerce policy corpus; run a five-query retrieval benchmark; and contain reports whose claims match generated evidence.

## Scope

The work covers four connected deliverables:

1. Complete the public APIs in `src/chunking.py`, `src/store.py`, and `src/agent.py` without changing their existing signatures.
2. Build a six-document Vietnamese corpus derived from current public official eBay policy pages, with buyer and seller audiences represented and one inventory row per document.
3. Add a reproducible benchmark that compares fixed-size, recursive, and heading/section-aware chunking and records retrieval results for exactly five questions.
4. Replace the report templates with an honest individual report and a repository-level experiment report. No unprovided teammate names or group participation claims will be invented.

Out of scope: production persistence, a web interface, authenticated crawling, paid APIs, and bypassing robots.txt or access controls.

## Core Implementation

### Chunking

`SentenceChunker` will preserve sentence-ending punctuation, group at most `max_sentences_per_chunk` sentences, trim whitespace, and return an empty list for empty input.

`RecursiveChunker` will split using the configured separators in priority order. Oversized pieces recurse to smaller separators; adjacent small pieces are merged while respecting `chunk_size`. If no separator remains, text is cut into hard size-bounded slices. Empty input returns an empty list.

`compute_similarity` will calculate cosine similarity and return `0.0` when either vector has zero magnitude.

`ChunkingStrategyComparator` will return the exact keys `fixed_size`, `by_sentences`, and `recursive`. Each entry will contain `count`, `avg_length`, and `chunks`, with a zero average for empty input.

### Vector store

`EmbeddingStore` will use the deterministic in-memory backend for required behavior, regardless of whether ChromaDB happens to be installed. Each stored record will contain an ID, content, copied metadata, and embedding. Metadata will always contain `doc_id`, defaulting to the input document ID only when the caller did not supply a source-document ID.

Both `search()` and `search_with_filter()` will delegate ranking to the same helper. Filtering happens before ranking. Results are sorted descending by score, limited to `top_k`, and do not expose raw embedding vectors. Deletion removes every chunk whose metadata `doc_id` matches the requested source document.

### RAG agent

`KnowledgeBaseAgent.answer()` will retrieve top-k chunks, construct a grounded prompt with numbered context blocks and source identifiers, and call the injected LLM function. The prompt will instruct the model to use only supplied evidence and acknowledge missing evidence. An empty store will return a direct no-information response without calling the LLM.

## Corpus and Provenance

The corpus will live under `data/ebay-policies/` and contain six focused Markdown documents. Each document will be a concise Vietnamese paraphrase of a current official, publicly accessible eBay policy page rather than a long copied passage. The set will cover returns/refunds, money-back protection, item-not-received handling, seller return obligations, warranty or condition obligations, and abusive or invalid claims.

Every file will have YAML front matter containing:

- `doc_id`
- `title`
- `source_url`
- `retrieved_at` set to the actual collection date
- `document_version`, using the stated effective/update date or `not-stated`
- `audience` with at least `buyer` and `seller` represented
- `category`
- `language: vi`

`data/ebay-policies/sources.csv` will map one-to-one to the six Markdown files and record the public-source basis. Source discovery and verification will use official eBay pages only. If a selected page is inaccessible or disallows automated access, it will be replaced by another official public page rather than bypassed.

## Benchmark Design

`bench.py` will parse YAML front matter without introducing a new required dependency, separate metadata from body text, create chunk-level `Document` objects, and retain the original `doc_id` in every chunk.

Three strategies will be evaluated on the same corpus and questions:

- fixed-size chunks with overlap;
- recursive structural chunks;
- a heading/section-aware chunker designed for policy documents.

The benchmark will use a dependency-free normalized lexical hashing embedder so retrieval reflects shared Vietnamese policy terms instead of the starter `MockEmbedder`'s random MD5-derived vectors. The implementation will be deterministic and clearly labelled as a local lexical baseline, not presented as a neural semantic model.

Exactly five verifiable questions will be defined with gold evidence markers. At least one question will be run both with and without an `audience` metadata filter. Scoring will inspect retrieved chunk contents, not only `doc_id`: 2 points for answer evidence at rank 1, 1 point at rank 2 or 3, and 0 when evidence is absent. Output will include top-three chunks, scores, strategy totals, the filter A/B comparison, and one real failure analysis in `ket_qua_benchmark.txt`.

## Reports

`report/REPORT_CANHAN.md` will identify Phạm Văn Kiên and `2A202602590`, explain the implemented algorithms, include the fresh test output, record five similarity predictions and measured results, and summarize the individual's benchmark results.

`report/REPORT_NHOM.md` will document the repository experiment as a single-person submission because no teammate information was supplied. It will compare the three strategies as experimental configurations and will not claim that unnamed people performed work. It will include corpus inventory, metadata schema, five shared benchmark questions and gold answers, strategy comparison, filter evidence, failure analysis, and presentation points.

## Work Log

`THUC_HIEN.md` at the repository root will be maintained throughout implementation. Each completed stage will record the date, files changed, commands run, observed results, and remaining work. Entries must report actual evidence and must not mark a stage complete before its verification command succeeds.

## Testing and Evidence

Existing tests are the primary contract. They will be run before implementation to establish the expected red baseline, then in focused groups during implementation, and finally as a complete suite. Additional regression tests will cover important behavior not fully asserted by the starter suite: punctuation preservation, recursive chunk merging and hard-split fallback, metadata copying, filter-before-ranking, hidden embeddings, empty-store agent behavior, and grounded prompt construction.

Final verification consists of:

1. `pytest tests/ -v` with all tests passing.
2. `python main.py "Chunking là gì?"` completing successfully.
3. `python bench.py` regenerating `ket_qua_benchmark.txt` successfully.
4. A corpus audit confirming six unique documents, required metadata, one-to-one `sources.csv`, and both buyer and seller audiences.
5. A repository scan confirming no remaining implementation `TODO` or `NotImplementedError` in `src/`, and no secrets or virtual-environment files tracked.

## Error Handling and Integrity

Empty text, zero vectors, empty stores, missing optional source fields, and filters with no matches will produce valid empty or zero results rather than exceptions. Benchmark and report values will be generated from actual commands. Missing personal or team information will be described honestly rather than filled with fabricated details. External policy facts will be supported by the corpus and official source URLs, with collection dates recorded.

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from pathlib import Path
from typing import Protocol

from main import configure_utf8_output
from src import Document, EmbeddingStore, FixedSizeChunker, RecursiveChunker


CORPUS_FILES = [
    Path("data/ecommerce/buyer-dispute-resolution-policy.md"),
    Path("data/ecommerce/return-refund-policy.md"),
    Path("data/ecommerce/seller-penalty-violation-policy.md"),
    Path("data/ecommerce/seller-warranty-policy.md"),
    Path("data/ecommerce/shipping-fee-refund-policy.md"),
]
OUTPUT_PATH = Path("ket_qua_benchmark.txt")

BENCHMARK_CASES = [
    {
        "query": "Hai bên thương lượng tranh chấp trong bao lâu trước khi yêu cầu sàn can thiệp?",
        "gold_doc_id": "buyer-dispute-resolution-policy",
        "evidence_terms": ["24 giờ", "yêu cầu sàn can thiệp"],
        "gold_answer": "Hai bên có 24 giờ thương lượng trước khi một bên yêu cầu sàn can thiệp.",
    },
    {
        "query": "Thời hạn trả hàng của Shopee Mall và shop thường là bao nhiêu ngày?",
        "gold_doc_id": "return-refund-policy",
        "evidence_terms": ["7 ngày", "3 ngày"],
        "gold_answer": "Shopee Mall là 7 ngày và shop thường là 3 ngày kể từ khi nhận hàng thành công.",
    },
    {
        "query": "Người bán tích lũy 12 điểm phạt trở lên sẽ chịu chế tài gì?",
        "gold_doc_id": "seller-penalty-violation-policy",
        "evidence_terms": ["12 điểm", "28 ngày"],
        "gold_answer": "Gian hàng có thể bị khóa 28 ngày hoặc chấm dứt hợp tác vĩnh viễn.",
    },
    {
        "query": "Bên chịu trách nhiệm phải phản hồi yêu cầu hỗ trợ và xử lý trong thời hạn nào?",
        "gold_doc_id": "seller-warranty-policy",
        "evidence_terms": ["48 giờ làm việc", "14 ngày làm việc"],
        "gold_answer": "Phản hồi trong 48 giờ làm việc và xử lý không quá 14 ngày làm việc.",
        "metadata_filter": {"audience": "seller"},
    },
    {
        "query": "Hạn mức hoàn cước tối đa cho đơn nội tỉnh và liên tỉnh là bao nhiêu?",
        "gold_doc_id": "shipping-fee-refund-policy",
        "evidence_terms": ["50.000 vnđ", "100.000 vnđ"],
        "gold_answer": "Tối đa 50.000 VNĐ cho đơn nội tỉnh và 100.000 VNĐ cho đơn liên tỉnh.",
    },
]


class Chunker(Protocol):
    def chunk(self, text: str) -> list[str]: ...


def parse_policy_file(path: Path) -> tuple[dict[str, str], str]:
    """Parse the simple scalar YAML front matter used by the lab corpus."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"Missing front matter: {path}")
    try:
        _, raw_metadata, body = text.split("---", 2)
    except ValueError as error:
        raise ValueError(f"Invalid front matter: {path}") from error

    metadata: dict[str, str] = {}
    for raw_line in raw_metadata.strip().splitlines():
        if not raw_line.strip():
            continue
        key, separator, value = raw_line.partition(":")
        if not separator:
            raise ValueError(f"Invalid metadata line in {path}: {raw_line}")
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, body.strip()


class HeadingChunker:
    """Keep Markdown headings attached to their following policy section."""

    def __init__(self, max_chars: int = 700) -> None:
        self.max_chars = max(1, max_chars)

    def chunk(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        sections = [
            section.strip()
            for section in re.split(r"(?=^#{1,6}\s+)", text, flags=re.MULTILINE)
            if section.strip()
        ]
        chunks: list[str] = []
        splitter = RecursiveChunker(chunk_size=self.max_chars)
        for section in sections:
            chunks.extend(splitter.chunk(section))
        return chunks


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).lower()
    return " ".join(re.findall(r"[\w%–-]+", normalized, flags=re.UNICODE))


class LexicalHashEmbedder:
    """Dependency-free, deterministic lexical baseline for the lab benchmark."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = max(8, dim)
        self._backend_name = f"lexical-hash-{self.dim}"

    def __call__(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _normalize_text(text).split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0.0:
            return vector
        return [value / magnitude for value in vector]


def build_chunk_documents(
    metadata: dict[str, str],
    body: str,
    strategy_name: str,
    chunker: Chunker,
) -> list[Document]:
    doc_id = metadata["doc_id"]
    documents = []
    for index, content in enumerate(chunker.chunk(body)):
        chunk_metadata = dict(metadata)
        chunk_metadata.update(
            {
                "doc_id": doc_id,
                "chunk_index": index,
                "strategy": strategy_name,
            }
        )
        documents.append(
            Document(
                id=f"{doc_id}#{strategy_name}#{index}",
                content=content,
                metadata=chunk_metadata,
            )
        )
    return documents


def load_corpus() -> list[tuple[dict[str, str], str]]:
    return [parse_policy_file(path) for path in CORPUS_FILES]


def _evidence_rank(results: list[dict], evidence_terms: list[str]) -> int | None:
    normalized_terms = [_normalize_text(term) for term in evidence_terms]
    for rank, result in enumerate(results, start=1):
        content = _normalize_text(result["content"])
        if all(term in content for term in normalized_terms):
            return rank
    return None


def _score_for_rank(rank: int | None) -> int:
    if rank == 1:
        return 2
    if rank in {2, 3}:
        return 1
    return 0


def evaluate_strategy(
    strategy_name: str,
    chunker: Chunker,
    corpus: list[tuple[dict[str, str], str]],
) -> dict:
    documents = [
        chunk
        for metadata, body in corpus
        for chunk in build_chunk_documents(metadata, body, strategy_name, chunker)
    ]
    store = EmbeddingStore(
        collection_name=f"benchmark-{strategy_name}",
        embedding_fn=LexicalHashEmbedder(),
    )
    store.add_documents(documents)

    cases = []
    for case in BENCHMARK_CASES:
        metadata_filter = case.get("metadata_filter")
        results = store.search_with_filter(
            case["query"], top_k=3, metadata_filter=metadata_filter
        )
        rank = _evidence_rank(results, case["evidence_terms"])
        cases.append(
            {
                **case,
                "results": results,
                "evidence_rank": rank,
                "score": _score_for_rank(rank),
            }
        )

    filter_case = next(case for case in BENCHMARK_CASES if case.get("metadata_filter"))
    unfiltered_results = store.search(filter_case["query"], top_k=3)
    filtered_results = store.search_with_filter(
        filter_case["query"],
        top_k=3,
        metadata_filter=filter_case["metadata_filter"],
    )
    return {
        "name": strategy_name,
        "chunk_count": len(documents),
        "avg_length": (
            sum(len(document.content) for document in documents) / len(documents)
            if documents
            else 0.0
        ),
        "cases": cases,
        "total": sum(case["score"] for case in cases),
        "filter_ab": {
            "query": filter_case["query"],
            "unfiltered": unfiltered_results,
            "filtered": filtered_results,
        },
    }


def _result_line(rank: int, result: dict) -> str:
    preview = " ".join(result["content"].split())[:150]
    return (
        f"    {rank}. score={result['score']:.4f} "
        f"doc_id={result['metadata'].get('doc_id')} | {preview}"
    )


def render_report(evaluations: list[dict]) -> str:
    lines = [
        "KẾT QUẢ BENCHMARK — CHÍNH SÁCH TRẢ HÀNG/HOÀN TIỀN SHOPEE",
        "Corpus: 5 tài liệu thương mại điện tử do người dùng cung cấp tại data/ecommerce/",
        "Embedding: lexical-hash-512 (deterministic, không phải mô hình ngữ nghĩa)",
        "Cách chấm: evidence ở top-1 = 2; top-2/3 = 1; vắng top-3 = 0",
        "",
    ]
    for evaluation in evaluations:
        lines.extend(
            [
                f"=== Chiến lược: {evaluation['name']} ===",
                f"Số chunk: {evaluation['chunk_count']}",
                f"Độ dài trung bình: {evaluation['avg_length']:.2f}",
            ]
        )
        for index, case in enumerate(evaluation["cases"], start=1):
            lines.append(f"Q{index}: {case['query']}")
            lines.append(f"  Gold: {case['gold_answer']}")
            lines.append(
                f"  Evidence rank: {case['evidence_rank'] or 'không có'} | Điểm: {case['score']}/2"
            )
            lines.extend(
                _result_line(rank, result)
                for rank, result in enumerate(case["results"], start=1)
            )
        lines.append(f"Tổng điểm: {evaluation['total']}/10")
        lines.append("A/B metadata filter (audience=seller):")
        lines.append(
            "  Không lọc: "
            + ", ".join(
                result["metadata"].get("doc_id", "?")
                for result in evaluation["filter_ab"]["unfiltered"]
            )
        )
        lines.append(
            "  Có lọc: "
            + ", ".join(
                result["metadata"].get("doc_id", "?")
                for result in evaluation["filter_ab"]["filtered"]
            )
        )
        lines.append("")

    weakest = min(
        (
            (case["score"], evaluation["name"], index, case)
            for evaluation in evaluations
            for index, case in enumerate(evaluation["cases"], start=1)
        ),
        key=lambda item: item[0],
    )
    lines.append("=== Phân tích lỗi/rủi ro ===")
    if weakest[0] < 2:
        lines.append(
            f"Failure thật: {weakest[1]} Q{weakest[2]} chỉ đạt {weakest[0]}/2; "
            "lexical hashing ưu tiên từ trùng lặp và có thể xếp chunk cùng chủ đề nhưng thiếu đủ bằng chứng lên cao."
        )
    else:
        lines.append(
            "Không có câu 0/1 điểm trong lần chạy này. Rủi ro nhỏ nhất vẫn là lexical hashing "
            "không hiểu từ đồng nghĩa; cần kiểm tra trực tiếp nội dung chunk thay vì chỉ tin score."
        )
    return "\n".join(lines).rstrip() + "\n"


def run_benchmark() -> list[dict]:
    corpus = load_corpus()
    strategies: list[tuple[str, Chunker]] = [
        ("fixed_size", FixedSizeChunker(chunk_size=450, overlap=80)),
        ("recursive", RecursiveChunker(chunk_size=450)),
        ("heading", HeadingChunker(max_chars=700)),
    ]
    evaluations = [
        evaluate_strategy(name, chunker, corpus) for name, chunker in strategies
    ]
    OUTPUT_PATH.write_text(render_report(evaluations), encoding="utf-8")
    return evaluations


def main() -> int:
    configure_utf8_output()
    evaluations = run_benchmark()
    print(OUTPUT_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

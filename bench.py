from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from main import configure_utf8_output
from src import Document, EmbeddingStore, FixedSizeChunker, RecursiveChunker
from src.embeddings import OpenRouterEmbedder


CORPUS_FILES = [
    Path("data/shopee-return-refund/return-eligibility.md"),
    Path("data/shopee-return-refund/return-window.md"),
    Path("data/shopee-return-refund/return-evidence.md"),
    Path("data/shopee-return-refund/return-shipping-and-packaging.md"),
    Path("data/shopee-return-refund/refund-methods-and-time.md"),
    Path("data/shopee-return-refund/seller-return-refund-obligations.md"),
]
OUTPUT_PATH = Path("ket_qua_benchmark.txt")

BENCHMARK_CASES = [
    {
        "query": "Các lý do liên quan đến sản phẩm gồm hư hỏng, bể vỡ, sai sản phẩm hoặc thiếu phụ kiện là gì?",
        "gold_doc_id": "return-eligibility",
        "evidence_terms": ["hư hỏng", "sai sản phẩm"],
        "gold_answer": "Có thể yêu cầu khi hàng hư hỏng, sai hoặc thiếu hàng/phụ kiện, khác mô tả hay nghi là hàng giả/nhái.",
    },
    {
        "query": "Đối với thực phẩm tươi sống hoặc đông lạnh, trừ lý do chưa nhận được hàng, thời hạn ngắn hơn là bao lâu?",
        "gold_doc_id": "return-window",
        "evidence_terms": ["thực phẩm tươi sống", "24 giờ"],
        "gold_answer": "Thời hạn là 24 giờ kể từ khi đơn được cập nhật giao hàng thành công.",
    },
    {
        "query": "Khi nghi ngờ hàng giả, người mua nên cung cấp bằng chứng kỹ thuật nào?",
        "gold_doc_id": "return-evidence",
        "evidence_terms": ["mã qr", "số seri"],
        "gold_answer": "Có thể cung cấp quá trình quét mã QR, kiểm tra số seri và đối chiếu bao bì với hàng chính hãng.",
    },
    {
        "query": "Tiền hoàn về thẻ tín dụng hoặc ghi nợ thường mất bao lâu?",
        "gold_doc_id": "refund-methods-and-time",
        "evidence_terms": ["thẻ tín dụng", "7–14 ngày làm việc"],
        "gold_answer": "Thẻ tín dụng hoặc ghi nợ thường mất 7–14 ngày làm việc, tùy ngân hàng phát hành.",
    },
    {
        "query": "Nếu người bán hoàn dưới 50% giá trị sản phẩm, Shopee có thể xử lý thế nào?",
        "gold_doc_id": "seller-return-refund-obligations",
        "evidence_terms": ["50%", "cấn trừ"],
        "gold_answer": "Shopee có thể cấn trừ phần chênh lệch từ Số dư Tài khoản Shopee của người bán để trả người mua.",
        "metadata_filter": {"audience": "seller"},
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


def create_benchmark_embedder(
    provider: str | None = None, api_key: str | None = None
):
    selected = (provider or os.getenv("BENCHMARK_EMBEDDING", "auto")).strip().lower()
    resolved_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
    if selected == "lexical" or (selected == "auto" and not resolved_key):
        return LexicalHashEmbedder()
    if selected in {"auto", "openrouter"}:
        return OpenRouterEmbedder(api_key=resolved_key)
    raise ValueError(
        "BENCHMARK_EMBEDDING must be one of: auto, lexical, openrouter"
    )


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
    embedding_fn=None,
) -> dict:
    documents = [
        chunk
        for metadata, body in corpus
        for chunk in build_chunk_documents(metadata, body, strategy_name, chunker)
    ]
    embedder = embedding_fn or LexicalHashEmbedder()
    store = EmbeddingStore(
        collection_name=f"benchmark-{strategy_name}",
        embedding_fn=embedder,
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
        "embedding_backend": getattr(
            embedder, "_backend_name", embedder.__class__.__name__
        ),
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
    preview = " ".join(result["content"].split())[:150].rstrip()
    return (
        f"    {rank}. score={result['score']:.4f} "
        f"doc_id={result['metadata'].get('doc_id')} | {preview}"
    )


def render_report(evaluations: list[dict]) -> str:
    lines = [
        "KẾT QUẢ BENCHMARK — CHÍNH SÁCH TRẢ HÀNG/HOÀN TIỀN SHOPEE",
        "Corpus: 6 tài liệu Shopee đã crawl và chuẩn hóa tại data/shopee-return-refund/",
        f"Embedding: {evaluations[0]['embedding_backend']}",
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
            "embedding backend có thể xếp chunk cùng chủ đề nhưng thiếu đủ bằng chứng lên cao."
        )
    else:
        lines.append(
            "Không có câu 0/1 điểm trong lần chạy này. Rủi ro nhỏ nhất vẫn là lexical hashing "
            "không hiểu từ đồng nghĩa; cần kiểm tra trực tiếp nội dung chunk thay vì chỉ tin score."
        )
    return "\n".join(lines).rstrip() + "\n"


def run_benchmark(embedding_fn=None) -> list[dict]:
    corpus = load_corpus()
    embedder = embedding_fn or create_benchmark_embedder()
    strategies: list[tuple[str, Chunker]] = [
        ("fixed_size", FixedSizeChunker(chunk_size=450, overlap=80)),
        ("recursive", RecursiveChunker(chunk_size=450)),
        ("heading", HeadingChunker(max_chars=700)),
    ]
    evaluations = [
        evaluate_strategy(name, chunker, corpus, embedder)
        for name, chunker in strategies
    ]
    OUTPUT_PATH.write_text(render_report(evaluations), encoding="utf-8")
    return evaluations


def main() -> int:
    configure_utf8_output()
    load_dotenv(override=False)
    evaluations = run_benchmark()
    print(OUTPUT_PATH.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

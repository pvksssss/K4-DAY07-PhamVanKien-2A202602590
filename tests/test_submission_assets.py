import csv
from pathlib import Path
from urllib.parse import urlparse


CORPUS_DIR = Path("data/shopee-return-refund")
EXPECTED_FILES = {
    "return-eligibility.md",
    "return-window.md",
    "return-evidence.md",
    "return-shipping-and-packaging.md",
    "refund-methods-and-time.md",
    "seller-return-refund-obligations.md",
}
REQUIRED_METADATA = {
    "doc_id",
    "title",
    "source_url",
    "retrieved_at",
    "document_version",
    "audience",
    "category",
    "language",
}


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} thiếu YAML front matter"
    _, raw_metadata, body = text.split("---", 2)
    assert body.strip(), f"{path} không có nội dung"
    metadata = {}
    for line in raw_metadata.strip().splitlines():
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def test_return_refund_corpus_has_exactly_six_documents():
    assert CORPUS_DIR.is_dir()
    assert {path.name for path in CORPUS_DIR.glob("*.md")} == EXPECTED_FILES


def test_every_document_has_traceable_metadata():
    seen_ids = set()
    audiences = set()
    for path in sorted(CORPUS_DIR.glob("*.md")):
        metadata = parse_front_matter(path)
        assert REQUIRED_METADATA <= metadata.keys()
        assert all(metadata[key] for key in REQUIRED_METADATA)
        assert metadata["doc_id"] == path.stem
        assert metadata["doc_id"] not in seen_ids
        assert metadata["language"] == "vi"
        parsed_url = urlparse(metadata["source_url"])
        assert parsed_url.scheme == "https"
        assert parsed_url.hostname and (
            parsed_url.hostname == "shopee.vn"
            or parsed_url.hostname.endswith(".shopee.vn")
        )
        seen_ids.add(metadata["doc_id"])
        audiences.add(metadata["audience"])
    assert {"buyer", "seller"} <= audiences


def test_sources_csv_matches_documents_one_to_one():
    with (CORPUS_DIR / "sources.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    csv_ids = {row["doc_id"] for row in rows}
    document_ids = {path.stem for path in CORPUS_DIR.glob("*.md")}
    assert len(rows) == 6
    assert csv_ids == document_ids
    assert all(row["license_or_permission"] == "public-source" for row in rows)

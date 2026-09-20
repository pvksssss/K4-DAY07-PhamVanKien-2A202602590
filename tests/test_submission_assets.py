import csv
from pathlib import Path
from urllib.parse import urlparse


CORPUS_FILES = [
    Path("data/ecommerce/buyer-dispute-resolution-policy.md"),
    Path("data/ecommerce/return-refund-policy.md"),
    Path("data/ecommerce/seller-penalty-violation-policy.md"),
    Path("data/ecommerce/seller-warranty-policy.md"),
    Path("data/ecommerce/shipping-fee-refund-policy.md"),
]
MANIFEST_PATH = Path("data/ecommerce_sources.csv")
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


def test_ecommerce_corpus_has_exactly_five_selected_documents():
    assert len(CORPUS_FILES) == 5
    assert all(path.is_file() for path in CORPUS_FILES)


def test_every_document_has_traceable_metadata():
    seen_ids = set()
    audiences = set()
    for path in CORPUS_FILES:
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
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    csv_ids = {row["doc_id"] for row in rows}
    document_ids = {path.stem for path in CORPUS_FILES}
    assert len(rows) == 5
    assert csv_ids == document_ids
    assert all(row["license_or_permission"] == "user-provided" for row in rows)

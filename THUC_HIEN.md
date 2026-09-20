# Nhật ký thực hiện Lab 07

Tài liệu này ghi lại các công việc đã thực hiện, thay đổi trong repository và bằng chứng kiểm tra. Trạng thái chỉ được đánh dấu hoàn thành sau khi lệnh xác minh tương ứng chạy thành công.

## Thông tin bài làm

- Sinh viên: Phạm Văn Kiên
- Mã số: `2A202602590`
- Chủ đề: Chunking, Embedding Store và RAG trên chính sách thương mại điện tử
- Ngày bắt đầu: 2026-09-20

## Nhật ký

### 2026-09-20 — Khảo sát và thiết kế

- [x] Đọc các tài liệu Markdown, rubric, bài tập và hướng dẫn thu thập dữ liệu.
- [x] Đối chiếu cấu trúc `src/`, `tests/`, `data/`, `report/` và `main.py`.
- [x] Xác định trạng thái starter: các TODO trong `src/chunking.py`, `src/store.py`, `src/agent.py` chưa được triển khai; báo cáo và corpus chưa hoàn thiện.
- [x] Thống nhất phạm vi làm trọn bài: code lõi, corpus sáu tài liệu, benchmark năm câu hỏi và hai báo cáo.
- [x] Tạo đặc tả tại `docs/superpowers/specs/2026-09-20-complete-lab-07-design.md`.
- [x] Commit đặc tả ban đầu: `d91d021 docs: define complete Lab 07 design`.
- [x] Hoàn thành kế hoạch triển khai chi tiết tại `docs/superpowers/plans/2026-09-20-complete-lab-07.md`.
- [x] Thu hẹp corpus và benchmark về một chủ đề duy nhất: chính sách đổi trả và hoàn tiền.
- [x] Theo yêu cầu bổ sung, chọn nền tảng cụ thể là Shopee Việt Nam; không sử dụng corpus eBay.
- [x] Ghi nhận baseline của bộ test.
- [x] Hoàn thiện code lõi.
- [x] Hoàn thiện corpus và kiểm tra provenance.
- [x] Chạy benchmark và sinh kết quả.
- [ ] Hoàn thiện báo cáo.
- [ ] Chạy xác minh cuối cùng.

## Bằng chứng hiện có

- Repository có 42 test trong `tests/test_solution.py`.
- Tài liệu bài học mô tả baseline dự kiến là 11 pass và 31 fail trước khi triển khai.
- Baseline thực tế bằng `python -m pytest tests/ -v`: **11 passed, 31 failed**; các lỗi thất bại tại những nhánh `NotImplementedError` chưa triển khai.
- Môi trường hiện tại: Python 3.14.5, pytest 9.1.1. Dù lab khuyến nghị Python 3.11, baseline thu thập thành công trên môi trường sẵn có.

### 2026-09-20 — Task 1: Chunking và cosine similarity

- [x] Viết regression test trước cho bảo toàn dấu câu, text chỉ có whitespace, gom dòng nhỏ và hard-split khi hết separator.
- [x] Xác nhận RED: `python -m pytest tests/test_regressions.py -v` → 4 failed do `NotImplementedError`.
- [x] Triển khai `SentenceChunker`, `RecursiveChunker`, `compute_similarity` và `ChunkingStrategyComparator`.
- [x] Xác nhận GREEN: lệnh kiểm tra tập trung → **27 passed, 19 deselected**.

### 2026-09-20 — Task 2: EmbeddingStore in-memory

- [x] Viết regression test trước cho copy metadata, ẩn embedding và filter-before-ranking.
- [x] Xác nhận RED: 3 test mới thất bại tại `EmbeddingStore.add_documents` chưa triển khai.
- [x] Chuẩn hóa record, dùng chung một đường ranking, lọc trước khi xếp hạng và xóa theo `doc_id`.
- [x] Xác nhận GREEN: lệnh kiểm tra store tập trung → **17 passed, 32 deselected**.

### 2026-09-20 — Task 3: KnowledgeBaseAgent và demo CLI

- [x] Viết test RED cho store rỗng không gọi LLM và prompt có nguồn đánh số/ràng buộc grounding.
- [x] Triển khai luồng retrieve → context → prompt → `llm_fn` và thông báo khi không có dữ liệu.
- [x] Bộ test sau triển khai: **51 passed**.
- [x] Phát hiện `main.py` lỗi `UnicodeEncodeError` trên terminal CP1252; xác nhận nguyên nhân bằng `sys.stdout.encoding` và chạy đối chứng với `PYTHONIOENCODING=utf-8`.
- [x] Thêm regression test RED và cấu hình UTF-8 tại biên CLI.
- [x] Xác nhận sau sửa: **52 passed**; `python main.py "Chunking là gì?"` thoát mã 0 và in đúng tiếng Việt.

### 2026-09-20 — Task 4: Crawl và chuẩn hóa corpus Shopee

- [x] Viết corpus audit trước; xác nhận RED: 3 test thất bại vì chưa có thư mục/tài liệu/`sources.csv`.
- [x] Tạo `crawl_urls.csv` gồm 6 URL chính thức thuộc `help.shopee.vn`, đủ metadata buyer/seller.
- [x] Chạy crawler của repo; lần đầu bị sandbox chặn socket, lần chạy được cấp quyền đã kiểm tra `robots.txt` và lưu thành công **6/6 trang**, không có URL bị bỏ qua.
- [x] Lưu bản crawl thô trong staging bị Git ignore; kiểm tra cho thấy mỗi trang dài khoảng 4,9–26,4 KB và có nội dung giao diện lặp.
- [x] Làm sạch thành 6 tài liệu Markdown tập trung duy nhất vào chính sách đổi trả/hoàn tiền, không giữ menu/banner/nội dung ngoài chủ đề.
- [x] Tạo `sources.csv` khớp một-một với tài liệu và ghi ngày truy xuất 2026-09-20.
- [x] Corpus audit GREEN: **3 passed**; đủ metadata, 6 `doc_id` duy nhất, có cả `buyer` và `seller`, URL HTTPS chính thức của Shopee.

### 2026-09-20 — Task 5: Benchmark retrieval

- [x] Viết test trước cho parser front matter, heading chunker, lexical hashing, metadata chunk và đúng 5 benchmark cases.
- [x] Xác nhận RED: test collection lỗi `ModuleNotFoundError: No module named 'bench'`.
- [x] Triển khai `bench.py` với ba chiến lược: fixed-size, recursive và heading/section.
- [x] Dùng lexical hashing chuẩn hóa, deterministic, không mô tả sai là neural semantic embedding.
- [x] Unit test benchmark GREEN: **5 passed**.
- [x] Sinh lại `ket_qua_benchmark.txt` trên 5 file người dùng cung cấp: fixed-size **8/10**, recursive **10/10**, heading **10/10**.
- [x] A/B filter `audience=seller` loại các chunk buyer khỏi top-3 ở câu hỏi dành cho người bán.
- [x] Failure case thật: fixed-size đạt 0/2 ở câu bảo hành người bán vì hai mốc `48 giờ làm việc` và `14 ngày làm việc` bị tách sang các chunk khác nhau.

### 2026-09-20 — Điều chỉnh corpus theo yêu cầu người dùng

- [x] Thay corpus cuối bằng đúng 5 file Markdown người dùng cung cấp trong `data/ecommerce/`: `buyer-dispute-resolution-policy.md`, `return-refund-policy.md`, `seller-penalty-violation-policy.md`, `seller-warranty-policy.md`, `shipping-fee-refund-policy.md`.
- [x] Xóa 6 tài liệu Markdown đã crawl trước đó cùng 2 CSV hỗ trợ cũ trong `data/shopee-return-refund/`; các file vẫn có thể khôi phục từ commit `33d2e50`.
- [x] Tạo `data/ecommerce_sources.csv` ánh xạ một-một và ghi rõ `license_or_permission=user-provided`; không tuyên bố đã xác minh độc lập các URL có sẵn trong front matter.
- [x] Xác nhận RED có chủ đích khi tạm thiếu manifest: **1 failed, 2 passed**.
- [x] Corpus audit và benchmark unit test sau thay thế: **8 passed**.
- [x] Chạy lại benchmark thành công với kết quả fixed-size **8/10**, recursive **10/10**, heading **10/10**; A/B `audience=seller` loại tài liệu buyer khỏi top-3.

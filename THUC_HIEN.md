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
- [x] Ghi nhận baseline của bộ test.
- [ ] Hoàn thiện code lõi.
- [ ] Hoàn thiện corpus và kiểm tra provenance.
- [ ] Chạy benchmark và sinh kết quả.
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

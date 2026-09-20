# Báo cáo cá nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Phạm Văn Kiên

**Mã sinh viên:** `2A202602590`

**Nhóm:** Nhóm 4 người — phụ trách chiến lược sentence-based

**Ngày:** 2026-09-20

## 1. Khởi động

### Cosine similarity

Cosine similarity đo độ cùng hướng của hai vector. Giá trị gần 1 biểu thị hai vector rất giống về hướng; gần 0 là ít liên quan; giá trị âm cho biết chúng hướng ngược nhau.

- Ví dụ cao: “Thời hạn hoàn tiền qua thẻ là bao lâu?” và “Bao lâu tiền hoàn về thẻ tín dụng?”. Hai câu có cùng ý định và từ khóa chính.
- Ví dụ thấp: “Cách đóng gói hàng trả lại?” và “Vector embedding được chuẩn hóa thế nào?”. Hai câu thuộc hai chủ đề khác nhau.

Cosine được ưu tiên hơn khoảng cách Euclid cho embedding văn bản vì nó so sánh hướng, ít bị ảnh hưởng bởi độ lớn vector hoặc độ dài văn bản.

### Tính số chunk

Với tài liệu 10.000 ký tự, `chunk_size=500`, `overlap=50`, bước dịch là `500 - 50 = 450`:

`ceil((10.000 - 50) / 450) = ceil(22,11) = 23 chunk`.

Khi overlap tăng lên 100, bước dịch còn 400:

`ceil((10.000 - 100) / 400) = ceil(24,75) = 25 chunk`.

Overlap lớn hơn giữ được nhiều ngữ cảnh ở biên chunk nhưng làm tăng số chunk, dung lượng lưu và chi phí truy xuất.

## 2. Hướng tiếp cận

### Chunking

Chiến lược cá nhân được chọn là `SentenceChunker(max_sentences_per_chunk=3)`. Chunker dùng regex phát hiện khoảng trắng sau `.`, `!`, `?`, giữ lại dấu câu rồi gom tối đa ba câu hoàn chỉnh vào mỗi chunk. Chuỗi rỗng hoặc chỉ có khoảng trắng trả về danh sách rỗng.

Cách chia theo câu được chọn làm phương án thứ tư vì ba thành viên còn lại lần lượt thử fixed-size, recursive và heading-aware. Mục tiêu là giữ nguyên câu chứa điều kiện, đối tượng và mốc thời gian, tránh cắt mất bằng chứng ở biên ký tự. Hạn chế là regex đơn giản có thể tách sai chữ viết tắt hoặc số thập phân.

`RecursiveChunker` thử separator theo thứ tự ưu tiên. Phần còn quá dài tiếp tục được tách bằng separator nhỏ hơn; khi hết separator thì hard-split theo `chunk_size`. Các mảnh nhỏ liền kề được ghép lại nếu tổng chiều dài không vượt giới hạn.

### EmbeddingStore

Store dùng backend in-memory xác định, sao chép metadata để không sửa dữ liệu của caller và tự bổ sung `doc_id` khi thiếu. Khi tìm kiếm, query và tài liệu được embedding, tính dot product rồi sắp xếp điểm giảm dần; kết quả không làm lộ vector embedding.

`search_with_filter` lọc metadata trước khi xếp hạng, nên `top_k` chỉ áp dụng trên tập ứng viên hợp lệ. `delete_document` loại toàn bộ chunk có cùng metadata `doc_id` và trả về trạng thái đã xóa hay không.

### KnowledgeBaseAgent

Agent lấy top-k chunk, tạo các khối ngữ cảnh đánh số `[1]`, `[2]` kèm nguồn, rồi yêu cầu LLM chỉ trả lời dựa trên bằng chứng được cung cấp và thừa nhận khi thiếu dữ liệu. Nếu store rỗng, agent trả thông báo trực tiếp mà không gọi LLM.

## 3. Kết quả kiểm thử

Lệnh: `python -m pytest tests/ -v`

```text
collected 66 items
tests/test_benchmark.py: 10 passed
tests/test_regressions.py: 11 passed
tests/test_solution.py: 42 passed
tests/test_submission_assets.py: 3 passed
============================= 66 passed in 0.11s =============================
```

Kết quả: **66/66 test pass**, gồm đủ 42 test gốc và 24 test bổ sung.

## 4. Dự đoán độ tương tự

Các phép đo dùng trực tiếp `compute_similarity`.

| Cặp vector | Dự đoán | Kết quả thực tế | Đúng? |
|---|---:|---:|---|
| `[1, 0]` và `[1, 0]` | Rất cao | `1.0000` | Có |
| `[1, 1]` và `[2, 1]` | Cao | `0.9487` | Có |
| `[1, 0]` và `[0, 1]` | Thấp | `0.0000` | Có |
| `[1, 0]` và `[-1, 0]` | Âm/đối nghịch | `-1.0000` | Có |
| `[0, 0]` và `[1, 1]` | Không xác định, hàm nên trả 0 | `0.0000` | Có |

Trường hợp vector 0 đáng chú ý nhất: cosine theo công thức không xác định do mẫu số bằng 0, nên triển khai chủ động trả `0.0` để API ổn định.

## 5. Kết quả truy xuất cá nhân

Chiến lược cá nhân là sentence-based với `SentenceChunker(max_sentences_per_chunk=3)`. Trên 6 tài liệu, cấu hình tạo 20 chunk với độ dài trung bình 347,60 ký tự. Benchmark cuối dùng `nvidia/nemotron-3-embed-1b:free` qua OpenRouter; tài liệu được embedding theo batch với `search_document`, còn câu hỏi dùng `search_query`. Lexical hashing vẫn được giữ làm chế độ offline.

| # | Query | Top-1 | Score | Liên quan | Kết quả |
|---|---|---|---:|---|---|
| 1 | Các lý do liên quan đến sản phẩm gồm hư hỏng, bể vỡ, sai sản phẩm hoặc thiếu phụ kiện là gì? | `return-eligibility`, chunk chứa trọn danh sách lý do | 0.6471 | Có ở rank 1 | 2/2 |
| 2 | Thực phẩm tươi sống/đông lạnh có thời hạn ngắn hơn bao lâu? | `return-window`, chunk chứa mốc 24 giờ | 0.6928 | Có ở rank 1 | 2/2 |
| 3 | Nghi hàng giả cần bằng chứng kỹ thuật nào? | `return-evidence`, chunk chứa mã QR và số seri | 0.4356 | Có ở rank 1 | 2/2 |
| 4 | Hoàn tiền về thẻ tín dụng/ghi nợ mất bao lâu? | `refund-methods-and-time`, chunk chứa mốc 7–14 ngày | 0.4354 | Có ở rank 1 | 2/2 |
| 5 | Người bán hoàn dưới 50% thì Shopee xử lý thế nào? | `seller-return-refund-obligations`, chunk chứa cơ chế cấn trừ | 0.6783 | Có ở rank 1 | 2/2 |

Sentence-based đưa chunk đủ bằng chứng lên top-1 ở **5/5 câu**, tổng **10/10**. Q1 có score `0.6471`, cao hơn top-1 của ba chiến lược còn lại vì toàn bộ danh sách lý do nằm trong một câu hoàn chỉnh. Ở Q4, chunk chứa phần thẻ thanh toán và mốc 7–14 ngày đứng rank 1; trong khi recursive và heading-aware đặt chunk này ở rank 2.

So với toàn nhóm, kết quả là fixed-size **10/10**, recursive **9/10**, heading-aware **9/10**, sentence-based **10/10**. Sentence-based đồng hạng nhất với fixed-size nhưng tạo ít chunk hơn: 20 so với 21. Kết quả này chỉ áp dụng cho corpus và năm câu hỏi hiện tại; không khẳng định sentence-based luôn tốt hơn trên mọi loại tài liệu.

## 6. Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Khởi động | 5/5 |
| Hướng tiếp cận | 10/10 |
| Hoàn thiện code | 30/30 |
| Dự đoán độ tương tự | 5/5 |
| Kết quả truy xuất | 10/10 |
| **Tổng** | **60/60** |

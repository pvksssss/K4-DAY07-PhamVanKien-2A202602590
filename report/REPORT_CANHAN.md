# Báo cáo cá nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Phạm Văn Kiên

**Mã sinh viên:** `2A202602590`

**Nhóm:** Bài nộp cá nhân

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

`SentenceChunker` dùng regex phát hiện khoảng trắng sau `.`, `!`, `?`, giữ lại dấu câu rồi gom tối đa số câu đã cấu hình. Chuỗi rỗng hoặc chỉ có khoảng trắng trả về danh sách rỗng.

`RecursiveChunker` thử separator theo thứ tự ưu tiên. Phần còn quá dài tiếp tục được tách bằng separator nhỏ hơn; khi hết separator thì hard-split theo `chunk_size`. Các mảnh nhỏ liền kề được ghép lại nếu tổng chiều dài không vượt giới hạn.

### EmbeddingStore

Store dùng backend in-memory xác định, sao chép metadata để không sửa dữ liệu của caller và tự bổ sung `doc_id` khi thiếu. Khi tìm kiếm, query và tài liệu được embedding, tính dot product rồi sắp xếp điểm giảm dần; kết quả không làm lộ vector embedding.

`search_with_filter` lọc metadata trước khi xếp hạng, nên `top_k` chỉ áp dụng trên tập ứng viên hợp lệ. `delete_document` loại toàn bộ chunk có cùng metadata `doc_id` và trả về trạng thái đã xóa hay không.

### KnowledgeBaseAgent

Agent lấy top-k chunk, tạo các khối ngữ cảnh đánh số `[1]`, `[2]` kèm nguồn, rồi yêu cầu LLM chỉ trả lời dựa trên bằng chứng được cung cấp và thừa nhận khi thiếu dữ liệu. Nếu store rỗng, agent trả thông báo trực tiếp mà không gọi LLM.

## 3. Kết quả kiểm thử

Lệnh: `python -m pytest tests/ -v`

```text
collected 65 items
tests/test_benchmark.py: 9 passed
tests/test_regressions.py: 11 passed
tests/test_solution.py: 42 passed
tests/test_submission_assets.py: 3 passed
============================= 65 passed in 0.09s =============================
```

Kết quả: **65/65 test pass**, gồm đủ 42 test gốc và 23 test bổ sung.

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

Chiến lược cá nhân chọn là heading/section-aware vì cấu trúc Markdown của chính sách có các mục độc lập. Benchmark cuối dùng `nvidia/nemotron-3-embed-1b:free` qua OpenRouter; tài liệu được embedding theo batch với `search_document`, còn câu hỏi dùng `search_query`. Lexical hashing vẫn được giữ làm chế độ offline.

| # | Query | Top-1 | Score | Liên quan | Kết quả |
|---|---|---|---:|---|---|
| 1 | Các lý do liên quan đến sản phẩm gồm hư hỏng, bể vỡ, sai sản phẩm hoặc thiếu phụ kiện là gì? | `return-eligibility`, mục “Những tình huống có thể gửi yêu cầu” | 0.5043 | Có | 2/2 |
| 2 | Thực phẩm tươi sống/đông lạnh có thời hạn ngắn hơn bao lâu? | `return-window`, mục thực phẩm tươi sống | 0.6940 | Có | 2/2 |
| 3 | Nghi hàng giả cần bằng chứng kỹ thuật nào? | `return-evidence`, mục nội dung nên ghi nhận | 0.4317 | Có | 2/2 |
| 4 | Hoàn tiền về thẻ tín dụng/ghi nợ mất bao lâu? | Top-1 nói về ví/ngân hàng; chunk thẻ thanh toán ở rank 2 | 0.4088 | Có ở rank 2 | 1/2 |
| 5 | Người bán hoàn dưới 50% thì Shopee xử lý thế nào? | `seller-return-refund-obligations`, mục số tiền hoàn | 0.7025 | Có | 2/2 |

Có chunk đủ bằng chứng trong top-3 ở **5/5 câu**, tổng **9/10**. Nemotron sửa được failure Q3 của lexical baseline bằng cách đưa section chứa “mã QR” và “số seri” lên top-1. Q4 vẫn chỉ đạt 1 điểm vì chunk thẻ thanh toán nằm ở rank 2, sau chunk ví/tài khoản ngân hàng cùng tài liệu.

## 6. Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Khởi động | 5/5 |
| Hướng tiếp cận | 10/10 |
| Hoàn thiện code | 30/30 |
| Dự đoán độ tương tự | 5/5 |
| Kết quả truy xuất | 9/10 |
| **Tổng** | **59/60** |

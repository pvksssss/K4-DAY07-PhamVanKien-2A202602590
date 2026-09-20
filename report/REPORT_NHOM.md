# Báo cáo repository — Lab 7: Embedding & Vector Store
**Nhóm:**G34
**Thành Viên:** `Đinh Kim Thái — 2A202602417`
                `Nguyễn Lê Phước Tiến — 2A202602616`
                `Vũ Huy Đô — 2A202602555`
                `Phạm Văn Kiên — 2A202602590`
**Ngày:** 2026-09-20


Bốn thành viên tương ứng với bốn hướng thử nghiệm độc lập trên cùng corpus: fixed-size, recursive, heading-aware và sentence-based. Repository này chạy lại cả bốn cấu hình trên cùng embedding và bộ câu hỏi để việc so sánh công bằng; tên ba thành viên còn lại không được ghi vì chưa có thông tin xác thực.

## 1. Lựa chọn tài liệu

### Chủ đề

Corpus tập trung vào chính sách trả hàng và hoàn tiền của Shopee Việt Nam. Chủ đề phù hợp với RAG vì câu trả lời phụ thuộc vào điều kiện, mốc thời gian, bằng chứng, phương thức hoàn tiền và vai trò buyer/seller nằm ở nhiều mục khác nhau.

### Danh mục dữ liệu

| # | Tài liệu | Nguồn | Ngày/phiên bản | Số ký tự | Metadata chính |
|---|---|---|---|---:|---|
| 1 | Điều kiện yêu cầu trả hàng/hoàn tiền | `https://help.shopee.vn/portal/4/article/188931` | 2026-09-20 / not-stated | 1.565 | buyer, eligibility |
| 2 | Thời hạn gửi yêu cầu | `https://help.shopee.vn/portal/4/article/188931` | 2026-09-20 / not-stated | 1.253 | buyer, request-window |
| 3 | Bằng chứng trả hàng/hoàn tiền | `https://help.shopee.vn/portal/4/article/79467` | 2026-09-20 / not-stated | 1.421 | buyer, evidence |
| 4 | Đóng gói và gửi trả | `https://help.shopee.vn/portal/4/article/79508` | 2026-09-20 / not-stated | 1.339 | buyer, return-shipping |
| 5 | Phương thức và thời gian hoàn tiền | `https://help.shopee.vn/portal/4/article/189473` | 2026-09-20 / not-stated | 1.529 | buyer, refund-timing |
| 6 | Nghĩa vụ người bán | `https://help.shopee.vn/portal/4/article/77251` | 2026-09-20 / not-stated | 1.588 | seller, seller-obligations |

Các trang nguồn công khai đã được crawler kiểm tra `robots.txt` và lưu thành công 6/6 vào staging trước khi làm sạch. Corpus cuối là nội dung tóm lược tập trung; `sources.csv` ánh xạ một-một với 6 tài liệu.

- [x] Corpus chỉ dùng nguồn công khai, không chứa thông tin đăng nhập, dữ liệu cá nhân hay tài liệu nội bộ.
- [x] Mỗi tài liệu có `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language`.
- [x] Corpus có cả audience `buyer` và `seller`.

| Trường | Kiểu | Ví dụ | Tác dụng |
|---|---|---|---|
| `doc_id` | string | `return-window` | Truy vết và xóa toàn bộ chunk của tài liệu |
| `audience` | enum | `buyer`, `seller` | Lọc trước khi ranking |
| `category` | string | `refund-timing` | Thu hẹp chủ đề |
| `source_url` | URL | URL bài Shopee Help | Đối chiếu nguồn |
| `retrieved_at` | date | `2026-09-20` | Theo dõi độ mới |
| `document_version` | string | `not-stated` | Ghi nhận phiên bản khi nguồn không công bố |

## 2. Thiết kế chiến lược

Bốn chiến lược dùng cùng 6 tài liệu, 5 câu hỏi, Nemotron semantic embedding và cách chấm. API key chỉ được đọc từ `.env` đã Git-ignore. Document chunks được gửi theo batch; query embedding được cache trong một lần chạy. Lexical hashing vẫn là chế độ offline để tái lập khi không có API.

| Thành viên | Chiến lược | Mục tiêu thử nghiệm |
|---|---|---|
| `Đinh Kim Thái — 2A202602417` | Fixed-size | Đo hiệu quả của cửa sổ cố định có overlap |
| `Nguyễn Lê Phước Tiến — 2A202602616` | Recursive | Ưu tiên ranh giới đoạn, dòng, câu rồi mới cắt cứng |
| `Vũ Huy Đô — 2A202602555` | Heading-aware | Giữ tiêu đề Markdown đi cùng section chính sách |
| `Phạm Văn Kiên — 2A202602590` | Sentence-based | Gom tối đa 3 câu hoàn chỉnh vào mỗi chunk |

| Cấu hình | Tham số | Số chunk | Độ dài TB | Điểm |
|---|---|---:|---:|---:|
| Fixed-size | size 450, overlap 80 | 21 | 389,76 | 10/10 |
| Recursive | size 450, separator theo cấu trúc | 23 | 302,22 | 9/10 |
| Heading-aware | mỗi heading gắn với section, max 700 | 27 | 257,15 | 9/10 |
| Sentence-based | tối đa 3 câu/chunk | 20 | 347,60 | 10/10 |

- Fixed-size đơn giản, có overlap, nhưng có thể cắt giữa section.
- Recursive tôn trọng đoạn/dòng tốt hơn, song vẫn phụ thuộc separator và giới hạn kích thước.
- Heading-aware giữ nhãn mục cùng nội dung và thuận lợi cho trích dẫn; đổi lại tạo nhiều chunk ngắn, trong đó heading-only có thể cạnh tranh điểm với section thật.
- Sentence-based giữ câu hoàn chỉnh, tạo ít chunk nhất và đưa đủ bằng chứng lên top-1 ở cả 5 câu; hạn chế là regex đơn giản có thể tách sai chữ viết tắt hoặc số thập phân.

Fixed-size và sentence-based đồng hạng cao nhất với 10/10. Fixed-size dùng overlap để giữ các mốc thời gian liền nhau; sentence-based giữ trọn câu chứa điều kiện và con số; kết quả cho thấy lựa chọn tốt nhất còn phụ thuộc cách đặt câu hỏi và cách chấm rank.

## 3. Câu hỏi và chất lượng truy xuất

| # | Câu hỏi | Gold answer | Tài liệu chứa bằng chứng |
|---|---|---|---|
| 1 | Các lý do liên quan đến sản phẩm gồm hư hỏng, bể vỡ, sai sản phẩm hoặc thiếu phụ kiện là gì? | Các trường hợp này cho phép gửi yêu cầu; còn có khác mô tả và nghi hàng giả/nhái. | `return-eligibility` |
| 2 | Thực phẩm tươi sống hoặc đông lạnh có thời hạn ngắn hơn bao lâu? | 24 giờ kể từ khi giao hàng thành công. | `return-window` |
| 3 | Khi nghi ngờ hàng giả, cần bằng chứng kỹ thuật nào? | Quét mã QR, kiểm tra số seri, đối chiếu bao bì chính hãng. | `return-evidence` |
| 4 | Hoàn tiền về thẻ tín dụng hoặc ghi nợ mất bao lâu? | 7–14 ngày làm việc tùy ngân hàng phát hành. | `refund-methods-and-time` |
| 5 | Nếu người bán hoàn dưới 50% giá trị sản phẩm thì sao? | Shopee có thể cấn trừ phần chênh lệch từ số dư người bán để trả người mua. | `seller-return-refund-obligations` |

| Câu | Fixed | Recursive | Heading | Sentence | Nhận xét |
|---|---:|---:|---:|---:|---|
| Q1 | 2 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| Q2 | 2 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| Q3 | 2 | 2 | 2 | 2 | Nemotron đưa bằng chứng QR/seri lên top-1 |
| Q4 | 2 | 1 | 1 | 2 | Recursive/heading có bằng chứng ở rank 2; sentence ở rank 1 |
| Q5 | 2 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| **Tổng** | **10/10** | **9/10** | **9/10** | **10/10** | Cả 5 câu đều có bằng chứng trong top-3 |

### Thử nghiệm metadata filter

Q5 được chạy thêm với `audience=seller`. Với sentence-based strategy của Phạm Văn Kiên:

- Không lọc: `seller-return-refund-obligations`, `return-eligibility`, `return-eligibility`.
- Có lọc: cả ba vị trí đều thuộc `seller-return-refund-obligations`.

Filter không thay đổi top-1 vì tài liệu đúng đã đứng đầu, nhưng loại hoàn toàn chunk buyer khỏi top-3. Điều này làm context đưa vào agent tập trung đúng đối tượng hơn và chứng minh filter được áp dụng trước ranking.

### Phân tích lỗi

Failure còn lại là Q4 của recursive và heading: chunk nói về Ví ShopeePay/tài khoản ngân hàng đứng trên chunk thẻ tín dụng do cùng chủ đề hoàn tiền, nên bằng chứng đúng chỉ ở rank 2. Sentence-based khắc phục trường hợp này vì nhóm câu tạo ra chunk có phần “Thẻ thanh toán” và mốc 7–14 ngày, được xếp rank 1. Có thể tiếp tục cải thiện recursive/heading bằng reranker hoặc query expansion; không nên chỉnh gold answer để làm đẹp điểm.

## 4. Demo và bài học

Các điểm trình bày chính:

1. Chạy `python -m pytest tests/ -v` để chứng minh 66 test pass.
2. Chạy `python bench.py` để tái tạo toàn bộ kết quả và file `ket_qua_benchmark.txt`.
3. So sánh lexical baseline với kết quả Nemotron 10/9/9/10 và Q5 filter để thấy embedding, chunking và metadata giải quyết các phần khác nhau của retrieval.

Bài học lớn nhất là semantic embedding sửa được lỗi diễn đạt của Q3 nhưng không đảm bảo mọi bằng chứng đều lên rank 1. Nếu làm lại, repository nên thêm nhiều cách diễn đạt cho mỗi ý, lưu cache embedding không chứa bí mật và thử reranker trên top-k.

## 5. Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Lựa chọn tài liệu | 10/10 |
| Thiết kế chiến lược | 15/15 |
| Chất lượng truy xuất | 10/10 |
| Thuyết trình/demo | 5/5 |
| **Tổng** | **40/40** |

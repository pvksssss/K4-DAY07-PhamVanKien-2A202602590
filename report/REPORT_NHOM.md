# Báo cáo repository — Lab 7: Embedding & Vector Store

**Hình thức:** Bài nộp cá nhân, không có thành viên nhóm khác

**Thực hiện:** Phạm Văn Kiên — `2A202602590`

**Ngày:** 2026-09-20

Ba “chiến lược” trong báo cáo là ba cấu hình thí nghiệm trên cùng corpus, không phải phần việc của ba thành viên khác nhau.

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

Ba chiến lược dùng cùng 6 tài liệu, 5 câu hỏi, lexical-hash embedding và cách chấm. Vì corpus nhỏ, thí nghiệm ưu tiên tính tái lập hơn chất lượng của mô hình neural.

| Cấu hình | Tham số | Số chunk | Độ dài TB | Điểm |
|---|---|---:|---:|---:|
| Fixed-size | size 450, overlap 80 | 21 | 389,76 | 8/10 |
| Recursive | size 450, separator theo cấu trúc | 23 | 302,22 | 8/10 |
| Heading-aware | mỗi heading gắn với section, max 700 | 27 | 257,15 | 8/10 |

- Fixed-size đơn giản, có overlap, nhưng có thể cắt giữa section.
- Recursive tôn trọng đoạn/dòng tốt hơn, song vẫn phụ thuộc separator và giới hạn kích thước.
- Heading-aware giữ nhãn mục cùng nội dung và thuận lợi cho trích dẫn; đổi lại tạo nhiều chunk ngắn, trong đó heading-only có thể cạnh tranh điểm với section thật.

Ba chiến lược bằng điểm trên bộ câu hỏi này. Heading-aware được chọn làm cấu hình trình bày vì nguồn là Markdown có cấu trúc và kết quả dễ giải thích, không phải vì có điểm cao hơn.

## 3. Câu hỏi và chất lượng truy xuất

| # | Câu hỏi | Gold answer | Tài liệu chứa bằng chứng |
|---|---|---|---|
| 1 | Các lý do liên quan đến sản phẩm gồm hư hỏng, bể vỡ, sai sản phẩm hoặc thiếu phụ kiện là gì? | Các trường hợp này cho phép gửi yêu cầu; còn có khác mô tả và nghi hàng giả/nhái. | `return-eligibility` |
| 2 | Thực phẩm tươi sống hoặc đông lạnh có thời hạn ngắn hơn bao lâu? | 24 giờ kể từ khi giao hàng thành công. | `return-window` |
| 3 | Khi nghi ngờ hàng giả, cần bằng chứng kỹ thuật nào? | Quét mã QR, kiểm tra số seri, đối chiếu bao bì chính hãng. | `return-evidence` |
| 4 | Hoàn tiền về thẻ tín dụng hoặc ghi nợ mất bao lâu? | 7–14 ngày làm việc tùy ngân hàng phát hành. | `refund-methods-and-time` |
| 5 | Nếu người bán hoàn dưới 50% giá trị sản phẩm thì sao? | Shopee có thể cấn trừ phần chênh lệch từ số dư người bán để trả người mua. | `seller-return-refund-obligations` |

| Câu | Fixed | Recursive | Heading | Nhận xét |
|---|---:|---:|---:|---|
| Q1 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| Q2 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| Q3 | 0 | 0 | 0 | Đúng tài liệu nhưng section chứa QR/seri không vào top-3 |
| Q4 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| Q5 | 2 | 2 | 2 | Đủ bằng chứng ở top-1 |
| **Tổng** | **8/10** | **8/10** | **8/10** | 4/5 câu đạt tối đa |

### Thử nghiệm metadata filter

Q5 được chạy thêm với `audience=seller`. Với heading strategy:

- Không lọc: `seller-return-refund-obligations`, `return-eligibility`, `return-shipping-and-packaging`.
- Có lọc: cả ba vị trí đều thuộc `seller-return-refund-obligations`.

Filter không thay đổi top-1 vì tài liệu đúng đã đứng đầu, nhưng loại hoàn toàn chunk buyer khỏi top-3. Điều này làm context đưa vào agent tập trung đúng đối tượng hơn và chứng minh filter được áp dụng trước ranking.

### Phân tích lỗi

Q3 là failure thật của cả ba cấu hình. Lexical hashing đưa các chunk nói chung về “bằng chứng” lên cao, nhưng section có đồng thời “mã QR” và “số seri” không vào top-3. Cải tiến phù hợp là dùng embedding ngữ nghĩa tốt hơn, lexical/BM25 hybrid, tăng `top_k`, hoặc thêm reranker; không nên chỉ kết luận rằng chunking sai.

## 4. Demo và bài học

Các điểm trình bày chính:

1. Chạy `python -m pytest tests/ -v` để chứng minh 60 test pass.
2. Chạy `python bench.py` để tái tạo toàn bộ kết quả và file `ket_qua_benchmark.txt`.
3. So sánh Q3 thất bại với Q5 filter thành công để thấy chunking, embedding và metadata giải quyết các phần khác nhau của retrieval.

Bài học lớn nhất là chiến lược chia chunk không thể bù hoàn toàn cho biểu diễn từ vựng yếu. Nếu làm lại, repository nên lưu cả raw snapshot và clean corpus có checksum, thêm benchmark nhiều cách diễn đạt hơn, và so sánh lexical baseline với một embedding tiếng Việt thực tế.

## 5. Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Lựa chọn tài liệu | 10/10 |
| Thiết kế chiến lược | 14/15 |
| Chất lượng truy xuất | 8/10 |
| Thuyết trình/demo | 5/5 |
| **Tổng** | **37/40** |

# Cách thực hiện bài Lab 07 — Embedding, Vector Store và RAG

## 1. Mục tiêu của bài

Bài làm xây dựng một hệ thống truy xuất thông tin nhỏ theo mô hình RAG (Retrieval-Augmented Generation) cho chủ đề **chính sách trả hàng và hoàn tiền của Shopee Việt Nam**.

Hệ thống thực hiện đầy đủ chuỗi xử lý:

```text
Trang chính sách công khai
        ↓
Kiểm tra robots.txt và thu thập nội dung
        ↓
Làm sạch, chuẩn hóa Markdown và metadata
        ↓
Chia tài liệu thành các chunk
        ↓
Biến chunk thành vector embedding
        ↓
Lưu vào EmbeddingStore
        ↓
Tìm top-k chunk gần câu hỏi nhất
        ↓
Lọc theo metadata nếu cần
        ↓
Đưa context vào agent để tạo câu trả lời có nguồn
        ↓
Đánh giá bằng 5 câu hỏi benchmark
```

Các sản phẩm chính của bài gồm:

- Mã nguồn chunking, vector store và RAG agent trong `src/`.
- Corpus 6 tài liệu tại `data/shopee-return-refund/`.
- Danh mục nguồn `sources.csv`.
- Chương trình benchmark `bench.py`.
- Kết quả thực nghiệm `ket_qua_benchmark.txt`.
- Báo cáo cá nhân và báo cáo nhóm trong `report/`.

---

## 2. Khảo sát yêu cầu và xây dựng baseline

### 2.1. Đọc cấu trúc dự án

Các file quan trọng được xác định như sau:

| File/thư mục | Vai trò |
|---|---|
| `src/models.py` | Khai báo cấu trúc `Document` |
| `src/chunking.py` | Các thuật toán chia văn bản và cosine similarity |
| `src/embeddings.py` | Các backend embedding |
| `src/store.py` | Kho vector trong bộ nhớ |
| `src/agent.py` | Agent hỏi đáp theo mô hình RAG |
| `scripts/fetch_public_pages.py` | Thu thập các trang công khai |
| `bench.py` | Tạo chunk, chạy retrieval và chấm benchmark |
| `tests/` | Kiểm thử chức năng và tài nguyên bài nộp |

### 2.2. Chạy baseline trước khi sửa code

Lệnh dùng để xác định trạng thái ban đầu:

```powershell
python -m pytest tests/ -v
```

Baseline theo đề là **11 test pass và 31 test fail**. Các lỗi ban đầu chủ yếu là `NotImplementedError`, cho thấy cấu trúc dự án đúng nhưng các phần bắt buộc chưa được cài đặt.

Mục đích của bước baseline:

- Phân biệt lỗi do môi trường với lỗi do code chưa hoàn thiện.
- Biết chính xác số lượng chức năng cần cài đặt.
- Có mốc để so sánh sau mỗi checkpoint.

---

## 3. Thu thập corpus chính sách Shopee

### 3.1. Chọn chủ đề và phạm vi

Chủ đề được chọn là **chính sách trả hàng/hoàn tiền Shopee**, phù hợp với yêu cầu thương mại điện tử của lớp L3B.

Corpus được chia thành 6 tài liệu theo từng ý nghiệp vụ thay vì lưu một trang rất dài:

| `doc_id` | Nội dung | Đối tượng |
|---|---|---|
| `return-eligibility` | Điều kiện được yêu cầu trả hàng/hoàn tiền | buyer |
| `return-window` | Thời hạn gửi yêu cầu | buyer |
| `return-evidence` | Bằng chứng cần cung cấp | buyer |
| `return-shipping-and-packaging` | Đóng gói và gửi trả | buyer |
| `refund-methods-and-time` | Phương thức và thời gian nhận tiền | buyer |
| `seller-return-refund-obligations` | Nghĩa vụ của người bán | seller |

Cách chia này có hai lợi ích:

1. Mỗi tài liệu tập trung vào một nhóm câu hỏi, giảm nhiễu khi retrieval.
2. Metadata `audience` có ít nhất hai giá trị `buyer` và `seller`, nhờ đó có thể kiểm thử bộ lọc thật sự.

### 3.2. Chuẩn bị danh sách URL

Crawler nhận một file CSV có cột bắt buộc là `url`. Các cột như `doc_id`, `title`, `audience`, `category`, `language`, `document_version` và `license_or_permission` được đưa vào metadata của tài liệu.

Ví dụ cấu trúc một dòng đầu vào:

```csv
url,doc_id,title,audience,category,language,document_version,license_or_permission
https://help.shopee.vn/portal/4/article/188931,return-eligibility,Điều kiện yêu cầu trả hàng hoặc hoàn tiền,buyer,eligibility,vi,not-stated,public-source
```

### 3.3. Crawl có kiểm soát

Script sử dụng:

```powershell
python scripts/fetch_public_pages.py data/urls.csv --output-dir data/shopee-return-refund
```

Crawler được thiết kế thận trọng:

- Chỉ chấp nhận URL HTTP/HTTPS hợp lệ.
- Đọc và kiểm tra `robots.txt` trước khi tải trang.
- Bỏ qua URL bị robots.txt từ chối.
- Chờ ít nhất 1 giây giữa các request.
- Chỉ nhận `text/html` hoặc `text/plain`.
- Loại bỏ các thẻ gây nhiễu như `script`, `style`, `nav`, `footer`, `header`, `iframe`.
- Không lưu trang có nội dung trích xuất quá ngắn.
- Ghi kết quả thành file Markdown và cập nhật `sources.csv`.

Không cố vượt qua robots.txt hoặc cơ chế bảo vệ của website. Nếu một nguồn không cho phép crawler truy cập, cách xử lý đúng là chọn nguồn khác.

### 3.4. Làm sạch và chuẩn hóa

Nội dung crawl thô có thể chứa menu, banner, điều hướng và văn bản không liên quan. Vì vậy, sau khi crawl cần đọc lại từng file và giữ lại:

- Điều kiện áp dụng.
- Mốc thời gian.
- Phương thức hoàn tiền.
- Bằng chứng cần cung cấp.
- Trách nhiệm của người mua/người bán.
- Các ngoại lệ quan trọng.

Không nên chunk trực tiếp dữ liệu thô vì các đoạn menu lặp lại có thể chiếm top-k và làm giảm chất lượng truy xuất.

### 3.5. Chuẩn metadata

Mỗi file Markdown dùng YAML front matter:

```yaml
---
doc_id: return-window
title: Thời hạn gửi yêu cầu trả hàng hoàn tiền
source_url: https://help.shopee.vn/portal/4/article/188931
retrieved_at: 2026-09-20
document_version: "not-stated"
audience: buyer
category: request-window
language: vi
---
```

Ý nghĩa các trường:

| Trường | Công dụng |
|---|---|
| `doc_id` | Định danh tài liệu và hỗ trợ xóa tất cả chunk của tài liệu |
| `title` | Tên dễ đọc của tài liệu |
| `source_url` | Truy vết về nguồn công khai |
| `retrieved_at` | Ghi nhận thời điểm lấy dữ liệu |
| `document_version` | Phiên bản nguồn; dùng `not-stated` nếu nguồn không công bố |
| `audience` | Phân biệt nội dung dành cho buyer hoặc seller |
| `category` | Nhóm nghiệp vụ để có thể lọc/mở rộng sau này |
| `language` | Ngôn ngữ tài liệu |

File `sources.csv` ánh xạ một-một với 6 file Markdown. Không đưa khóa API, cookie, thông tin đăng nhập hoặc dữ liệu cá nhân vào corpus.

---

## 4. Cài đặt các chiến lược chunking

Chunking quyết định phần văn bản nào được embedding và retrieval. Chunk quá lớn chứa nhiều ý gây nhiễu; chunk quá nhỏ có thể mất ngữ cảnh.

### 4.1. Fixed-size chunking

`FixedSizeChunker` chia văn bản theo số ký tự cố định, có vùng chồng lấp:

```text
chunk 1: ký tự 0 → 449
chunk 2: ký tự 370 → 819
chunk 3: ký tự 740 → 1189
```

Trong benchmark sử dụng:

```python
FixedSizeChunker(chunk_size=450, overlap=80)
```

Bước dịch của cửa sổ:

```text
step = chunk_size - overlap = 450 - 80 = 370
```

Ưu điểm:

- Đơn giản, ổn định và dễ dự đoán số chunk.
- Overlap giúp giữ thông tin nằm sát ranh giới hai chunk.
- Trong bộ benchmark hiện tại, chiến lược này đạt kết quả tốt nhất.

Nhược điểm:

- Có thể cắt ngang câu hoặc cắt giữa một mục Markdown.
- Phần overlap làm tăng số vector và chi phí embedding.

### 4.2. Sentence chunking

`SentenceChunker` dùng biểu thức chính quy:

```python
r"(?<=[.!?])(?:[ \t]+|\n+)"
```

Lookbehind `(?<=[.!?])` giúp tách sau dấu kết thúc câu nhưng vẫn giữ lại dấu câu. Sau đó, tối đa 3 câu được ghép thành một chunk.

Các trường hợp được xử lý:

- Văn bản rỗng trả về `[]`.
- `max_sentences_per_chunk` tối thiểu là 1.
- Khoảng trắng dư được loại bỏ.

Hạn chế đã nhận diện: cách tách đơn giản có thể hiểu sai chữ viết tắt, số thập phân hoặc một số cách xuống dòng đặc biệt.

Trong benchmark nhóm 4 người, đây là chiến lược thứ tư với cấu hình:

```python
SentenceChunker(max_sentences_per_chunk=3)
```

Kết quả thực nghiệm là 20 chunk, độ dài trung bình 347,60 ký tự và 10/10. Cả năm chunk đủ bằng chứng đều đứng top-1. Chiến lược đặc biệt hiệu quả với Q4 vì câu chứa “thẻ tín dụng hoặc ghi nợ” và mốc “7–14 ngày làm việc” được giữ trong cùng một chunk.

### 4.3. Recursive chunking

`RecursiveChunker` thử các separator theo thứ tự từ ranh giới lớn đến nhỏ:

```python
["\n\n", "\n", ". ", " ", ""]
```

Thuật toán:

1. Nếu đoạn hiện tại không vượt `chunk_size`, giữ nguyên.
2. Thử tách bằng separator ưu tiên cao nhất.
3. Nếu không tách được, chuyển sang separator tiếp theo.
4. Nếu một phần vẫn quá dài, tiếp tục đệ quy với các separator còn lại.
5. Các phần nhỏ liền kề được ghép lại nếu tổng độ dài chưa vượt giới hạn.
6. Khi hết separator, cắt cứng theo số ký tự để đảm bảo thuật toán luôn dừng.

Trong benchmark sử dụng:

```python
RecursiveChunker(chunk_size=450)
```

Ưu điểm là tôn trọng đoạn, dòng và câu tốt hơn fixed-size. Nhược điểm là số lượng/độ dài chunk phụ thuộc mạnh vào cấu trúc tài liệu.

### 4.4. Heading-aware chunking

Đây là chiến lược riêng được viết trong `bench.py`. Văn bản Markdown được tách khi gặp heading:

```python
re.split(r"(?=^#{1,6}\s+)", text, flags=re.MULTILINE)
```

Mỗi heading được giữ cùng section phía sau. Nếu section dài hơn `max_chars=700`, section tiếp tục được chia bằng `RecursiveChunker`.

Ưu điểm:

- Giữ tên mục đi cùng nội dung.
- Chunk dễ đọc, dễ giải thích và thuận tiện trích dẫn.
- Phù hợp với tài liệu chính sách có cấu trúc tiêu đề rõ ràng.

Nhược điểm:

- Section ngắn tạo nhiều chunk nhỏ.
- Heading-only hoặc nội dung quá ngắn có thể cạnh tranh điểm với chunk chứa bằng chứng đầy đủ.

### 4.5. So sánh tự động các chunker

`ChunkingStrategyComparator.compare()` chạy ba chiến lược có sẵn trên cùng văn bản và trả về:

```python
{
    "fixed_size": {"count": ..., "avg_length": ..., "chunks": [...]},
    "by_sentences": {"count": ..., "avg_length": ..., "chunks": [...]},
    "recursive": {"count": ..., "avg_length": ..., "chunks": [...]},
}
```

Nếu văn bản rỗng, `count = 0`, `avg_length = 0.0`, tránh lỗi chia cho 0.

---

## 5. Tính cosine similarity

Độ tương tự giữa vector câu hỏi `a` và vector tài liệu `b` được tính bằng:

```text
cosine(a, b) = (a · b) / (||a|| × ||b||)
```

Trong đó:

```text
a · b = Σ(ai × bi)
||a|| = sqrt(Σ(ai²))
||b|| = sqrt(Σ(bi²))
```

`compute_similarity()` thực hiện ba bước:

1. Tính độ lớn của hai vector.
2. Nếu một vector có độ lớn bằng 0, trả về `0.0` để tránh chia cho 0.
3. Trả về dot product chia cho tích hai độ lớn.

Với embedding đã được chuẩn hóa về độ dài 1, dot product bằng cosine similarity. Vì vậy `EmbeddingStore` có thể dùng `_dot()` trực tiếp khi xếp hạng.

Cosine phù hợp với text embedding vì quan tâm đến hướng biểu diễn ngữ nghĩa hơn là độ lớn tuyệt đối của vector.

---

## 6. Xây dựng EmbeddingStore

### 6.1. Cấu trúc dữ liệu

Mỗi chunk được biểu diễn bằng `Document`:

```python
Document(
    id="return-window#fixed_size#0",
    content="...nội dung chunk...",
    metadata={
        "doc_id": "return-window",
        "chunk_index": 0,
        "strategy": "fixed_size",
        "audience": "buyer",
        "category": "request-window",
    },
)
```

Một record trong store gồm:

- `id`: định danh duy nhất của chunk.
- `content`: nội dung chunk.
- `metadata`: metadata gốc cộng thông tin chunk.
- `embedding`: vector số thực.

### 6.2. Thêm tài liệu

`add_documents()` hỗ trợ hai kiểu embedder:

- Embedder thông thường: gọi từng chuỗi qua `embedding_fn(text)`.
- Embedder hỗ trợ batch: gọi `embed_documents(list[str])` một lần.

Khi dùng batch, số embedding trả về phải bằng số document. Nếu lệch, chương trình báo `ValueError` để tránh gắn nhầm vector với nội dung.

`doc_id` được tự động thêm vào metadata nếu chưa có, giúp `delete_document()` hoạt động ổn định.

### 6.3. Tìm kiếm top-k

`search(query, top_k)` thực hiện:

1. Tạo embedding cho query.
2. Tính dot product giữa query embedding và từng record.
3. Sắp xếp giảm dần theo score.
4. Trả về tối đa `top_k` kết quả.

Mỗi kết quả có dạng:

```python
{
    "id": "...",
    "content": "...",
    "metadata": {...},
    "score": 0.7025,
}
```

Nếu store rỗng hoặc `top_k <= 0`, kết quả là danh sách rỗng.

### 6.4. Lọc metadata trước khi ranking

`search_with_filter()` lọc record trước, sau đó mới tính similarity:

```python
store.search_with_filter(
    query,
    top_k=3,
    metadata_filter={"audience": "seller"},
)
```

Thứ tự đúng là:

```text
Toàn bộ record → lọc metadata → tính score → sắp xếp → lấy top-k
```

Nếu tìm top-k trước rồi mới lọc, kết quả đúng có thể nằm ngoài top-k ban đầu và bị mất.

Nhiều điều kiện filter được kết hợp bằng phép AND: record phải khớp tất cả cặp khóa/giá trị.

### 6.5. Xóa tài liệu

`delete_document(doc_id)` loại bỏ tất cả record có:

```python
record["metadata"]["doc_id"] == doc_id
```

Hàm trả `True` nếu có ít nhất một chunk bị xóa, ngược lại trả `False`.

---

## 7. Các cách tạo embedding

### 7.1. Mock embedding

`MockEmbedder` tạo vector xác định từ MD5 và bộ sinh số giả ngẫu nhiên. Vector được chuẩn hóa về độ dài 1.

Mục đích:

- Chạy test nhanh và không cần mạng.
- Kết quả lặp lại được.
- Kiểm thử luồng dữ liệu, không dùng để đánh giá chất lượng ngữ nghĩa.

### 7.2. Lexical hashing baseline

`LexicalHashEmbedder` là baseline offline trong `bench.py`:

1. Chuẩn hóa Unicode NFC và chuyển chữ thường.
2. Tách token.
3. Băm mỗi token bằng SHA-256 vào vector 512 chiều.
4. Dùng một byte của hash để chọn dấu cộng/trừ.
5. Chuẩn hóa vector.

Cách này nhận ra từ trùng nhau nhưng không hiểu tốt từ đồng nghĩa hoặc cách diễn đạt khác.

### 7.3. OpenRouter Nemotron semantic embedding

Benchmark chính dùng model:

```text
nvidia/nemotron-3-embed-1b:free
```

Cấu hình trong `.env`:

```env
OPENROUTER_API_KEY=<khóa-của-bạn>
OPENROUTER_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
```

Không ghi khóa thật vào tài liệu, source code hoặc Git. `.env` đã nằm trong `.gitignore`.

`OpenRouterEmbedder` gọi endpoint:

```text
https://openrouter.ai/api/v1/embeddings
```

Hai loại đầu vào được phân biệt:

- Document chunk: `input_type="search_document"`.
- Câu hỏi: `input_type="search_query"`.

Các tối ưu đã áp dụng:

- Gửi toàn bộ document chunks theo batch thay vì từng request.
- Cache embedding theo khóa `(input_type, text)` trong một lần chạy.
- Sắp xếp response theo `index` trước khi ghép lại với input.
- Kiểm tra số vector nhận về có khớp số văn bản hay không.
- Timeout mặc định 60 giây.

### 7.4. Cơ chế chọn backend

`create_benchmark_embedder()` có ba chế độ:

| `BENCHMARK_EMBEDDING` | Hành vi |
|---|---|
| `auto` | Có OpenRouter key thì dùng Nemotron, không có key thì dùng lexical |
| `openrouter` | Bắt buộc dùng OpenRouter |
| `lexical` | Chạy offline bằng lexical hashing |

Ví dụ chạy baseline offline trên PowerShell:

```powershell
$env:BENCHMARK_EMBEDDING = "lexical"
python bench.py
Remove-Item Env:BENCHMARK_EMBEDDING
```

Ngoài ra dự án còn có `LocalEmbedder`, `OpenAIEmbedder` và `GeminiEmbedder`, nhưng chúng không bắt buộc cho checkpoint cốt lõi.

---

## 8. Xây dựng KnowledgeBaseAgent theo RAG

`KnowledgeBaseAgent.answer()` triển khai luồng RAG cơ bản:

1. Nhận câu hỏi từ người dùng.
2. Gọi `store.search(question, top_k=3)`.
3. Nếu không có kết quả, trả thông báo không tìm thấy thông tin.
4. Ghép các chunk thành context có đánh số `[1]`, `[2]`, `[3]`.
5. Chọn nguồn theo thứ tự ưu tiên `source`, `source_url`, `doc_id`, rồi `id`.
6. Tạo prompt yêu cầu LLM chỉ dùng context và phải trích dẫn nguồn.
7. Gọi `llm_fn(prompt)` để sinh câu trả lời.

Nội dung cốt lõi của prompt:

```text
Chỉ sử dụng ngữ cảnh được cung cấp; không suy đoán thông tin bên ngoài.
Trích dẫn nguồn bằng [1], [2]...
Nếu ngữ cảnh không đủ, nói rõ rằng không tìm thấy đủ thông tin.
```

`llm_fn` được truyền từ ngoài vào thay vì gắn cứng một nhà cung cấp LLM. Nhờ vậy, test có thể dùng hàm giả lập và ứng dụng thật có thể thay bằng API khác.

---

## 9. Thiết kế benchmark

### 9.1. Bộ 5 câu hỏi

Benchmark bao phủ năm dạng thông tin khác nhau:

| Câu | Nội dung kiểm tra | Gold document |
|---|---|---|
| Q1 | Lý do sản phẩm đủ điều kiện trả hàng | `return-eligibility` |
| Q2 | Thời hạn 24 giờ cho thực phẩm tươi sống/đông lạnh | `return-window` |
| Q3 | Bằng chứng QR và số seri khi nghi hàng giả | `return-evidence` |
| Q4 | Thời gian 7–14 ngày hoàn về thẻ | `refund-methods-and-time` |
| Q5 | Người bán hoàn dưới 50% và cơ chế cấn trừ | `seller-return-refund-obligations` |

Mỗi case gồm:

- `query`: câu hỏi.
- `gold_doc_id`: tài liệu đúng.
- `evidence_terms`: các cụm từ bắt buộc phải xuất hiện trong chunk bằng chứng.
- `gold_answer`: câu trả lời chuẩn để đối chiếu.
- `metadata_filter`: chỉ dùng khi câu hỏi cần giới hạn đối tượng.

Q5 dùng:

```python
{"audience": "seller"}
```

để chứng minh metadata filter hoạt động trên một yêu cầu thực tế.

### 9.2. Tạo chunk document

Với mỗi chiến lược, từng chunk được gắn ID:

```text
<doc_id>#<strategy_name>#<chunk_index>
```

Ví dụ:

```text
return-evidence#heading#2
```

Metadata gốc được giữ nguyên, đồng thời thêm `chunk_index` và `strategy`. Nhờ đó có thể truy vết một kết quả về đúng tài liệu, đúng chunk và đúng chiến lược.

### 9.3. Chấm theo evidence rank

Không chấm chỉ bằng `doc_id`. Một tài liệu có thể được retrieval đúng nhưng chunk trả về không chứa đủ thông tin để trả lời.

Benchmark chuẩn hóa nội dung và kiểm tra tất cả `evidence_terms` có cùng xuất hiện trong chunk hay không.

Quy tắc điểm:

| Vị trí chunk đủ bằng chứng | Điểm |
|---|---:|
| Top 1 | 2 |
| Top 2 hoặc Top 3 | 1 |
| Không có trong Top 3 | 0 |

Tổng tối đa là 10 điểm cho 5 câu hỏi.

### 9.4. Thí nghiệm A/B metadata filter

Với Q5, benchmark chạy hai lần:

```text
A: search không lọc audience
B: search_with_filter(audience=seller)
```

Kết quả heading strategy:

- Không lọc: top-3 còn lẫn chunk buyer.
- Có lọc: cả ba kết quả đều thuộc `seller-return-refund-obligations`.

Top-1 không đổi vì tài liệu seller vốn đã đứng đầu, nhưng context sạch hơn và không còn nội dung dành cho buyer.

---

## 10. Kết quả thực nghiệm

Kết quả khi dùng OpenRouter Nemotron:

| Chiến lược | Tham số | Số chunk | Độ dài trung bình | Điểm |
|---|---|---:|---:|---:|
| Fixed-size | size 450, overlap 80 | 21 | 389,76 | 10/10 |
| Recursive | size 450 | 23 | 302,22 | 9/10 |
| Heading-aware | max 700, fallback recursive | 27 | 257,15 | 9/10 |
| Sentence-based | tối đa 3 câu/chunk | 20 | 347,60 | 10/10 |

Nhận xét:

- Fixed-size và sentence-based đồng hạng nhất với 10/10.
- Sentence-based tạo ít chunk nhất, giữ trọn câu và đưa evidence của cả 5 câu lên top-1.
- Recursive và heading đều tìm được bằng chứng cho cả 5 câu trong top-3.
- Q4 của recursive và heading chỉ được 1 điểm vì chunk chứa thông tin thẻ tín dụng/ghi nợ nằm ở rank 2.
- Nemotron cải thiện rõ trường hợp Q3 so với lexical baseline nhờ hiểu quan hệ ngữ nghĩa giữa câu hỏi về “bằng chứng kỹ thuật” và nội dung “mã QR/số seri”.

### 10.1. Ý nghĩa của điểm 8/10, 9/10 và 10/10

Điểm không phải tỷ lệ phần trăm câu trả lời đúng hoàn toàn. Đây là tổng điểm theo vị trí evidence:

- `10/10`: cả 5 câu đều có chunk đủ bằng chứng ở top-1.
- `9/10`: bốn câu có bằng chứng ở top-1, một câu ở top-2 hoặc top-3.
- `8/10`: có thể là ba câu ở top-1 và hai câu ở top-2/3, hoặc một tổ hợp khác có tổng bằng 8.

Do đó 8/10 vẫn có thể nghĩa là cả 5 câu đều tìm thấy bằng chứng trong top-3, nhưng thứ hạng chưa tối ưu.

### 10.2. Phân tích failure Q4

Câu hỏi Q4 yêu cầu thời gian hoàn tiền về thẻ tín dụng/ghi nợ. Trong cùng tài liệu còn có các đoạn về Ví ShopeePay và tài khoản ngân hàng. Các chunk này cùng chủ đề hoàn tiền nên embedding đánh giá gần nhau.

Ở recursive và heading:

- Chunk ví/tài khoản ngân hàng đứng rank 1.
- Chunk thẻ tín dụng/ghi nợ đứng rank 2.
- Vì evidence vẫn nằm trong top-3, câu được 1/2 điểm.

Sentence-based không gặp failure này: chunk gom theo câu chứa đủ tên phương thức thanh toán và thời gian hoàn tiền, nên evidence lên rank 1 và đạt 2/2.

Cách cải thiện có thể thử:

- Query expansion với các cụm “credit card”, “debit card”, “ngân hàng phát hành”.
- Hybrid search kết hợp semantic score và lexical match.
- Reranker trên top-k ban đầu.
- Điều chỉnh chunk để heading “Thẻ tín dụng/ghi nợ” luôn đi cùng mốc `7–14 ngày làm việc`.
- Tăng bộ câu hỏi paraphrase để kiểm tra tính ổn định thay vì tối ưu cho một câu duy nhất.

Không sửa gold answer chỉ để tăng điểm vì điều đó làm mất giá trị của benchmark.

---

## 11. Cách chạy lại toàn bộ bài

### 11.1. Cài môi trường

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 11.2. Cấu hình embedding thật

Tạo `.env` ở thư mục gốc:

```env
OPENROUTER_API_KEY=<khóa-của-bạn>
OPENROUTER_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
```

Không commit `.env`.

### 11.3. Chạy kiểm thử

```powershell
python -m pytest tests/ -v
```

Trạng thái đã xác minh của dự án là **65 test pass**, trong đó toàn bộ 42 test cốt lõi của đề đều pass.

### 11.4. Chạy demo

```powershell
python main.py "Chunking là gì?"
```

`main.py` đọc các file mẫu, tạo vector, chạy top-3 search và đưa kết quả cho demo agent.

### 11.5. Chạy benchmark Nemotron

```powershell
python bench.py
```

Chương trình in báo cáo ra terminal và ghi đè kết quả mới vào:

```text
ket_qua_benchmark.txt
```

### 11.6. Chạy benchmark offline

```powershell
$env:BENCHMARK_EMBEDDING = "lexical"
python bench.py
Remove-Item Env:BENCHMARK_EMBEDDING
```

Lưu ý: chạy lexical sẽ ghi kết quả lexical vào `ket_qua_benchmark.txt`. Muốn giữ kết quả Nemotron làm bài nộp, cần chạy lại benchmark với OpenRouter sau đó.

---

## 12. Kiểm thử và các trường hợp biên

Các nhóm hành vi cần kiểm thử gồm:

### Chunking

- Chuỗi rỗng trả danh sách rỗng.
- Văn bản ngắn hơn `chunk_size` chỉ tạo một chunk.
- Fixed-size không tạo chunk vượt kích thước.
- Overlap đúng giữa hai chunk liên tiếp.
- Sentence chunker giữ dấu câu.
- Recursive chunker dừng đúng khi hết separator.
- Comparator không chia cho 0 với văn bản rỗng.

### Similarity

- Hai vector giống nhau có similarity cao.
- Vector trực giao có similarity bằng hoặc gần 0.
- Vector zero trả về `0.0`, không gây `ZeroDivisionError`.

### Store

- Thêm danh sách rỗng không làm thay đổi store.
- Số record bằng số `Document`, vì store không tự chunk.
- Search trả đúng thứ tự score giảm dần.
- `top_k <= 0` trả danh sách rỗng.
- Metadata filter được áp dụng trước ranking.
- Xóa một `doc_id` phải xóa toàn bộ chunk của tài liệu.
- Xóa `doc_id` không tồn tại trả `False`.
- Batch embedder trả sai số vector phải báo lỗi.

### Agent

- Store rỗng trả câu thông báo không tìm thấy thông tin.
- Prompt có context, câu hỏi và nhãn nguồn.
- Prompt yêu cầu không suy đoán ngoài tài liệu.
- Kết quả retrieval được đánh số để LLM trích dẫn.

### Benchmark và bảo mật

- Corpus có đúng 5–10 file Markdown.
- `sources.csv` khớp một-một với corpus.
- Có cả audience buyer và seller.
- Có đúng 5 benchmark case.
- Có ít nhất một case dùng metadata filter.
- `.env` không được Git theo dõi.
- Không in API key ra terminal hoặc file kết quả.

---

## 13. Các quyết định thiết kế quan trọng

### 13.1. Tại sao dùng store trong bộ nhớ?

Bài yêu cầu hiểu nguyên lý vector store, không yêu cầu vận hành cơ sở dữ liệu lớn. Store trong bộ nhớ có ưu điểm:

- Ít phụ thuộc.
- Chạy test rất nhanh.
- Dễ quan sát record, metadata và score.
- Đủ cho corpus 6 tài liệu và vài chục chunk.

Nếu triển khai thực tế với dữ liệu lớn, có thể thay bằng ChromaDB, FAISS, Qdrant hoặc dịch vụ vector database khác mà vẫn giữ giao diện `add/search/filter/delete` tương tự.

### 13.2. Tại sao chấm evidence thay vì chỉ chấm doc_id?

Một tài liệu dài có thể đúng chủ đề nhưng chunk top-1 không chứa câu trả lời. Agent chỉ nhìn thấy chunk được đưa vào context, không nhìn thấy toàn bộ tài liệu. Vì vậy, evidence-level evaluation phản ánh khả năng trả lời thực tế tốt hơn document-level evaluation.

### 13.3. Tại sao cần metadata filter?

Semantic embedding chỉ đo sự gần nhau về nội dung. Nó không đảm bảo ràng buộc nghiệp vụ như:

- Nội dung dành cho buyer hay seller.
- Chính sách của quốc gia nào.
- Phiên bản/ngày hiệu lực nào.
- Danh mục sản phẩm nào.

Metadata xử lý các ràng buộc cứng; embedding xử lý độ liên quan mềm. Hai cơ chế bổ sung cho nhau.

### 13.4. Tại sao giữ lexical baseline?

Lexical baseline giúp:

- Chạy lại không cần mạng hoặc API key.
- So sánh lợi ích thực của semantic embedding.
- Phát hiện benchmark quá dễ: nếu lexical đã đạt tuyệt đối, bộ câu hỏi có thể chỉ kiểm tra trùng từ.

---

## 14. Hạn chế hiện tại và hướng phát triển

Hệ thống hiện tại có các hạn chế:

- Store chỉ tồn tại trong bộ nhớ, tắt chương trình là mất vector.
- Cache OpenRouter chỉ tồn tại trong một process, chưa lưu xuống đĩa.
- Chưa có reranker.
- Chưa kết hợp BM25/keyword search với semantic search.
- Benchmark mới có 5 câu, chưa kiểm tra nhiều cách diễn đạt tương đương.
- Agent mẫu chưa gọi một LLM thật trong `main.py`; `demo_llm` chỉ cho thấy prompt được tạo đúng.
- Parser YAML trong benchmark chỉ hỗ trợ front matter scalar đơn giản.
- Chunker theo câu chưa xử lý đầy đủ chữ viết tắt và số thập phân.

Hướng phát triển hợp lý:

1. Thêm persistent vector database.
2. Cache embedding theo hash nội dung để giảm số lần gọi API.
3. Thêm hybrid retrieval và reranking.
4. Mở rộng benchmark với câu hỏi paraphrase và câu không có đáp án.
5. Đánh giá thêm precision@k, recall@k, MRR và nDCG.
6. Gắn citation với `source_url` và vị trí section chính xác.
7. Theo dõi phiên bản tài liệu để re-index khi chính sách thay đổi.

---

## 15. Đối chiếu checkpoint

| Checkpoint | Cách hoàn thành | Bằng chứng |
|---|---|---|
| CP1 | Thiết lập môi trường và chạy baseline | Ghi nhận 11 pass, 31 fail ban đầu |
| CP2 | Thu thập và chuẩn hóa corpus | 6 file Markdown, `sources.csv`, buyer/seller metadata |
| CP3 | Cài đặt chunker, similarity và comparator | Các test chunking/similarity pass |
| CP4 | Hoàn thiện store và agent | Toàn bộ test cốt lõi pass, demo chạy được |
| CP5 | Thiết kế 5 câu hỏi và 4 chiến lược cho nhóm 4 người | `BENCHMARK_CASES` và bốn cấu hình trong `bench.py` |
| CP6 | Chạy, so sánh và phân tích lỗi | `ket_qua_benchmark.txt`, hai báo cáo |
| CP7 | Hoàn thiện tài nguyên nộp bài | Code, data, benchmark và báo cáo đã có; còn thao tác push/nộp link nếu chưa thực hiện |

---

## 16. Kết luận

Bài làm không chỉ hoàn thiện các hàm theo test mà còn xây dựng một quy trình retrieval có thể đo lường:

- Dữ liệu có nguồn gốc và metadata rõ ràng.
- Ba cách chunking được chạy trên cùng corpus để so sánh công bằng.
- Vector store hỗ trợ thêm, tìm, lọc và xóa.
- Agent tạo prompt có grounding và citation.
- Benchmark chấm theo vị trí của bằng chứng thật thay vì chỉ theo tên tài liệu.
- Semantic embedding Nemotron cho kết quả tốt hơn lexical baseline ở câu hỏi cần hiểu cách diễn đạt.

Kết quả hiện tại cho thấy fixed-size với overlap đạt `10/10`, recursive đạt `9/10`, heading-aware đạt `9/10`, và sentence-based đạt `10/10`. Quan trọng hơn, phân tích Q4 chỉ ra rằng retrieval đúng tài liệu chưa chắc đã đưa đúng bằng chứng lên rank 1; sentence-based giải quyết được trường hợp này nhờ giữ trọn các câu liên quan, trong khi recursive/heading vẫn có thể cần hybrid search hoặc reranking.

# Module AI Product Labeling System

## 1. Tổng quan dự án

### 1.1 Mô tả dự án
Hệ thống AI tự động phân tích và gắn nhãn sản phẩm từ hình ảnh, sử dụng:
- **Qwen2.5-VL** cho phân tích hình ảnh và gắn nhãn thông minh
- **Jina CLIP v2** cho tạo embedding đa phương tiện (text + image)
- **Milvus Vector DB** để lưu trữ và tìm kiếm vector
- **PostgreSQL** cho dữ liệu gốc
- **Streaming Pipeline** xử lý real-time

### 1.2 Kiến trúc tổng thể
```
PostgreSQL → Crawl Data → Qwen2.5-VL Label → Jina Embedding → Milvus Insert
     ↑              ↓                ↓               ↓            ↓
  Raw Data    Filter Duplicates   Smart Analysis   Vector Gen   Search Ready
```

## 2. Cấu trúc mã nguồn

### 2.1 File `label_me.py` - Core Pipeline

#### Classes chính:

**`ProductLabel`**
- **Mục đích**: Cấu trúc lưu trữ kết quả phân tích từ Qwen2.5-VL
- **Thuộc tính**: 16 trường phân tích chi tiết (image_recipient, target_audience, usage_purpose, etc.)

**`ProductRecord`**
- **Mục đích**: Cấu trúc record để insert vào Milvus
- **Thuộc tính**: Chứa vectors, metadata, thông tin sản phẩm

**`StreamingProductPipeline`** - Class chính
- **Mục đích**: Pipeline xử lý streaming từ crawl đến insert

#### Phương thức quan trọng:

**`__init__()`**
```python
def __init__(self, db_config, qwen_model="qwen2.5vl:latest", 
             milvus_host="10.10.4.25", max_workers=1, insert_batch_size=5)
```
**Logic chi tiết:**
1. **Khởi tạo cấu hình**: Lưu trữ tham số database, model, Milvus
2. **Khởi tạo Embedding Service**: Tạo instance EmbeddingService với Jina CLIP v2
3. **Kết nối PostgreSQL**: Gọi `_connect_db()` để establish connection
4. **Kết nối Milvus**: Gọi `_connect_milvus()` và `_setup_collection()`
5. **Khởi tạo queues & locks**: Tạo queue cho streaming, locks cho thread safety
6. **Khởi tạo statistics**: Dict tracking processed/inserted/failed counts
7. **Cache initialization**: Image cache với thread-safe locks

**`run_streaming_pipeline()`**
```python
def run_streaming_pipeline(self, start_date: str, end_date: str, limit: int = 1000)
```
**Logic từng bước:**
1. **Reset statistics**: Xóa stats cũ, ghi start time
2. **STEP 1 - Crawl**: 
   - Gọi `crawl_data_by_date_range()` lấy raw data từ PostgreSQL
   - Kiểm tra nếu không có data thì return
3. **STEP 2 - Filter duplicates**:
   - Gọi `filter_existing_records()` để loại bỏ records đã tồn tại
   - Update statistics với duplicate count
4. **STEP 3 - Start background worker**:
   - Tạo thread chạy `_streaming_insert_worker()` 
   - Worker này lắng nghe queue để insert records
5. **STEP 4 - Parallel processing**:
   - Dùng ThreadPoolExecutor với max_workers threads
   - Mỗi thread chạy `_process_and_queue_record()` cho 1 record
   - Monitor progress và handle exceptions/timeouts
6. **STEP 5 - Cleanup**:
   - Signal worker thread dừng (put None vào queue)
   - Join thread, tính statistics cuối cùng

**`crawl_data_by_date_range()`**
```python
def crawl_data_by_date_range(self, start_date: str, end_date: str, limit: int = 1000)
```
**Logic SQL query:**
1. **Connection check**: Kiểm tra và reconnect DB nếu cần
2. **Query construction**: 
   ```sql
   SELECT 
       COALESCE(product_id::text, CONCAT('SP_', SUBSTRING(MD5(RANDOM()::text), 1, 8))) as id_sanpham,
       COALESCE(image, '') as image,
       -- Generate fake metrics from impression
       ROUND(impression * (0.01 + RANDOM() * 0.05))::int::text as like,
   FROM ai_craw.product_marketing_summary
   WHERE published_at BETWEEN %s AND %s
   AND image IS NOT NULL AND image != ''
   ORDER BY published_at DESC LIMIT %s
   ```
3. **Data processing**: Convert cursor results thành list of dictionaries
4. **Error handling**: Return empty list nếu có lỗi

**`filter_existing_records()`**
```python
def filter_existing_records(self, raw_data_list: List[Dict])
```
**Logic batch checking:**
1. **Extract IDs**: Lấy tất cả id_sanpham từ raw_data_list
2. **Batch query**: Gọi `check_ids_exist_batch()` để kiểm tra existence
3. **Split records**: 
   - `new_records`: Records chưa tồn tại trong Milvus
   - `existing_records`: Records đã tồn tại (skip)
4. **Return tuple**: (new_records, existing_records, duplicate_count)

**`check_ids_exist_batch()`**
```python
def check_ids_exist_batch(self, id_list: List[str]) -> Dict[str, bool]
```
**Logic tối ưu batch query:**
1. **Batch splitting**: Chia id_list thành batches 100 IDs
2. **Milvus query**: Cho mỗi batch:
   ```python
   expr = " or ".join([f'id_sanpham == "{id}"' for id in batch_ids])
   results = self.collection.query(expr=expr, output_fields=["id_sanpham"])
   ```
3. **Result mapping**: Tạo dict {id: exists_boolean}
4. **Combine results**: Merge tất cả batch results

**`label_image_with_qwen()`**
```python
def label_image_with_qwen(self, image_url: str) -> ProductLabel
```
**Logic AI analysis:**
1. **Image preprocessing**: Gọi `_analyze_with_qwen_vl()` 
2. **Download & optimize**: `_download_image_cached()` + `_smart_resize_image()`
3. **AI inference**:
   ```python
   response = ollama.generate(
       model=self.qwen_model,
       prompt=detailed_prompt,  # 16 category analysis
       images=[base64_image],
       options={'temperature': 0.0, 'num_gpu': -1}
   )
   ```
4. **JSON parsing**: `_extract_json_from_qwen_response()` parse response
5. **Create ProductLabel**: Mapping JSON results to ProductLabel dataclass

**`_smart_resize_image()`**
```python
def _smart_resize_image(self, image_bytes: bytes, max_width=1024, max_height=1024)
```
**Logic image optimization:**
1. **Load image**: PIL.Image.open() từ BytesIO
2. **Size check**: So sánh với max dimensions
3. **Aspect ratio preserved resize**:
   ```python
   ratio = min(max_width/original_width, max_height/original_height)
   new_size = (int(original_width * ratio), int(original_height * ratio))
   ```
4. **Format conversion**: RGBA → RGB với white background
5. **JPEG optimization**: Save với quality=85, optimize=True, progressive=True
6. **Size reporting**: Log original vs optimized sizes

**`_process_and_queue_record()`**
```python
def _process_and_queue_record(self, raw_data: Dict[str, Any]) -> bool
```
**Logic xử lý 1 record:**
1. **Validate image URL**: Check raw_data['image'] không empty
2. **AI Labeling**: Gọi `label_image_with_qwen()` → ProductLabel
3. **Create metadata**: Convert ProductLabel thành dict
4. **Generate description**: Gọi `_create_description()` tạo markdown text
5. **Generate vectors**: Gọi `_generate_vectors()` → (image_vector, text_vector)
6. **Create ProductRecord**: Assemble tất cả data thành ProductRecord
7. **Queue for insert**: `self.ready_records_queue.put(record)`
8. **Update stats**: Increment processed_count (thread-safe)

**`_streaming_insert_worker()`**
```python
def _streaming_insert_worker(self)
```
**Logic background worker:**
1. **Batch buffer initialization**: `batch_buffer = []`
2. **Infinite loop**:
   - `record = self.ready_records_queue.get(timeout=5)`
   - Nếu record is None: break (shutdown signal)
   - Add record to batch_buffer
   - Nếu `len(batch_buffer) >= insert_batch_size`: insert batch
3. **Timeout handling**: Nếu queue empty 5s → insert batch hiện tại
4. **Final cleanup**: Insert batch_buffer còn lại trước khi exit

**`_insert_batch_immediate()`**
```python
def _insert_batch_immediate(self, records: List[ProductRecord])
```
**Logic Milvus batch insert:**
1. **Data preparation**: Extract từng field từ ProductRecord list:
   ```python
   ids = [record.id_sanpham for record in records]
   image_vectors = [record.image_vector for record in records]
   # ... cho tất cả fields
   ```
2. **Milvus insert**:
   ```python
   data = [ids, image_vectors, description_vectors, ...]
   mr = self.collection.insert(data)
   self.collection.flush()  # Force persist
   ```
3. **Statistics update**: Thread-safe update inserted_count, insert_batches
4. **Error handling**: Catch exceptions, update failed_count

**`_create_description()`**
```python
def _create_description(self, label: ProductLabel) -> str
```
**Logic tạo markdown description:**
1. **Helper function**: `format_list()` format arrays thành comma-separated string
2. **Template structure**: 
   - Thông Tin Cơ Bản (main_subject, product_type, trademark_level)
   - Đối Tượng & Mục Đích (recipient, audience, purpose, occasion)
   - Phân Loại Sản Phẩm (niche, sentiment, message_type, personalization)
   - Thiết Kế & Trưng Bày (context, design_style, color_aesthetic)
   - Tóm Tắt (summary paragraph)
3. **Safe formatting**: Handle empty lists với "Unknown" fallback

### 2.2 File `embedding_service.py` - Embedding Service

#### Classes chính:

**`JinaV4EmbeddingService`**
- **Model**: jinaai/jina-clip-v2  
- **Chức năng**: Tạo embedding cho text và image
- **Tối ưu**: Auto dtype selection, GPU acceleration, batch processing

**`EmbeddingService`**
- **Chức năng**: Wrapper class tương thích với pipeline hiện tại
- **Method chính**: `_generate_vectors()`, `_generate_vectors_batch()`

#### Phương thức chi tiết:

**`__init__()`**
```python
def __init__(self, device=None, max_length=8192)
```
**Logic khởi tạo:**
1. **Device selection**:
   ```python
   self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
   ```
2. **Dtype optimization**:
   - GPU + BF16 support: `torch.bfloat16`  
   - GPU only: `torch.float16`
   - CPU: `torch.float32`
3. **Model loading**:
   ```python
   self.model = AutoModel.from_pretrained(
       "jinaai/jina-clip-v2", 
       torch_dtype=model_dtype
   ).to(self.device)
   ```
4. **Fallback mechanism**: Nếu lỗi dtype, retry với float32
5. **Embedding dimension detection**: Test với dummy input

**`embed_text()`**
```python
def embed_text(self, text: str, normalize_output: bool = True) -> np.ndarray
```
**Logic embedding text:**
1. **Input validation**: Return zero vector nếu text empty
2. **Preprocessing**:
   ```python
   inputs = self.processor(
       text=[text], 
       return_tensors="pt", 
       padding=True, 
       truncation=True,
       max_length=self.max_length
   )
   ```
3. **Device transfer**: Move inputs to GPU/CPU
4. **Model inference**: 
   ```python
   with torch.no_grad():
       outputs = self._safe_model_inference(
           self.model.get_text_features, 
           **inputs
       )
   ```
5. **Output processing**: Convert to float32 numpy, normalize if requested

**`embed_image()`**
```python
def embed_image(self, image_url: str, normalize_output: bool = True) -> np.ndarray
```
**Logic embedding image:**
1. **Input validation**: Return zero vector nếu URL empty
2. **Image loading**: Gọi `_load_image()`
   - Download từ URL hoặc load local file
   - Convert to RGB format
   - Thumbnail resize nếu > 1024px
3. **Preprocessing**:
   ```python
   inputs = self.processor(images=[image], return_tensors="pt")
   ```
4. **Model inference**: Tương tự embed_text với `get_image_features`
5. **Output processing**: Convert to normalized numpy array

**`_load_image()`**
```python
def _load_image(self, image_url: str) -> Image.Image
```
**Logic load và preprocess image:**
1. **URL detection**: Check http:// hoặc https://
2. **Download handling**:
   ```python
   response = requests.get(url, timeout=30, headers={
       'User-Agent': 'Mozilla/5.0...'
   })
   image = Image.open(BytesIO(response.content))
   ```
3. **Format conversion**: Convert to RGB nếu khác format
4. **Size optimization**: Thumbnail resize max 1024px với LANCZOS
5. **Error handling**: Raise ValueError với message chi tiết

**`_safe_model_inference()`**
```python  
def _safe_model_inference(self, model_fn, **kwargs)
```
**Logic error recovery:**
1. **Normal execution**: Try gọi model_fn với kwargs
2. **Dtype error detection**:
   ```python
   if "BFloat16" in str(e) or "unsupported ScalarType" in str(e):
   ```
3. **Fallback mechanism**: 
   - Convert model to float32: `self.model = self.model.float()`
   - Retry model inference
4. **Re-raise**: Nếu không phải dtype error

**`embed_multimodal()`**
```python
def embed_multimodal(self, text: str, image_url: str = None, normalize: bool = True) -> tuple
```
**Logic đa phương tiện:**
1. **Text embedding**: Luôn tạo text embedding
2. **Image embedding**: Chỉ tạo nếu có image_url
3. **Fallback**: Zero vector nếu image_url empty
4. **Return**: Tuple (image_vector, text_vector)

**`embed_texts_batch()`**
```python
def embed_texts_batch(self, texts: List[str], normalize: bool = True, batch_size: int = 32)
```
**Logic batch processing:**
1. **Batch splitting**: 
   ```python
   for i in range(0, len(texts), batch_size):
       batch_texts = texts[i:i + batch_size]
   ```
2. **Batch preprocessing**:
   ```python
   inputs = self.processor(
       text=batch_texts,
       return_tensors="pt", 
       padding=True, 
       truncation=True
   )
   ```
3. **Batch inference**: Single forward pass cho cả batch
4. **Individual extraction**: Split embeddings cho từng text
5. **Error handling**: Zero vectors cho failed batch

**`embed_images_batch()`**
```python
def embed_images_batch(self, image_urls: List[str], normalize: bool = True, batch_size: int = 16)
```
**Logic batch image processing:**
1. **Smaller batch size**: 16 thay vì 32 (images consume more memory)
2. **Image loading loop**:
   ```python
   for url in batch_urls:
       try:
           image = self._load_image(url) if url else None
           batch_images.append(image)
   ```
3. **Valid images filtering**: Loại bỏ None images
4. **Batch processing**: Chỉ process valid images
5. **Result mapping**: Map embeddings trở lại original order
6. **Mixed results**: Combine real embeddings với zero vectors

**`get_model_info()`**
```python
def get_model_info(self) -> dict
```
**Logic system info:**
```python
return {
    'model_name': self.model_name,
    'embedding_dimension': self.embedding_dim,
    'device': self.device,
    'torch_dtype': str(self.model.dtype)
}
```

#### Wrapper Class Logic:

**`EmbeddingService._generate_vectors()`**
```python
def _generate_vectors(self, text: str, image_url: str = None) -> tuple
```
**Logic tích hợp với pipeline:**
1. **Multimodal call**: Gọi `embed_multimodal()`
2. **Normalization**: Luôn normalize=True cho cosine similarity
3. **Logging**: Log embedding dimensions
4. **Return**: (image_vector, text_vector) format cho pipeline

**`_generate_vectors_batch()`**
```python  
def _generate_vectors_batch(self, descriptions: List[str], image_urls: List[str] = None) -> tuple
```
**Logic batch integration:**
1. **Text batch**: Gọi `embed_texts_batch()`
2. **Image batch**: Gọi `embed_images_batch()` nếu có URLs
3. **Fallback**: Zero vectors nếu không có image_urls  
4. **Return**: (image_vectors_list, text_vectors_list)

## 3. Cấu hình hệ thống

### 3.1 Database Configuration
```python
db_config = {
    'host': '45.79.189.110',
    'database': 'ai_db', 
    'user': 'ai_engineer',
    'password': 'StrongPassword123',
    'port': 5432
}
```

### 3.2 Milvus Configuration
```python
milvus_host = "10.10.4.25"
milvus_port = "19530"
collection_name = "product_collection_v4"
```

### 3.3 Model Configuration
```python
qwen_model = "qwen2.5vl:latest"  # Qwen2.5-VL model
jina_model = "jinaai/jina-clip-v2"  # Embedding model
```

### 3.4 Pipeline Parameters
```python
max_workers = 1          # Số workers xử lý parallel
insert_batch_size = 5    # Batch size cho insert
embedding_dim = 1024     # Dimension của embedding vectors
```

## 4. Cấu trúc dữ liệu

### 4.1 PostgreSQL Schema
**Table**: `ai_craw.product_marketing_summary`

Các cột chính:
- `product_id`: ID sản phẩm
- `image`: URL hình ảnh
- `published_at`: Thời gian publish
- `title`: Tiêu đề sản phẩm
- `store`: Tên cửa hàng
- `impression`, `clicks`, `spend`: Metrics marketing

### 4.2 Milvus Collection Schema
**Collection**: `product_collection_v4`

Các field:
- `id_sanpham` (VARCHAR, Primary): ID duy nhất
- `image_vector` (FLOAT_VECTOR): Image embedding 1024D
- `description_vector` (FLOAT_VECTOR): Text embedding 1024D
- `metadata` (JSON): Kết quả phân tích từ Qwen2.5-VL
- `image`, `description`: Dữ liệu gốc
- Các field khác: `date`, `like`, `comment`, `share`, `platform`, etc.

### 4.3 Metadata Structure (từ Qwen2.5-VL)
16 trường phân tích:
1. `image_recipient`: Người nhận sản phẩm
2. `target_audience`: Đối tượng mua hàng
3. `usage_purpose`: Mục đích sử dụng
4. `occasion`: Dịp sử dụng
5. `niche_theme`: Chủ đề/ngách thị trường
6. `sentiment_tone`: Cảm xúc/tông điệu
7. `message_type`: Loại thông điệp
8. `personalization_type`: Kiểu cá nhân hóa
9. `product_type`: Loại sản phẩm
10. `placement_display_context`: Ngữ cảnh trưng bày
11. `design_style`: Phong cách thiết kế
12. `color_aesthetic`: Thẩm mỹ màu sắc
13. `trademark_level`: Mức độ thương hiệu
14. `main_subject`: Chủ thể chính in trên sản phẩm
15. `text`: Nội dung chữ trên sản phẩm

## 5. Hướng dẫn vận hành

### 5.1 Setup Environment
```bash
# Install dependencies
pip install psycopg2 requests pillow pymilvus ollama torch transformers scikit-learn

# Pull Qwen model
ollama pull qwen2.5vl:latest

# Setup GPU (nếu có)
export CUDA_VISIBLE_DEVICES=0
export OLLAMA_NUM_GPU=1
```

### 5.2 Chạy Pipeline
```python
from label_me import StreamingProductPipeline

# Khởi tạo pipeline
pipeline = StreamingProductPipeline(
    db_config=db_config,
    qwen_model="qwen2.5vl:latest",
    milvus_host="10.10.4.25",
    milvus_port="19530",
    max_workers=1,
    insert_batch_size=5
)

# Chạy pipeline
stats = pipeline.run_streaming_pipeline(
    start_date="2020-01-01",
    end_date="2021-10-10", 
    limit=1000
)
```

### 5.3 Monitoring
Pipeline cung cấp real-time statistics:
- `processed_count`: Số records đã xử lý
- `inserted_count`: Số records đã insert thành công
- `failed_count`: Số records thất bại
- `duplicate_count`: Số records trùng lặp
- `total_time_seconds`: Tổng thời gian xử lý

## 6. Tối ưu Performance

### 6.1 GPU Optimization
- Qwen2.5-VL: Sử dụng GPU với các tham số được tối ưu
- Jina CLIP: Auto dtype selection (bfloat16/float16/float32)
- Memory management: Clear cache định kỳ

### 6.2 Streaming Architecture
- Insert ngay sau khi embedding → Tiết kiệm memory
- Queue-based processing → Real-time feedback
- Parallel processing → Tăng throughput
- Batch insert → Giảm I/O overhead

### 6.3 Smart Image Processing
- Auto resize images (512x512) cho AI analysis
- Quality optimization (JPEG 90%)
- Memory-efficient processing
- Caching mechanism

## 7. Error Handling

### 7.1 Robust Error Handling
- Database connection retry logic
- Model inference error recovery
- Image download timeout handling
- Vector generation fallback (zero vectors)

### 7.2 Monitoring & Logging
- Detailed progress logging
- Error statistics tracking
- Failed records logging
- Performance metrics

## 8. Backup & Recovery

### 8.1 Data Backup
- PostgreSQL: Standard database backup
- Milvus: Collection backup/restore
- Statistics: JSON export functionality

### 8.2 Recovery Procedures
- Duplicate detection prevents data loss
- Resume capability từ timestamp
- Partial processing recovery

## 9. Future Improvements

### 9.1 Scalability
- Multi-GPU support
- Distributed processing
- Load balancing
- Auto-scaling workers

### 9.2 Model Upgrades
- Support multiple vision models
- A/B testing framework
- Model performance comparison
- Fine-tuning capabilities

## 10. Liên hệ & Support

### 10.1 Technical Issues
- Check logs trong console output
- Verify database/Milvus connections
- Monitor GPU memory usage
- Check model availability (ollama list)

### 10.2 Performance Tuning
- Adjust `max_workers` dựa trên hardware
- Optimize `insert_batch_size` cho Milvus
- Configure model parameters trong ollama
- Monitor memory usage

## 11. Logic từng hàm hỗ trợ quan trọng

### 11.1 Database và Connection Logic

**`_connect_db()`**
```python
def _connect_db(self) -> bool
```
**Logic kết nối PostgreSQL:**
1. **Connection establishment**: `psycopg2.connect(**self.db_config)`
2. **Error handling**: Catch exceptions, log lỗi, return False
3. **Success confirmation**: Log thành công, return True
4. **Connection storage**: Lưu vào `self.db_connection`

**`_connect_milvus()`**
```python  
def _connect_milvus(self)
```
**Logic kết nối Milvus:**
1. **Connection setup**:
   ```python
   connections.connect(
       alias="default",
       host=self.milvus_host, 
       port=self.milvus_port
   )
   ```
2. **Exception handling**: Raise Exception với error message nếu fail

### 11.2 Milvus Collection Management Logic

**`_create_collection_schema()`**
```python
def _create_collection_schema(self)
```
**Logic tạo schema Milvus:**
1. **Field definitions**:
   ```python
   fields = [
       FieldSchema(name="id_sanpham", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=100),
       FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
       FieldSchema(name="description_vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
       # ... other fields
   ]
   ```
2. **Schema creation**: `CollectionSchema(fields=fields, description=...)`
3. **Dynamic dimension**: Sử dụng `self.embedding_dim` từ Jina model

**`_setup_collection()`**
```python
def _setup_collection(self)
```
**Logic setup collection:**
1. **Existence check**: `utility.has_collection(self.collection_name)`
2. **Load existing**: `Collection(self.collection_name)` nếu tồn tại
3. **Create new**: 
   - Tạo schema với `_create_collection_schema()`
   - `Collection(name, schema)`
   - Gọi `_create_indexes()`
4. **Load collection**: `self.collection.load()` để ready for queries

**`_create_indexes()`**
```python
def _create_indexes(self)
```
**Logic tạo vector indexes:**
1. **nlist calculation**: `nlist = min(self.embedding_dim, 1024)`
2. **Index parameters**:
   ```python
   index_params = {
       "metric_type": "COSINE",     # Cosine similarity
       "index_type": "IVF_FLAT",    # Inverted File Flat
       "params": {"nlist": nlist}
   }
   ```
3. **Create indexes**: Tạo riêng cho image_vector và description_vector
4. **Optimization**: nlist phụ thuộc embedding dimension

### 11.3 Qwen2.5-VL Analysis Logic

**`_create_qwen_prompt()`**
```python
def _create_qwen_prompt(self) -> str
```
**Logic tạo AI prompt:**
1. **Structured analysis framework**: 16 categories phân tích
2. **Think-step-by-step approach**: Hướng dẫn AI reasoning
3. **Specific instructions**: 
   - Focus on printed/visual content, NOT product itself
   - Market segmentation thinking
   - Consumer psychology analysis
4. **Output format**: Strict JSON structure requirement
5. **Quality standards**: Self-check questions

**`_download_image_cached()`**
```python
def _download_image_cached(self, url: str) -> bytes
```
**Logic image caching:**
1. **Cache check**: Thread-safe check `self.image_cache`
2. **Cache hit**: Return cached bytes immediately  
3. **Cache miss**:
   ```python
   response = requests.get(url, timeout=15, headers={'User-Agent': '...'})
   response.raise_for_status()
   image_bytes = response.content
   ```
4. **Cache update**: Thread-safe store in cache
5. **Error handling**: Raise Exception với detailed message

**`_extract_json_from_qwen_response()`**
```python
def _extract_json_from_qwen_response(self, content: str) -> Dict
```
**Logic parse AI response:**
1. **Clean content**: Remove markdown code blocks
   ```python
   content = re.sub(r'```json\s*', '', content)
   content = re.sub(r'```\s*', '', content)
   ```
2. **Direct JSON parse**: Try `json.loads(content)` first
3. **Regex fallback**: Search for JSON pattern trong text
   ```python
   json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
   ```
4. **Error handling**: Raise exception nếu không tìm thấy valid JSON

**`_analyze_with_qwen_vl()`**
```python
def _analyze_with_qwen_vl(self, image_url: str) -> Dict
```
**Logic AI inference:**
1. **Image download**: Gọi `_download_image_cached()`
2. **Image optimization**: Gọi `_smart_resize_image()` 
3. **Base64 encoding**: Encode optimized image
4. **Ollama inference**:
   ```python
   response = ollama.generate(
       model=self.qwen_model,
       prompt=prompt,
       images=[image_base64],
       options={
           'temperature': 0.0,    # Deterministic
           'num_gpu': -1,         # Use all GPUs  
           'gpu_layers': -1,      # All layers on GPU
           'f16_kv': True,        # FP16 for KV cache
           'mlock': True          # Lock model in RAM
       }
   )
   ```
5. **Response parsing**: Extract JSON từ AI response

### 11.4 Monitoring và Statistics Logic

**`get_real_time_stats()`**
```python
def get_real_time_stats(self) -> Dict[str, Any]
```
**Logic thread-safe statistics:**
1. **Thread safety**: Sử dụng `self.insert_stats_lock`
2. **Deep copy**: Return `self.stats.copy()` để avoid race conditions
3. **Real-time access**: Có thể gọi từ bất kỳ thread nào

**`start_progress_monitor()`**
```python
def start_progress_monitor(self, total_records: int, interval: int = 10)
```
**Logic background monitoring:**
1. **Monitor thread**: Tạo daemon thread
2. **Periodic reporting**: Sleep `interval` seconds, log progress
3. **Completion detection**: Exit when processed >= total_records
4. **Thread management**: Return thread handle để có thể control

### 11.5 Cleanup và Resource Management Logic

**`clear_cache()`**
```python
def clear_cache(self)
```
**Logic memory cleanup:**
1. **Thread-safe clear**: Sử dụng `self.cache_lock`
2. **Memory release**: `self.image_cache.clear()`
3. **Logging**: Confirm cache cleared

**`close_connections()`**
```python
def close_connections(self)
```
**Logic cleanup resources:**
1. **Database connection**: `self.db_connection.close()`
2. **Error handling**: Try/except để avoid exceptions during cleanup
3. **Logging**: Confirm connections closed

**`save_stats_to_json()`**
```python
def save_stats_to_json(self, stats: Dict[str, Any], filename: str = None)
```
**Logic persist statistics:**
1. **Filename generation**: Auto timestamp nếu không provide
2. **UTF-8 encoding**: `encoding='utf-8'` cho Vietnamese text
3. **JSON formatting**: `indent=2, ensure_ascii=False` 
4. **Error handling**: Catch và log file write errors

### 11.6 Queue Management Logic

**Queue workflow trong streaming:**
1. **Producer threads**: `_process_and_queue_record()` put records
2. **Consumer thread**: `_streaming_insert_worker()` get records  
3. **Batch accumulation**: Worker accumulates until batch_size
4. **Timeout handling**: Auto-insert partial batches after timeout
5. **Shutdown signal**: None object signals worker to stop
6. **Thread synchronization**: Join với timeout để ensure cleanup

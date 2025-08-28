# TÀI LIỆU BÀN GIAO DỰ ÁN
## RAG Multi-Agent Workflow for Enhanced RnD Assistant

## 🏗️ KIẾN TRÚC TỔNG QUAN

### Cấu trúc Workflow
```
START → Query Classifier → [Smart Search | Traditional Search] → Analysis Agents → Response Generator → END
```

### Thành phần chính:
1. **RAGMultiAgentWorkflow** - Orchestrator chính
2. **Query Classifier** - Phân loại câu hỏi
3. **Smart Product Search** - Tìm kiếm thông minh
4. **Analysis Agents** - Các agent phân tích chuyên biệt
5. **Response Generator** - Tạo câu trả lời cuối cùng
6. **Milvus Manager** - Quản lý vector database
7. **Search Tools** - Bộ công cụ tìm kiếm nâng cao
8. **Data Processor** - Xử lý và cache dữ liệu

---

## 📁 CHI TIẾT CÁC FILE VÀ HÀM

### 1. FILE: `RAGMultiAgentWorkflow` (Orchestrator chính)

#### Mục đích:
Điều phối toàn bộ workflow, quản lý luồng xử lý giữa các agents

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: Khởi tạo workflow và kết nối các thành phần
**Logic**:
- Kết nối Milvus database
- Khởi tạo tất cả các agents
- Xây dựng workflow graph

##### `_build_workflow(self) -> StateGraph`
**Chức năng**: Xây dựng LangGraph workflow
**Logic**:
- Định nghĩa các nodes (classify_query, search_products, smart_search, v.v.)
- Thiết lập routing logic:
  - START → classify_query
  - classify_query → [smart_search | search_products]
  - search_products → [benchmark | market_gap | verify_idea | audience_volume]
  - Tất cả → generate_response → END

##### `_route_after_classification(self, state) -> str`
**Chức năng**: Điều hướng sau phân loại
**Logic**:
- Nếu query_type == "smart_search" → đi đến smart_search
- Ngược lại → đi đến search_products

##### `_route_to_analysis(self, state) -> str`
**Chức năng**: Điều hướng đến analysis agent phù hợp
**Logic**: Trả về đúng query_type để route đến agent tương ứng

##### `async process_query(self, query: str, input_image: str = None) -> str`
**Chức năng**: Xử lý query chính và trả về kết quả
**Logic**:
- Tạo initial_state từ query và image
- Chạy workflow.ainvoke()
- Trả về final_answer hoặc error message

---

### 2. FILE: `query_classifier_agent.py`

#### Mục đích:
Phân loại câu hỏi của user vào 5 loại chính để định hướng xử lý

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: Khởi tạo classifier với temperature=0 để đảm bảo tính nhất quán
**Logic**: Tạo ChatPromptTemplate với system prompt định nghĩa 5 loại câu hỏi

##### `async process(self, state) -> Dict[str, Any]`
**Chức năng**: Phân loại query vào 1 trong 5 loại
**Logic**:
- Gửi query đến LLM với prompt định nghĩa các loại
- Nhận response và clean up
- Cập nhật state["query_type"]
- Log kết quả phân loại

**5 Loại được phân loại**:
1. **"benchmark"**: So sánh đối thủ, winning/losing ideas
2. **"market_gap"**: Khoảng trống thị trường, cơ hội chưa khai thác
3. **"verify_idea"**: Xác minh ý tưởng, kiểm tra concept
4. **"audience_volume"**: Ước tính audience volume
5. **"smart_search"**: Tìm kiếm thông minh (mặc định cho các trường hợp khác)

---

### 3. FILE: `smart_product_search_agent.py`

#### Mục đích:
Agent tìm kiếm sản phẩm thông minh với khả năng xử lý đa phương thức và filter extraction

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: Khởi tạo với vision model và metadata mappings
**Logic**:
- Khởi tạo ChatOpenAI cho vision tasks
- Load metadata mappings cho backward compatibility
- Temperature=0.2 để cân bằng tính sáng tạo và nhất quán

##### `async _extract_filters_with_ai(self, user_query: str) -> Dict[str, Any]`
**Chức năng**: **CORE FUNCTION** - Sử dụng AI để extract filters từ query
**Logic chi tiết**:

1. **Tạo prompt phân tích**:
   - Lấy thời gian hiện tại
   - Tạo detailed prompt yêu cầu AI nhận diện:
     - NAME_STORE: Tên cửa hàng/thương hiệu
     - PLATFORM: Nền tảng bán hàng
     - DATE_RANGE & TIME_FILTERS: Các điều kiện thời gian

2. **Gửi query đến AI**:
   - Sử dụng LLM để phân tích query
   - AI trả về JSON format với các filters

3. **Validation và cleanup**:
   - Parse JSON response
   - Validate từng field (name_store, platform, date filters)
   - Check date format với `_is_valid_date_string()`
   - **QUAN TRỌNG**: Loại bỏ date filters nếu không có time keywords

##### `_is_valid_date_string(self, date_str: str) -> bool`
**Chức năng**: Kiểm tra tính hợp lệ của date string
**Logic**:
- Check format DD/MM/YYYY
- Validate ngày, tháng, năm hợp lệ
- Năm phải >= 2020

##### `_contains_time_keywords(self, query: str) -> bool`
**Chức năng**: **CRITICAL FUNCTION** - Kiểm tra query có chứa từ khóa thời gian
**Logic**:
- Define comprehensive time keywords list:
  - Ngày tháng cụ thể: "ngày", "tháng", "năm"
  - Thời gian tương đối: "hôm nay", "tuần này"
  - Khoảng thời gian: "từ", "đến", "trước", "sau"
  - Regex patterns cho date formats
- Trả về True nếu tìm thấy bất kỳ time keyword nào

##### `async determine_search_type(self, state) -> Dict[str, Any]`
**Chức năng**: Xác định loại tìm kiếm và extract filters
**Logic**:

1. **Extract filters với AI**:
   - Gọi `_extract_filters_with_ai()`
   - Lưu vào state["extracted_filters"]
   - Tạo filter_summary cho logging

2. **Analyze metadata** (legacy):
   - Phân tích text để detect metadata
   - Tạo enriched_query với metadata context

3. **Determine search type** (8 loại):
   - **image_to_image**: Có image + từ khóa "tương tự"
   - **url_to_image**: Có image URL + từ khóa "tương tự"
   - **image_to_text**: Có image + từ khóa "mô tả"
   - **url_to_text**: Có image URL + từ khóa "mô tả"
   - **text_to_image**: Từ khóa "tìm hình"
   - **multimodal_search**: Có image + text query phức tạp
   - **multimodal_url_search**: Có image URL + text query
   - **text_to_text**: Mặc định

##### `async execute_smart_search(self, state) -> Dict[str, Any]`
**Chức năng**: Thực hiện tìm kiếm theo loại đã xác định
**Logic**:

1. **Lấy search parameters**:
   - search_type từ state
   - enriched_query (có metadata)
   - **filters từ AI extraction**

2. **Execute search theo type**:
   - **text_to_image**: `search_by_description_tool` với filters
   - **image_to_image**: `search_by_image_tool` với filters
   - **url_to_image**: Download image → convert base64 → search
   - **image_to_text**: Convert image to text → search by description
   - **multimodal_search**: `search_multimodal_tool` với text + image + filters
   - **text_to_text**: `search_by_description_tool` với filters

3. **Error handling**:
   - Try-catch cho các operations có thể fail
   - Trả về error messages rõ ràng

##### `async _image_to_text_description(self, image_base64: str) -> str`
**Chức năng**: Chuyển đổi image thành text description
**Logic**:
- Sử dụng vision model với prompt tiếng Việt
- Tạo HumanMessage với image_url format
- Trả về detailed description hoặc error message

##### Helper Functions:

##### `_analyze_text_metadata(self, text: str) -> Dict[str, List[str]]`
**Chức năng**: Legacy function - phân tích metadata từ text
**Logic**: Sử dụng predefined mappings để detect main_subject, product_type, recipient

##### `_is_image_url(self, text: str) -> bool`
**Chức năng**: Kiểm tra text có phải image URL
**Logic**: Check URL pattern + image extensions

##### `_is_base64_image(self, text: str) -> bool`
**Chức năng**: Kiểm tra text có phải base64 image
**Logic**: Check data:image prefix hoặc base64 pattern

---

### 4. FILE: `base_agent.py`

#### Mục đích:
Base class cho tất cả agents, cung cấp common functionality

#### Các hàm chính:

##### `__init__(self, temperature: float = 0.3)`
**Chức năng**: Khởi tạo base agent với LLM
**Logic**: Tạo ChatOpenAI instance với API key và temperature

##### `_safe_int_convert(self, value) -> int`
**Chức năng**: Chuyển đổi value thành integer một cách an toàn
**Logic**:
- Handle string với dấu phẩy
- Return 0 nếu conversion fails
- Dùng cho xử lý engagement numbers

##### `_calculate_engagement_score(self, product: Dict) -> int`
**Chức năng**: Tính engagement score cho product
**Logic**:
- likes + comments * 5 + shares * 10
- Weighted scoring để ưu tiên interactions có giá trị cao

---

### 5. FILE: `response_generator_agent.py`

#### Mục đích:
Agent cuối cùng trong workflow, tạo câu trả lời cuối cùng dựa trên kết quả từ các analysis agents

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: Khởi tạo với temperature=0.3 để cân bằng creativity và consistency
**Logic**: Inherit từ BaseAgent, sử dụng temperature moderate cho text generation

##### `async process(self, state) -> Dict[str, Any]`
**Chức năng**: **MAIN DISPATCHER** - Điều phối tạo response theo query_type
**Logic**:
- Lấy query_type từ state
- Route đến đúng response generator:
  - "smart_search" → `_generate_smart_search_response()`
  - "benchmark" → `_generate_benchmark_response()`
  - "market_gap" → `_generate_market_gap_response()`
  - "verify_idea" → `_generate_verify_idea_response()`
  - "audience_volume" → `_generate_audience_volume_response()`
- Cập nhật state["final_answer"] và log message

##### `_generate_smart_search_response(self, state) -> str`
**Chức năng**: Tạo response cho smart search queries
**Logic chi tiết**:

1. **Header và Metadata**:
   - Lấy search_type, results, query từ state
   - Tạo title với search type được format

2. **Error Handling**:
   - Check empty results hoặc error trong results
   - Return early với error message nếu có lỗi

3. **Overview Section**:
   - Số lượng sản phẩm tìm thấy
   - Confirm có image URLs

4. **Results Display** (top 100):
   - Loop qua results để hiển thị:
     - Store name
     - **Image URL** (key feature)
     - Description (truncated)
     - Engagement metrics
     - Similarity score
     - Platform và date

5. **Specialized Insights**:
   - Thêm image analysis insights cho image search types
   - Include search_description nếu có (từ image-to-text)

6. **Next Steps**:
   - Actionable recommendations
   - Emphasis on image URLs usage

##### `_generate_benchmark_response(self, state) -> str`
**Chức năng**: Tạo response cho benchmark analysis
**Logic chi tiết**:

1. **Performance Overview**:
   - Total products analyzed
   - Aggregate engagement metrics
   - Average engagement calculation

2. **Winners vs Losers Analysis**:
   - Count và comparison
   - Identify top performers vs underperformers

3. **Winning Products Display**:
   - Top 100 winning products với:
     - Engagement score calculation
     - **Image URLs** for visual analysis
     - Store info và platform

4. **Success Factors Analysis**:
   - Key success factors từ analysis
   - Metadata insights breakdown:
     - Popular themes
     - Target audiences
     - Platform distribution

5. **Actionable Recommendations**:
   - Market signal interpretation
   - Strategy recommendations based on win/loss ratio
   - Visual analysis recommendations

##### `_generate_market_gap_response(self, state) -> str`
**Chức năng**: Tạo response cho market gap analysis
**Logic chi tiết**:

1. **Current Market Landscape**:
   - Popular themes analysis
   - Main target audiences
   - Popular occasions

2. **Identified Gaps**:
   - Audience gaps (underserved segments)
   - Occasion gaps (missed opportunities)
   - Theme gaps (underdeveloped areas)

3. **Market Opportunities**:
   - List opportunities từ analysis
   - Underserved segments identification

4. **Competitor Weaknesses**:
   - Areas where competitors are weak
   - Exploitation opportunities

5. **Action Plan**:
   - 5-step strategic plan
   - Multi-platform recommendations
   - Visual differentiation strategy

##### `_generate_verify_idea_response(self, state) -> str`
**Chức năng**: Tạo response cho idea verification
**Logic chi tiết**:

1. **Verification Results**:
   - Similar products count
   - Market validation status
   - Success rate percentage

2. **Viability Assessment**:
   - 5-tier viability scale:
     - high_viability
     - moderate_viability
     - low_viability
     - high_risk
     - untested_concept
   - Color-coded messaging system

3. **Performance Breakdown**:
   - High/medium/low performers count
   - Success distribution analysis

4. **Similar Concepts Display**:
   - Top 10 similar concepts với:
     - Similarity scores
     - **Image URLs** for comparison
     - Engagement analysis
     - Platform performance

5. **Pattern Analysis**:
   - Best performing platform identification
   - Common success themes
   - Performance patterns

6. **Strategic Recommendations**:
   - Next steps based on viability
   - Visual analysis guidance
   - A/B testing suggestions

##### `_generate_audience_volume_response(self, state) -> str`
**Chức năng**: Tạo response cho audience volume estimation
**Logic chi tiết**:

1. **Volume Estimation**:
   - 3-tier estimate system:
     - Conservative estimate
     - Recommended estimate (primary)
     - Optimistic estimate
   - Sample size và total engagement

2. **Platform-wise Analysis**:
   - Sort platforms by engagement
   - Display cho mỗi platform:
     - Product count
     - Average engagement
     - Estimated audience per platform

3. **Trend Analysis**:
   - 4 trend directions:
     - increasing (growing)
     - decreasing (declining)
     - stable (consistent)
     - insufficient_data
   - Data span analysis

4. **Confidence Level**:
   - 5-tier confidence system
   - Color-coded reliability indicators

5. **Strategic Recommendations**:
   - Strategy based on volume size:
     - >10K: Mass market approach
     - >1K: Targeted marketing
     - <1K: Niche strategy
   - Pricing và positioning guidance

### Helper Functions trong Response Generator:

##### `_calculate_engagement_score(self, product) -> int`
**Chức năng**: Inherited từ BaseAgent, tính engagement score
**Logic**: likes + comments*5 + shares*10 (weighted scoring)

---

### 6. FILE: `rag_multi_agent_workflow.py` (CORE ORCHESTRATOR)

#### Mục đích:
**TRUNG TÂM ĐIỀU PHỐI** - Quản lý toàn bộ workflow và kết nối các agents

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: **SYSTEM INITIALIZATION** - Khởi tạo toàn bộ hệ thống
**Logic**:
1. **Database Connection**: Kết nối Milvus vector database
2. **Agent Initialization**: Khởi tạo tất cả 8 agents:
   - classifier_agent
   - search_agent
   - smart_search_agent
   - benchmark_agent
   - market_gap_agent
   - verify_idea_agent
   - audience_volume_agent
   - response_generator
3. **Workflow Build**: Gọi _build_workflow() để tạo StateGraph

##### `_build_workflow(self) -> StateGraph`
**Chức năng**: **CORE WORKFLOW ARCHITECT** - Xây dựng LangGraph workflow
**Logic chi tiết**:

1. **Create StateGraph**:
   - Initialize với AgentState schema

2. **Add Nodes** (8 nodes):
   - classify_query: Phân loại query
   - search_products: Traditional search
   - smart_search: Smart/multimodal search
   - 4 analysis nodes: benchmark, market_gap, verify_idea, audience_volume
   - generate_response: Final response generation

3. **Define Edges**:
   - **Linear Flow**: START → classify_query
   - **Conditional Routing 1**: classify_query → [smart_search | search_products]
   - **Direct Path**: smart_search → generate_response
   - **Conditional Routing 2**: search_products → [4 analysis types]
   - **Convergence**: All analysis → generate_response → END

4. **Compile Workflow**: Tạo executable workflow

##### `_route_after_classification(self, state) -> str`
**Chức năng**: **ROUTING LOGIC 1** - Điều hướng sau classification
**Logic**:
- Input: state với query_type
- Logic: Nếu query_type == "smart_search" → route to smart_search
- Else → route to traditional search ("other")
- Return: routing key

##### `_route_to_analysis(self, state) -> str`
**Chức năng**: **ROUTING LOGIC 2** - Điều hướng đến analysis agent
**Logic**:
- Input: state với query_type
- Return: exact query_type để route đến đúng analysis agent
- Direct mapping: query_type = node_name

##### **NODE WRAPPER FUNCTIONS** (8 functions):

##### `async _classify_query(self, state) -> AgentState`
**Chức năng**: Node wrapper cho query classification
**Logic**: Gọi classifier_agent.process(state)

##### `async _search_products(self, state) -> AgentState`
**Chức năng**: Node wrapper cho traditional product search
**Logic**: Gọi search_agent.process(state)

##### `async _smart_search(self, state) -> AgentState`
**Chức năng**: Node wrapper cho smart/multimodal search
**Logic**: Gọi smart_search_agent.process(state)

##### `async _benchmark_analysis(self, state) -> AgentState`
**Chức năng**: Node wrapper cho benchmark analysis
**Logic**: Gọi benchmark_agent.process(state)

##### `async _market_gap_analysis(self, state) -> AgentState`
**Chức năng**: Node wrapper cho market gap analysis
**Logic**: Gọi market_gap_agent.process(state)

##### `async _verify_idea_analysis(self, state) -> AgentState`
**Chức năng**: Node wrapper cho idea verification
**Logic**: Gọi verify_idea_agent.process(state)

##### `async _audience_volume_analysis(self, state) -> AgentState`
**Chức năng**: Node wrapper cho audience volume analysis
**Logic**: Gọi audience_volume_agent.process(state)

##### `async _generate_response(self, state) -> AgentState`
**Chức năng**: Node wrapper cho response generation
**Logic**: Gọi response_generator.process(state)

##### **PUBLIC INTERFACE FUNCTIONS**:

##### `async process_query(self, query: str, input_image: str = None) -> str`
**Chức năng**: **MAIN PUBLIC API** - Process user query
**Logic**:
1. **Create Initial State**: Gọi create_initial_state(query, input_image)
2. **Execute Workflow**: await self.workflow.ainvoke(initial_state)
3. **Extract Result**: Return final_state["final_answer"]
4. **Error Handling**: Try-catch với Vietnamese error message

##### `get_workflow_graph(self)`
**Chức năng**: Visualization support - trả về workflow graph
**Logic**: Return compiled workflow cho debugging/visualization

##### `async process_query_with_state(self, query: str, input_image: str = None) -> Dict[str, Any]`
**Chức năng**: **DEBUG API** - Process query và return full state
**Logic**:
- Similar to process_query nhưng return toàn bộ final_state
- Dùng cho debugging và inspection
- Include error trong response thay vì raise exception

---

### 7. FILE: `chatbot.py` (USER INTERFACE)

#### Mục đích:
**FRONT-END INTERFACE** - Cung cấp giao diện chat cho user tương tác với hệ thống

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: Initialize chatbot instance
**Logic**:
- Tạo RAGMultiAgentWorkflow instance
- Print welcome message với Vietnamese

##### `async chat(self, user_input: str, image_base64: Optional[str] = None) -> str`
**Chức năng**: **CORE CHAT FUNCTION** - Main chat interface
**Logic**:
1. **Input Validation**: Check empty input
2. **Logging**: Print processing status với emoji
3. **Image Detection**: Check và log nếu có image
4. **Workflow Execution**: await self.workflow.process_query()
5. **Return Response**: Return formatted response

##### `run_interactive(self)`
**Chức năng**: **INTERACTIVE SESSION** - Run continuous chat session
**Logic chi tiết**:

1. **Welcome Banner**:
   - System description
   - Feature list (5 main functions)
   - Smart search capabilities
   - Special commands

2. **Main Loop**:
   - **Input Handling**: input() với prompt
   - **Exit Commands**: 'quit', 'exit', 'bye'
   - **Empty Input**: Skip processing

3. **Image Handling**:
   - **Command Detection**: 'image:' prefix
   - **File Loading**: 
     - Extract path từ command
     - Read binary file
     - Convert to base64
     - Get additional query về image
   - **Error Handling**: Try-catch cho file operations

4. **Query Processing**:
   - **Execute**: asyncio.run(self.chat())
   - **Display**: Print formatted response
   - **Error Handling**: Catch và display exceptions

5. **Session Management**:
   - **Interrupt Handling**: KeyboardInterrupt (Ctrl+C)
   - **Graceful Exit**: Thank you message
   - **Error Recovery**: Continue session sau errors

### Special Features trong Chatbot:

##### **Image Input Support**:
- Command format: 'image:[path]'
- Automatic base64 conversion
- Secondary prompt for image-related query
- Error handling cho invalid paths

##### **Multi-language Support**:
- Vietnamese interface
- English/Vietnamese mixed commands
- Localized error messages

##### **Interactive Features**:
- Rich console output với emoji
- Progress indicators
- Clear command structure
- Help information

---

### 8. FILE: `milvus_manager.py` (DATABASE LAYER)

#### Mục đích:
**VECTOR DATABASE INTERFACE** - Quản lý tất cả operations với Milvus vector database

#### Các hàm chính:

##### `__init__(self)`
**Chức năng**: **SYSTEM INITIALIZATION** - Khởi tạo kết nối và embedding service
**Logic**:
- Kết nối Milvus database (localhost:19530)
- Khởi tạo embedding service
- Load collection information
- Setup image processing capabilities

##### `connect(self) -> bool`
**Chức năng**: Thiết lập kết nối đến Milvus server
**Logic**:
- Connect với default configuration
- Error handling cho connection failures
- Return True/False based on success

##### `search_by_text_description(self, description: str, top_k: int = 100, filters: Optional[Dict] = None) -> List[Dict]`
**Chức năng**: **TEXT SEARCH CORE** - Tìm kiếm sản phẩm bằng text description
**Logic**:
1. **Vector Generation**: Convert text description thành embedding vector
2. **Filter Construction**: Build Milvus filter expressions từ filters dict
3. **Search Execution**: Execute vector similarity search
4. **Results Processing**: Convert Milvus results thành standard format
5. **Error Handling**: Graceful error handling với fallback

##### `search_by_image_vector(self, image_vector: List[float], top_k: int = 100, filters: Optional[Dict] = None) -> List[Dict]`
**Chức năng**: **IMAGE VECTOR SEARCH** - Tìm kiếm bằng image vector
**Logic**:
1. **Vector Validation**: Check image vector format và dimensions
2. **Filter Application**: Apply date/platform/store filters
3. **Similarity Search**: Execute vector search trong image vector field
4. **Result Ranking**: Sort by similarity score
5. **Metadata Enrichment**: Add additional product metadata

##### `search_by_image_url(self, image_url: str, top_k: int = 100, filters: Optional[Dict] = None) -> List[Dict]`
**Chức năng**: **URL-BASED IMAGE SEARCH** - Tìm kiếm bằng image URL
**Logic**:
1. **URL Processing**: Download image từ URL
2. **Image Conversion**: Convert thành appropriate format
3. **Vector Generation**: Extract image features thành vector
4. **Search Delegation**: Call search_by_image_vector với generated vector
5. **Cleanup**: Clean up temporary files

##### `search_multimodal(self, text: str = "", image_url: str = "", top_k: int = 100, filters: Optional[Dict] = None) -> List[Dict]`
**Chức năng**: **MULTIMODAL SEARCH ENGINE** - Combined text + image search
**Logic**:
1. **Input Processing**: Process both text và image inputs
2. **Vector Generation**: Create combined multimodal vectors
3. **Weight Balancing**: Balance text vs image similarity weights
4. **Hybrid Search**: Execute both text và image searches
5. **Result Fusion**: Combine và rank results từ both modalities
6. **Deduplication**: Remove duplicate results

##### `get_image_vector(self, image: PIL.Image) -> List[float]`
**Chức năng**: **IMAGE FEATURE EXTRACTION** - Convert PIL Image thành vector
**Logic**:
- Use embedding service để extract image features
- Normalize vector dimensions
- Handle various image formats
- Error handling cho corrupted images

##### `get_query_vector(self, query: str) -> List[float]`
**Chức năng**: **TEXT EMBEDDING** - Convert text query thành embedding vector
**Logic**:
- Use text embedding model
- Normalize vector length
- Handle multilingual text (Vietnamese/English)
- Cache frequently used queries

##### **BATCH OPERATIONS**:

##### `batch_search_texts(self, descriptions: List[str], top_k: int = 100) -> List[List[Dict]]`
**Chức năng**: **BATCH TEXT SEARCH** - Process multiple text queries simultaneously
**Logic**:
1. **Batch Vectorization**: Convert all descriptions thành vectors cùng lúc
2. **Parallel Search**: Execute multiple searches concurrently
3. **Result Collection**: Collect results từ all searches
4. **Memory Management**: Efficient memory usage cho large batches

##### `batch_search_images(self, image_urls: List[str], top_k: int = 100, filters: Optional[Dict] = None) -> List[List[Dict]]`
**Chức năng**: **BATCH IMAGE SEARCH** - Process multiple image URLs
**Logic**:
1. **URL Validation**: Validate all image URLs
2. **Concurrent Download**: Download images in parallel
3. **Batch Vector Extraction**: Extract features từ all images
4. **Parallel Search**: Execute searches concurrently
5. **Resource Cleanup**: Clean up all temporary files

##### **UTILITY FUNCTIONS**:

##### `get_model_info(self) -> Dict[str, Any]`
**Chức năng**: Return information về embedding models being used
**Logic**:
- Model names và versions
- Vector dimensions
- Performance metrics
- Configuration details

##### `health_check(self) -> Dict[str, Any]`
**Chức năng**: **SYSTEM HEALTH CHECK** - Kiểm tra tình trạng database và connections
**Logic**:
1. **Connection Test**: Test Milvus connection status
2. **Collection Status**: Verify collection existence và accessibility
3. **Performance Metrics**: Check query response times
4. **Resource Usage**: Monitor memory và CPU usage
5. **Error Detection**: Identify potential issues

##### **FILTER CONSTRUCTION**:

##### `_build_filter_expression(self, filters: Dict[str, Any]) -> str`
**Chức năng**: **FILTER BUILDER** - Convert filter dict thành Milvus expression
**Logic**:
1. **Date Range Filters**: 
   - Handle DD/MM/YYYY format
   - Convert thành Milvus timestamp expressions
   - Support date_start và date_end
2. **Platform Filters**: Match exact platform names
3. **Store Name Filters**: Support partial matching với LIKE operator
4. **Logical Operators**: Combine multiple filters với AND/OR
5. **Expression Validation**: Validate syntax before execution

---

### 9. FILE: `search_tools.py` (ADVANCED SEARCH TOOLKIT)

#### Mục đích:
**COMPREHENSIVE SEARCH TOOLKIT** - Bộ công cụ tìm kiếm nâng cao với AI-powered processing

#### Các Class và Tool chính:

##### **CLASS: SearchQueryProcessor**
**Mục đích**: Advanced query processor với Vietnamese-English mapping và attribute extraction

##### `CATEGORY_MAPPINGS` (Static Dictionary)
**Chức năng**: **MULTILINGUAL MAPPING** - Vietnamese-English product category mapping
**Nội dung**:
- Product types: 'mũ' → ['cap', 'hat'], 'nón' → ['cap', 'hat']
- Objects: 'bảng' → ['plaque', 'desk plaque'], 'biển' → ['plaque']
- Occasions: 'sinh nhật' → ['birthday'], 'thể thao' → ['sports']
- Recipients: 'con gái' → ['daughter'], 'con trai' → ['son']
- Relationships: 'cha' → ['father', 'dad'], 'mẹ' → ['mother', 'mom']

##### `ATTRIBUTE_HIERARCHY` (Static Dictionary)
**Chức năng**: **STRUCTURED ATTRIBUTES** - Hierarchical attribute classification
**Structure**:
- **product_type**: ['cap', 'hat', 'desk plaque', 'plaque']
- **subject**: ['basketball team logo', 'mascot', 'logo'] 
- **recipient**: ['daughter', 'son', 'kids', 'children']
- **giver**: ['from mother', 'from father', 'from wife', 'from husband']
- **occasion**: ['birthday', 'christmas', 'father\'s day', 'mother\'s day']
- **theme**: ['basketball', 'sports']
- **colors**: ['orange', 'blue', 'pink', 'red', 'green', 'yellow']
- **style**: ['elegant', 'sports theme', 'sentimental', 'energetic']
- **text_content**: ['champs', 'okc', 'thunder', 'oklahoma city thunder']
- **brand_level**: ['tm resemblance']

##### `extract_key_attributes(cls, description: str) -> Dict[str, List[str]]`
**Chức năng**: **ATTRIBUTE EXTRACTION** - Extract structured attributes từ description
**Logic**:
1. **Text Preprocessing**: Convert description to lowercase
2. **Pattern Matching**: Loop through ATTRIBUTE_HIERARCHY
3. **Keyword Detection**: Find matching keywords trong description
4. **Classification**: Group keywords theo categories
5. **Return Structure**: Dictionary với category → list of found attributes

##### `expand_query_terms(cls, query: str) -> List[str]`
**Chức năng**: **QUERY EXPANSION** - Expand query với synonyms và related terms
**Logic**:
1. **Base Terms**: Start với original query
2. **Vietnamese-English Mapping**: Add English equivalents cho Vietnamese terms
3. **Attribute-based Expansion**: Add related terms từ same categories
4. **Deduplication**: Remove duplicate terms
5. **Limitation**: Limit to reasonable number of terms để avoid noise

##### `create_structured_query(cls, query: str) -> str`
**Chức năng**: **QUERY STRUCTURING** - Create priority-based structured query
**Logic**:
1. **Attribute Extraction**: Extract attributes từ original query
2. **Priority Organization**:
   - **High Priority**: Product type và main subject
   - **Medium Priority**: Recipient và occasion
   - **Lower Priority**: Style, colors, themes
3. **Query Construction**: Build structured query với priority sections
4. **Expansion Integration**: Add expanded terms cho better matching
5. **Format**: "Original | Product: X | Subject: Y | For: Z | Related: terms"

##### `score_results(cls, results: List[Dict], original_query: str) -> List[Dict]`
**Chức năng**: **INTELLIGENT RESULT SCORING** - Post-process và score results
**Logic**:
1. **Query Analysis**: Extract attributes từ original query
2. **Result Analysis**: Extract attributes từ each result
3. **Attribute Matching**: Calculate overlap giữa query và result attributes
4. **Match Score Calculation**: 
   - Count matched attributes per category
   - Calculate percentage match score
5. **Combined Scoring**: 
   - 30% attribute match score
   - 70% original similarity score
6. **Result Ranking**: Sort by combined score
7. **Metadata Addition**: Add match details để debugging

#### **SEARCH TOOLS** (LangChain Tools):

##### `@tool search_by_description_tool(description, top_k, use_enhanced_processing, filters)`
**Chức năng**: **ENHANCED TEXT SEARCH** - Advanced text search với processing options
**Logic**:
1. **Processing Decision**: Check use_enhanced_processing flag
2. **Enhanced Path**:
   - Create SearchQueryProcessor instance
   - Generate structured query với create_structured_query()
   - Execute search với enhanced query
   - Score results với intelligent scoring
   - Return top_k results
3. **Standard Path**: Direct milvus search without enhancement
4. **Error Handling**: Comprehensive error catching và logging

##### `@tool multi_strategy_search_tool(query, strategies, top_k, filters)`
**Chức năng**: **MULTI-STRATEGY SEARCH** - Execute multiple search strategies simultaneously
**Logic**:
1. **Strategy Definition**: Support 4 strategies:
   - **exact**: Direct query search
   - **expanded**: Search với expanded terms
   - **structured**: Search với structured query
   - **fuzzy**: Search với extracted attributes only
2. **Parallel Execution**: Execute all selected strategies
3. **Result Collection**: Collect results từ all strategies
4. **Deduplication**: Remove duplicate results across strategies
5. **Strategy Tagging**: Tag each result với source strategy
6. **Intelligent Ranking**: Apply scoring across all results
7. **Analytics**: Return strategy analysis và query breakdown

##### `@tool smart_product_search_tool(query, context, top_k, filters)`
**Chức năng**: **CONTEXT-AWARE SEARCH** - Search với user context và preferences
**Logic**:
1. **Query Enhancement**: Enhance query với context information:
   - **user_preferences**: Add preference terms to query
   - **previous_searches**: Consider search history
   - **filter_preferences**: Apply user's default filters
2. **Context Integration**: Build enhanced query từ all context sources
3. **Enhanced Search**: Use enhanced description search
4. **Post-filtering**: Apply must_have_attributes từ context
5. **Result Validation**: Ensure results match required attributes

##### `@tool search_by_image_tool(image_base64, top_k, filters)`
**Chức năng**: **IMAGE SIMILARITY SEARCH** - Find products similar to input image
**Logic**:
1. **Image Decoding**: Decode base64 thành binary image data
2. **Image Loading**: Load với PIL Image
3. **Vector Extraction**: Convert image thành feature vector
4. **Database Search**: Execute vector similarity search
5. **Filter Application**: Apply date/platform/store filters
6. **Error Handling**: Handle corrupted images và encoding errors

##### `@tool search_by_image_url_tool(image_url, top_k, filters)`
**Chức năng**: **URL IMAGE SEARCH** - Search using image từ URL
**Logic**:
1. **URL Validation**: Validate image URL format
2. **Image Download**: Download image từ URL
3. **Format Conversion**: Convert to appropriate format
4. **Search Delegation**: Call milvus_manager.search_by_image_url
5. **Resource Cleanup**: Clean up downloaded files

##### `@tool search_multimodal_tool(text, image_base64, top_k, filters)`
**Chức năng**: **MULTIMODAL SEARCH ENGINE** - Combined text + image search
**Logic**:
1. **Input Processing**: Handle both text và image inputs
2. **Image Handling**: Create temporary file từ base64
3. **Text Enhancement**: Apply query processing to text
4. **Multimodal Execution**: Call milvus_manager.search_multimodal
5. **Resource Management**: Clean up temporary files
6. **Error Recovery**: Handle partial failures gracefully

##### `@tool search_products_with_filters_tool(query, filters, top_k)`
**Chức năng**: **FILTERED PRODUCT SEARCH** - Search với comprehensive filtering
**Logic**:
1. **Query Enhancement**: Apply structured query processing
2. **Vector Generation**: Convert enhanced query thành vector
3. **Filtered Search**: Execute search với all provided filters
4. **Direct Database Call**: Call milvus_manager.search_products

#### **BATCH PROCESSING TOOLS**:

##### `@tool batch_search_descriptions_tool(descriptions, top_k)`
**Chức năng**: **BATCH TEXT SEARCH** - Process multiple descriptions simultaneously
**Logic**:
1. **Batch Enhancement**: Apply structured processing to all descriptions
2. **Batch Execution**: Call milvus_manager.batch_search_texts
3. **Parallel Processing**: Process multiple queries concurrently
4. **Result Organization**: Return results trong same order as input

##### `@tool batch_search_images_tool(image_urls, top_k, filters)`
**Chức năng**: **BATCH IMAGE SEARCH** - Process multiple images at once
**Logic**:
1. **URL Validation**: Validate all image URLs
2. **Batch Processing**: Process multiple images simultaneously
3. **Filter Application**: Apply consistent filters across all searches
4. **Error Isolation**: Handle individual failures without affecting batch

#### **ANALYSIS TOOLS**:

##### `@tool similarity_comparison_tool(text1, text2, image1_base64, image2_base64, filters)`
**Chức năng**: **PRODUCT SIMILARITY ANALYSIS** - Deep comparison between two products
**Logic**:
1. **Multimodal Processing**: Handle both text và image inputs
2. **Image File Management**: Create temporary files cho images
3. **Enhanced Text Processing**: Apply structured processing to both texts
4. **Multimodal Embedding**: Generate combined embeddings cho both products
5. **Similarity Calculation**:
   - **Text Similarity**: Cosine similarity between text vectors
   - **Image Similarity**: Cosine similarity between image vectors (if both images provided)
   - **Overall Similarity**: Weighted average (50% text, 50% image)
6. **Attribute Analysis**: Compare extracted attributes between products:
   - **Category-wise Comparison**: Analyze each attribute category
   - **Common Attributes**: List shared characteristics
   - **Unique Attributes**: List differences
   - **Similarity Scores**: Calculate Jaccard similarity cho each category
7. **Interpretation**: Provide human-readable similarity levels
8. **Resource Cleanup**: Clean up all temporary files

##### `@tool get_embedding_info_tool()`
**Chức năng**: **MODEL INFORMATION** - Get embedding model details
**Logic**: Return milvus_manager.get_model_info()

##### `@tool find_trend_clusters_tool(descriptions, similarity_threshold, filters)`
**Chức năng**: **TREND CLUSTERING** - Group similar products into clusters
**Logic**:
1. **Text Enhancement**: Apply structured processing to all descriptions
2. **Batch Embedding**: Generate embeddings cho all descriptions
3. **Clustering Algorithm**:
   - **Similarity Matrix**: Calculate pairwise similarities
   - **Threshold Clustering**: Group items above similarity threshold
   - **Cluster Formation**: Create non-overlapping clusters
4. **Cluster Analysis**:
   - **Attribute Extraction**: Extract attributes cho each cluster
   - **Dominant Theme**: Identify main theme cho each cluster
   - **Common Attributes**: Find shared characteristics
5. **Trend Analysis**: 
   - **Cluster Sizes**: Analyze cluster distribution
   - **Theme Distribution**: Identify popular themes
   - **Market Insights**: Provide trend insights
6. **Result Structure**: Return comprehensive cluster information

---

### 10. FILE: `data_processor.py` (DATA MANAGEMENT LAYER)

#### Mục đích:
**HIGH-PERFORMANCE DATA PROCESSING** - Streamlit-optimized data loading với advanced caching

#### Các hàm chính:

##### **CONNECTION MANAGEMENT**:

##### `@st.cache_resource get_milvus_connection()`
**Chức năng**: **CACHED CONNECTION** - Singleton Milvus connection với caching
**Logic**:
- **Resource Caching**: Use Streamlit's cache_resource cho singleton pattern
- **Connection Setup**: Connect to localhost:19530
- **Error Handling**: Graceful error handling với user feedback
- **Return Status**: Boolean success indicator

##### `connect_to_milvus()`
**Chức năng**: **CONNECTION WRAPPER** - Wrapper function cho cached connection
**Logic**: Simple wrapper để get_milvus_connection() cho consistency

#### **DATA LOADING WITH ADVANCED CACHING**:

##### `@st.cache_data(ttl=7200) load_collection_data()`
**Chức năng**: **ID-BASED PAGINATION LOADER** - Load collection data với intelligent pagination
**Logic chi tiết**:

1. **Collection Validation**:
   - Check collection existence với utility.has_collection()
   - Load collection và get total entity count

2. **ID-Based Pagination Setup**:
   - **Batch Size**: 16384 records per batch (optimized size)
   - **Pagination Method**: ID-based thay vì offset-based để avoid offset limitations
   - **Starting Point**: Begin với empty last_id

3. **Progressive Loading Loop**:
   ```python
   while True:
       if last_id:
           expr = f'id_sanpham > "{last_id}"'  # Query records after last_id
       else:
           expr = ""  # First batch - get all
       
       batch_results = collection.query(expr=expr, limit=batch_size)
       if not batch_results: break  # No more data
       
       # Sort batch by ID to ensure order
       batch_results.sort(key=lambda x: x.get('id_sanpham', ''))
       all_results.extend(batch_results)
       last_id = batch_results[-1].get('id_sanpham', '')  # Update for next batch
   ```

4. **Progress Tracking**:
   - **Visual Progress Bar**: Real-time progress indication
   - **Status Updates**: Batch-by-batch status messages
   - **Memory Monitoring**: Track loaded record count
   - **Performance Metrics**: Batch timing và throughput

5. **Error Handling**:
   - **Batch-level Recovery**: Continue on individual batch failures
   - **Timeout Handling**: Handle connection timeouts gracefully
   - **Memory Management**: Efficient memory usage cho large datasets

6. **Output Fields**: Load comprehensive fields:
   - id_sanpham, platform, description, metadata
   - date, like, comment, share, name_store

##### `@st.cache_data(ttl=7200) load_collection_data_with_pagination()`
**Chức năng**: **ALTERNATIVE PAGINATION LOADER** - Backup loading method
**Logic**:
- Similar to main loader but với different error handling strategy
- More aggressive continuation on errors
- Simplified progress tracking
- Used as fallback when main loader has issues

#### **COLLECTION INFORMATION**:

##### `@st.cache_data(ttl=1800) check_collection_exists(collection_name)`
**Chức năng**: **CACHED EXISTENCE CHECK** - Check collection existence với caching
**Logic**: Simple cached wrapper around utility.has_collection()

##### `@st.cache_data(ttl=900) get_collection_info()`
**Chức năng**: **COMPREHENSIVE COLLECTION STATS** - Get detailed collection information
**Logic**:
1. **Basic Statistics**:
   - Total entity count
   - Collection name và status
2. **Pagination Estimates**:
   - Batch size configuration
   - Estimated number of batches
   - Expected loading time
3. **Performance Testing**:
   - Sample query execution time
   - Performance benchmarks
4. **Method Information**:
   - Pagination method details (ID-based unlimited)
   - Configuration parameters

#### **METADATA PROCESSING WITH CACHING**:

##### `@st.cache_data(ttl=3600) parse_metadata_cached(data_hash, data)`
**Chức năng**: **HASH-BASED METADATA CACHING** - Cache processed metadata by content hash
**Logic**:
- **Content Hashing**: Generate MD5 hash của data content
- **Cache Key**: Use data hash as cache key
- **Processing Delegation**: Call parse_metadata_internal()
- **Cache Benefits**: Avoid reprocessing same data multiple times

##### `parse_metadata(data)`
**Chức năng**: **METADATA PARSER ENTRY POINT** - Main metadata parsing function
**Logic**:
1. **Input Validation**: Check data availability
2. **Content Hashing**: Generate hash của data cho caching
3. **Cache Lookup**: Check if processed version exists
4. **Processing**: Call cached parser function

##### `parse_metadata_internal(data)`
**Chức năng**: **CORE METADATA PROCESSOR** - Internal parsing logic với batch processing
**Logic**:
1. **Batch Processing Setup**:
   - **Batch Size**: 1000 items per batch để optimize memory
   - **Memory Management**: Process data in chunks
2. **Item Processing Loop**:
   ```python
   for item in batch_data:
       try:
           metadata = json.loads(item.get('metadata', '{}'))
           row = {
               'id_sanpham': item.get('id_sanpham', ''),
               'platform': item.get('platform', ''),
               # ... other fields
           }
           # Add metadata fields
           for key, value in metadata.items():
               row[key] = format_metadata_value(value)
           parsed_data.append(row)
       except: continue
   ```
3. **Data Transformation**:
   - **JSON Parsing**: Parse metadata JSON strings
   - **Type Conversion**: Convert engagement numbers to integers
   - **List Formatting**: Format list values thành comma-separated strings
   - **Error Handling**: Skip problematic records với warnings

#### **UTILITY FUNCTIONS WITH CACHING**:

##### `@st.cache_data safe_int_convert(value)`
**Chức năng**: **SAFE INTEGER CONVERSION** - Convert values to integers với error handling
**Logic**:
- **Type Handling**: Handle int, float, string inputs
- **String Cleaning**: Remove commas và spaces
- **Validation**: Check if string is numeric
- **Default Value**: Return 0 on conversion errors

##### `@st.cache_data parse_engagement_string(engagement_str)`
**Chức năng**: **ENGAGEMENT DATA PARSER** - Parse complex engagement data formats
**Logic**:
1. **Format Detection**: Identify engagement string format:
   - **JSON Format**: {"like": 100, "comment": 20, "share": 5}
   - **Dictionary Format**: like: 100, comment: 20, share: 5  
   - **Simple Number**: Single total engagement number
2. **JSON Parsing**: Handle JSON-like strings với json.loads()
3. **Regex Extraction**: Use regex to extract numbers after keywords
4. **Fallback Distribution**: Distribute total engagement:
   - 70% likes, 20% comments, 10% shares
5. **Error Recovery**: Return zero values on parsing errors

#### **BATCH PROCESSING WITH CACHING**:

##### `@st.cache_data process_batch_data(data_batch_hash, data_batch)`
**Chức năng**: **CACHED BATCH PROCESSING** - Process data batches với caching
**Logic**:
1. **Hash-based Caching**: Use batch content hash cho cache key
2. **Item Processing**: Process each item trong batch:
   - Extract key fields
   - Calculate engagement scores
   - Add processing timestamps
3. **Error Isolation**: Handle individual item errors without affecting batch

##### `calculate_engagement_score(item)`
**Chức năng**: **ENGAGEMENT SCORE CALCULATION** - Calculate weighted engagement score
**Logic**:
- **Weighted Formula**: likes + comments*5 + shares*10
- **Reasoning**: Comments và shares have higher engagement value
- **Safe Conversion**: Use safe_int_convert cho all inputs

#### **CACHE MANAGEMENT**:

##### `clear_data_cache()`
**Chức năng**: **CACHE CLEARING** - Clear all data-related caches
**Logic**: Call st.cache_data.clear() và provide user feedback

##### `get_cache_stats()`
**Chức năng**: **CACHE STATISTICS** - Get cache performance information
**Logic**: Return available cache statistics (limited by Streamlit version)

##### `@st.cache_data(ttl=300) health_check()`
**Chức năng**: **SYSTEM HEALTH MONITORING** - Check system health với caching
**Logic**:
1. **Connection Test**: Test Milvus connection
2. **Collection Test**: Verify collection accessibility
3. **Information Gathering**: Get collection info if available
4. **Status Assessment**: Determine overall system health
5. **Timestamp**: Add health check timestamp
6. **Error Handling**: Provide detailed error information

---

## 🔄 LUỒNG XỬ LÝ CHÍNH

### 1. Query Processing Flow:
```
User Query → Query Classifier → [Smart Search | Traditional Analysis]
```

### 2. Smart Search Flow:
```
Query + Image → Determine Search Type → Extract Filters → Execute Search → Results
```

### 3. Filter Extraction Flow:
```
User Query → AI Analysis → JSON Extraction → Validation → Clean Filters
```

### 4. Database Integration Flow:
```
Search Tools → Milvus Manager → Vector Database → Processed Results
```

### 5. Data Loading Flow:
```
Collection → ID-based Pagination → Batch Processing → Cached Results → DataFrame
```

---

## 🎯 ĐIỂM MẠNH CỦA HỆ THỐNG

### 1. Flexible Filter Recognition:
- Không cần predefined mappings
- AI tự động nhận diện filters từ natural language
- Support cả tiếng Việt và tiếng Anh

### 2. Multi-modal Search:
- Text-to-text, text-to-image, image-to-image
- URL image support
- Multimodal search combining text + image

### 3. Intelligent Routing:
- Automatic query classification
- Context-aware processing
- Efficient resource utilization

### 4. Robust Error Handling:
- Graceful degradation
- Clear error messages
- Fallback mechanisms

### 5. Advanced Search Processing:
- AI-powered query enhancement
- Multi-strategy search execution
- Intelligent result scoring và ranking

### 6. High-Performance Data Management:
- ID-based pagination (unlimited scaling)
- Comprehensive caching strategies
- Batch processing optimization
- Real-time progress tracking

### 7. Scalable Vector Database Integration:
- Efficient vector similarity search
- Multi-modal embeddings
- Advanced filtering capabilities
- Batch operations support

---

## ⚠️ ĐIỂM CẦN LƯU Ý

### 1. Time Keywords Detection:
- Function `_contains_time_keywords()` rất quan trọng
- Prevent false positive date extraction
- Cần maintain comprehensive keyword list

### 2. Filter Validation:
- Date format phải DD/MM/YYYY
- Validation logic trong `_is_valid_date_string()`
- AI response parsing cần robust error handling

### 3. Search Type Logic:
- 8 loại search type khác nhau
- Priority order trong `determine_search_type()`
- Image URL vs base64 handling

### 4. API Dependencies:
- OpenAI API key management
- Vision model limits
- Milvus database connection

### 5. Memory Management:
- Large dataset loading considerations  
- Batch processing memory usage
- Cache size limitations
- Progress tracking overhead

### 6. Database Performance:
- ID-based pagination benefits và limitations
- Vector search performance tuning
- Filter expression optimization
- Concurrent access handling

---

## 🚀 HƯỚNG DẪN DEPLOYMENT

### Environment Setup:
```bash
pip install langchain langgraph openai
pip install pymilvus streamlit pandas pillow
# Cần setup Milvus database
# Configure OpenAI API key
```

### Key Configuration:
- API keys trong Config.settings
- Milvus database connection string (localhost:19530)
- Model names và parameters
- Streamlit caching configuration

### Database Setup:
- Milvus server installation và configuration
- Collection schema setup
- Index optimization cho vector fields
- Data migration và initial loading

---

## 📞 THÔNG TIN HỖ TRỢ

### Architecture Decisions:
- LangGraph để orchestrate workflow
- AI-based filter extraction thay vì rule-based
- Multi-modal support cho flexibility
- ID-based pagination cho unlimited scaling
- Comprehensive caching strategies
- Advanced search processing pipeline

### Performance Considerations:
- Temperature settings cho different tasks
- Caching strategies cho optimal performance
- Database query optimization
- Memory management cho large datasets
- Batch processing efficiency
- Vector search performance tuning

### Maintenance Notes:
- Regular cache clearing might be needed
- Monitor Milvus database performance
- Update search query processors theo user feedback
- API rate limit monitoring
- Error log analysis cho system health

---

**Lưu ý**: Đây là hệ thống AI phức tạp với nhiều integration points và advanced features. Cần hiểu rõ logic của từng component để maintain và extend hiệu quả. Đặc biệt chú ý đến caching strategies và database performance optimization.

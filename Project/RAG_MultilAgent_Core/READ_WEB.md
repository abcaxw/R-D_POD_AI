# Product Analytics Dashboard

## 1. Tổng quan dự án

**Tên dự án:** Milvus Product Analytics Dashboard với RnD Assistant  
**Mục đích:** Xây dựng hệ thống phân tích sản phẩm và chatbot hỗ trợ nghiên cứu phát triển sản phẩm từ dữ liệu Milvus Vector Database  
**Ngôn ngữ:** Python, Streamlit  
**Database:** Milvus Vector Database  

## 2. Cấu trúc dự án

```
├── Web.py                    # File chính khởi chạy ứng dụng
├── data/
│   └── data_processor.py     # Xử lý dữ liệu từ Milvus
├── ui/
│   ├── chatbot_interface.py  # Giao diện chatbot
│   ├── filter_interface.py   # Giao diện lọc dữ liệu  
│   ├── metadata_analysis.py  # Phân tích metadata
│   └── feedback.py           # Hệ thống feedback
└── chatbot.py               # Logic chatbot (import từ bên ngoài)
```

## 3. Chi tiết từng file và chức năng

### 3.1 Web.py (File chính)

**Mục đích:** File khởi chạy chính của ứng dụng Streamlit

#### Các hàm quan trọng:

**`get_connection_status()`**
- **Chức năng:** Kiểm tra kết nối đến Milvus Database
- **Cache:** 30 phút để tránh kiểm tra liên tục
- **Logic:** Gọi `connect_to_milvus()` và trả về trạng thái boolean
- **Lý do cache:** Tiết kiệm tài nguyên, tránh spam connection

**`load_collection_data_cached()`**  
- **Chức năng:** Tải dữ liệu từ Milvus với ID-based pagination (không giới hạn offset)
- **Cache:** 2 tiếng, tối đa 3 entries
- **Logic:** 
  - Sử dụng `load_collection_data_with_pagination()` thay vì offset-based
  - Convert dữ liệu thành format có thể serialize
  - Hiển thị progress và thông tin collection
- **Đặc biệt:** Phương pháp unlimited loading, vượt qua giới hạn offset 16384 của Milvus

**`load_collection_data_fallback()`**
- **Chức năng:** Phương pháp dự phòng với logic cũ (có giới hạn offset)
- **Cache:** 2 tiếng, tối đa 3 entries  
- **Logic:** Query toàn bộ dữ liệu với limit 16384 (phương pháp cũ)
- **Khi dùng:** Khi phương pháp ID-based pagination thất bại

**`initialize_cached_chatbot()`**
- **Chức năng:** Khởi tạo chatbot với resource caching
- **Cache:** Resource cache - chỉ tạo 1 lần
- **Logic:** Import và tạo instance RnDChatbot, xử lý exception nếu import fail

**`initialize_session_state()`**
- **Chức năng:** Khởi tạo các biến session state một cách tối ưu
- **Logic:**
  - Quản lý trạng thái app (initialized, connection_status)
  - Quản lý chatbot state (initialized, chat_history, loading)
  - Quản lý filter settings với persistence
  - Quản lý data loading state
  - Tracking performance và maintenance counter

**`main()`**
- **Chức năng:** Hàm chính điều khiển luồng ứng dụng
- **Logic:**
  1. Cấu hình trang Streamlit
  2. Kiểm tra kết nối Milvus
  3. Load dữ liệu với caching (unlimited loading)
  4. Tạo sidebar filter
  5. Hiển thị tabs (Chatbot vs Metadata Analysis)
  6. Tự động cleanup dữ liệu cũ

**`cleanup_old_data()`**
- **Chức năng:** Cleanup dữ liệu cũ để tránh memory leak
- **Logic:**
  - Giới hạn chat history tối đa 50 messages
  - Reset connection check sau 2 tiếng không hoạt động

### 3.2 data/data_processor.py

**Mục đích:** Xử lý tất cả logic liên quan đến dữ liệu Milvus

#### Các hàm quan trọng:

**`get_milvus_connection()`**
- **Chức năng:** Tạo kết nối đến Milvus với caching
- **Cache:** Resource cache
- **Logic:** Connect với host="localhost", port="19530"
- **Error handling:** Trả về False nếu lỗi kết nối

**`load_collection_data_with_pagination()`**
- **Chức năng:** Load dữ liệu với ID-based pagination thông minh (CORE FUNCTION)
- **Cache:** 2 tiếng, tối đa 3 entries
- **Logic chi tiết:**
  ```python
  1. Khởi tạo: last_id = "", batch_size = 16384
  2. Loop vô hạn:
     - Nếu last_id rỗng: query expr = ""
     - Nếu có last_id: query expr = f'id_sanpham > "{last_id}"'
     - Query với limit = batch_size
     - Sắp xếp results theo id_sanpham
     - Cập nhật last_id = result cuối cùng.id_sanpham
     - Nếu không có results: break
  3. Kết thúc khi không còn dữ liệu
  ```
- **Tại sao quan trọng:** Vượt qua giới hạn offset 16384 của Milvus, có thể load unlimited records

**`parse_metadata_cached()`**
- **Chức năng:** Parse metadata JSON với caching based on data hash
- **Cache:** 1 tiếng, tối đa 5 entries
- **Logic:** Tạo MD5 hash của data để làm cache key, tránh parse lại cùng dữ liệu

**`parse_metadata_internal()`**
- **Chức năng:** Logic parse metadata thực tế với batch processing
- **Logic:**
  - Xử lý từng batch 1000 items để tối ưu memory
  - Parse JSON metadata từ string
  - Convert list values thành comma-separated strings
  - Safe convert các field số (like, comment, share)
  - Trả về pandas DataFrame

**`get_collection_info()`**
- **Chức năng:** Lấy thông tin collection với ID-based estimation
- **Cache:** 15 phút
- **Logic:** 
  - Tính toán estimated_batches = ceil(total_entities / batch_size)
  - Estimate load time dựa trên sample query time
  - Trả về metadata về pagination method

### 3.3 ui/chatbot_interface.py

**Mục đích:** Giao diện chính của chatbot với các chức năng download và feedback

#### Các hàm quan trọng:

**`initialize_chatbot_state()`**
- **Chức năng:** Khởi tạo state management cho chatbot interface
- **Logic:** Setup cache cho products, download queue, prevent_rerun flags

**`create_download_package_cached()`**
- **Chức năng:** Tạo ZIP package cho download với caching
- **Logic chi tiết:**
  ```python
  1. Tạo cache_key từ search_id, rank, hash(product_data)
  2. Kiểm tra cache trong session_state (TTL = 1 tiếng)
  3. Nếu không có cache:
     - Tạo ZIP file in-memory
     - Add Excel metadata file
     - Download và add image từ URL
     - Cache kết quả
  4. Return zip_data, filename
  ```

**`create_all_products_zip_package()`**
- **Chức năng:** Tạo master ZIP package chứa tất cả products
- **Cache:** Streamlit cache_data
- **Logic:**
  - Tạo master Excel file với tất cả products data
  - Download tất cả images vào folder "Images/"
  - Tạo summary sheet với statistics
  - Limit 12 products để tránh timeout

**`create_master_excel_file()`**
- **Chức năng:** Tạo Excel file tổng hợp với formatting
- **Logic:**
  - Sheet 1: Products_Data với full data và formatting
  - Sheet 2: Summary với statistics và top performers
  - Auto-adjust column widths
  - Format URLs, numbers with proper styles

**`handle_chat_input()`**
- **Chức năng:** Xử lý input từ user (text + image upload)
- **Logic:**
  - Layout: text input + upload button + send button
  - Image chỉ upload khi click send (không upload ngay)
  - Preview image trước khi gửi
  - Gọi `process_chat_message()` khi send

**`upload_to_get_url_cached()`**
- **Chức năng:** Upload image với caching để tránh upload lại
- **Cache:** 30 phút
- **Logic:**
  - Tạo hash từ file content làm cache key
  - Kiểm tra session_state cache trước khi upload
  - Optimize image trước upload (resize, convert format)
  - Cache result với TTL

**`process_chat_message()`**
- **Chức năng:** Xử lý tin nhắn chat và response
- **Logic:**
  - Gọi chatbot.chat() với async
  - Thêm vào chat_history
  - Parse products từ response nếu có
  - Cache products data với search_id
  - Trigger rerun để update UI

**`parse_products_from_response()`**
- **Chức năng:** Parse products từ chatbot response text
- **Cache:** Streamlit cache_data
- **Logic phức tạp:**
  ```python
  1. Split response thành lines
  2. Tìm section "Top Results"
  3. Parse từng product:
     - Detect product header: "**X. Store Name**"
     - Parse Image URL, Description, Engagement, Platform, Date, Similarity
     - Handle multi-line descriptions
     - Extract summary từ structured description
  4. Return list of product dictionaries
  ```

**`render_no_reload_download_section()`**
- **Chức năng:** Render download buttons mà không reload trang
- **Logic:** Pre-generate ZIP và cache, sử dụng st.download_button

**`render_download_all_button()`**
- **Chức năng:** Render button download tất cả products
- **Logic:** 
  - Sử dụng session_state để manage download state
  - Generate ZIP khi click, show download button khi ready
  - Reset functionality để tạo package mới

#### Feedback System Functions:

**`render_image_feedback_inline()`**
- **Chức năng:** Render feedback buttons cho images
- **Logic:** Thumbs up/down buttons, lưu feedback vào FeedbackSystem

**`record_product_feedback()` & `record_analysis_feedback()`**
- **Chức năng:** Lưu feedback vào session_state
- **Logic:** Timestamp + product/analysis data

**`export_feedback_summary()`**
- **Chức năng:** Export comprehensive feedback report
- **Logic:** Aggregate tất cả feedback types thành text report

### 3.4 ui/metadata_analysis.py

**Mục đích:** Phân tích và trực quan hóa metadata từ sản phẩm, cung cấp giao diện tương tác để khám phá dữ liệu

#### Core Analysis Functions:

**`analyze_metadata_field(field_name)`**
- **Chức năng:** Phân tích một field metadata cụ thể
- **Cache:** 30 phút (1800s)
- **Logic chi tiết:**
  ```python
  1. Kiểm tra field có tồn tại trong DataFrame
  2. Xử lý values dạng list (comma-separated)
  3. Split và clean các giá trị: strip whitespace, quotes
  4. Sử dụng Counter để đếm frequency
  5. Tạo DataFrame top 10 most common values
  6. Return: result_df (top 10), all_values (unique list)
  ```
- **Input:** DataFrame, field_name string
- **Output:** Tuple (DataFrame với Count, List unique values)

**`get_filtered_and_sorted_products(df, field_name, field_value, limit=None)`**
- **Chức năng:** Lọc và sắp xếp sản phẩm theo engagement score
- **Cache:** 10 phút (600s)
- **Logic chi tiết:**
  ```python
  1. Filter products có chứa field_value (case-insensitive)
  2. Calculate engagement_score = like + comment + share
  3. Sort theo engagement_score descending
  4. Apply limit nếu có (None = unlimited)
  5. Prepare statistics dictionary
  6. Return: (filtered_df, stats_dict)
  ```
- **Features đặc biệt:**
  - Unlimited display option (limit=None)
  - Smart engagement scoring
  - Comprehensive statistics tracking

**`get_metadata_fields()`**
- **Chức năng:** Lấy danh sách các metadata fields cần phân tích
- **Cache:** 30 phút (1800s)
- **Return:** List 14 fields chuẩn:
  ```python
  ["image_recipient", "target_audience", "usage_purpose", "occasion",
   "niche_theme", "sentiment_tone", "message_type", "personalization_type",
   "product_type", "placement_display_context", "design_style",
   "color_aesthetic", "main_subject", "text"]
  ```

#### Visualization Functions:

**`analyze_single_field_compact(df, field_name)`**
- **Chức năng:** Tạo compact analysis widget cho một field
- **Logic:**
  1. Hiển thị metrics (Total features, Unique values, Top count)
  2. Tạo clickable horizontal bar chart với Plotly
  3. Handle click events để auto-switch sang View Products tab
  4. Expandable detailed data table
  5. Auto-fill form khi click chart bar
- **Interactive Features:**
  - Click-to-navigate functionality
  - Color-coded bar charts (viridis colorscale)
  - Expandable details section

**`show_sample_products(df, field_name, field_value)`**
- **Chức năng:** Hiển thị gallery sản phẩm với tùy chọn hiển thị linh hoạt
- **Layout:** 5-column grid layout với responsive design
- **Logic phức tạp:**
  ```python
  1. Session state management:
     - products_limit (50/200/unlimited)
     - selected_product (cho modal)
     - expanded_products tracking
  
  2. Display controls:
     - 50 products button
     - 200 products button  
     - "HIỂN THỊ TẤT CẢ" button (unlimited)
     - Load more functionality
     - Reset to 50 button
  
  3. Grid rendering:
     - 5 columns per row
     - Image display với fallback
     - Compact info trong expander
     - Click handlers cho modal popup
  
  4. Progress tracking:
     - Show current/total counts
     - "Has more" indicators
     - Smart loading messages
  ```

#### Modal System:

**`show_large_product_modal(product)`**
- **Chức năng:** Hiển thị modal chi tiết sản phẩm full-screen
- **Features:** 
  - Streamlit @st.dialog decorator
  - Responsive CSS với viewport sizing
  - 2-column layout (image + info)
  - Comprehensive product information
  - Scrollable content sections

**Advanced Modal CSS:**
```css
- Viewport-based sizing (90vw x 85vh)
- Custom modal positioning và backdrop
- Grid layout cho content (1fr 1.8fr ratio)
- Gradient backgrounds và modern styling
- Mobile-responsive breakpoints
- Smooth animations và hover effects
```

**Modal Content Sections:**
1. **Header:** Product ID với gradient styling
2. **Image Section:** Auto-scaling với hover effects
3. **Info Section:** Scrollable với multiple cards
4. **Basic Info Card:** Store, Platform, Date, ID
5. **Engagement Metrics:** 4-column grid với st.metric
6. **Description:** Scrollable text area với custom styling

#### Navigation System:

**`create_metadata_tab_interface(df)`**
- **Chức năng:** Tạo tab navigation system với state management
- **Session State Variables:**
  ```python
  - current_view: "overview" | "view_products"
  - view_radio_index: 0 | 1 (cho radio button sync)
  - selected_metadata_field: field name
  - selected_metadata_value: field value
  - auto_fill_triggered: boolean flag
  - chart_clicked: boolean flag
  ```

**Navigation Logic:**
```python
1. Initialize all session states với default values
2. Create radio buttons với custom CSS styling
3. Handle automatic switching từ chart clicks
4. Sync radio button index với current_view
5. Manual tab switching logic
6. Content routing based on current_view
```

**`show_overview_content(df)` & `show_view_products_content(df)`**
- **Overview:** Grid layout tất cả metadata fields với clickable charts
- **View Products:** Manual selection interface + product gallery
- **Auto-fill Logic:** Chart click → switch tab → populate selectors → display products

#### Interactive Features:

**Chart Click Handling:**
```python
1. Plotly chart với on_select="rerun" parameter
2. Event processing từ st.plotly_chart
3. Extract clicked point data (point_index hoặc y value)  
4. Auto-populate session state variables
5. Switch to View Products tab
6. Auto-fill field và value selectors
7. Display success message với selected criteria
```

**Smart State Management:**
- Persistent filter selections across tabs
- Chart click flags để distinguish auto vs manual selection
- Product limit tracking với expand/collapse functionality
- Modal state management với cleanup

#### Performance Optimizations:

**Multi-level Caching:**
- Field analysis: 30 phút cache
- Product filtering: 10 phút cache  
- Metadata fields: 30 phút cache
- UI state persistence across reloads

**Memory Management:**
- Lazy loading của product images
- Batch processing cho large datasets
- Session state cleanup mechanisms
- Efficient DataFrame operations

### 3.5 ui/filter_interface.py

**Mục đích:** Tạo sidebar filtering interface với session state persistence và real-time statistics

#### Main Filter Functions:

**`create_sidebar_filter(df)`**
- **Chức năng:** Tạo comprehensive sidebar filter interface
- **Session State Management:**
  ```python
  - sidebar_store: Selected store (persistent)
  - sidebar_platform: Selected platform (persistent) 
  - sidebar_start_date: Date range start (persistent)
  - sidebar_end_date: Date range end (persistent)
  - filter_changed: Flag để track changes
  ```

**Filter Components Logic:**

**1. Store Filter:**
```python
- Extract unique stores từ name_store column
- Sort alphabetically với "Tất cả" option đầu tiên
- Selectbox với index persistence từ session state
- Auto-update session state khi thay đổi
```

**2. Platform Filter:**
```python  
- Extract unique platforms từ platform column
- Sort alphabetically với "Tất cả" option đầu tiên
- Selectbox với index persistence từ session state
- Auto-update session state khi thay đổi
```

**3. Date Range Filter:**
```python
Logic phức tạp:
1. Parse date column với error handling
2. Calculate min_date và max_date từ data
3. Two separate st.date_input widgets:
   - start_date: "Từ ngày" với validation
   - end_date: "Đến ngày" với validation
4. Date range validation:
   - start_date không được sau end_date
   - Error message nếu invalid range
   - Auto-reset về previous valid values
5. Session state persistence cho cả 2 dates
```

**4. Reset Functionality:**
```python
Reset button logic:
1. Reset tất cả filters về default values
2. Store = "Tất cả", Platform = "Tất cả"  
3. Date range = full data range (min to max)
4. Set filter_changed flag = True
5. Trigger st.rerun() để refresh UI
```

**Change Detection System:**
```python
Comprehensive change tracking:
1. Compare current selections với session state
2. Set filter_changed flag khi có thay đổi
3. Update session state values immediately  
4. Trigger dependent components refresh
5. Used by caching system để invalidate stale data
```

**`apply_filters_cached(df, selected_store, selected_platform, date_range)`**
- **Chức năng:** Apply tất cả filters lên DataFrame với caching optimization
- **Cache:** 5 phút (300s) để optimize performance
- **Logic chi tiết:**
  ```python
  1. Copy DataFrame để avoid mutation
  2. Store filter:
     - Skip nếu "Tất cả"
     - Filter exact match với name_store column
  3. Platform filter:  
     - Skip nếu "Tất cả"
     - Filter exact match với platform column
  4. Date filter:
     - Parse date column với pd.to_datetime
     - Create Timestamp objects cho start/end
     - Filter với date range using >= và <=
     - Handle timezone issues với tz_localize(None)
  5. Return filtered DataFrame
  ```

**Error Handling trong Date Processing:**
```python
Try-catch wrapping:
1. pd.to_datetime với errors='coerce'
2. Handle malformed dates gracefully  
3. Fallback to None values nếu parsing fails
4. User-friendly error messages
5. Preserve previous valid selections
```

**`create_sidebar_stats(filtered_df)`**
- **Chức năng:** Hiển thị real-time statistics trong sidebar
- **Layout:** 2x2 metrics grid layout
- **Metrics Calculated:**

**1. Data Volume Metrics:**
```python
- Total products: len(filtered_df)
- Unique stores: filtered_df['name_store'].nunique()  
- Unique platforms: filtered_df['platform'].nunique()
```

**2. Engagement Metrics:**
```python  
Total engagement calculation:
- Sum all likes: filtered_df['like'].astype(int).sum()
- Sum all comments: filtered_df['comment'].astype(int).sum()  
- Sum all shares: filtered_df['share'].astype(int).sum()
- Total = likes + comments + shares
- Format với thousands separator: f"{total:,}"
```

**3. Filter Status Indicators:**
```python
Conditional messaging:
- len(filtered_df) == 0: Warning "Không có dữ liệu phù hợp!"
- len(filtered_df) > 0: Success "X sản phẩm khả dụng"
- Color-coded status với emoji indicators
```

#### Advanced Features:

**Session State Persistence Strategy:**
```python
Initialization logic:
1. Check existing session state values
2. Initialize với sensible defaults nếu missing
3. Date range defaults to full data range
4. Store và Platform defaults to "Tất cả"
5. Maintain state across app reloads
```

**Date Validation System:**
```python
Multi-layer validation:
1. Input level: min_value và max_value constraints
2. Logic level: start <= end validation
3. Error display: st.error với descriptive messages
4. Recovery: auto-reset to previous valid values
5. User guidance: clear error messaging
```

**Performance Considerations:**
- Caching filter results để avoid repeated processing
- Efficient DataFrame operations với vectorized functions
- Memory-conscious date parsing với error handling
- Lazy evaluation cho expensive statistics calculations

#### Integration Points:

**Web.py Integration:**
```python
Main app loop:
1. Call create_sidebar_filter() để get selections
2. Call apply_filters_cached() để get filtered data
3. Store filtered_df trong session_state
4. Pass filtered data to all tabs (Chatbot + Metadata Analysis)
5. Call create_sidebar_stats() để show real-time stats
```

**Metadata Analysis Integration:**
- Filtered data automatically flows to all analysis functions
- Charts và statistics reflect current filter selections  
- Product galleries show only filtered results
- Search functionality respects active filters

**Cross-Tab State Management:**
- Filter selections persist across tab switches
- Filtered data shared between Chatbot và Metadata Analysis
- Statistics update in real-time khi thay đổi tabs
- Session state coordination between all components

### 3.6 Hệ thống Cache và Performance

#### Cache Strategy:

1. **Connection Cache (30 phút):** Tránh kiểm tra connection liên tục
2. **Data Cache (2 tiếng):** Cache dữ liệu Milvus, ID-based pagination results
3. **Resource Cache:** Chatbot instance, CSS, static content
4. **Session State Cache:** Products data, download packages, feedback
5. **Filter Cache (5 phút):** Cached filter results để optimize performance - MỚI
6. **Analysis Cache (30 phút):** Metadata field analysis và statistics - MỚI

#### ID-based Pagination Logic:

**Tại sao cần thiết:**
- Milvus có giới hạn offset = 16384
- Không thể query records > 16384 với offset-based pagination
- ID-based pagination không có giới hạn này

**Cách hoạt động:**
```python
# Thay vì: offset += limit (bị giới hạn)
# Sử dụng: id_sanpham > last_id (unlimited)

last_id = ""
while True:
    if last_id:
        expr = f'id_sanpham > "{last_id}"'
    else:
        expr = ""
    
    results = collection.query(expr=expr, limit=batch_size)
    if not results: break
    
    # Process results
    last_id = results[-1]['id_sanpham']  # Cập nhật cho batch tiếp theo
```

### 3.7 Error Handling & Recovery

**`handle_app_errors()`**
- **Chức năng:** Wrapper xử lý lỗi graceful cho toàn app
- **Logic:** Try-catch main(), provide recovery options

**`handle_download_error()`**  
- **Chức năng:** Xử lý lỗi download gracefully
- **Logic:** Show error, offer retry, provide JSON fallback

**Filter Error Handling - MỚI:**
- Date validation với recovery mechanisms
- Graceful fallback khi filter fails
- User-friendly error messages với actionable guidance
- Automatic reset capabilities

**Modal Error Handling - MỚI:**
- Safe product data processing với try-catch wrapping
- Fallback displays khi image loading fails  
- Graceful degradation cho missing metadata fields
- User notification cho processing errors

**Auto-maintenance:**
- Cleanup cache cũ mỗi 50 interactions
- Memory management cho chat history
- Session state cleanup
- Filter state maintenance và optimization

## 4. Các điểm kỹ thuật quan trọng

### 4.1 Unlimited Data Loading
- Sử dụng ID-based pagination thay vì offset-based
- Vượt qua giới hạn 16384 records của Milvus
- Batch processing với progress tracking

### 4.2 Caching Strategy
- Multi-level caching: Streamlit cache + session state + resource cache
- TTL management để tránh stale data
- Hash-based cache keys cho data integrity

### 4.3 No-Reload Download System
- Pre-generate ZIP packages và cache
- Session state management cho download state
- Error recovery với fallback options

### 4.4 Performance Optimizations
- Lazy loading cho heavy operations
- Batch processing cho large datasets
- Memory cleanup và maintenance tasks
- Image optimization trước upload

### 4.5 Interactive Data Exploration - MỚI
- Click-to-navigate functionality từ charts
- Real-time filtering với persistent state
- Modal system cho detailed product views
- Smart pagination với unlimited display options

### 4.6 Advanced UI/UX Features - MỚI
- Responsive grid layouts với mobile support
- Custom CSS styling với modern design principles
- Progressive loading với user feedback
- Intuitive navigation với state management

## 5. Cấu hình và Dependencies

### 5.1 Required Libraries:
```python
streamlit
pandas
pymilvus
asyncio
json
base64
requests
zipfile
xlsxwriter
PIL (Pillow)
plotly  # MỚI - cho interactive charts
collections  # MỚI - cho Counter functionality
```

### 5.2 External Dependencies:
- Milvus Database (localhost:19530)
- ImgBB API (cho image upload)
- RnDChatbot module (external import)

### 5.3 Database Schema:
Collection: "product_collection_v4"
Fields: id_sanpham, platform, description, metadata, date, like, comment, share, name_store

### 5.4 Metadata Schema:
**Required metadata fields trong JSON format:**
```json
{
  "image_recipient": "string|array",
  "target_audience": "string|array", 
  "usage_purpose": "string|array",
  "occasion": "string|array",
  "niche_theme": "string|array",
  "sentiment_tone": "string|array",
  "message_type": "string|array",
  "personalization_type": "string|array",
  "product_type": "string|array",
  "placement_display_context": "string|array",
  "design_style": "string|array", 
  "color_aesthetic": "string|array",
  "main_subject": "string|array",
  "text": "string|array"
}
```

## 6. Hướng dẫn triển khai

1. **Setup Milvus Database:** Đảm bảo Milvus running trên localhost:19530
2. **Install Dependencies:** `pip install -r requirements.txt`
3. **Configure API Keys:** Thay ImgBB API key trong `upload_to_imgbb_optimized()`
4. **Import RnDChatbot:** Đảm bảo có file `chatbot.py` với class `RnDChatbot

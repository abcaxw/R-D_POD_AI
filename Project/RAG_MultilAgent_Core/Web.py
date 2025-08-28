import streamlit as st
import pandas as pd
import json
import asyncio
from pymilvus import connections, Collection, utility
import warnings
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Import modules
from ui.chatbot_interface import create_chatbot_interface
from ui.filter_interface import create_sidebar_filter, apply_filters_cached, create_sidebar_stats
from ui.metadata_analysis import create_metadata_tab_interface, get_metadata_fields
from data.data_processor import connect_to_milvus, parse_metadata, get_collection_info, load_collection_data_with_pagination

# Import chatbot - Đảm bảo file này có trong cùng thư mục
try:
    from chatbot import RnDChatbot
    CHATBOT_AVAILABLE = True
except ImportError:
    CHATBOT_AVAILABLE = False

warnings.filterwarnings('ignore')


# ==================== CACHING CONFIGURATION ====================

# Cache connection status để tránh kết nối lại liên tục
@st.cache_data(ttl=1800)  # Cache 30 phút
def get_connection_status():
    """Cache connection status để tránh kiểm tra liên tục"""
    try:
        return connect_to_milvus()
    except Exception as e:
        return False

# Enhanced load_collection_data with ID-based pagination - NO OFFSET LIMIT
@st.cache_data(
    ttl=7200,  # Cache 2 tiếng
    max_entries=3,
    show_spinner="🔄 Đang tải dữ liệu từ Milvus với ID-based pagination..."
)
def load_collection_data_cached():
    """Load dữ liệu từ collection với ID-based pagination - không giới hạn offset"""
    try:
        # Hiển thị thông tin collection trước khi load
        collection_info = get_collection_info()
        
        # Sử dụng ID-based pagination thay vì offset-based
        raw_data = load_collection_data_with_pagination()

        if not raw_data:
            st.error("⚠ Không thể tải dữ liệu từ Milvus!")
            return []

        # Convert to serializable format (list of dicts)
        serializable_results = []
        for item in raw_data:
            # Convert each item to regular dict
            serializable_item = {}
            for key, value in item.items():
                # Handle different value types
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    # Convert iterables to list
                    serializable_item[key] = list(value) if not isinstance(value, dict) else value
                else:
                    serializable_item[key] = value
            serializable_results.append(serializable_item)

        return serializable_results

    except Exception as e:
        st.error(f"⚠ Lỗi load dữ liệu: {e}")
        return []


# Alternative fallback method with original logic for comparison
@st.cache_data(
    ttl=7200,
    max_entries=3,
    show_spinner="🔄 Đang tải dữ liệu với method dự phòng..."
)
def load_collection_data_fallback():
    """Fallback method với logic cũ (có giới hạn offset)"""
    try:
        collection_name = "product_collection_v4"

        if not utility.has_collection(collection_name):
            st.error(f"⚠ Collection '{collection_name}' không tồn tại!")
            return []

        collection = Collection(collection_name)
        collection.load()

        # Query toàn bộ dữ liệu với giới hạn cũ
        results = collection.query(
            expr="",  # Query tất cả
            output_fields=["id_sanpham", "platform", "description", "metadata", "date", "like", "comment", "share", "name_store"],
            limit=16384  # Giới hạn max của phương pháp cũ
        )

        # Convert to serializable format
        serializable_results = []
        for item in results:
            serializable_item = {}
            for key, value in item.items():
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    serializable_item[key] = list(value) if not isinstance(value, dict) else value
                else:
                    serializable_item[key] = value
            serializable_results.append(serializable_item)

        return serializable_results

    except Exception as e:
        st.error(f"⚠ Lỗi fallback load dữ liệu: {e}")
        return []


# Cache chatbot initialization
@st.cache_resource
def initialize_cached_chatbot():
    """Initialize chatbot với resource caching - chỉ khởi tạo 1 lần"""
    if CHATBOT_AVAILABLE:
        try:
            return RnDChatbot()
        except Exception as e:
            st.error(f"⚠ Lỗi khởi tạo chatbot: {e}")
            return None
    return None


# Cache CSS loading
@st.cache_data
def load_cached_css():
    """Cache CSS để tránh load lại mỗi lần"""
    css = """
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    .filter-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .chart-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    .metadata-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .metadata-item {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    .stButton > button {
        width: 100%;
        margin: 2px 0;
    }
    .engagement-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .product-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        background: #f9f9f9;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# Cache static content
@st.cache_data
def get_header_content():
    """Cache nội dung header tĩnh"""
    return """
    <div class="main-header">
        <h1>🚀 Milvus Product Analytics Dashboard</h1>
        <p>🤖 RnD Assistant - Chatbot phân tích dữ liệu từ Milvus Vector Database</p>
        <small>✅ Unlimited Data Loading - No Offset Limit</small>
    </div>
    """


# Cache static loading message
@st.cache_data
def get_loading_messages():
    """Cache các thông báo loading"""
    return {
        'initial': "🔄 Đang tải dữ liệu từ Milvus với ID-based pagination...",
        'success': "✅ Dữ liệu đã được tải thành công với unlimited records!",
        'waiting': "⏳ Vui lòng đợi dữ liệu được tải...",
        'no_data': "❌ Không có dữ liệu để hiển thị!",
        'switch_tab': "⚡ Chuyển đổi tab - không cần tải lại dữ liệu",
        'unlimited': "🚀 Đang load unlimited data - không giới hạn offset!"
    }


# ==================== SESSION STATE MANAGEMENT ====================

def initialize_session_state():
    """Khởi tạo session state một cách tối ưu"""
    # Chỉ khởi tạo nếu chưa có
    if 'app_initialized' not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.last_connection_check = None
        st.session_state.connection_status = None

    if 'chatbot_initialized' not in st.session_state:
        st.session_state.chatbot_initialized = False
        st.session_state.chatbot = None
        st.session_state.chat_history = []
        st.session_state.chatbot_loading = False

    # Filter settings với persistence
    if 'filter_settings' not in st.session_state:
        st.session_state.filter_settings = {}
        st.session_state.filtered_df = pd.DataFrame()
        st.session_state.filter_applied = False
        st.session_state.filter_changed = False

    # Sidebar filter state
    if 'sidebar_store' not in st.session_state:
        st.session_state.sidebar_store = 'Tất cả'
    if 'sidebar_platform' not in st.session_state:
        st.session_state.sidebar_platform = 'Tất cả'
    if 'sidebar_date_range' not in st.session_state:
        st.session_state.sidebar_date_range = None

    # Data loading state
    if 'app_data_loaded' not in st.session_state:
        st.session_state.app_data_loaded = False
        st.session_state.master_df = pd.DataFrame()

    # Current active tab persistence
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "chatbot"

    # Metadata view mode state
    if 'metadata_view_mode' not in st.session_state:
        st.session_state.metadata_view_mode = "overview"
    if 'selected_metadata_field' not in st.session_state:
        st.session_state.selected_metadata_field = None
    if 'selected_metadata_value' not in st.session_state:
        st.session_state.selected_metadata_value = None

    # Performance tracking
    if 'page_load_count' not in st.session_state:
        st.session_state.page_load_count = 0
        st.session_state.last_activity = datetime.now()

    # Data loading method tracking
    if 'loading_method' not in st.session_state:
        st.session_state.loading_method = "id_based"  # Default to unlimited method

    st.session_state.page_load_count += 1
    st.session_state.last_activity = datetime.now()


# ==================== OPTIMIZED CHATBOT INITIALIZATION ====================

def setup_chatbot_optimized():
    """Thiết lập chatbot với caching tối ưu"""
    if not CHATBOT_AVAILABLE:
        if st.session_state.page_load_count == 1:  # Chỉ hiện warning lần đầu
            st.warning("⚠️ Không thể import chatbot. Chức năng chatbot sẽ bị vô hiệu hóa.")
        return False

    # Chỉ khởi tạo nếu chưa có và không đang loading
    if not st.session_state.chatbot_initialized and not st.session_state.chatbot_loading:
        st.session_state.chatbot_loading = True
    return st.session_state.chatbot_initialized


# ==================== MAIN APPLICATION ====================

def main():
    """Main application với unlimited data loading"""

    # Cấu hình trang - chỉ chạy 1 lần
    st.set_page_config(
        page_title="Milvus Product Analytics Dashboard - Unlimited",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    initialize_session_state()

    # Load CSS (cached)
    load_cached_css()

    # Header (cached content)
    st.markdown(get_header_content(), unsafe_allow_html=True)

    # Check connection
    if not get_connection_status():
        st.error("⚠️ Không thể kết nối tới Milvus. Vui lòng kiểm tra kết nối!")
        return

    # Data loading với session state caching - sử dụng ID-based pagination
    loading_msgs = get_loading_messages()

    if 'app_data_loaded' not in st.session_state or st.session_state.app_data_loaded == False:
    
        
        with st.spinner(loading_msgs['unlimited']):
            # Sử dụng method mới với unlimited loading
            raw_data = load_collection_data_cached()

            if not raw_data:
                st.warning("⚠ Thử sử dụng method dự phòng...")
                with st.spinner("🔄 Đang thử method dự phòng..."):
                    raw_data = load_collection_data_fallback()
                
                if not raw_data:
                    st.error("❌ Không thể tải dữ liệu từ Milvus!")
                    return

            df = parse_metadata(raw_data)
            if df.empty:
                st.error("❌ Không thể parse dữ liệu metadata!")
                return

            # Cache data trong session state
            st.session_state.master_df = df
            st.session_state.app_data_loaded = True

            # Show success message với thống kê
            success_placeholder = st.empty()
            success_placeholder.success(f"""
            ✅ {loading_msgs['success']}
            
            📊 **Thống kê tải dữ liệu:**
            - Tổng records: {len(df):,}
            - Phương pháp: ID-based pagination (unlimited)
            - Thời gian: {datetime.now().strftime('%H:%M:%S')}
            """)
            time.sleep(2)  # Brief delay to show success
            success_placeholder.empty()
    else:
        # Sử dụng data đã cached - không có spinner loading
        df = st.session_state.master_df
        
        # Hiển thị thông tin data đã load
        st.sidebar.success(f"📊 Data loaded: {len(df):,} records")

    # Sidebar filter (always visible) với persistent state - chỉ hiển thị khi có data
    if st.session_state.app_data_loaded and not st.session_state.master_df.empty:
        selected_store, selected_platform, date_range = create_sidebar_filter(df)

        # Apply filters với caching
        filtered_df = apply_filters_cached(df, selected_store, selected_platform, date_range)
        st.session_state.filtered_df = filtered_df

        # Show stats in sidebar với unlimited data info
        create_sidebar_stats(filtered_df)
        
        # Thêm thông tin về unlimited loading
        st.sidebar.markdown("---")
        st.sidebar.success("🚀 **Unlimited Loading Active**")
        st.sidebar.info(f"✅ No offset limit\n📈 ID-based pagination\n💾 Cached: {len(df):,} records")

        # Simple tab implementation với session state - instant switching
        col1, col2 = st.columns(2)
        with col1:
            chatbot_clicked = st.button("🤖 Chatbot Assistant",
                                        use_container_width=True,
                                        type="primary" if st.session_state.active_tab == "chatbot" else "secondary")
            if chatbot_clicked:
                st.session_state.active_tab = "chatbot"

        with col2:
            metadata_clicked = st.button("📊 Metadata Analysis",
                                         use_container_width=True,
                                         type="primary" if st.session_state.active_tab == "metadata" else "secondary")
            if metadata_clicked:
                st.session_state.active_tab = "metadata"

        st.markdown("---")

        # Display content based on active tab - instant loading, no data reload
        if st.session_state.active_tab == "chatbot":
            st.header("🤖 Chatbot Assistant")
            # Setup chatbot
            setup_chatbot_optimized()
            # Main chatbot interface
            create_chatbot_interface()

        elif st.session_state.active_tab == "metadata":
            # Metadata analysis với sub-tabs (Overview và View Products)
            create_metadata_tab_interface(df)
    else:
        # Show loading state or error if data not available
        if not st.session_state.app_data_loaded:
            st.info(get_loading_messages()['waiting'])
        else:
            st.error(get_loading_messages()['no_data'])

    # Auto-cleanup old data (tùy chọn)
    cleanup_old_data()


# ==================== CLEANUP FUNCTIONS ====================

def cleanup_old_data():
    """Cleanup dữ liệu cũ để tránh memory leak"""
    # Giới hạn chat history
    max_history = 50
    if len(st.session_state.chat_history) > max_history:
        st.session_state.chat_history = st.session_state.chat_history[-max_history:]

    # Reset connection check nếu app không hoạt động lâu
    if st.session_state.last_activity < datetime.now() - timedelta(hours=2):
        st.session_state.last_connection_check = None
        st.session_state.connection_status = None


# ==================== ERROR HANDLING ====================

def handle_app_errors():
    """Xử lý lỗi app với graceful degradation"""
    try:
        main()
    except Exception as e:
        st.error(f"""
        ⚠ **Đã xảy ra lỗi ứng dụng:**

        `{str(e)}`

        **Khắc phục:**
        1. Refresh trang (F5)
        2. Xóa cache trình duyệt
        3. Kiểm tra kết nối mạng
        4. Thử lại với method dự phòng
        """)

        # Reset session state nếu có lỗi nghiêm trọng
        if st.button("🔄 Reset ứng dụng"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        # Option to try fallback method
        if st.button("🛠 Thử method dự phòng"):
            st.session_state.app_data_loaded = False
            st.session_state.loading_method = "fallback"
            st.rerun()


if __name__ == "__main__":
    handle_app_errors()

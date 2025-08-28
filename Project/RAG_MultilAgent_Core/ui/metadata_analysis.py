import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
import plotly.graph_objects as go

@st.cache_data(ttl=1800)  # Cache 30 phút
def analyze_metadata_field(df, field_name):
    """Phân tích một field metadata cụ thể"""
    if field_name not in df.columns:
        return pd.DataFrame(), []

    # Xử lý các giá trị là list (cách nhau bởi dấu phẩy)
    all_values = []
    for value in df[field_name].dropna():
        if isinstance(value, str) and value.strip():
            # Split by comma and clean
            values = [v.strip().strip('"').strip("'") for v in value.split(',')]
            all_values.extend([v for v in values if v])

    # Đếm frequency
    counter = Counter(all_values)

    # Tạo DataFrame
    result_df = pd.DataFrame(counter.most_common(10), columns=[field_name, 'Count'])

    return result_df, list(counter.keys())


@st.cache_data(ttl=600)
def get_filtered_and_sorted_products(df, field_name, field_value, limit=None):  # Đổi từ limit=10 thành limit=None
    """Lọc và sắp xếp sản phẩm theo engagement - không giới hạn số lượng mặc định"""

    # Filter products có chứa field_value
    filtered_products = df[df[field_name].str.contains(field_value, na=False, case=False)]

    if len(filtered_products) == 0:
        return pd.DataFrame(), {}

    # Calculate engagement score (like + comment + share)
    filtered_products = filtered_products.copy()
    filtered_products['engagement_score'] = (
            filtered_products['like'].astype(int) +
            filtered_products['comment'].astype(int) +
            filtered_products['share'].astype(int)
    )

    # Sort by engagement score descending
    sorted_products = filtered_products.sort_values('engagement_score', ascending=False)

    # Nếu không có limit hoặc limit lớn hơn tổng số, lấy tất cả
    if limit is None or limit >= len(sorted_products):
        top_products = sorted_products
    else:
        top_products = sorted_products.head(limit)

    # Prepare statistics
    stats = {
        'total_found': len(filtered_products),
        'showing_top': len(top_products),
        'total_likes': top_products['like'].astype(int).sum() if len(top_products) > 0 else 0,
        'total_comments': top_products['comment'].astype(int).sum() if len(top_products) > 0 else 0,
        'total_shares': top_products['share'].astype(int).sum() if len(top_products) > 0 else 0,
        'total_engagement': top_products['engagement_score'].sum() if len(top_products) > 0 else 0,
        'has_more': False if limit is None else len(filtered_products) > limit
    }

    return top_products, stats

# ============================Hiển thị phần view product detail============================
def show_sample_products(df, field_name, field_value):
    """Gallery 5 cột + popup chi tiết sản phẩm với tùy chọn hiển thị tất cả"""

    # Session state với limit cao hơn
    if 'products_limit' not in st.session_state:
        st.session_state.products_limit = 50  # Tăng từ 20 lên 50
    if 'selected_product' not in st.session_state:
        st.session_state.selected_product = None

    # Thêm tùy chọn hiển thị tất cả
    col_limit1, col_limit2, col_limit3 = st.columns([2, 2, 2])

    with col_limit1:
        if st.button("📋 Hiển thị 50 sản phẩm đầu"):
            st.session_state.products_limit = 50
            st.rerun()

    with col_limit2:
        if st.button("📄 Hiển thị 200 sản phẩm"):
            st.session_state.products_limit = 200
            st.rerun()

    with col_limit3:
        if st.button("🌟 HIỂN THỊ TẤT CẢ", type="primary"):
            st.session_state.products_limit = None  # Không giới hạn
            st.rerun()

    # Get data
    try:
        current_limit = st.session_state.products_limit
        top_products, stats = get_filtered_and_sorted_products(df, field_name, field_value, current_limit)
    except Exception as e:
        st.error(f"Lỗi khi lấy dữ liệu: {e}")
        return

    if top_products.empty:
        st.warning(f"Không tìm thấy sản phẩm nào có {field_name} = '{field_value}'")
        return

    # Hiển thị thông tin số lượng
    if current_limit is None:
        st.subheader(f"🖼️ TẤT CẢ {stats.get('showing_top', 0)} sản phẩm có {field_name} = '{field_value}'")
        st.success(f"✅ Đang hiển thị tất cả {stats.get('total_found', 0)} sản phẩm được tìm thấy!")
    else:
        st.subheader(f"🖼️ Top {stats.get('showing_top', 0)} sản phẩm hot có {field_name} = '{field_value}'")
        if stats.get('has_more', False):
            st.info(f"📊 Hiển thị {stats.get('showing_top', 0)} trong tổng số {stats.get('total_found', 0)} sản phẩm")

    # Grid 5 cột
    cols_per_row = 5
    for row_start in range(0, len(top_products), cols_per_row):
        row_products = top_products.iloc[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col, (_, product) in zip(cols, row_products.iterrows()):
            try:
                product_id = product.get('id_sanpham', 'unknown')
                product_key = f"{field_name}_{field_value}_{product_id}"

                with col:
                    img_url = None
                    if 'image_url' in product and pd.notna(product['image_url']) and str(product['image_url']).strip():
                        img_url = product['image_url']
                    elif 'image_path' in product and pd.notna(product['image_path']) and str(
                            product['image_path']).strip():
                        img_url = product['image_path']

                    if st.button("🖼️", key=f"btn_{product_key}"):
                        st.session_state.selected_product = product.to_dict()
                        st.rerun()

                    if img_url:
                        try:
                            st.image(img_url, width=500, use_container_width=False)
                        except Exception:
                            st.markdown(
                                "<div style='width:500px;height:500px;background:#ddd;display:flex;align-items:center;justify-content:center;border-radius:8px;'>❌</div>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.markdown(
                            "<div style='width:500px;height:500px;background:#ddd;display:flex;align-items:center;justify-content:center;border-radius:8px;'>❌</div>",
                            unsafe_allow_html=True
                        )

                    # Hiển thị thêm thông tin ngắn gọn dưới ảnh
                    with st.expander(f"Info {product_id}"):
                        st.write(f"**Like:** {product.get('like', 0):,}")
                        st.write(f"**Comment:** {product.get('comment', 0):,}")
                        st.write(f"**Share:** {product.get('share', 0):,}")
                        st.write(f"**Store:** {product.get('name_store', 'N/A')}")

            except Exception:
                with col:
                    st.error("Lỗi sản phẩm")

    # Chỉ hiển thị nút load thêm nếu không phải đang hiển thị tất cả
    if current_limit is not None and stats.get('has_more', False):
        st.markdown("---")
        col_load1, col_load2 = st.columns(2)
        with col_load1:
            if st.button("📄 Xem thêm 50 sản phẩm"):
                st.session_state.products_limit += 50
                st.rerun()
        with col_load2:
            if st.button("🌟 Hiển thị tất cả ngay"):
                st.session_state.products_limit = None
                st.rerun()

    # Reset button (luôn hiển thị)
    if st.session_state.products_limit != 50:
        if st.button("🔄 Reset về 50 sản phẩm đầu"):
            st.session_state.products_limit = 50
            st.rerun()

    # Modal popup chi tiết sản phẩm
    if st.session_state.selected_product:
        try:
            show_large_product_modal(st.session_state.selected_product)
        except Exception as e:
            st.error("Lỗi hiển thị chi tiết sản phẩm")
            st.session_state.selected_product = None


@st.dialog("Chi tiết sản phẩm")
def show_large_product_modal(product):
    """Hiển thị modal chi tiết sản phẩm với kích thước lớn hơn - Fix hiển thị thông tin"""

    if not product:
        st.error("Không có thông tin sản phẩm")
        return

    # CSS tối ưu cho modal lớn - điều chỉnh khung ngoài
    st.markdown("""
    <style>
    /* Điều chỉnh khung modal chính */
    .stDialog {
        width: 100vw !important;
        height: 100vh !important;
        max-width: none !important;
        max-height: none !important;
    }

    .stDialog > div {
        width: 90vw !important;
        max-width: 1600px !important;
        height: 85vh !important;
        max-height: 85vh !important;
        margin: auto !important;
        transform: translate(0, 0) !important;
    }

    .stDialog [data-testid="stVerticalBlock"] {
        height: 100% !important;
        overflow-y: auto !important;
        padding: 0 !important;
    }

    /* Override Streamlit modal constraints */
    div[role="dialog"] {
        width: 90vw !important;
        max-width: 1600px !important;
        height: 85vh !important;
        max-height: 85vh !important;
    }

    /* Modal backdrop */
    .stDialog::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.7);
        z-index: -1;
    }

    /* Container chính với padding nhỏ hơn để tận dụng không gian */
    .large-modal-container {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        padding: 20px;
        box-sizing: border-box;
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 15px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        overflow: hidden;
    }

    /* Header nhỏ gọn hơn */
    .large-modal-header {
        text-align: center;
        margin-bottom: 25px;
        padding-bottom: 15px;
        border-bottom: 2px solid #e2e8f0;
        flex-shrink: 0;
    }

    .large-modal-header h1 {
        font-size: 2rem !important;
        color: #1e293b;
        margin: 0 0 10px 0;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .large-modal-header .product-id {
        font-size: 1rem;
        color: #64748b;
        font-weight: 600;
        background: #f1f5f9;
        padding: 8px 16px;
        border-radius: 20px;
        display: inline-block;
    }

    /* Grid layout chính với spacing nhỏ hơn */
    .large-modal-content {
        display: grid;
        grid-template-columns: 1fr 1.8fr;
        gap: 30px;
        flex: 1;
        overflow: hidden;
        min-height: 0;
    }

    /* Cột ảnh - tối ưu không gian */
    .image-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        overflow: hidden;
    }

    .image-section img {
        max-width: 100%;
        height: auto;
        max-height: 60vh;
        border-radius: 15px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.12);
        transition: transform 0.3s ease;
    }

    .image-section img:hover {
        transform: scale(1.03);
    }

    .no-image-placeholder {
        width: 300px;
        height: 300px;
        background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 15px;
        font-size: 3rem;
        color: #94a3b8;
        border: 2px dashed #cbd5e1;
    }

    /* Cột thông tin - scrollable */
    .info-section {
        display: flex;
        flex-direction: column;
        gap: 20px;
        overflow-y: auto;
        padding-right: 15px;
        max-height: 70vh;
    }

    /* Card thông tin nhỏ gọn hơn */
    .info-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.06);
        border-left: 4px solid #3b82f6;
        flex-shrink: 0;
    }

    .info-card h3 {
        font-size: 1.5rem !important;
        color: #1e293b;
        margin: 0 0 15px 0;
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 700;
    }

    .info-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #f1f5f9;
        font-size: 1.1rem;
    }

    .info-item:last-child {
        border-bottom: none;
    }

    .info-label {
        font-weight: 700;
        color: #374151;
        font-size: 1.1rem;
    }

    .info-value {
        color: #1e293b;
        font-weight: 600;
        font-size: 1.1rem;
    }

    /* Engagement metrics nhỏ gọn */
    .engagement-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
        margin-top: 8px;
    }

    .metric-card {
        background: linear-gradient(135deg, #fff, #f8fafc);
        padding: 18px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        border: 1px solid #e2e8f0;
        transition: transform 0.2s ease;
    }

    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    }

    .metric-icon {
        font-size: 2rem;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1e293b;
        margin-bottom: 4px;
    }

    .metric-label {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 500;
    }

    /* Description section nhỏ gọn */
    .description-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.06);
        border-left: 4px solid #10b981;
    }

    .description-text {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #374151;
        max-height: 150px;
        overflow-y: auto;
        background: #f9fafb;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }

    /* Close button nhỏ gọn */
    .close-button-container {
        text-align: center;
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #e2e8f0;
        flex-shrink: 0;
    }

    /* Responsive */
    @media (max-width: 1200px) {
        .large-modal-content {
            grid-template-columns: 1fr;
            gap: 30px;
        }

        .large-modal-header h1 {
            font-size: 2rem !important;
        }

        .engagement-grid {
            grid-template-columns: repeat(4, 1fr);
        }
    }

    @media (max-width: 768px) {
        .large-modal-container {
            padding: 20px;
        }

        .engagement-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # Container chính
    st.markdown('<div class="large-modal-container">', unsafe_allow_html=True)

    # Header
    try:
        product_id = product.get('id_sanpham', 'Unknown')
        st.markdown(f'''
            <div class="large-modal-header">
                <h1>🛍️ Chi tiết sản phẩm</h1>
                <div class="product-id">ID: {product_id}</div>
            </div>
        ''', unsafe_allow_html=True)
    except Exception:
        st.error("Lỗi hiển thị tiêu đề")

    # Content grid
    st.markdown('<div class="large-modal-content">', unsafe_allow_html=True)

    # Cột 1: Ảnh sản phẩm
    col1, col2 = st.columns([1, 1.5], gap="large")

    with col1:
        st.markdown('<div class="image-section">', unsafe_allow_html=True)
        try:
            img_url = None
            if product.get("image_url") and pd.notna(product["image_url"]):
                img_url = product["image_url"]
            elif product.get("image_path") and pd.notna(product["image_path"]):
                img_url = product["image_path"]

            if img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.markdown('<div class="no-image-placeholder">❌</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="no-image-placeholder">❌</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Cột 2: Thông tin chi tiết + Engagement + Mô tả
    with col2:
        st.markdown('<div class="info-section">', unsafe_allow_html=True)

        # HIỂN THỊ THÔNG TIN BẰNG STREAMLIT THAY VÌ HTML

        # 1. Thông tin cơ bản
        with st.container():
            st.markdown("### 📋 Thông tin cơ bản")

            col_info1, col_info2 = st.columns([1, 1.5])
            with col_info1:
                st.markdown("**🏪 Cửa hàng:**")
                st.markdown("**📱 Platform:**")
                st.markdown("**📅 Ngày đăng:**")
                st.markdown("**🆔 Mã sản phẩm:**")

            with col_info2:
                st.markdown(
                    f"<span style='font-size: 1.1rem; color: #1e293b; font-weight: 600;'>{product.get('name_store', 'N/A')}</span>",
                    unsafe_allow_html=True)
                st.markdown(
                    f"<span style='font-size: 1.1rem; color: #1e293b; font-weight: 600;'>{product.get('platform', 'N/A')}</span>",
                    unsafe_allow_html=True)
                st.markdown(
                    f"<span style='font-size: 1.1rem; color: #1e293b; font-weight: 600;'>{product.get('date', 'N/A')}</span>",
                    unsafe_allow_html=True)
                st.markdown(
                    f"<span style='font-size: 1.1rem; color: #1e293b; font-weight: 600;'>{product.get('id_sanpham', 'N/A')}</span>",
                    unsafe_allow_html=True)

        # 2. Engagement Metrics
        with st.container():
            st.markdown("### 📊 Engagement Metrics")

            try:
                likes = product.get('like', 0)
                comments = product.get('comment', 0)
                shares = product.get('share', 0)
                score = product.get('engagement_score', 0)

                # Format số với dấu phẩy
                def format_number(value):
                    try:
                        if pd.notna(value) and str(value).replace('.', '').replace(',', '').isdigit():
                            return f"{int(float(value)):,}"
                        return "0"
                    except:
                        return "0"

                def format_float(value):
                    try:
                        if pd.notna(value):
                            return f"{float(value):.1f}"
                        return "0.0"
                    except:
                        return "0.0"

                likes_str = format_number(likes)
                comments_str = format_number(comments)
                shares_str = format_number(shares)
                score_str = format_float(score)

                # Hiển thị metrics trong 4 cột với style tùy chỉnh
                st.markdown("""
                <style>
                .metric-container {
                    text-align: center;
                    padding: 15px;
                    background: #f8fafc;
                    border-radius: 10px;
                    border: 1px solid #e2e8f0;
                    margin-bottom: 10px;
                }
                .metric-value {
                    font-size: 1.8rem !important;
                    font-weight: bold;
                    color: #1e293b;
                    margin-bottom: 5px;
                }
                .metric-label {
                    font-size: 1rem !important;
                    color: #64748b;
                    font-weight: 600;
                }
                </style>
                """, unsafe_allow_html=True)

                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

                with metric_col1:
                    st.metric(label="👍 Lượt thích", value=likes_str)

                with metric_col2:
                    st.metric(label="💬 Bình luận", value=comments_str)

                with metric_col3:
                    st.metric(label="🔄 Chia sẻ", value=shares_str)

                with metric_col4:
                    st.metric(label="🔥 Điểm tương tác", value=score_str)

            except Exception as e:
                st.error("Lỗi hiển thị metrics")

        # 3. Mô tả sản phẩm
        with st.container():
            st.markdown("### 📝 Mô tả sản phẩm")
            try:
                description = product.get("description", "Không có mô tả")
                if len(str(description)) > 2000:
                    description = str(description)[:2000] + "..."

                # Hiển thị mô tả trong text_area với style tùy chỉnh
                st.markdown("""
                <style>
                .stTextArea textarea {
                    font-size: 1.1rem !important;
                    color: #000000 !important;
                    font-weight: 500 !important;
                    line-height: 1.6 !important;
                    background: #f8fafc !important;
                    border: 2px solid #e2e8f0 !important;
                    border-radius: 10px !important;
                    padding: 15px !important;
                }
                .stTextArea textarea:disabled {
                    color: #1e293b !important;  /* Màu chữ khi disabled */
                    -webkit-text-fill-color: #1e293b !important; /* Fix Safari/Chrome */
                    opacity: 1 !important; /* Bỏ mờ */
                }    
                </style>        
                """, unsafe_allow_html=True)

                st.text_area(
                    label="Mô tả sản phẩm",  # Provide a proper label
                    value=description,
                    height=200,
                    disabled=True,
                    label_visibility="collapsed"  # Hide the label visually while keeping it for accessibility
                )
            except Exception:
                st.error("Lỗi hiển thị mô tả")

        st.markdown('</div>', unsafe_allow_html=True)  # end info-section

    # Close button
    st.markdown('<div class="close-button-container">', unsafe_allow_html=True)
    if st.button("❌ Đóng popup", key="close_modal_btn", use_container_width=False):
        st.session_state.selected_product = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def show_sample_products_fullscreen(df, field_name, field_value):
    """Phiên bản modal overlay HTML thuần với kích thước toàn màn hình"""

    # Session state
    if 'products_limit' not in st.session_state:
        st.session_state.products_limit = 20
    if 'selected_product' not in st.session_state:
        st.session_state.selected_product = None

    # CSS cho modal overlay toàn màn hình
    if st.session_state.selected_product:
        st.markdown("""
        <style>
        .fullscreen-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.95);
            backdrop-filter: blur(10px);
            z-index: 999999;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 0;
            margin: 0;
        }

        .fullscreen-modal-content {
            background: white;
            border-radius: 25px;
            padding: 60px;
            width: 95vw;
            height: 95vh;
            max-width: none;
            max-height: none;
            overflow-y: auto;
            box-shadow: 0 50px 100px rgba(0,0,0,0.5);
            animation: modalZoomIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            display: flex;
            flex-direction: column;
        }

        .fullscreen-modal-header {
            text-align: center;
            margin-bottom: 50px;
            padding-bottom: 30px;
            border-bottom: 4px solid #e2e8f0;
        }

        .fullscreen-modal-header h1 {
            font-size: 4rem;
            margin: 0 0 20px 0;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .fullscreen-modal-body {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 80px;
            flex: 1;
            min-height: 0;
        }

        .fullscreen-image-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }

        .fullscreen-image-section img {
            max-width: 100%;
            max-height: 70vh;
            border-radius: 25px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.2);
        }

        .fullscreen-info-section {
            display: flex;
            flex-direction: column;
            gap: 40px;
            overflow-y: auto;
        }

        .fullscreen-info-card {
            background: linear-gradient(135deg, #f8fafc, #e2e8f0);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .fullscreen-info-card h3 {
            font-size: 2rem;
            color: #1e293b;
            margin: 0 0 30px 0;
        }

        .fullscreen-info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 2px solid rgba(226, 232, 240, 0.5);
            font-size: 1.4rem;
        }

        .fullscreen-engagement-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 30px;
        }

        .fullscreen-metric-card {
            background: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            border: 3px solid #f1f5f9;
        }

        .fullscreen-metric-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }

        .fullscreen-metric-value {
            font-size: 3rem;
            font-weight: bold;
            color: #1e293b;
            margin-bottom: 10px;
        }

        .fullscreen-close-btn {
            position: absolute;
            top: 30px;
            right: 40px;
            background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
            color: white;
            border: none;
            padding: 20px 30px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1.5rem;
            font-weight: bold;
            box-shadow: 0 10px 30px rgba(255,107,107,0.4);
            transition: all 0.3s ease;
        }

        .fullscreen-close-btn:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(255,107,107,0.5);
        }

        @keyframes modalZoomIn {
            from {
                opacity: 0;
                transform: scale(0.3) rotateY(30deg);
            }
            to {
                opacity: 1;
                transform: scale(1) rotateY(0deg);
            }
        }

        @media (max-width: 1400px) {
            .fullscreen-modal-body {
                grid-template-columns: 1fr;
                gap: 50px;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    # Hiển thị grid sản phẩm với ảnh lớn hơn
    try:
        current_limit = st.session_state.products_limit
        top_products, stats = get_filtered_and_sorted_products(df, field_name, field_value, current_limit)
    except Exception as e:
        st.error(f"Lỗi khi lấy dữ liệu: {e}")
        return

    if top_products.empty:
        st.warning(f"Không tìm thấy sản phẩm nào có {field_name} = '{field_value}'")
        return

    st.subheader(f"🖼️ Top {stats.get('showing_top', 0)} sản phẩm hot có {field_name} = '{field_value}'")

    # Grid 5 cột với ảnh lớn hơn
    cols_per_row = 5
    for row_start in range(0, len(top_products), cols_per_row):
        row_products = top_products.iloc[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col, (_, product) in zip(cols, row_products.iterrows()):
            try:
                product_id = product.get('id_sanpham', 'unknown')
                product_key = f"{field_name}_{field_value}_{product_id}"

                with col:
                    img_url = None
                    if 'image_url' in product and pd.notna(product['image_url']) and str(product['image_url']).strip():
                        img_url = product['image_url']
                    elif 'image_path' in product and pd.notna(product['image_path']) and str(
                            product['image_path']).strip():
                        img_url = product['image_path']

                    if st.button("🖼️", key=f"btn_{product_key}"):
                        st.session_state.selected_product = product.to_dict()
                        st.rerun()

                    if img_url:
                        try:
                            # Tăng kích thước ảnh từ 120px lên 180px
                            st.image(img_url, width=180, use_container_width=False)
                        except Exception:
                            st.markdown(
                                "<div style='width:180px;height:180px;background:#ddd;display:flex;align-items:center;justify-content:center;border-radius:8px;'>❌</div>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.markdown(
                            "<div style='width:180px;height:180px;background:#ddd;display:flex;align-items:center;justify-content:center;border-radius:8px;'>❌</div>",
                            unsafe_allow_html=True
                        )
            except Exception:
                with col:
                    st.error("Lỗi sản phẩm")

    # Nút load thêm
    if stats.get('has_more', False):
        st.markdown("---")
        if st.button("📄 Xem thêm 20 sản phẩm"):
            st.session_state.products_limit += 20
            st.rerun()

    if st.session_state.products_limit > 20:
        if st.button("🔄 Reset về 20 sản phẩm đầu"):
            st.session_state.products_limit = 20
            st.rerun()

    # Modal overlay toàn màn hình với thông tin hiển thị đúng
    if st.session_state.selected_product:
        try:
            product = st.session_state.selected_product

            # Format dữ liệu đúng cách
            product_id = str(product.get('id_sanpham', 'Unknown'))
            name_store = str(product.get('name_store', 'N/A'))
            platform = str(product.get('platform', 'N/A'))
            date = str(product.get('date', 'N/A'))
            description = str(product.get('description', 'Không có mô tả'))
            if len(description) > 1500:
                description = description[:1500] + "..."

            # Format engagement metrics đúng cách
            def safe_format_number(value):
                try:
                    if pd.notna(value) and str(value).replace('.', '').replace(',', '').isdigit():
                        return f"{int(float(value)):,}"
                    return "0"
                except:
                    return "0"

            def safe_format_float(value):
                try:
                    if pd.notna(value):
                        return f"{float(value):.1f}"
                    return "0.0"
                except:
                    return "0.0"

            likes = product.get('like', 0)
            comments = product.get('comment', 0)
            shares = product.get('share', 0)
            score = product.get('engagement_score', 0)

            likes_str = safe_format_number(likes)
            comments_str = safe_format_number(comments)
            shares_str = safe_format_number(shares)
            score_str = safe_format_float(score)

            # Get image URL
            img_url = None
            if product.get("image_url") and pd.notna(product["image_url"]):
                img_url = str(product["image_url"])
            elif product.get("image_path") and pd.notna(product["image_path"]):
                img_url = str(product["image_path"])

            # Tạo HTML cho modal toàn màn hình với dữ liệu thực
            modal_html = f"""
            <div class="fullscreen-modal-overlay" onclick="closeModal()">
                <div class="fullscreen-modal-content" onclick="event.stopPropagation()">
                    <button onclick="closeModal()" class="fullscreen-close-btn">✕ Đóng</button>

                    <div class="fullscreen-modal-header">
                        <h1>🛍️ Chi tiết sản phẩm</h1>
                        <div style="font-size: 1.8rem; color: #64748b; background: #f1f5f9; padding: 15px 30px; border-radius: 30px; display: inline-block;">
                            ID: {product_id}
                        </div>
                    </div>

                    <div class="fullscreen-modal-body">
                        <div class="fullscreen-image-section">
                            {f'<img src="{img_url}" alt="Product Image">' if img_url else '<div style="width: 500px; height: 500px; background: linear-gradient(135deg, #f1f5f9, #e2e8f0); display: flex; align-items: center; justify-content: center; border-radius: 25px; font-size: 6rem; color: #94a3b8; border: 5px dashed #cbd5e1;">❌</div>'}
                        </div>

                        <div class="fullscreen-info-section">
                            <div class="fullscreen-info-card">
                                <h3>📋 Thông tin cơ bản</h3>
                                <div class="fullscreen-info-item">
                                    <span style="font-weight: 700; color: #475569;">🏪 Cửa hàng:</span>
                                    <span style="color: #059669; font-weight: 600;">{name_store}</span>
                                </div>
                                <div class="fullscreen-info-item">
                                    <span style="font-weight: 700; color: #475569;">📱 Platform:</span>
                                    <span style="color: #7c3aed; font-weight: 600;">{platform}</span>
                                </div>
                                <div class="fullscreen-info-item">
                                    <span style="font-weight: 700; color: #475569;">📅 Ngày đăng:</span>
                                    <span style="color: #dc2626; font-weight: 600;">{date}</span>
                                </div>
                                <div class="fullscreen-info-item" style="border-bottom: none;">
                                    <span style="font-weight: 700; color: #475569;">🆔 Mã sản phẩm:</span>
                                    <span style="background: #e5e7eb; padding: 8px 16px; border-radius: 10px; font-family: monospace; font-weight: 600;">{product_id}</span>
                                </div>
                            </div>

                            <div class="fullscreen-info-card">
                                <h3>📊 Engagement Metrics</h3>
                                <div class="fullscreen-engagement-grid">
                                    <div class="fullscreen-metric-card">
                                        <div class="fullscreen-metric-icon">👍</div>
                                        <div class="fullscreen-metric-value">{likes_str}</div>
                                        <div style="font-size: 1.2rem; color: #64748b; font-weight: 600;">Lượt thích</div>
                                    </div>
                                    <div class="fullscreen-metric-card">
                                        <div class="fullscreen-metric-icon">💬</div>
                                        <div class="fullscreen-metric-value">{comments_str}</div>
                                        <div style="font-size: 1.2rem; color: #64748b; font-weight: 600;">Bình luận</div>
                                    </div>
                                    <div class="fullscreen-metric-card">
                                        <div class="fullscreen-metric-icon">🔄</div>
                                        <div class="fullscreen-metric-value">{shares_str}</div>
                                        <div style="font-size: 1.2rem; color: #64748b; font-weight: 600;">Chia sẻ</div>
                                    </div>
                                    <div class="fullscreen-metric-card">
                                        <div class="fullscreen-metric-icon">🔥</div>
                                        <div class="fullscreen-metric-value">{score_str}</div>
                                        <div style="font-size: 1.2rem; color: #64748b; font-weight: 600;">Điểm tương tác</div>
                                    </div>
                                </div>
                            </div>

                            <div class="fullscreen-info-card">
                                <h3>📝 Mô tả sản phẩm</h3>
                                <div style="background: #f9fafb; padding: 30px; border-radius: 15px; border: 2px solid #e5e7eb; font-size: 1.3rem; line-height: 1.8; color: #374151; max-height: 300px; overflow-y: auto;">
                                    {description}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <script>
            function closeModal() {{
                // Sử dụng postMessage để giao tiếp với Streamlit
                window.parent.postMessage({{
                    type: 'streamlit:closeModal'
                }}, '*');

                // Fallback: thử trigger click event
                const buttons = window.parent.document.querySelectorAll('[data-testid="stButton"] button');
                const closeBtn = Array.from(buttons).find(btn => btn.textContent.includes('Đóng modal fallback'));
                if (closeBtn) {{
                    closeBtn.click();
                }}
            }}

            // Xử lý phím ESC
            document.addEventListener('keydown', function(event) {{
                if (event.key === 'Escape') {{
                    closeModal();
                }}
            }});
            </script>
            """

            st.markdown(modal_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Lỗi hiển thị modal: {e}")
            st.session_state.selected_product = None

        # Nút ẩn để đóng modal (fallback)
        if st.button("❌ Đóng modal fallback", key="close_modal_fallback"):
            st.session_state.selected_product = None
            st.rerun()


# ============================================Filter sản phẩm theo danh mục==================================================================
# Hàm tiện ích để thay thế hàm gốc
def get_filtered_and_sorted_products(df, field_name, field_value, limit=20):
    """
    Hàm helper để lọc và sắp xếp sản phẩm
    Thay thế bằng logic thực tế của bạn
    """
    try:
        # Lọc theo field
        filtered_df = df[df[field_name] == field_value].copy() if field_name in df.columns else df.copy()

        # Sắp xếp theo engagement_score nếu có
        if 'engagement_score' in filtered_df.columns:
            filtered_df = filtered_df.sort_values('engagement_score', ascending=False)

        # Lấy top products
        top_products = filtered_df.head(limit)

        # Stats
        stats = {
            'showing_top': len(top_products),
            'total_found': len(filtered_df),
            'has_more': len(filtered_df) > limit
        }

        return top_products, stats
    except Exception as e:
        # Fallback
        return df.head(limit), {'showing_top': min(limit, len(df)), 'total_found': len(df), 'has_more': len(df) > limit}


@st.cache_data(ttl=1800)
def get_metadata_fields():
    """Lấy danh sách các metadata fields cần phân tích"""
    return [
        "image_recipient", "target_audience", "usage_purpose", "occasion",
        "niche_theme", "sentiment_tone", "message_type", "personalization_type",
        "product_type", "placement_display_context", "design_style",
        "color_aesthetic", "main_subject", "text"
    ]


def analyze_single_field_compact(df, field_name):
    """Phân tích một field metadata với biểu đồ có thể click"""
    with st.container():
        st.markdown(f'<div class="metadata-item">', unsafe_allow_html=True)
        st.subheader(f"📈 {field_name.replace('_', ' ').title()}")

        # Get analysis data
        result_df, all_values = analyze_metadata_field(df, field_name)

        if result_df.empty:
            st.info(f"Không có dữ liệu cho {field_name}")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # Statistics in a row
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("Tổng features", len(all_values))
        with stat_col2:
            st.metric("Unique", len(result_df))
        with stat_col3:
            if len(result_df) > 0:
                top_count = result_df.iloc[0]['Count']
                st.metric("Top count", top_count)

        # Create clickable bar chart
        if len(result_df) > 0:
            st.markdown("💡 **Click vào thanh bar để chuyển sang View Products**")

            # Create the clickable chart
            top_10 = result_df.head(10)

            fig = px.bar(
                top_10,
                x='Count',
                y=field_name,
                orientation='h',
                title=f"Click vào thanh bar để xem top 10 sản phẩm",
                color='Count',
                color_continuous_scale='viridis',
                height=300
            )

            fig.update_layout(
                showlegend=False,
                margin=dict(l=0, r=0, t=40, b=0)
            )

            # Display chart and handle clicks
            event = st.plotly_chart(fig, use_container_width=True, key=f"chart_{field_name}", on_select="rerun")

            # Handle click events to automatically switch to view products and fill data
            if event and 'selection' in event and 'points' in event['selection']:
                if len(event['selection']['points']) > 0:
                    clicked_point = event['selection']['points'][0]

                    if 'point_index' in clicked_point:
                        point_index = clicked_point['point_index']
                        if point_index < len(top_10):
                            clicked_value = top_10.iloc[point_index][field_name]
                    elif 'y' in clicked_point:
                        clicked_value = clicked_point['y']
                    else:
                        clicked_value = None

                    if clicked_value:
                        # Set session state for automatic switch and fill
                        st.session_state.selected_metadata_field = field_name
                        st.session_state.selected_metadata_value = clicked_value
                        st.session_state.current_view = "view_products"
                        st.session_state.auto_fill_triggered = True
                        st.session_state.chart_clicked = True

                        # CRITICAL: Force radio button to update its displayed value
                        st.session_state.view_radio_index = 1  # Index for "View Products"

                        st.success(f"✅ Đã chọn: {field_name} = '{clicked_value}'. Chuyển sang View Products...")
                        st.rerun()

            # Compact data table (top 10)
            with st.expander("📋 Xem dữ liệu chi tiết"):
                st.dataframe(result_df, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)


def create_metadata_analysis_tab(df):
    """Tạo tab hiển thị toàn bộ metadata cùng lúc - Overview tab"""
    # Get filtered data from sidebar
    filtered_df = st.session_state.get('filtered_df', df)

    if len(filtered_df) == 0:
        st.warning("⚠️ Không có dữ liệu để hiển thị! Vui lòng điều chỉnh bộ lọc trong sidebar.")
        return

    metadata_fields = get_metadata_fields()

    # Custom CSS for better layout
    st.markdown("""
    <style>
    .metadata-item {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        background-color: #f9f9f9;
    }
    .metadata-grid {
        display: grid;
        gap: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Display all metadata fields in a grid layout
    st.markdown('<div class="metadata-grid">', unsafe_allow_html=True)

    # Create grid with 2 columns
    for i in range(0, len(metadata_fields), 2):
        col1, col2 = st.columns(2)

        # First column
        with col1:
            if i < len(metadata_fields):
                analyze_single_field_compact(filtered_df, metadata_fields[i])

        # Second column
        with col2:
            if i + 1 < len(metadata_fields):
                analyze_single_field_compact(filtered_df, metadata_fields[i + 1])

    st.markdown('</div>', unsafe_allow_html=True)


def show_overview_content(df):
    """Show overview tab content"""
    st.header("📊 Phân tích Metadata tổng quan")
    st.markdown("Nhấp vào các thanh biểu đồ để xem chi tiết sản phẩm trong tab **View Products**")
    create_metadata_analysis_tab(df)


def show_view_products_content(df):
    """Show view products tab content"""
    st.header("👁️ Xem chi tiết sản phẩm")

    # Check if we came from a chart click and show notification
    if st.session_state.get('auto_fill_triggered', False):
        st.success(
            f"🎯 Đã tự động chọn từ biểu đồ: **{st.session_state.selected_metadata_field}** = **{st.session_state.selected_metadata_value}**")
        st.session_state.auto_fill_triggered = False  # Reset flag

    # Manual selection interface
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        metadata_fields = get_metadata_fields()
        field_index = 0
        # Only auto-fill if came from chart click
        if st.session_state.get('selected_metadata_field') in metadata_fields and st.session_state.get('chart_clicked',
                                                                                                       False):
            field_index = metadata_fields.index(st.session_state.selected_metadata_field)

        selected_field = st.selectbox(
            "Chọn metadata field:",
            metadata_fields,
            index=field_index,
            key="field_selector"
        )

    with col2:
        # Get unique values for selected field
        filtered_df = st.session_state.get('filtered_df', df)
        if selected_field in filtered_df.columns:
            _, unique_values = analyze_metadata_field(filtered_df, selected_field)
            if unique_values:
                value_index = 0
                # Only auto-fill if came from chart click and field matches
                if (st.session_state.get('selected_metadata_value') in unique_values and
                        st.session_state.get('chart_clicked', False) and
                        selected_field == st.session_state.get('selected_metadata_field')):
                    value_index = unique_values.index(st.session_state.selected_metadata_value)

                selected_value = st.selectbox(
                    "Chọn giá trị:",
                    unique_values,
                    index=value_index,
                    key="value_selector"
                )
            else:
                st.warning(f"Không có dữ liệu cho {selected_field}")
                selected_value = None
        else:
            st.warning(f"Field {selected_field} không tồn tại")
            selected_value = None

    with col3:
        if st.button("🔍 Xem sản phẩm", type="primary"):
            if selected_field and selected_value:
                st.session_state.selected_metadata_field = selected_field
                st.session_state.selected_metadata_value = selected_value
                st.session_state.chart_clicked = False  # Reset chart click flag
                # Reset products limit when selecting new criteria
                st.session_state.products_limit = 10
                st.session_state.expanded_products = set()
                st.rerun()

    # Show products if selection is made
    if selected_field and selected_value:
        st.markdown("---")
        show_sample_products(filtered_df, selected_field, selected_value)
    else:
        st.info("👆 Chọn metadata field và giá trị ở trên để xem sản phẩm tương ứng")


def create_metadata_tab_interface(df):
    """Tạo interface cho metadata tab với navigation có thể điều khiển"""

    # Initialize session state
    if 'current_view' not in st.session_state:
        st.session_state.current_view = "overview"

    if 'view_radio_index' not in st.session_state:
        st.session_state.view_radio_index = 0

    if 'selected_metadata_field' not in st.session_state:
        st.session_state.selected_metadata_field = None

    if 'selected_metadata_value' not in st.session_state:
        st.session_state.selected_metadata_value = None

    if 'auto_fill_triggered' not in st.session_state:
        st.session_state.auto_fill_triggered = False

    if 'chart_clicked' not in st.session_state:
        st.session_state.chart_clicked = False

    # Create custom tab-like navigation using radio buttons
    st.markdown("### 📋 Navigation")

    # Custom CSS for tab-like appearance
    st.markdown("""
    <style>
    .stRadio > div {
        flex-direction: row;
        gap: 20px;
    }
    .stRadio > div > label {
        background-color: #f0f0f0;
        padding: 10px 20px;
        border-radius: 20px;
        border: 2px solid transparent;
        cursor: pointer;
        transition: all 0.3s;
    }
    .stRadio > div > label:hover {
        background-color: #e0e0e0;
    }
    .stRadio > div > label[data-checked="true"] {
        background-color: #ff4b4b;
        color: white;
        border-color: #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

    # Navigation selection - use session state to determine current index
    view_options = ["📊 Metadata Overview", "👁️ View Products"]

    # Update radio index based on current_view
    if st.session_state.current_view == "overview":
        st.session_state.view_radio_index = 0
    else:
        st.session_state.view_radio_index = 1

    selected_view = st.radio(
        "Chọn view:",
        view_options,
        index=st.session_state.view_radio_index,
        horizontal=True,
        key="view_selector"
    )

    # Handle manual tab switching
    if selected_view == "📊 Metadata Overview" and st.session_state.current_view != "overview":
        st.session_state.current_view = "overview"
        st.session_state.view_radio_index = 0
        st.session_state.chart_clicked = False
        st.rerun()
    elif selected_view == "👁️ View Products" and st.session_state.current_view != "view_products":
        st.session_state.current_view = "view_products"
        st.session_state.view_radio_index = 1
        st.session_state.chart_clicked = False
        st.rerun()

    st.markdown("---")

    # Show content based on current view
    if st.session_state.current_view == "overview":
        show_overview_content(df)
    else:
        show_view_products_content(df)

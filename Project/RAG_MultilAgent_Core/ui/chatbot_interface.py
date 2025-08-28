import streamlit as st
import asyncio
import pandas as pd
import json
import base64
import requests
import zipfile
from io import BytesIO
import xlsxwriter
from PIL import Image
from collections import Counter
from data.data_processor import safe_int_convert, parse_engagement_string
import time
from datetime import datetime
import uuid
from ui.chatbot_render_agents import (
    render_chat_messages_with_feedback,
    route_message_to_renderer
)
# Import chatbot - đảm bảo file này có trong cùng thư mục
try:
    from chatbot import RnDChatbot

    CHATBOT_AVAILABLE = True
except ImportError:
    CHATBOT_AVAILABLE = False

from ui.feedback import (
    FeedbackSystem,
    initialize_feedback_session,
    render_feedback_for_product,
    show_feedback_analytics
)
...

# ==================== STATE MANAGEMENT ====================
def initialize_chatbot_state():
    """Khởi tạo state cho chatbot interface"""
    if 'chatbot_products_cache' not in st.session_state:
        st.session_state.chatbot_products_cache = {}

    if 'chatbot_last_search_id' not in st.session_state:
        st.session_state.chatbot_last_search_id = None

    if 'chatbot_download_queue' not in st.session_state:
        st.session_state.chatbot_download_queue = {}

    if 'prevent_rerun' not in st.session_state:
        st.session_state.prevent_rerun = False

def cache_products_data(search_id, products):
    """Cache products data để tránh mất thông tin"""
    st.session_state.chatbot_products_cache[search_id] = {
        'products': products,
        'timestamp': datetime.now(),
        'cached_at': time.time()
    }
    st.session_state.chatbot_last_search_id = search_id


def get_cached_products(search_id=None):
    """Lấy cached products data"""
    if search_id is None:
        search_id = st.session_state.chatbot_last_search_id

    if search_id and search_id in st.session_state.chatbot_products_cache:
        return st.session_state.chatbot_products_cache[search_id]['products']
    return None


# ==================== DOWNLOAD FUNCTIONS ====================

@st.cache_data
def download_image_from_url(url):
    """Download image from URL and return as bytes - CACHED"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        return None


@st.cache_data
def create_excel_metadata(product_data, rank):
    """Create Excel metadata file - CACHED"""
    try:
        # Create in-memory Excel file
        excel_buffer = BytesIO()

        # Create workbook and worksheet
        workbook = xlsxwriter.Workbook(excel_buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet('Product_Metadata')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })

        data_format = workbook.add_format({
            'font_size': 11,
            'border': 1,
            'text_wrap': True
        })

        # Headers
        headers = ['Field', 'Value']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Product data
        engagement_data = product_data.get("engagement", {})
        if isinstance(engagement_data, dict):
            likes = safe_int_convert(engagement_data.get("like", 0))
            comments = safe_int_convert(engagement_data.get("comment", 0))
            shares = safe_int_convert(engagement_data.get("share", 0))
        else:
            likes = comments = shares = 0

        engagement_score = likes + comments * 5 + shares * 10

        # Data rows
        data_rows = [
            ['Rank', rank],
            ['Store Name', product_data.get('store', f'Store {rank}')],
            ['Image URL', product_data.get('image_url', '')],
            ['Description', product_data.get('description', 'Không có mô tả')],
            ['Platform', product_data.get('platform', 'Unknown')],
            ['Date', product_data.get('date', 'N/A')],
            ['Similarity', product_data.get('similarity', '')],
            ['Likes', f"{likes:,}"],
            ['Comments', f"{comments:,}"],
            ['Shares', f"{shares:,}"],
            ['Engagement Score', f"{engagement_score:,}"],
            ['Download Timestamp', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]

        # Write data
        for row_idx, (field, value) in enumerate(data_rows, 1):
            worksheet.write(row_idx, 0, field, data_format)
            worksheet.write(row_idx, 1, str(value), data_format)

        # Auto-adjust column widths
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 50)

        # Close workbook
        workbook.close()
        excel_buffer.seek(0)

        return excel_buffer.getvalue()

    except Exception as e:
        st.error(f"❌ Lỗi tạo Excel metadata: {str(e)}")
        return None


def create_download_package_cached(product_data, rank, search_id):
    """Create ZIP package với caching để tránh tạo lại"""
    cache_key = f"{search_id}_{rank}_{hash(str(product_data))}"

    # Kiểm tra cache trong session state
    if cache_key in st.session_state.chatbot_download_queue:
        cached_data = st.session_state.chatbot_download_queue[cache_key]
        if time.time() - cached_data['created_at'] < 3600:  # Cache 1 tiếng
            return cached_data['zip_data'], cached_data['filename']

    # Tạo mới nếu chưa có cache
    try:
        # Create in-memory ZIP file
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Clean store name for filename
            store_name_clean = product_data.get('store', f'Store_{rank}').replace(' ', '_').replace('/', '_').replace(
                '\\', '_')
            base_filename = f"product_{rank}_{store_name_clean}"

            # Add Excel metadata
            excel_data = create_excel_metadata(product_data, rank)
            if excel_data:
                zip_file.writestr(f"{base_filename}_metadata.xlsx", excel_data)

            # Try to add image if URL exists
            image_url = product_data.get('image_url', '')
            if image_url and image_url.strip() and image_url != 'N/A':
                try:
                    image_data = download_image_from_url(image_url)
                    if image_data:
                        # Determine image extension from URL or default to jpg
                        if any(ext in image_url.lower() for ext in ['.png', '.jpeg', '.jpg', '.gif', '.webp']):
                            for ext in ['.png', '.jpeg', '.jpg', '.gif', '.webp']:
                                if ext in image_url.lower():
                                    image_ext = ext
                                    break
                        else:
                            image_ext = '.jpg'

                        zip_file.writestr(f"{base_filename}_image{image_ext}", image_data)
                    else:
                        # Add a text file explaining image download failed
                        error_msg = f"Failed to download image from: {image_url}\nTimestamp: {pd.Timestamp.now()}"
                        zip_file.writestr(f"{base_filename}_image_error.txt", error_msg)

                except Exception as e:
                    # Add error log to ZIP
                    error_msg = f"Image download error: {str(e)}\nURL: {image_url}\nTimestamp: {pd.Timestamp.now()}"
                    zip_file.writestr(f"{base_filename}_image_error.txt", error_msg)
            else:
                # Add note about missing image
                note_msg = f"No image URL available for this product\nTimestamp: {pd.Timestamp.now()}"
                zip_file.writestr(f"{base_filename}_no_image.txt", note_msg)

        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()
        filename = f"{base_filename}_package.zip"

        # Cache result
        st.session_state.chatbot_download_queue[cache_key] = {
            'zip_data': zip_data,
            'filename': filename,
            'created_at': time.time()
        }

        return zip_data, filename

    except Exception as e:
        st.error(f"❌ Lỗi tạo package download: {str(e)}")
        return None, None


# ==================== NEW: DOWNLOAD ALL ZIP FUNCTION ====================

@st.cache_data
def create_all_products_zip_package(products, search_id):
    """Create master ZIP package with 1 images folder + 1 Excel file - CACHED"""
    try:
        # Create in-memory ZIP file
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as master_zip:

            # Create master Excel file with all products data
            master_excel_data = create_master_excel_file(products, search_id)
            if master_excel_data:
                master_zip.writestr(f"Products_Data_{search_id}.xlsx", master_excel_data)

            # Download and add all images to Images folder
            for rank, product in enumerate(products[:12], 1):  # Limit to 12 products
                try:
                    image_url = product.get('image_url', '')
                    store_name = clean_store_name(product.get('store', f'Store_{rank}'))

                    if image_url and image_url.strip() and image_url != 'N/A':
                        try:
                            image_data = download_image_from_url(image_url)
                            if image_data:
                                # Determine image extension
                                image_ext = '.jpg'  # Default
                                for ext in ['.png', '.jpeg', '.jpg', '.gif', '.webp']:
                                    if ext in image_url.lower():
                                        image_ext = ext
                                        break

                                # Save to Images folder with rank and store name
                                image_filename = f"Images/{rank:02d}_{store_name}{image_ext}"
                                master_zip.writestr(image_filename, image_data)

                        except Exception as e:
                            # Create a text file for failed download
                            error_msg = f"Failed to download image for Product #{rank}\nStore: {product.get('store', 'Unknown')}\nURL: {image_url}\nError: {str(e)}\nTimestamp: {pd.Timestamp.now()}"
                            master_zip.writestr(f"Images/{rank:02d}_{store_name}_ERROR.txt", error_msg)
                    else:
                        # Create placeholder for missing image
                        placeholder_msg = f"No image available for Product #{rank}\nStore: {product.get('store', 'Unknown')}\nTimestamp: {pd.Timestamp.now()}"
                        master_zip.writestr(f"Images/{rank:02d}_{store_name}_NO_IMAGE.txt", placeholder_msg)

                except Exception as e:
                    error_msg = f"Processing error for Product #{rank}\nError: {str(e)}\nTimestamp: {pd.Timestamp.now()}"
                    master_zip.writestr(f"Images/{rank:02d}_PROCESSING_ERROR.txt", error_msg)

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    except Exception as e:
        st.error(f"❌ Lỗi tạo master ZIP package: {str(e)}")
        return None


def create_master_excel_file(products, search_id):
    """Create single Excel file with all products data including URLs and metadata"""
    try:
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            # Prepare comprehensive data
            products_data = []

            for rank, product in enumerate(products, 1):
                # Parse engagement data
                engagement_data = product.get("engagement", {})
                if isinstance(engagement_data, dict):
                    likes = safe_int_convert(engagement_data.get("like", 0))
                    comments = safe_int_convert(engagement_data.get("comment", 0))
                    shares = safe_int_convert(engagement_data.get("share", 0))
                else:
                    likes = comments = shares = 0

                engagement_score = likes + comments * 5 + shares * 10
                store_name = clean_store_name(product.get('store', f'Store_{rank}'))

                # Determine image filename in ZIP
                image_url = product.get('image_url', '')
                image_filename = ""
                if image_url and image_url.strip() and image_url != 'N/A':
                    # Determine extension
                    image_ext = '.jpg'  # Default
                    for ext in ['.png', '.jpeg', '.jpg', '.gif', '.webp']:
                        if ext in image_url.lower():
                            image_ext = ext
                            break
                    image_filename = f"Images/{rank:02d}_{store_name}{image_ext}"
                else:
                    image_filename = f"Images/{rank:02d}_{store_name}_NO_IMAGE.txt"

                products_data.append({
                    'Rank': rank,
                    'Store_Name': product.get('store', f'Store {rank}'),
                    'Image_URL': image_url,
                    'Image_File_In_ZIP': image_filename,
                    'Description': product.get('description', 'Không có mô tả'),
                    'Platform': product.get('platform', 'Unknown'),
                    'Date': product.get('date', 'N/A'),
                    'Similarity_Score': product.get('similarity', ''),
                    'Likes': likes,
                    'Comments': comments,
                    'Shares': shares,
                    'Engagement_Score': engagement_score,
                    'Download_Timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                })

            # Create DataFrame
            df = pd.DataFrame(products_data)

            # Write to Excel with formatting
            df.to_excel(writer, sheet_name='Products_Data', index=False)

            # Get workbook and worksheet for formatting
            workbook = writer.book
            worksheet = writer.sheets['Products_Data']

            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1,
                'text_wrap': True
            })

            url_format = workbook.add_format({
                'font_color': '#0000EE',
                'underline': True
            })

            number_format = workbook.add_format({
                'num_format': '#,##0'
            })

            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Format URL columns
            url_col = df.columns.get_loc('Image_URL')
            for row in range(1, len(df) + 1):
                if df.iloc[row - 1]['Image_URL']:  # If URL exists
                    worksheet.write_url(row, url_col, df.iloc[row - 1]['Image_URL'], url_format)

            # Format number columns
            number_cols = ['Likes', 'Comments', 'Shares', 'Engagement_Score']
            for col_name in number_cols:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name)
                    for row in range(1, len(df) + 1):
                        worksheet.write(row, col_idx, df.iloc[row - 1][col_name], number_format)

            # Auto-adjust column widths
            for col_num, col_name in enumerate(df.columns):
                if col_name == 'Description':
                    worksheet.set_column(col_num, col_num, 50)  # Wider for description
                elif col_name == 'Image_URL':
                    worksheet.set_column(col_num, col_num, 40)  # Wider for URL
                elif col_name == 'Store_Name':
                    worksheet.set_column(col_num, col_num, 25)  # Medium for store name
                else:
                    max_len = max(
                        df[col_name].astype(str).map(len).max() if len(df) > 0 else 10,
                        len(str(col_name))
                    ) + 2
                    worksheet.set_column(col_num, col_num, min(max_len, 30))

            # Add summary sheet
            create_summary_sheet(writer, df, search_id)

        excel_buffer.seek(0)
        return excel_buffer.getvalue()

    except Exception as e:
        st.error(f"❌ Lỗi tạo master Excel file: {str(e)}")
        return None


def create_summary_sheet(writer, df, search_id):
    """Add summary sheet to Excel file"""
    try:
        # Create summary data
        summary_data = [
            ['Search ID', search_id],
            ['Total Products', len(df)],
            ['Generated Time', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['', ''],
            ['ENGAGEMENT STATISTICS', ''],
            ['Total Likes', f"{df['Likes'].sum():,}"],
            ['Total Comments', f"{df['Comments'].sum():,}"],
            ['Total Shares', f"{df['Shares'].sum():,}"],
            ['Total Engagement Score', f"{df['Engagement_Score'].sum():,}"],
            ['Average Engagement Score', f"{df['Engagement_Score'].mean():.1f}"],
            ['', ''],
            ['PLATFORM DISTRIBUTION', ''],
        ]

        # Add platform counts
        platform_counts = df['Platform'].value_counts()
        for platform, count in platform_counts.items():
            summary_data.append([f"{platform}", f"{count} products"])

        # Add top performers
        summary_data.extend([
            ['', ''],
            ['TOP 5 PERFORMERS', ''],
        ])

        top_performers = df.nlargest(5, 'Engagement_Score')[['Rank', 'Store_Name', 'Engagement_Score']]
        for _, row in top_performers.iterrows():
            summary_data.append([f"#{int(row['Rank'])} {row['Store_Name']}", f"{row['Engagement_Score']:,}"])

        # Create summary DataFrame
        summary_df = pd.DataFrame(summary_data, columns=['Metric', 'Value'])

        # Write to Excel
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Format summary sheet
        workbook = writer.book
        summary_worksheet = writer.sheets['Summary']

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#2196F3',
            'font_color': 'white',
            'border': 1
        })

        section_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E3F2FD',
            'border': 1
        })

        # Apply formatting
        for col_num, value in enumerate(summary_df.columns.values):
            summary_worksheet.write(0, col_num, value, header_format)

        # Highlight section headers
        section_headers = ['ENGAGEMENT STATISTICS', 'PLATFORM DISTRIBUTION', 'TOP 5 PERFORMERS']
        for row_idx, (metric, value) in enumerate(summary_data, 1):
            if metric in section_headers:
                summary_worksheet.write(row_idx, 0, metric, section_format)
                summary_worksheet.write(row_idx, 1, value, section_format)

        # Auto-adjust columns
        summary_worksheet.set_column('A:A', 25)
        summary_worksheet.set_column('B:B', 20)

    except Exception as e:
        st.error(f"❌ Lỗi tạo summary sheet: {str(e)}")


def create_summary_excel(products, search_id):
    """Create summary Excel file for all products"""
    try:
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            # Prepare data for DataFrame
            summary_data = []

            for rank, product in enumerate(products, 1):
                engagement_data = product.get("engagement", {})
                if isinstance(engagement_data, dict):
                    likes = safe_int_convert(engagement_data.get("like", 0))
                    comments = safe_int_convert(engagement_data.get("comment", 0))
                    shares = safe_int_convert(engagement_data.get("share", 0))
                else:
                    likes = comments = shares = 0

                engagement_score = likes + comments * 5 + shares * 10

                summary_data.append({
                    'Rank': rank,
                    'Store Name': product.get('store', f'Store {rank}'),
                    'Platform': product.get('platform', 'Unknown'),
                    'Date': product.get('date', 'N/A'),
                    'Similarity': product.get('similarity', ''),
                    'Likes': likes,
                    'Comments': comments,
                    'Shares': shares,
                    'Engagement Score': engagement_score,
                    'Image URL': product.get('image_url', ''),
                    'Description Preview': product.get('description', '')
                })

            # Create DataFrame and save to Excel
            df = pd.DataFrame(summary_data)
            df.to_excel(writer, sheet_name='All Products Summary', index=False)

            # Get workbook and worksheet for formatting
            workbook = writer.book
            worksheet = writer.sheets['All Products Summary']

            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4CAF50',
                'font_color': 'white',
                'border': 1
            })

            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Auto-adjust column widths
            for col_num, col_name in enumerate(df.columns):
                max_len = max(df[col_name].astype(str).map(len).max(), len(col_name)) + 2
                worksheet.set_column(col_num, col_num, min(max_len, 50))

        excel_buffer.seek(0)
        return excel_buffer.getvalue()

    except Exception as e:
        st.error(f"❌ Lỗi tạo summary Excel: {str(e)}")
        return None


def clean_store_name(store_name):
    """Clean store name for use in filenames"""
    if not store_name:
        return "Unknown_Store"

    # Remove/replace problematic characters
    cleaned = store_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    cleaned = cleaned.replace('<', '').replace('>', '').replace(':', '_')
    cleaned = cleaned.replace('"', '').replace('|', '_').replace('?', '').replace('*', '')

    # Limit length
    if len(cleaned) > 30:
        cleaned = cleaned[:30]

    return cleaned




# Initialize chatbot
@st.cache_resource
def initialize_chatbot():
    """Initialize chatbot with caching"""
    if CHATBOT_AVAILABLE:
        try:
            return RnDChatbot()
        except Exception as e:
            st.error(f"❌ Lỗi khởi tạo chatbot: {e}")
            return None
    return None


# ==================== MAIN CHATBOT INTERFACE ====================

def create_chatbot_interface():
    """Tạo giao diện chatbot với NO-RELOAD download system"""

    # Initialize state
    initialize_chatbot_state()

    if not CHATBOT_AVAILABLE:
        st.error("❌ Chatbot không khả dụng. Vui lòng kiểm tra import.")
        return

    # Initialize chatbot
    if not st.session_state.chatbot_initialized:
        with st.spinner("🔄 Đang khởi tạo chatbot..."):
            st.session_state.chatbot = initialize_chatbot()
            if st.session_state.chatbot:
                st.session_state.chatbot_initialized = True
                st.success("✅ Chatbot đã sẵn sàng!")
            else:
                st.error("❌ Không thể khởi tạo chatbot")
                return

    # Features info section
    st.markdown("""
    <div class="features-info">
        <div style="text-align: center; margin-bottom: 1rem;">
            <h3 style="margin: 0; font-size: 18px;">🎯 RnD Assistant Features</h3>
        </div>
        <div class="features-grid">
            <div class="feature-item">📊 Benchmark Analysis</div>
            <div class="feature-item">🕳️ Market Gap Discovery</div>
            <div class="feature-item">✅ Idea Verification</div>
            <div class="feature-item">📈 Audience Volume</div>
            <div class="feature-item">🔍 Smart Image Search</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Chat messages container với NO RELOAD - SỬ DỤNG RENDERER MỚI
    render_chat_messages_with_feedback()

    # Chat input section
    handle_chat_input()

    # Control buttons
    render_control_buttons_with_feedback()




def render_analysis_feedback(search_id, analysis_type, title):
    """Render feedback for analysis-only responses (no products)"""
    st.markdown(f"### 📝 Rate {title}")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("👍 Helpful", key=f"helpful_{search_id}"):
            record_analysis_feedback(search_id, analysis_type, "helpful")
            st.success("Thanks for feedback!")

    with col2:
        if st.button("👎 Not Helpful", key=f"not_helpful_{search_id}"):
            record_analysis_feedback(search_id, analysis_type, "not_helpful")
            st.info("We'll improve!")

    with col3:
        if st.button("🤔 Needs Detail", key=f"needs_detail_{search_id}"):
            record_analysis_feedback(search_id, analysis_type, "needs_detail")
            st.info("Noted!")


def record_product_feedback(product_id, feedback_type, product_data):
    """Record feedback for products"""
    if 'product_feedback' not in st.session_state:
        st.session_state.product_feedback = {}

    st.session_state.product_feedback[product_id] = {
        'type': feedback_type,
        'timestamp': datetime.now(),
        'product': product_data
    }


def record_analysis_feedback(search_id, analysis_type, feedback_type):
    """Record feedback for analysis responses"""
    if 'analysis_feedback' not in st.session_state:
        st.session_state.analysis_feedback = {}

    st.session_state.analysis_feedback[search_id] = {
        'analysis_type': analysis_type,
        'feedback': feedback_type,
        'timestamp': datetime.now()
    }


def export_feedback_summary():
    """Export comprehensive feedback summary"""
    report = f"=== RnD ASSISTANT FEEDBACK REPORT ===\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    # Product Feedback
    product_feedback = st.session_state.get('product_feedback', {})
    if product_feedback:
        report += f"PRODUCT FEEDBACK ({len(product_feedback)} items):\n"
        for pid, data in product_feedback.items():
            report += f"- {data['type'].upper()}: {data['product'].get('store', 'Unknown')} [{data['timestamp']}]\n"
        report += "\n"

    # Analysis Feedback
    analysis_feedback = st.session_state.get('analysis_feedback', {})
    if analysis_feedback:
        report += f"ANALYSIS FEEDBACK ({len(analysis_feedback)} items):\n"
        for sid, data in analysis_feedback.items():
            report += f"- {data['analysis_type']}: {data['feedback']} [{data['timestamp']}]\n"
        report += "\n"

    # Smart Search Feedback (existing)
    feedback_data = st.session_state.get('feedback_data', {})
    if feedback_data:
        report += f"SMART SEARCH FEEDBACK ({len(feedback_data)} items):\n"
        for search_id, search_data in feedback_data.items():
            for product_id, product_feedback in search_data.get('products', {}).items():
                report += f"- {product_feedback.get('rating', 'N/A')}: {product_feedback.get('store', 'Unknown')}\n"

    return report


def handle_chat_input():
    """Handle chat input - OPTIMIZED VERSION"""

    # Layout: text input + upload button + send button
    col1, col2, col3 = st.columns([8, 1, 1])

    with col1:
        user_input = st.text_input(
            "Nhập câu hỏi của bạn...",
            placeholder="VD: Tìm hình ảnh keychain Star Wars cho Dad, Phân tích benchmark sản phẩm này...",
            key=f"chat_input_{len(st.session_state.chat_history)}",
            label_visibility="collapsed"
        )

    with col2:
        # Upload button với dấu +
        uploaded_file = st.file_uploader(
            "➕",
            type=['png', 'jpg', 'jpeg', 'gif', 'bmp'],
            key=f"image_upload_{len(st.session_state.chat_history)}",
            help="Upload hình ảnh",
            label_visibility="collapsed"
        )

    with col3:
        send_button = st.button(
            "📤",
            key=f"send_button_{len(st.session_state.chat_history)}",
            use_container_width=True,
            type="primary"
        )

    # Process input - NO UPLOAD YET
    final_input = user_input
    has_image = uploaded_file is not None

    if has_image:
        # Chỉ hiện preview, không upload ngay
        st.image(uploaded_file, width=100)
        st.info("ℹ️ Ảnh sẽ được upload khi gửi tin nhắn")

    # Send message - UPLOAD chỉ khi click send
    if send_button and (final_input.strip() or has_image):
        if has_image:
            # Upload ảnh chỉ khi thực sự cần
            with st.spinner("📤 Đang upload ảnh..."):
                image_url = upload_to_get_url_cached(uploaded_file)

                if image_url:
                    if final_input.strip():
                        final_input = f"{final_input.strip()} {image_url}"
                    else:
                        final_input = image_url
                else:
                    st.error("❌ Upload thất bại, gửi tin nhắn không có ảnh")
                    if not final_input.strip():
                        return  # Không có text và upload thất bại

        process_chat_message(final_input)


@st.cache_data(ttl=1800)  # Cache 30 phút
def upload_to_get_url_cached(uploaded_file):
    """Upload với cache để tránh upload lại cùng 1 file"""
    try:
        # Tạo cache key từ file content
        file_hash = hash(uploaded_file.getvalue())
        cache_key = f"upload_{file_hash}_{uploaded_file.size}"

        # Kiểm tra cache trong session state
        if 'image_upload_cache' not in st.session_state:
            st.session_state.image_upload_cache = {}

        if cache_key in st.session_state.image_upload_cache:
            cached_data = st.session_state.image_upload_cache[cache_key]
            if time.time() - cached_data['upload_time'] < 1800:  # 30 phút
                return cached_data['url']

        # Upload mới
        url = upload_to_imgbb_optimized(uploaded_file)

        if url:
            # Cache result
            st.session_state.image_upload_cache[cache_key] = {
                'url': url,
                'upload_time': time.time()
            }

            # Giới hạn cache size (chỉ giữ 20 ảnh gần nhất)
            if len(st.session_state.image_upload_cache) > 20:
                oldest_key = min(st.session_state.image_upload_cache.keys(),
                                 key=lambda k: st.session_state.image_upload_cache[k]['upload_time'])
                del st.session_state.image_upload_cache[oldest_key]

        return url

    except Exception as e:
        st.error(f"❌ Upload error: {e}")
        return None


def upload_to_imgbb_optimized(uploaded_file):
    """Upload to imgbb - OPTIMIZED VERSION"""
    try:
        import base64

        # Tối ưu image trước khi upload
        optimized_file = optimize_image_for_upload(uploaded_file)

        # Convert to base64
        image_data = base64.b64encode(optimized_file).decode()

        # API key (thay bằng key thật)
        api_key = "0c95a9a8d404c40718d653f3852e7bad"

        payload = {
            'key': api_key,
            'image': image_data
        }

        # Reduced timeout cho faster response
        response = requests.post('https://api.imgbb.com/1/upload',
                                 data=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['data']['url']

        return None

    except Exception as e:
        print(f"ImgBB upload error: {e}")
        return None


def optimize_image_for_upload(uploaded_file):
    """Tối ưu ảnh để upload nhanh hơn"""
    try:
        from PIL import Image
        import io

        # Mở ảnh
        img = Image.open(uploaded_file)

        # Resize nếu quá lớn (max 1024px)
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert sang RGB nếu cần
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background

        # Save với chất lượng tối ưu
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)

        return output.getvalue()

    except Exception:
        # Fallback: trả về file gốc
        uploaded_file.seek(0)
        return uploaded_file.getvalue()


def clear_upload_cache():
    """Clear upload cache để tiết kiệm memory"""
    if 'image_upload_cache' in st.session_state:
        current_time = time.time()
        keys_to_remove = []

        for key, data in st.session_state.image_upload_cache.items():
            if current_time - data['upload_time'] > 1800:  # 30 phút
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state.image_upload_cache[key]

def handle_chat_input_with_real_url():
    """Upload image → Get real URL → Process normally"""
    add_simple_upload_style()
    handle_chat_input()

def process_chat_message(user_input):
    """Process chat message without reload"""
    if st.session_state.chatbot and not st.session_state.prevent_rerun:
        st.session_state.prevent_rerun = True

        # Show processing indicator
        with st.spinner("🤖 RnD Assistant đang xử lý..."):
            try:
                response = asyncio.run(st.session_state.chatbot.chat(user_input))

                # Add to chat history
                st.session_state.chat_history.append((user_input, response))

                # Parse và cache products nếu có
                if "Smart Search Results:" in response:
                    search_id = f"search_{len(st.session_state.chat_history) - 1}_{hash(response)}"
                    products = parse_products_from_response(response)
                    if products:
                        cache_products_data(search_id, products)

                st.rerun()

            except Exception as e:
                st.error(f"❌ Lỗi xử lý câu hỏi: {e}")
            finally:
                st.session_state.prevent_rerun = False


def render_control_buttons_with_feedback():
    """Render control buttons với feedback controls"""
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🗑️ Clear Chat", key="clear_chat_with_feedback"):
            st.session_state.chat_history = []
            st.session_state.chatbot_products_cache = {}
            st.session_state.chatbot_download_queue = {}
            st.rerun()

    with col2:
        if st.button("🔄 Restart System", key="restart_system_with_feedback"):
            st.session_state.chatbot_initialized = False
            st.session_state.chatbot = None
            st.session_state.chat_history = []
            st.session_state.chatbot_products_cache = {}
            st.session_state.chatbot_download_queue = {}
            # Don't clear feedback system - preserve feedback data
            st.rerun()

    with col3:
        if st.button("📊 Export Feedback", key="export_feedback_report"):
            try:
                report = export_feedback_summary()

                st.download_button(
                    label="📥 Download Report",
                    data=report,
                    file_name=f"feedback_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    key="download_feedback_report"
                )

                st.success("✅ Feedback report generated!")

            except Exception as e:
                st.error(f"❌ Export error: {str(e)}")


def render_feedback_dashboard():
    """Render comprehensive feedback dashboard"""
    if st.sidebar.checkbox("📈 Feedback Dashboard", key="show_feedback_dashboard"):
        st.sidebar.subheader("📈 Feedback Dashboard")

        try:
            initialize_feedback_session()
            feedback_system = st.session_state.feedback_system

            # Overall stats
            stats = feedback_system.get_feedback_statistics()

            if stats and stats['total_feedback'] > 0:
                # Key metrics in sidebar
                st.sidebar.metric("Total Feedback", stats['total_feedback'])

                col1, col2 = st.sidebar.columns(2)
                with col1:
                    st.metric("👍", stats['thumbs_up'])
                    st.metric("💬", stats['description_comments'])

                with col2:
                    st.metric("👎", stats['thumbs_down'])
                    st.metric("🎯", f"{stats['positive_rate']}%")

                # Recent activity
                if len(stats['feedback_dates']) > 0:
                    recent_feedback = len([d for d in stats['feedback_dates']
                                           if (datetime.now() - datetime.fromisoformat(d)).days <= 1])
                    st.sidebar.metric("📅 Today", recent_feedback)

                # Progress bar for positive rate
                progress_color = "#4CAF50" if stats['positive_rate'] >= 70 else "#FF9800" if stats[
                                                                                                 'positive_rate'] >= 50 else "#f44336"
                st.sidebar.markdown(f"""
                <div style="background: #f0f0f0; border-radius: 10px; padding: 5px;">
                    <div style="background: {progress_color}; height: 10px; border-radius: 5px; 
                               width: {stats['positive_rate']}%;"></div>
                </div>
                <small>Positive Rate: {stats['positive_rate']}%</small>
                """, unsafe_allow_html=True)

                # Export options
                st.sidebar.markdown("---")
                st.sidebar.subheader("📤 Export Options")

                if st.sidebar.button("📊 Export CSV", key="sidebar_export_csv"):
                    try:
                        if os.path.exists(feedback_system.feedback_file):
                            df_feedback = pd.read_csv(feedback_system.feedback_file)
                            csv_data = df_feedback.to_csv(index=False)

                            st.sidebar.download_button(
                                label="📥 Download CSV",
                                data=csv_data,
                                file_name=f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                key="sidebar_download_csv"
                            )
                    except Exception as e:
                        st.sidebar.error(f"Export error: {str(e)}")

                if st.sidebar.button("📝 Export Report", key="sidebar_export_report"):
                    try:
                        report = export_feedback_summary()

                        st.sidebar.download_button(
                            label="📥 Download Report",
                            data=report,
                            file_name=f"feedback_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            key="sidebar_download_report"
                        )
                    except Exception as e:
                        st.sidebar.error(f"Report error: {str(e)}")

            else:
                st.sidebar.info("📝 No feedback data yet")
                st.sidebar.markdown("""
                <small>
                Start testing products and provide feedback to see analytics here!
                </small>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.sidebar.error(f"Dashboard error: {str(e)}")


# ==================== NO-RELOAD PRODUCT RENDERING ====================
def render_download_all_button(products, searchid):
    """Alternative version using session state"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        master_filename = f"RnD_AllProducts{searchid}{timestamp}.zip"

        # Session state key
        download_state_key = f"download_state_{searchid}"

        # Initialize state
        if download_state_key not in st.session_state:
            st.session_state[download_state_key] = {
                'zip_data': None,
                'filename': None,
                'ready': False
            }

        # Main download button
        if st.button(
                "🚀 TẢI TẤT CẢ ZIP",
                key=f"main_download_{searchid}",
                use_container_width=True,
                type="primary",
                help=f"Tạo và tải về {len(products)} sản phẩm"
        ):
            # Generate ZIP on click
            with st.spinner("⚙️ Đang xử lý..."):
                zip_data = create_all_products_zip_package(products, searchid)
                if zip_data:
                    # Store in session state
                    st.session_state[download_state_key] = {
                        'zip_data': zip_data,
                        'filename': master_filename,
                        'ready': True
                    }
                    st.rerun()  # Refresh to show download button

        # Show download button if ready
        if st.session_state[download_state_key]['ready']:
            st.download_button(
                label="📥 TẢI XUỐNG NGAY",
                data=st.session_state[download_state_key]['zip_data'],
                file_name=st.session_state[download_state_key]['filename'],
                mime="application/zip",
                key=f"final_download_{searchid}_{timestamp}",
                use_container_width=True,
                type="secondary"
            )

            st.success(f"✅ Package sẵn sàng: {len(products)} sản phẩm")

            # Reset button to create new package
            if st.button("🔄 Tạo package mới", key=f"reset_{searchid}"):
                st.session_state[download_state_key] = {
                    'zip_data': None,
                    'filename': None,
                    'ready': False
                }
                st.rerun()

        # Status info
        st.markdown(f"""
        <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; 
                   padding: 10px; margin: 5px 0; font-size: 12px; text-align: center;">
            📊 <strong>{len(products)} sản phẩm</strong> sẵn sàng đóng gói
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Lỗi: {str(e)}")



def render_image_feedback_inline(product, rank, search_id):
    """Render inline image feedback without expander"""
    try:
        # Initialize feedback system
        initialize_feedback_session()
        feedback_system = st.session_state.feedback_system

        # Generate unique keys and product ID
        base_key = f"img_feedback_inline_{search_id}_{rank}"
        product_id = feedback_system.generate_product_id(product, rank, search_id)

        # Get existing feedback
        existing_feedback = feedback_system.get_product_feedback(product_id)

        # Compact layout for thumbs buttons
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("👍 Good",
                         key=f"{base_key}_thumbs_up",
                         help="Image chất lượng, phù hợp",
                         use_container_width=True,
                         type="secondary"):
                success = feedback_system.save_feedback(
                    product=product,
                    rank=rank,
                    search_id=search_id,
                    feedback_type="image_rating",
                    feedback_value="thumbs_up",
                    additional_data={"rating_method": "inline_button"}
                )
                if success:
                    st.success("✅ Saved!")
                    st.rerun()

        with col2:
            if st.button("👎 Bad",
                         key=f"{base_key}_thumbs_down",
                         help="Image không phù hợp, chất lượng kém",
                         use_container_width=True,
                         type="secondary"):
                success = feedback_system.save_feedback(
                    product=product,
                    rank=rank,
                    search_id=search_id,
                    feedback_type="image_rating",
                    feedback_value="thumbs_down",
                    additional_data={"rating_method": "inline_button"}
                )
                if success:
                    st.success("✅ Saved!")
                    st.rerun()

        with col3:
            # Show current feedback stats
            image_ratings = existing_feedback.get('image_ratings', [])
            if image_ratings:
                thumbs_up_count = sum(1 for r in image_ratings if r['value'] == 'thumbs_up')
                thumbs_down_count = sum(1 for r in image_ratings if r['value'] == 'thumbs_down')

                st.markdown(f"""
                <div style="background: #fff; padding: 8px; border-radius: 5px; 
                           text-align: center; border: 1px solid #ddd;">
                    <span style="color: #4CAF50; font-weight: bold;">👍 {thumbs_up_count}</span>
                    <span style="margin: 0 10px; color: #ccc;">|</span>
                    <span style="color: #f44336; font-weight: bold;">👎 {thumbs_down_count}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background: #fff; padding: 8px; border-radius: 5px; 
                           text-align: center; border: 1px solid #ddd; color: #999;">
                    Chưa có feedback
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Image feedback error: {str(e)}")



def render_no_reload_download_section(product, rank, search_id):
    """Render download section WITHOUT causing page reload"""

    # Tạo unique key cho download button
    download_key = f"download_{search_id}_{rank}_{int(time.time())}"

    # Pre-generate ZIP package và cache nó
    zip_data, zip_filename = create_download_package_cached(product, rank, search_id)

    if zip_data and zip_filename:
        # DOWNLOAD BUTTON - NO RELOAD
        st.download_button(
            label="🚀 TẢI NGAY ZIP PACKAGE",
            data=zip_data,
            file_name=zip_filename,
            mime="application/zip",
            key=download_key,
            use_container_width=True,
            type="primary"
        )


# ==================== HELPER FUNCTIONS ====================

def parse_products_from_response(response_text):
    """Parse products từ response text - CACHED"""
    lines = response_text.split('\n')
    products = []
    current_product = {}
    in_results_section = False
    collecting_description = False
    description_lines = []

    for line in lines:
        line_stripped = line.strip()

        if "Top Results" in line_stripped:
            in_results_section = True
            continue

        if in_results_section and line_stripped.startswith("**") and ". " in line_stripped and "**" in line_stripped:
            # Save previous description if collecting one
            if collecting_description and description_lines:
                summary = extract_summary_from_description("\n".join(description_lines))
                current_product['description'] = summary
                description_lines = []
                collecting_description = False

            # New product entry
            if current_product:
                products.append(current_product.copy())
                current_product = {}

            # Extract store name
            store_part = line_stripped.split("**")[1]
            if ". " in store_part:
                store_name = store_part.split(". ", 1)[1] if len(store_part.split(". ", 1)) > 1 else store_part
                current_product['store'] = store_name

        elif "Image URL:" in line_stripped:
            url = line_stripped.split("Image URL:** ")[1] if "Image URL:** " in line_stripped else ""
            current_product['image_url'] = url

        elif "Description:" in line_stripped:
            collecting_description = True
            if "Description:** " in line_stripped:
                desc_start = line_stripped.split("Description:** ")[1]
                if desc_start:
                    description_lines.append(desc_start)

        elif collecting_description:
            if any(field in line_stripped for field in ["Engagement:", "Platform:", "Date:", "Similarity:"]):
                summary = extract_summary_from_description("\n".join(description_lines))
                current_product['description'] = summary
                description_lines = []
                collecting_description = False

                # Parse other fields
                if "Engagement:" in line_stripped:
                    engagement_str = line_stripped.split("Engagement:** ")[
                        1] if "Engagement:** " in line_stripped else ""
                    engagement_dict = parse_engagement_string(engagement_str)
                    current_product['engagement'] = engagement_dict
                elif "Platform:" in line_stripped:
                    platform = line_stripped.split("Platform:** ")[1] if "Platform:** " in line_stripped else ""
                    current_product['platform'] = platform
                elif "Date:" in line_stripped:
                    date = line_stripped.split("Date:** ")[1] if "Date:** " in line_stripped else ""
                    current_product['date'] = date
                elif "Similarity:" in line_stripped:
                    similarity = line_stripped.split("Similarity:** ")[1] if "Similarity:** " in line_stripped else ""
                    current_product['similarity'] = similarity
            else:
                description_lines.append(line)

        # Parse standalone fields
        elif "Engagement:" in line_stripped:
            engagement_str = line_stripped.split("Engagement:** ")[1] if "Engagement:** " in line_stripped else ""
            engagement_dict = parse_engagement_string(engagement_str)
            current_product['engagement'] = engagement_dict
        elif "Platform:" in line_stripped:
            platform = line_stripped.split("Platform:** ")[1] if "Platform:** " in line_stripped else ""
            current_product['platform'] = platform
        elif "Date:" in line_stripped:
            date = line_stripped.split("Date:** ")[1] if "Date:** " in line_stripped else ""
            current_product['date'] = date
        elif "Similarity:" in line_stripped:
            similarity = line_stripped.split("Similarity:** ")[1] if "Similarity:** " in line_stripped else ""
            current_product['similarity'] = similarity

    # Handle last product
    if collecting_description and description_lines:
        summary = extract_summary_from_description("\n".join(description_lines))
        current_product['description'] = summary

    if current_product:
        products.append(current_product)

    return products


@st.cache_data
def extract_summary_from_description(description_text):
    """Extract summary from structured description - CACHED"""
    lines = description_text.split('\n')

    # Look for "## Tóm Tắt" or "##Tóm Tắt" section
    in_summary_section = False
    summary_lines = []

    for line in lines:
        line_stripped = line.strip()

        # Check if we found the summary section
        if line_stripped.startswith('## Thông Tin Cơ Bản ') or line_stripped.startswith('##Thông Tin Cơ Bản'):
            in_summary_section = True
            continue

        # If we're in summary section and hit another ## section, stop
        if in_summary_section and line_stripped.startswith('##') and 'Thông Tin Cơ Bản' not in line_stripped:
            break

        # Collect summary lines
        if in_summary_section and line_stripped:
            summary_lines.append(line_stripped)

    # If we found summary content, return it
    if summary_lines:
        return ' '.join(summary_lines)

    # Fallback: if no "Tóm Tắt" section found, try to extract first meaningful line
    # or return first 200 characters
    fallback_text = description_text.strip()

    return fallback_text


# ==================== CACHE CLEANUP FUNCTIONS ====================

def cleanup_download_cache():
    """Cleanup download cache để tránh memory leak"""
    current_time = time.time()
    keys_to_remove = []

    for key, data in st.session_state.chatbot_download_queue.items():
        if current_time - data['created_at'] > 3600:  # Remove cache older than 1 hour
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state.chatbot_download_queue[key]


def cleanup_products_cache():
    """Cleanup products cache để tránh memory leak"""
    current_time = datetime.now()
    keys_to_remove = []

    for key, data in st.session_state.chatbot_products_cache.items():
        if current_time - data['timestamp'] > pd.Timedelta(hours=2):  # Remove cache older than 2 hours
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state.chatbot_products_cache[key]


# ==================== DOWNLOAD ANALYTICS ====================

def track_download_analytics(product_rank, search_id, success=True):
    """Track download analytics"""
    if 'download_analytics' not in st.session_state:
        st.session_state.download_analytics = []

    analytics_entry = {
        'timestamp': datetime.now(),
        'product_rank': product_rank,
        'search_id': search_id,
        'success': success,
        'session_id': st.session_state.get('session_id', 'unknown')
    }

    st.session_state.download_analytics.append(analytics_entry)

    # Keep only last 100 entries
    if len(st.session_state.download_analytics) > 100:
        st.session_state.download_analytics = st.session_state.download_analytics[-100:]


def get_download_stats():
    """Get download statistics"""
    if 'download_analytics' not in st.session_state:
        return {}

    analytics = st.session_state.download_analytics
    total_downloads = len(analytics)
    successful_downloads = sum(1 for entry in analytics if entry['success'])

    return {
        'total_downloads': total_downloads,
        'successful_downloads': successful_downloads,
        'success_rate': f"{(successful_downloads / total_downloads * 100):.1f}%" if total_downloads > 0 else "0%",
        'last_download': analytics[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if analytics else "None"
    }


# ==================== ERROR RECOVERY SYSTEM ====================

def handle_download_error(product, rank, search_id, error):
    """Handle download errors gracefully"""
    st.error(f"❌ Download failed for Product #{rank}: {str(error)}")

    # Track error
    track_download_analytics(rank, search_id, success=False)

    # Offer alternative options
    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"🔄 Retry Download #{rank}", key=f"retry_download_{search_id}_{rank}"):
            # Clear cache and retry
            cache_key = f"{search_id}_{rank}_{hash(str(product))}"
            if cache_key in st.session_state.chatbot_download_queue:
                del st.session_state.chatbot_download_queue[cache_key]
            st.rerun()

    with col2:
        # Provide manual data as JSON
        metadata_json = create_metadata_json(product, rank)
        st.download_button(
            label=f"📄 Download JSON #{rank}",
            data=metadata_json,
            file_name=f"product_{rank}_metadata.json",
            mime="application/json",
            key=f"json_download_{search_id}_{rank}"
        )


def create_metadata_json(product, rank):
    """Create metadata JSON for download"""
    metadata = {
        "product_info": {
            "rank": rank,
            "store_name": product.get('store', f'Store {rank}'),
            "image_url": product.get('image_url', ''),
            "description": product.get('description', 'Không có mô tả'),
            "platform": product.get('platform', 'Unknown'),
            "date": product.get('date', 'N/A'),
            "similarity": product.get('similarity', '')
        },
        "engagement_data": product.get("engagement", {}),
        "analysis": {
            "engagement_score": calculate_engagement_score_standalone(product),
            "download_timestamp": pd.Timestamp.now().isoformat()
        }
    }
    return json.dumps(metadata, indent=2, ensure_ascii=False)


def calculate_engagement_score_standalone(product):
    """Calculate engagement score for a single product"""
    engagement_data = product.get("engagement", {})
    if isinstance(engagement_data, dict):
        likes = safe_int_convert(engagement_data.get("like", 0))
        comments = safe_int_convert(engagement_data.get("comment", 0))
        shares = safe_int_convert(engagement_data.get("share", 0))
    else:
        likes = comments = shares = 0

    return likes + comments * 5 + shares * 10


# ==================== AUTO MAINTENANCE ====================

def auto_maintenance():
    """Automatic maintenance tasks"""
    # Run cleanup every 50 interactions
    if 'maintenance_counter' not in st.session_state:
        st.session_state.maintenance_counter = 0

    st.session_state.maintenance_counter += 1

    if st.session_state.maintenance_counter % 50 == 0:
        cleanup_download_cache()
        cleanup_products_cache()


# ==================== ADVANCED FEATURES ====================

def show_cache_status():
    """Show cache status in sidebar"""
    if st.sidebar.checkbox("📊 Cache Status", key="show_cache_status"):
        st.sidebar.subheader("🗄️ Cache Information")

        # Products cache info
        products_cache_count = len(st.session_state.chatbot_products_cache)
        downloads_cache_count = len(st.session_state.chatbot_download_queue)

        st.sidebar.metric("Cached Searches", products_cache_count)
        st.sidebar.metric("Cached Downloads", downloads_cache_count)

        # Download stats
        download_stats = get_download_stats()
        if download_stats:
            st.sidebar.subheader("📈 Download Stats")
            for key, value in download_stats.items():
                st.sidebar.text(f"{key.replace('_', ' ').title()}: {value}")

        # Manual cache controls
        st.sidebar.subheader("🔧 Manual Controls")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🗑️ Clear Products", key="manual_clear_products"):
                st.session_state.chatbot_products_cache = {}
                st.success("✅ Products cache cleared!")

        with col2:
            if st.button("🗑️ Clear Downloads", key="manual_clear_downloads"):
                st.session_state.chatbot_download_queue = {}
                st.success("✅ Downloads cache cleared!")


def export_session_data():
    """Export session data for backup"""
    if st.sidebar.checkbox("💾 Export Session", key="export_session_data"):
        st.sidebar.subheader("💾 Session Export")

        session_data = {
            'chat_history': st.session_state.chat_history,
            'products_cache': st.session_state.chatbot_products_cache,
            'download_analytics': st.session_state.get('download_analytics', []),
            'export_timestamp': datetime.now().isoformat()
        }

        # Convert to JSON
        session_json = json.dumps(session_data, indent=2, ensure_ascii=False, default=str)

        st.sidebar.download_button(
            label="📥 Download Session Data",
            data=session_json,
            file_name=f"chatbot_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="export_session_button"
        )


# ==================== MAIN INTERFACE WITH AUTO-MAINTENANCE ====================

def create_chatbot_interface_with_maintenance():
    """Main chatbot interface với auto-maintenance"""
    # Run auto maintenance
    auto_maintenance()

    # Show additional features in sidebar
    show_cache_status()
    export_session_data()

    # Main chatbot interface
    create_chatbot_interface()


# ==================== PERFORMANCE OPTIMIZATIONS ====================

# Pre-load common resources
@st.cache_resource
def preload_common_resources():
    """Preload common resources to improve performance"""
    return {
        'image_placeholder': "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2Y1ZjVmNSIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0iY2VudHJhbCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iIzk5OSI+Tm8gSW1hZ2U8L3RleHQ+Cjwvc3ZnPg==",
        'loading_spinner': "🔄",
        'success_icon': "✅",
        'error_icon': "❌"
    }


# Lazy loading for heavy operations
def lazy_load_chatbot():
    """Lazy load chatbot only when needed"""
    if 'chatbot_lazy_loaded' not in st.session_state:
        st.session_state.chatbot_lazy_loaded = True
        return initialize_chatbot()
    return st.session_state.chatbot


# ==================== ENTRY POINT ====================

def main_with_feedback():
    """Main entry point with feedback system"""
    try:
        # Show feedback dashboard
        render_feedback_dashboard()

        # Main interface with feedback
        create_chatbot_interface_with_feedback()

    except Exception as e:
        st.error(f"❌ System error: {str(e)}")

        # Recovery options
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 Reset Chat", key="recovery_reset_chat"):
                for key in ['chatbot_products_cache', 'chatbot_download_queue', 'prevent_rerun']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        with col2:
            if st.button("🔄 Reset Feedback", key="recovery_reset_feedback"):
                for key in list(st.session_state.keys()):
                    if 'feedback' in key.lower():
                        del st.session_state[key]
                st.rerun()

        with col3:
            if st.button("🗑️ Reset All", key="recovery_reset_all"):
                st.session_state.clear()
                st.rerun()


def add_feedback_styles():
    """Add additional CSS for feedback system"""
    st.markdown("""
    <style>
    /* Feedback button styles */
    .stButton > button[data-testid="baseButton-secondary"] {
        transition: all 0.3s ease;
    }

    .stButton > button[data-testid="baseButton-secondary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* Feedback section animations */
    .feedback-section {
        animation: fadeInUp 0.5s ease-out;
    }

    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Success/error message styles */
    .stSuccess, .stError, .stWarning, .stInfo {
        animation: slideIn 0.3s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-10px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    </style>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    add_feedback_styles()
    main_with_feedback()
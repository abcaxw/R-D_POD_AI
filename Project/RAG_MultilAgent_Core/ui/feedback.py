import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import hashlib
import uuid
from typing import Dict, List, Optional, Any


class FeedbackSystem:
    """
    Hệ thống feedback cho ChatBot AI
    - Thumbs up/down cho images
    - Comment feedback cho descriptions
    - Lưu trữ trong CSV file với improved error handling
    """

    def __init__(self, feedback_file: str = "data/feedback_data.csv"):
        """
        Khởi tạo hệ thống feedback

        Args:
            feedback_file (str): Đường dẫn file lưu feedback
        """
        self.feedback_file = feedback_file
        self.columns = [
            'feedback_id',
            'product_id',
            'search_id',
            'product_rank',
            'feedback_type',  # 'image_rating', 'description_comment'
            'feedback_value',  # thumbs_up/thumbs_down hoặc comment text
            'product_data',  # JSON string của product data
            'date_created',
            'session_id',
            'user_agent',
            'additional_data'
        ]
        self.initialize_feedback_storage()

    def initialize_feedback_storage(self):
        """Khởi tạo file lưu trữ feedback với improved error handling"""
        try:
            # Tạo thư mục data nếu chưa có
            os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)

            # Kiểm tra và tạo file CSV nếu cần
            if not os.path.exists(self.feedback_file):
                self._create_empty_csv()
            else:
                # Kiểm tra file có valid không
                if not self._is_valid_csv():
                    st.warning(f"⚠️ File feedback bị lỗi, đang tạo lại...")
                    self._create_empty_csv()

        except Exception as e:
            st.error(f"❌ Lỗi khởi tạo feedback storage: {str(e)}")
            self._create_empty_csv()  # Fallback tạo file mới

    def _create_empty_csv(self):
        """Tạo file CSV trống với headers"""
        try:
            df_empty = pd.DataFrame(columns=self.columns)
            df_empty.to_csv(self.feedback_file, index=False)
        except Exception as e:
            st.error(f"❌ Không thể tạo file feedback: {str(e)}")

    def _is_valid_csv(self) -> bool:
        """Kiểm tra file CSV có valid không"""
        try:
            # Kiểm tra file size
            if os.path.getsize(self.feedback_file) == 0:
                return False

            # Thử đọc file
            df = pd.read_csv(self.feedback_file)

            # Kiểm tra có columns cần thiết không
            required_columns = ['feedback_id', 'product_id', 'feedback_type', 'feedback_value']
            if not all(col in df.columns for col in required_columns):
                return False

            return True

        except (pd.errors.EmptyDataError, pd.errors.ParserError, FileNotFoundError):
            return False
        except Exception:
            return False

    def _read_feedback_csv(self) -> pd.DataFrame:
        """Đọc CSV file với error handling"""
        try:
            if not os.path.exists(self.feedback_file):
                return pd.DataFrame(columns=self.columns)

            if not self._is_valid_csv():
                st.warning("⚠️ File feedback không valid, tạo lại file mới")
                self._create_empty_csv()
                return pd.DataFrame(columns=self.columns)

            df = pd.read_csv(self.feedback_file)

            # Đảm bảo có đủ columns
            for col in self.columns:
                if col not in df.columns:
                    df[col] = None

            return df

        except pd.errors.EmptyDataError:
            st.warning("⚠️ File feedback trống, khởi tạo lại")
            self._create_empty_csv()
            return pd.DataFrame(columns=self.columns)

        except Exception as e:
            st.error(f"❌ Lỗi đọc file feedback: {str(e)}")
            return pd.DataFrame(columns=self.columns)

    def generate_product_id(self, product: Dict, rank: int, search_id: str) -> str:
        """
        Tạo unique product ID

        Args:
            product (Dict): Product data
            rank (int): Product rank
            search_id (str): Search session ID

        Returns:
            str: Unique product ID
        """
        # Tạo hash từ các thông tin chính
        product_info = f"{search_id}_{rank}_{product.get('store', '')}_{product.get('image_url', '')}"
        product_hash = hashlib.md5(product_info.encode()).hexdigest()
        return f"prod_{product_hash[:12]}"

    def save_feedback(self,
                      product: Dict,
                      rank: int,
                      search_id: str,
                      feedback_type: str,
                      feedback_value: str,
                      additional_data: Optional[Dict] = None) -> bool:
        """
        Lưu feedback vào file CSV với improved error handling

        Args:
            product (Dict): Product data
            rank (int): Product rank
            search_id (str): Search session ID
            feedback_type (str): 'image_rating' hoặc 'description_comment'
            feedback_value (str): Giá trị feedback
            additional_data (Dict): Dữ liệu bổ sung

        Returns:
            bool: True nếu lưu thành công
        """
        try:
            # Tạo feedback record
            feedback_record = {
                'feedback_id': str(uuid.uuid4()),
                'product_id': self.generate_product_id(product, rank, search_id),
                'search_id': search_id,
                'product_rank': rank,
                'feedback_type': feedback_type,
                'feedback_value': feedback_value,
                'product_data': json.dumps(product, ensure_ascii=False),
                'date_created': datetime.now().isoformat(),
                'session_id': st.session_state.get('session_id', 'unknown'),
                'user_agent': st.session_state.get('user_agent', 'unknown'),
                'additional_data': json.dumps(additional_data or {}, ensure_ascii=False)
            }

            # Đọc file hiện tại
            df_existing = self._read_feedback_csv()

            # Thêm record mới
            df_new = pd.DataFrame([feedback_record])
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)

            # Lưu file với backup
            self._save_with_backup(df_combined)

            return True

        except Exception as e:
            st.error(f"❌ Lỗi lưu feedback: {str(e)}")
            return False

    def _save_with_backup(self, df: pd.DataFrame):
        """Lưu file với backup để tránh mất data"""
        try:
            # Tạo backup nếu file hiện tại exists
            if os.path.exists(self.feedback_file):
                backup_file = f"{self.feedback_file}.backup"
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(self.feedback_file, backup_file)

            # Lưu file mới
            df.to_csv(self.feedback_file, index=False)

            # Xóa backup nếu lưu thành công
            backup_file = f"{self.feedback_file}.backup"
            if os.path.exists(backup_file):
                os.remove(backup_file)

        except Exception as e:
            # Restore backup nếu có lỗi
            backup_file = f"{self.feedback_file}.backup"
            if os.path.exists(backup_file):
                if os.path.exists(self.feedback_file):
                    os.remove(self.feedback_file)
                os.rename(backup_file, self.feedback_file)
            raise e

    def get_product_feedback(self, product_id: str) -> Dict[str, Any]:
        """
        Lấy feedback cho một product với improved error handling

        Args:
            product_id (str): Product ID

        Returns:
            Dict: Feedback data
        """
        try:
            df = self._read_feedback_csv()

            if df.empty:
                return {
                    'image_ratings': [],
                    'description_comments': [],
                    'total_feedback': 0
                }

            product_feedback = df[df['product_id'] == product_id]

            result = {
                'image_ratings': [],
                'description_comments': [],
                'total_feedback': len(product_feedback)
            }

            for _, row in product_feedback.iterrows():
                try:
                    if row['feedback_type'] == 'image_rating':
                        result['image_ratings'].append({
                            'value': row['feedback_value'],
                            'date': row['date_created'],
                            'feedback_id': row['feedback_id']
                        })
                    elif row['feedback_type'] == 'description_comment':
                        result['description_comments'].append({
                            'comment': row['feedback_value'],
                            'date': row['date_created'],
                            'feedback_id': row['feedback_id']
                        })
                except Exception as row_error:
                    # Skip corrupted rows
                    continue

            return result

        except Exception as e:
            st.error(f"❌ Lỗi lấy feedback: {str(e)}")
            return {
                'image_ratings': [],
                'description_comments': [],
                'total_feedback': 0
            }

    def get_feedback_statistics(self) -> Dict[str, Any]:
        """
        Lấy thống kê feedback tổng quan với improved error handling

        Returns:
            Dict: Thống kê feedback
        """
        try:
            df = self._read_feedback_csv()

            if df.empty:
                return {
                    'total_feedback': 0,
                    'image_ratings': 0,
                    'description_comments': 0,
                    'thumbs_up': 0,
                    'thumbs_down': 0,
                    'unique_products': 0,
                    'unique_searches': 0,
                    'positive_rate': 0,
                    'feedback_dates': []
                }

            # Đảm bảo columns tồn tại trước khi filter
            df['feedback_type'] = df['feedback_type'].fillna('')
            df['feedback_value'] = df['feedback_value'].fillna('')

            stats = {
                'total_feedback': len(df),
                'image_ratings': len(df[df['feedback_type'] == 'image_rating']),
                'description_comments': len(df[df['feedback_type'] == 'description_comment']),
                'thumbs_up': len(df[(df['feedback_type'] == 'image_rating') &
                                    (df['feedback_value'] == 'thumbs_up')]),
                'thumbs_down': len(df[(df['feedback_type'] == 'image_rating') &
                                      (df['feedback_value'] == 'thumbs_down')]),
                'unique_products': df['product_id'].nunique() if 'product_id' in df.columns else 0,
                'unique_searches': df['search_id'].nunique() if 'search_id' in df.columns else 0,
                'feedback_dates': df['date_created'].dropna().tolist() if 'date_created' in df.columns else []
            }

            # Tính rating ratio
            total_ratings = stats['thumbs_up'] + stats['thumbs_down']
            if total_ratings > 0:
                stats['positive_rate'] = round((stats['thumbs_up'] / total_ratings) * 100, 1)
            else:
                stats['positive_rate'] = 0

            return stats

        except Exception as e:
            st.error(f"❌ Lỗi lấy thống kê: {str(e)}")
            return {
                'total_feedback': 0,
                'image_ratings': 0,
                'description_comments': 0,
                'thumbs_up': 0,
                'thumbs_down': 0,
                'unique_products': 0,
                'unique_searches': 0,
                'positive_rate': 0,
                'feedback_dates': []
            }

    def render_description_feedback(self,
                                    product: Dict,
                                    rank: int,
                                    search_id: str,
                                    key_suffix: str = "") -> None:
        """
        Render giao diện feedback cho description (comment box)

        Args:
            product (Dict): Product data
            rank (int): Product rank
            search_id (str): Search session ID
            key_suffix (str): Suffix cho unique keys
        """
        try:
            # Tạo unique keys
            base_key = f"desc_feedback_{search_id}_{rank}_{key_suffix}"
            product_id = self.generate_product_id(product, rank, search_id)

            # Get existing feedback
            existing_feedback = self.get_product_feedback(product_id)

            # Comment input
            with st.expander("💬 Feedback Description", expanded=False):
                comment_text = st.text_area(
                    "Nhận xét về description:",
                    placeholder="VD: Mô tả chính xác, có đủ thông tin cần thiết...",
                    key=f"{base_key}_comment_input",
                    height=100
                )

                col1, col2 = st.columns([1, 3])

                with col1:
                    if st.button("📤 Gửi feedback",
                                 key=f"{base_key}_submit_comment",
                                 type="primary"):
                        if comment_text.strip():
                            success = self.save_feedback(
                                product=product,
                                rank=rank,
                                search_id=search_id,
                                feedback_type="description_comment",
                                feedback_value=comment_text.strip(),
                                additional_data={
                                    "comment_length": len(comment_text.strip()),
                                    "submission_method": "manual_input"
                                }
                            )
                            if success:
                                st.success("✅ Đã lưu comment!")
                                st.rerun()
                        else:
                            st.warning("⚠️ Vui lòng nhập comment trước khi gửi")

                # Hiển thị existing comments
                description_comments = existing_feedback.get('description_comments', [])
                if description_comments:
                    st.markdown("**📝 Comments trước đó:**")
                    for i, comment in enumerate(description_comments[-3:]):  # Show last 3 comments
                        try:
                            comment_date = datetime.fromisoformat(comment['date']).strftime('%d/%m %H:%M')
                        except:
                            comment_date = "N/A"

                        st.markdown(f"""
                        <div style="background: #f0f2f6; padding: 8px; border-radius: 5px; 
                                   margin: 5px 0; font-size: 13px;">
                            <div style="color: #555;">🕐 {comment_date}</div>
                            <div style="margin-top: 3px;">{comment.get('comment', '')}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    if len(description_comments) > 3:
                        st.markdown(f"<small>... và {len(description_comments) - 3} comments khác</small>",
                                    unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Lỗi render description feedback: {str(e)}")

    def render_complete_feedback_section(self,
                                         product: Dict,
                                         rank: int,
                                         search_id: str,
                                         key_suffix: str = "") -> None:
        """
        Render complete feedback section (both image + description)

        Args:
            product (Dict): Product data
            rank (int): Product rank
            search_id (str): Search session ID
            key_suffix (str): Suffix cho unique keys
        """
        st.markdown("""
        <div style="background: linear-gradient(90deg, #e3f2fd 0%, #f3e5f5 100%); 
                   padding: 15px; border-radius: 10px; margin: 10px 0;">
            <div style="text-align: center; margin-bottom: 10px;">
                <strong style="color: #1976d2;">🎯 FEEDBACK ZONE</strong>
            </div>
        """, unsafe_allow_html=True)

        # Image Feedback Section
        st.markdown("**📷 Image Quality:**")
        self.render_image_feedback(product, rank, search_id, key_suffix)

        # Description Feedback Section
        st.markdown("**📝 Description Quality:**")
        self.render_description_feedback(product, rank, search_id, key_suffix)

        st.markdown('</div>', unsafe_allow_html=True)

    def render_feedback_analytics_sidebar(self) -> None:
        """Render feedback analytics trong sidebar"""
        if st.sidebar.checkbox("📊 Feedback Analytics", key="show_feedback_analytics"):
            st.sidebar.subheader("📊 Feedback Statistics")

            stats = self.get_feedback_statistics()

            if stats and stats['total_feedback'] > 0:
                st.sidebar.metric("Total Feedback", stats['total_feedback'])
                st.sidebar.metric("Positive Rate", f"{stats['positive_rate']}%")

                col1, col2 = st.sidebar.columns(2)
                with col1:
                    st.metric("👍", stats['thumbs_up'])
                with col2:
                    st.metric("👎", stats['thumbs_down'])

                st.sidebar.metric("💬 Comments", stats['description_comments'])
                st.sidebar.metric("🔍 Searches", stats['unique_searches'])
                st.sidebar.metric("📦 Products", stats['unique_products'])

                # Download feedback data
                if st.sidebar.button("📥 Export Feedback", key="export_feedback_data"):
                    try:
                        df_feedback = self._read_feedback_csv()
                        if not df_feedback.empty:
                            csv_data = df_feedback.to_csv(index=False)

                            st.sidebar.download_button(
                                label="📊 Download Feedback CSV",
                                data=csv_data,
                                file_name=f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                key="download_feedback_csv"
                            )
                        else:
                            st.sidebar.warning("⚠️ Không có data để export")
                    except Exception as e:
                        st.sidebar.error(f"❌ Export error: {str(e)}")
            else:
                st.sidebar.info("📝 Chưa có feedback nào")



# ==================== UTILITY FUNCTIONS ====================

@st.cache_data(ttl=300)  # Cache 5 phút
def load_feedback_system():
    """Load feedback system với caching"""
    return FeedbackSystem()


def initialize_feedback_session():
    """Initialize feedback session state"""
    if 'feedback_system' not in st.session_state:
        st.session_state.feedback_system = load_feedback_system()

    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())



def render_feedback_for_product(product: Dict, rank: int, search_id: str,
                                key_suffix: str = "") -> None:
    """
    Convenience function để render feedback cho 1 product

    Args:
        product (Dict): Product data
        rank (int): Product rank
        search_id (str): Search session ID
        key_suffix (str): Suffix cho unique keys
    """
    # Initialize feedback system
    initialize_feedback_session()

    # Render feedback section
    st.session_state.feedback_system.render_complete_feedback_section(
        product, rank, search_id, key_suffix
    )


def show_feedback_analytics():
    """Show feedback analytics trong sidebar"""
    # Initialize feedback system
    initialize_feedback_session()

    # Show analytics
    st.session_state.feedback_system.render_feedback_analytics_sidebar()
"""
Product Card Renderer
Handles rendering of individual product cards with feedback and detail modal
"""
import streamlit as st
from datetime import datetime
import time
from data.data_processor import safe_int_convert


def render_product_card_with_feedback(product, rank, search_id):
    """Render product card WITH FEEDBACK SYSTEM AND DETAIL MODAL"""

    # Extract data
    store_name = product.get('store', f'Store {rank}')
    image_url = product.get('image_url', '')
    description = product.get('description', 'Không có mô tả')
    full_description = product.get('full_description', description)
    platform = product.get('platform', 'Unknown')
    date = product.get('date', 'N/A')
    similarity = product.get('similarity', '')

    # Clean data
    store_name = store_name.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    description = description.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

    # Parse engagement data
    engagement_data = product.get("engagement", {})
    if isinstance(engagement_data, dict):
        likes = safe_int_convert(engagement_data.get("like", 0))
        comments = safe_int_convert(engagement_data.get("comment", 0))
        shares = safe_int_convert(engagement_data.get("share", 0))
    else:
        likes = comments = shares = 0

    # Calculate engagement score
    engagement_score = likes + comments * 5 + shares * 10

    # Unique container for this card
    card_container = st.container()

    with card_container:
        # Enhanced Card styling
        st.markdown(f"""
        <style>
        .product-card-{search_id}-{rank} {{
            border: 1px solid #e0e0e0;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            background: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }}
        .product-card-{search_id}-{rank}:hover {{
            box-shadow: 0 8px 20px rgba(0,0,0,0.12);
            transform: translateY(-2px);
        }}

        .feedback-section {{
            background: linear-gradient(135deg, #f8f9ff 0%, #fff0f8 100%);
            border: 2px dashed #e3f2fd;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
        }}

        .feedback-header {{
            text-align: center;
            font-weight: bold;
            color: #1976d2;
            margin-bottom: 10px;
            font-size: 16px;
        }}

        .engagement-stats {{
            display: flex;
            justify-content: space-around;
            background: #f5f5f5;
            border-radius: 12px;
            padding: 15px;
            margin: 15px 0;
        }}
        .engagement-item {{
            text-align: center;
            flex: 1;
        }}
        .engagement-number {{
            font-size: 18px;
            font-weight: bold;
            color: #1976d2;
        }}
        .engagement-label {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}
        </style>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="product-card-{search_id}-{rank}">', unsafe_allow_html=True)

        # Header section - ENHANCED
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <span style="background: linear-gradient(135deg, #4CAF50, #66BB6A); color: white; padding: 8px 16px; 
                           border-radius: 25px; font-weight: bold; font-size: 16px; box-shadow: 0 3px 8px rgba(76, 175, 80, 0.3);">#{rank}</span>
                <strong style="margin-left: 15px; font-size: 20px; color: #333;">{store_name}</strong>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="text-align: right; font-size: 13px; color: #666;">
                <div style="margin-bottom: 8px;">📅 {date}</div>
                <div style="background: linear-gradient(135deg, #e3f2fd, #bbdefb); color: #1976d2; padding: 6px 12px; 
                          border-radius: 15px; display: inline-block; font-weight: 500; box-shadow: 0 2px 6px rgba(25, 118, 210, 0.2);">
                    {platform}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Similarity score - ENHANCED
        if similarity:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #fff3e0, #ffcc02); color: #f57c00; padding: 10px 16px; 
                       border-radius: 25px; font-size: 14px; font-weight: 600; 
                       margin: 15px 0; width: fit-content; box-shadow: 0 3px 8px rgba(245, 124, 0, 0.2);">
                🎯 Similarity: {similarity}
            </div>
            """, unsafe_allow_html=True)

        # Image section WITH FEEDBACK - ENHANCED
        if image_url and image_url.strip() and image_url != 'N/A':
            try:
                st.image(image_url, use_container_width=True, caption="Product Image")
            except:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #f5f5f5, #eeeeee); padding: 80px; text-align: center; 
                           border-radius: 12px; color: #999; border: 2px dashed #ddd;">
                    <div style="font-size: 48px; margin-bottom: 10px;">📷</div>
                    <div style="font-size: 16px;">Không thể tải ảnh</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #f5f5f5, #eeeeee); padding: 80px; text-align: center; 
                       border-radius: 12px; color: #999; border: 2px dashed #ddd;">
                <div style="font-size: 48px; margin-bottom: 10px;">📷</div>
                <div style="font-size: 16px;">Không có hình ảnh</div>
            </div>
            """, unsafe_allow_html=True)

        # DESCRIPTION FEEDBACK SECTION - Right below brief description
        st.markdown('<div class="feedback-section">', unsafe_allow_html=True)
        st.markdown('<div class="feedback-header">📝 PHRASE CORRECTED FEEDBACK </div>', unsafe_allow_html=True)
        render_description_feedback_inline(product, rank, search_id)
        st.markdown('</div>', unsafe_allow_html=True)

        # Engagement stats section - NEW ENHANCED DISPLAY
        if any([likes, comments, shares]):
            st.markdown(f"""
            <div class="engagement-stats">
                <div class="engagement-item">
                    <div class="engagement-number">{likes:,}</div>
                    <div class="engagement-label">👍 Likes</div>
                </div>
                <div class="engagement-item">
                    <div class="engagement-number">{comments:,}</div>
                    <div class="engagement-label">💬 Comments</div>
                </div>
                <div class="engagement-item">
                    <div class="engagement-number">{shares:,}</div>
                    <div class="engagement-label">🔄 Shares</div>
                </div>
                <div class="engagement-item">
                    <div class="engagement-number">{engagement_score:,}</div>
                    <div class="engagement-label">⭐ Score</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Download section
        from ..chatbot_interface import render_no_reload_download_section
        render_no_reload_download_section(product, rank, search_id)

        # Detail Modal Integration
        render_detail_modal_button(product, rank, search_id, store_name, full_description,
                                  image_url, date, platform, similarity, engagement_score,
                                  likes, comments, shares)

        st.markdown('</div>', unsafe_allow_html=True)


def render_description_feedback_inline(product, rank, search_id):
    """Render inline description feedback"""
    try:
        # Initialize feedback system
        from ui.feedback import initialize_feedback_session
        initialize_feedback_session()
        feedback_system = st.session_state.feedback_system

        # Generate unique keys and product ID
        base_key = f"desc_feedback_inline_{search_id}_{rank}"
        product_id = feedback_system.generate_product_id(product, rank, search_id)

        # Get existing feedback
        existing_feedback = feedback_system.get_product_feedback(product_id)

        # Quick rating buttons for description
        st.markdown("**Quick Rating:**")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        quick_ratings = [
            ("⭐ Excellent", "excellent", "#4CAF50"),
            ("👍 Good", "good", "#2196F3"),
            ("👎 Poor", "poor", "#FF9800"),
            ("❌ Wrong", "wrong", "#f44336")
        ]

        for i, (label, value, color) in enumerate(quick_ratings):
            with [col1, col2, col3, col4][i]:
                if st.button(label,
                             key=f"{base_key}_quick_{value}",
                             help=f"Rate description as {value}",
                             use_container_width=True):
                    success = feedback_system.save_feedback(
                        product=product,
                        rank=rank,
                        search_id=search_id,
                        feedback_type="description_comment",
                        feedback_value=f"Quick rating: {value}",
                        additional_data={
                            "rating_type": "quick_rating",
                            "rating_value": value
                        }
                    )
                    if success:
                        st.success("✅ Quick rating saved!")
                        st.rerun()

        # Detailed comment section (compact)
        with st.expander("💬 Detailed Comment", expanded=False):
            comment_text = st.text_area(
                "Detailed feedback:",
                placeholder="Mô tả chi tiết về quality, accuracy, completeness...",
                key=f"{base_key}_detailed_comment",
                height=80
            )

            if st.button("📤 Submit Comment",
                         key=f"{base_key}_submit_detailed",
                         type="primary"):
                if comment_text.strip():
                    success = feedback_system.save_feedback(
                        product=product,
                        rank=rank,
                        search_id=search_id,
                        feedback_type="description_comment",
                        feedback_value=comment_text.strip(),
                        additional_data={
                            "comment_type": "detailed_comment",
                            "comment_length": len(comment_text.strip())
                        }
                    )
                    if success:
                        st.success("✅ Detailed comment saved!")
                        st.rerun()
                else:
                    st.warning("⚠️ Please enter a comment")

        # Show recent feedback summary
        description_comments = existing_feedback.get('description_comments', [])
        if description_comments:
            # Count quick ratings
            quick_ratings_count = {}
            detailed_comments_count = 0

            for comment in description_comments:
                if comment['comment'].startswith('Quick rating:'):
                    rating_value = comment['comment'].split(': ')[1]
                    quick_ratings_count[rating_value] = quick_ratings_count.get(rating_value, 0) + 1
                else:
                    detailed_comments_count += 1

            # Display summary
            st.markdown("**Feedback Summary:**")

            summary_parts = []
            for rating, count in quick_ratings_count.items():
                emoji_map = {'excellent': '⭐', 'good': '👍', 'poor': '👎', 'wrong': '❌'}
                emoji = emoji_map.get(rating, '📝')
                summary_parts.append(f"{emoji} {count}")

            if detailed_comments_count > 0:
                summary_parts.append(f"💬 {detailed_comments_count}")

            if summary_parts:
                st.markdown(f"""
                <div style="background: #f0f2f6; padding: 8px; border-radius: 5px; 
                           text-align: center; font-size: 13px;">
                    {' | '.join(summary_parts)}
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Description feedback error: {str(e)}")


def render_detail_modal_button(product, rank, search_id, store_name, full_description,
                               image_url, date, platform, similarity, engagement_score,
                               likes, comments, shares):
    """Render detail modal button and modal"""
    # UNIQUE Modal state key for each product
    desc_key = f"show_fb_post_{search_id}_{rank}"
    if desc_key not in st.session_state:
        st.session_state[desc_key] = False

    # Button to open detail modal
    st.markdown("<div style='margin-top: 20px; text-align: center;'>", unsafe_allow_html=True)

    if st.button(
            "📖 Xem Chi Tiết Đầy Đủ",
            key=f"btn_open_detail_{search_id}_{rank}",
            use_container_width=True,
            type="primary"
    ):
        # Clear all other modal states
        for key in list(st.session_state.keys()):
            if key.startswith('show_fb_post_') and key != desc_key:
                st.session_state[key] = False

        st.session_state[desc_key] = True
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # UNIQUE FULL SCREEN MODAL FOR EACH PRODUCT
    if st.session_state[desc_key]:
        @st.dialog(f"📋 Chi Tiết Đầy Đủ - {store_name}", width="large")
        def show_product_detail_modal():
            render_product_detail_modal_content(
                desc_key, search_id, rank, store_name, full_description,
                image_url, date, platform, similarity, engagement_score,
                likes, comments, shares
            )

        # Call the modal function
        show_product_detail_modal()


def render_product_detail_modal_content(desc_key, search_id, rank, store_name, full_description,
                                       image_url, date, platform, similarity, engagement_score,
                                       likes, comments, shares):
    """Render the content of the product detail modal"""
    # ENHANCED CSS for FULL SCREEN modal
    st.markdown("""
    <style>
    /* Force full screen modal */
    [data-testid="stDialog"] {
        width: 98vw !important;
        height: 95vh !important;
        max-width: none !important;
        max-height: none !important;
        position: fixed !important;
        top: 2.5vh !important;
        left: 1vw !important;
        margin: 0 !important;
    }

    [data-testid="stDialog"] > div {
        width: 100% !important;
        height: 100% !important;
        max-width: none !important;
        max-height: none !important;
        margin: 0 !important;
        padding: 20px !important;
        border-radius: 12px !important;
    }

    /* Modal content container */
    [data-testid="stDialog"] .stSelectbox,
    [data-testid="stDialog"] .stMarkdown {
        width: 100% !important;
    }

    /* Modal content scroll */
    .modal-content-scroll::-webkit-scrollbar {
        width: 8px;
    }
    .modal-content-scroll::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    .modal-content-scroll::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    .modal-content-scroll::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header with close button
    col_close, col_title = st.columns([1, 6])
    with col_close:
        if st.button("❌", key=f"close_x_{search_id}_{rank}", help="Đóng"):
            st.session_state[desc_key] = False
            st.rerun()

    with col_title:
        st.markdown(f"""
        <h2 style="color: #1976d2; margin: 0; font-size: 24px;">
            📋 Chi Tiết Đầy Đủ - {store_name}
        </h2>
        """, unsafe_allow_html=True)

    st.divider()

    # Main content area - FULL UTILIZATION
    desc = full_description.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

    # Layout: Left sidebar (info + image), Right main content
    col_sidebar, col_main = st.columns([1, 3])

    with col_sidebar:
        # Compact info card
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #e3f2fd, #ffffff); 
                   border: 1px solid #1976d2; border-radius: 12px; padding: 16px; margin-bottom: 15px;
                   box-shadow: 0 4px 12px rgba(25, 118, 210, 0.1);">
            <div style="color: #1976d2; font-size: 18px; font-weight: 600; margin-bottom: 12px; 
                      border-bottom: 2px solid #e3f2fd; padding-bottom: 8px;">
                🏪 Thông Tin
            </div>
            <div style="font-size: 13px; line-height: 1.6; color: #444;">
                <div style="margin-bottom: 6px;"><strong>Cửa hàng:</strong> {store_name}</div>
                <div style="margin-bottom: 6px;"><strong>Ngày:</strong> 📅 {date}</div>
                <div style="margin-bottom: 6px;"><strong>Nền tảng:</strong> 🏪 {platform}</div>
                {f'<div style="margin-bottom: 6px;"><strong>Độ tương tự:</strong> 🎯 {similarity}</div>' if similarity else ''}
                <div style="margin-bottom: 6px;"><strong>Điểm tương tác:</strong> ⭐ {engagement_score:,}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Engagement stats - COMPACT
        if any([likes, comments, shares]):
            st.markdown(f"""
            <div style="background: white; border: 1px solid #e0e0e0; border-radius: 12px; padding: 12px; margin-bottom: 15px;">
                <div style="color: #1976d2; font-size: 14px; font-weight: 600; margin-bottom: 8px; text-align: center;">
                    📊 Tương Tác
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                    <div style="text-align: center; background: #f8f9fa; padding: 6px; border-radius: 6px;">
                        <div style="font-weight: bold; color: #1976d2;">{likes:,}</div>
                        <div style="color: #666;">👍 Likes</div>
                    </div>
                    <div style="text-align: center; background: #f8f9fa; padding: 6px; border-radius: 6px;">
                        <div style="font-weight: bold; color: #1976d2;">{comments:,}</div>
                        <div style="color: #666;">💬 Comments</div>
                    </div>
                    <div style="text-align: center; background: #f8f9fa; padding: 6px; border-radius: 6px;">
                        <div style="font-weight: bold; color: #1976d2;">{shares:,}</div>
                        <div style="color: #666;">🔄 Shares</div>
                    </div>
                    <div style="text-align: center; background: #fff3e0; padding: 6px; border-radius: 6px;">
                        <div style="font-weight: bold; color: #f57c00;">{engagement_score:,}</div>
                        <div style="color: #666;">⭐ Score</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Image - OPTIMIZED SIZE
        if image_url and image_url.strip() and image_url != 'N/A':
            try:
                st.image(image_url, caption="Product Image", use_container_width=True)
            except Exception:
                st.markdown("""
                <div style="background: #f5f5f5; border-radius: 8px; padding: 40px; text-align: center; color: #999;">
                    <div style="font-size: 32px; margin-bottom: 8px;">📷</div>
                    <div style="font-size: 14px;">Không thể tải ảnh</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: #f5f5f5; border-radius: 8px; padding: 40px; text-align: center; color: #999;">
                <div style="font-size: 32px; margin-bottom: 8px;">📷</div>
                <div style="font-size: 14px;">Không có hình ảnh</div>
            </div>
            """, unsafe_allow_html=True)

    with col_main:
        # Main content - FULL HEIGHT UTILIZATION
        st.markdown(f"""
        <div style="background: #fafafa; border: 1px solid #e3f2fd; border-radius: 12px; 
                   padding: 24px; height: 75vh; overflow-y: auto;" class="modal-content-scroll">
            <div style="color: #1976d2; margin-bottom: 16px; font-size: 20px; font-weight: 600; 
                      border-bottom: 3px solid #e3f2fd; padding-bottom: 12px;">
                📝 Mô Tả Chi Tiết Đầy Đủ
            </div>
            <div style="white-space: pre-line; line-height: 1.5; font-size: 16px; color: #333;">
                {desc}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Bottom action bar
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    col_actions = st.columns([1, 1, 1, 1, 1])
    with col_actions[2]:  # Center the close button
        if st.button("🔙 Đóng Chi Tiết", key=f"close_main_{search_id}_{rank}",
                     use_container_width=True, type="secondary"):
            st.session_state[desc_key] = False
            st.rerun()
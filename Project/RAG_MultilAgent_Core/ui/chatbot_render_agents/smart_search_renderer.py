"""
Smart Search Renderer
Handles rendering of smart search results with feedback and downloads
"""
import streamlit as st
from datetime import datetime
import time


def render_smart_search_response_with_feedback(response_text, search_id):
    """Render smart search response WITH FEEDBACK SYSTEM AND LOAD MORE"""

    # Initialize feedback system
    from ui.feedback import initialize_feedback_session
    initialize_feedback_session()

    # Kiểm tra cached products trước
    from ..chatbot_interface import get_cached_products, parse_products_from_response, cache_products_data
    cached_products = get_cached_products(search_id)

    if cached_products:
        products = cached_products
    else:
        # Parse products từ response text
        products = parse_products_from_response(response_text)
        if products:
            cache_products_data(search_id, products)

    # Initialize session state for pagination
    if f"show_count_{search_id}" not in st.session_state:
        st.session_state[f"show_count_{search_id}"] = 12  # Show 12 products initially

    if f"products_per_load_{search_id}" not in st.session_state:
        st.session_state[f"products_per_load_{search_id}"] = 8  # Load 8 more each time

    # Render header với DOWNLOAD ALL button
    col1, col2 = st.columns([3, 1])

    with col1:
        current_showing = min(st.session_state[f"show_count_{search_id}"], len(products))
        st.markdown(f"""
        <div class="search-results-container">
            <div class="search-header">
                <h3 style="margin: 0; font-size: 1.25rem;">🔍 Smart Search Results with Feedback</h3>
                <p style="margin: 0.5rem 0 0; opacity: 0.9;">Hiển thị <strong>{current_showing}/{len(products)}</strong> sản phẩm phù hợp nhất</p>
                <p style="margin: 0.25rem 0 0; opacity: 0.7; font-size: 14px;">📊 Click thumbs up/down và comment để feedback quality</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        # DOWNLOAD ALL ZIP BUTTON
        if products and len(products) > 0:
            from ..chatbot_interface import render_download_all_button
            render_download_all_button(products, search_id)

    # Render products in grid WITH FEEDBACK
    if products:
        # Get products to show based on current show_count
        current_show_count = st.session_state[f"show_count_{search_id}"]
        products_to_show = products[:current_show_count]

        # Split products into rows of 4
        rows = [products_to_show[i:i + 4] for i in range(0, len(products_to_show), 4)]

        for row_index, row in enumerate(rows):
            cols = st.columns(len(row))

            for col_index, (col, product) in enumerate(zip(cols, row)):
                with col:
                    global_rank = row_index * 4 + col_index + 1
                    # Use the NEW function with feedback
                    from .product_card_renderer import render_product_card_with_feedback
                    render_product_card_with_feedback(product, global_rank, search_id)

        # LOAD MORE BUTTON
        if len(products) > current_show_count:
            st.markdown("<br>", unsafe_allow_html=True)

            # Center the button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                remaining_products = len(products) - current_show_count
                products_to_load = min(st.session_state[f"products_per_load_{search_id}"], remaining_products)

                load_more_button = st.button(
                    f"📦 Xem thêm {products_to_load} sản phẩm",
                    key=f"load_more_{search_id}",
                    use_container_width=True,
                    type="secondary",
                    help=f"Còn lại {remaining_products} sản phẩm chưa hiển thị"
                )

                if load_more_button:
                    # Increase show count
                    st.session_state[f"show_count_{search_id}"] += products_to_load
                    st.rerun()

        # Show "Collapse" button if more than initial 12 are shown
        elif current_show_count > 12:
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                collapse_button = st.button(
                    "🔼 Thu gọn (hiện 12 đầu tiên)",
                    key=f"collapse_{search_id}",
                    use_container_width=True,
                    type="secondary"
                )

                if collapse_button:
                    st.session_state[f"show_count_{search_id}"] = 12
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# Alternative function with custom parameters (optional)
def render_smart_search_with_custom_pagination(response_text, search_id, initial_count=12, load_more_count=8):
    """
    Version with customizable pagination parameters

    Args:
        response_text: The search response text
        search_id: Unique identifier for the search
        initial_count: Number of products to show initially (default: 12)
        load_more_count: Number of products to load each time (default: 8)
    """

    # Initialize feedback system
    from ui.feedback import initialize_feedback_session
    initialize_feedback_session()

    # Kiểm tra cached products trước
    from ..chatbot_interface import get_cached_products, parse_products_from_response, cache_products_data
    cached_products = get_cached_products(search_id)

    if cached_products:
        products = cached_products
    else:
        products = parse_products_from_response(response_text)
        if products:
            cache_products_data(search_id, products)

    # Initialize session state for pagination with custom parameters
    if f"show_count_{search_id}" not in st.session_state:
        st.session_state[f"show_count_{search_id}"] = initial_count

    if f"products_per_load_{search_id}" not in st.session_state:
        st.session_state[f"products_per_load_{search_id}"] = load_more_count

    # Render header
    col1, col2 = st.columns([3, 1])

    with col1:
        current_showing = min(st.session_state[f"show_count_{search_id}"], len(products))
        st.markdown(f"""
        <div class="search-results-container">
            <div class="search-header">
                <h3 style="margin: 0; font-size: 1.25rem;">🔍 Smart Search Results with Feedback</h3>
                <p style="margin: 0.5rem 0 0; opacity: 0.9;">Hiển thị <strong>{current_showing}/{len(products)}</strong> sản phẩm phù hợp nhất</p>
                <p style="margin: 0.25rem 0 0; opacity: 0.7; font-size: 14px;">📊 Click thumbs up/down và comment để feedback quality</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        if products and len(products) > 0:
            from ..chatbot_interface import render_download_all_button
            render_download_all_button(products, search_id)

    # Render products with pagination
    if products:
        current_show_count = st.session_state[f"show_count_{search_id}"]
        products_to_show = products[:current_show_count]

        # Grid layout
        rows = [products_to_show[i:i + 4] for i in range(0, len(products_to_show), 4)]

        for row_index, row in enumerate(rows):
            cols = st.columns(len(row))
            for col_index, (col, product) in enumerate(zip(cols, row)):
                with col:
                    global_rank = row_index * 4 + col_index + 1
                    from .product_card_renderer import render_product_card_with_feedback
                    render_product_card_with_feedback(product, global_rank, search_id)

        # Pagination controls
        _render_pagination_controls(products, search_id, initial_count)

    st.markdown('</div>', unsafe_allow_html=True)


def _render_pagination_controls(products, search_id, initial_count):
    """Render pagination controls (Load More / Collapse)"""

    current_show_count = st.session_state[f"show_count_{search_id}"]
    products_per_load = st.session_state[f"products_per_load_{search_id}"]

    st.markdown("<br>", unsafe_allow_html=True)

    # Load More Button
    if len(products) > current_show_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            remaining_products = len(products) - current_show_count
            products_to_load = min(products_per_load, remaining_products)

            # Custom styling for load more button
            st.markdown("""
            <style>
            .load-more-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 8px;
                color: white;
                padding: 12px 24px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            .load-more-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
            }
            </style>
            """, unsafe_allow_html=True)

            if st.button(
                f"📦 Xem thêm {products_to_load} sản phẩm",
                key=f"load_more_{search_id}",
                use_container_width=True,
                type="secondary",
                help=f"Còn lại {remaining_products} sản phẩm chưa hiển thị"
            ):
                st.session_state[f"show_count_{search_id}"] += products_to_load
                st.rerun()

    # Collapse Button
    elif current_show_count > initial_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                f"🔼 Thu gọn (hiện {initial_count} đầu tiên)",
                key=f"collapse_{search_id}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state[f"show_count_{search_id}"] = initial_count
                st.rerun()


# Helper function để reset pagination khi có search mới
def reset_pagination(search_id):
    """Reset pagination state for new search"""
    if f"show_count_{search_id}" in st.session_state:
        del st.session_state[f"show_count_{search_id}"]
    if f"products_per_load_{search_id}" in st.session_state:
        del st.session_state[f"products_per_load_{search_id}"]

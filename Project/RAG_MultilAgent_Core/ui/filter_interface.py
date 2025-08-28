import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def create_sidebar_filter(df):
    """Tạo interface filter trong sidebar với session state persistence"""
    with st.sidebar:
        st.header("🔍 Bộ lọc dữ liệu")
        st.markdown("---")

        # Initialize filter values from session state
        if 'sidebar_store' not in st.session_state:
            st.session_state.sidebar_store = 'Tất cả'
        if 'sidebar_platform' not in st.session_state:
            st.session_state.sidebar_platform = 'Tất cả'

        # Initialize date range separately for start and end dates
        if 'sidebar_start_date' not in st.session_state or 'sidebar_end_date' not in st.session_state:
            if 'date' in df.columns and not df['date'].empty:
                try:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                    min_date = df['date'].min().date()
                    max_date = df['date'].max().date()
                    st.session_state.sidebar_start_date = min_date
                    st.session_state.sidebar_end_date = max_date
                except:
                    st.session_state.sidebar_start_date = None
                    st.session_state.sidebar_end_date = None
            else:
                st.session_state.sidebar_start_date = None
                st.session_state.sidebar_end_date = None

        # Filter by name_store
        stores = ['Tất cả'] + sorted(df['name_store'].dropna().unique().tolist())
        selected_store = st.selectbox(
            "🏪 Cửa hàng:",
            stores,
            index=stores.index(st.session_state.sidebar_store) if st.session_state.sidebar_store in stores else 0,
            key="store_filter"
        )

        # Filter by platform
        platforms = ['Tất cả'] + sorted(df['platform'].dropna().unique().tolist())
        selected_platform = st.selectbox(
            "📱 Nền tảng:",
            platforms,
            index=platforms.index(
                st.session_state.sidebar_platform) if st.session_state.sidebar_platform in platforms else 0,
            key="platform_filter"
        )

        # Filter by date range with separate start and end date inputs
        start_date = None
        end_date = None

        if 'date' in df.columns and not df['date'].empty:
            try:
                df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.tz_localize(None)
                min_date = df['date'].min().date()
                max_date = df['date'].max().date()

                # Create two separate date inputs
                col1, col2 = st.columns(2)

                with col1:
                    start_date = st.date_input(
                        "📅 Từ ngày:",
                        value=st.session_state.sidebar_start_date if st.session_state.sidebar_start_date else min_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="start_date_filter"
                    )

                with col2:
                    end_date = st.date_input(
                        "📅 Đến ngày:",
                        value=st.session_state.sidebar_end_date if st.session_state.sidebar_end_date else max_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="end_date_filter"
                    )

                # Validate date range (start date should not be after end date)
                if start_date and end_date and start_date > end_date:
                    st.error("⚠️ Ngày bắt đầu không thể sau ngày kết thúc!")
                    # Reset to previous valid values
                    start_date = st.session_state.sidebar_start_date
                    end_date = st.session_state.sidebar_end_date

            except:
                start_date = None
                end_date = None

        # Update session state when filters change
        if selected_store != st.session_state.sidebar_store:
            st.session_state.sidebar_store = selected_store
            st.session_state.filter_changed = True

        if selected_platform != st.session_state.sidebar_platform:
            st.session_state.sidebar_platform = selected_platform
            st.session_state.filter_changed = True

        # Update date session state
        if start_date != st.session_state.sidebar_start_date:
            st.session_state.sidebar_start_date = start_date
            st.session_state.filter_changed = True

        if end_date != st.session_state.sidebar_end_date:
            st.session_state.sidebar_end_date = end_date
            st.session_state.filter_changed = True

        st.markdown("---")

        # Reset filter button
        if st.button("🔄 Đặt lại bộ lọc", use_container_width=True):
            st.session_state.sidebar_store = 'Tất cả'
            st.session_state.sidebar_platform = 'Tất cả'
            if 'date' in df.columns and not df['date'].empty:
                try:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.tz_localize(None)
                    min_date = df['date'].min().date()
                    max_date = df['date'].max().date()
                    st.session_state.sidebar_start_date = min_date
                    st.session_state.sidebar_end_date = max_date
                except:
                    st.session_state.sidebar_start_date = None
                    st.session_state.sidebar_end_date = None
            st.session_state.filter_changed = True
            st.rerun()

    # Return date range as tuple for backward compatibility
    date_range = (start_date, end_date) if start_date and end_date else None
    return selected_store, selected_platform, date_range


@st.cache_data(ttl=300)  # Cache 5 phút cho filter results
def apply_filters_cached(df, selected_store, selected_platform, date_range):
    """Áp dụng các bộ lọc lên DataFrame với caching"""
    filtered_df = df.copy()

    # Filter by store
    if selected_store != 'Tất cả':
        filtered_df = filtered_df[filtered_df['name_store'] == selected_store]

    # Filter by platform
    if selected_platform != 'Tất cả':
        filtered_df = filtered_df[filtered_df['platform'] == selected_platform]

    # Filter by date
    if date_range and len(date_range) == 2:
        filtered_df['date'] = pd.to_datetime(filtered_df['date'], errors='coerce')
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1])
        filtered_df = filtered_df[
            (filtered_df['date'] >= start_date) &
            (filtered_df['date'] <= end_date)
            ]
    return filtered_df


def create_sidebar_stats(filtered_df):
    """Hiển thị thống kê trong sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.subheader("📊 Thống kê")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📦 Sản phẩm", len(filtered_df))
            st.metric("🏪 Cửa hàng", filtered_df['name_store'].nunique())
        with col2:
            st.metric("📱 Nền tảng", filtered_df['platform'].nunique())
            total_engagement = (
                    filtered_df['like'].astype(int).sum() +
                    filtered_df['comment'].astype(int).sum() +
                    filtered_df['share'].astype(int).sum()
            )
            st.metric("❤️ Tương tác", f"{total_engagement:,}")

        # Filter status
        if len(filtered_df) == 0:
            st.warning("⚠️ Không có dữ liệu phù hợp!")
        else:
            st.success(f"✅ {len(filtered_df)} sản phẩm khả dụng")
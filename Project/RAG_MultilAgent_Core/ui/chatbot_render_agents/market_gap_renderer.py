"""
Market Gap Analysis Renderer
Handles rendering of market gap analysis responses with feedback
"""
import streamlit as st
from datetime import datetime


def render_market_gap_response_with_feedback(bot_msg, search_id):
    """Render market gap analysis response with feedback"""
    st.markdown(f"""
    <div class="bot-message">
        {bot_msg}
    </div>
    """, unsafe_allow_html=True)

    # Market gap specific feedback (no products, but can rate analysis quality)
    render_analysis_feedback(search_id, "market_gap", "Market Gap Analysis")


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


def record_analysis_feedback(search_id, analysis_type, feedback_type):
    """Record feedback for analysis responses"""
    if 'analysis_feedback' not in st.session_state:
        st.session_state.analysis_feedback = {}

    st.session_state.analysis_feedback[search_id] = {
        'analysis_type': analysis_type,
        'feedback': feedback_type,
        'timestamp': datetime.now()
    }
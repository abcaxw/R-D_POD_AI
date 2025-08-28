"""
Audience Volume Renderer
Handles rendering of audience volume estimation responses with feedback
"""
import streamlit as st
from datetime import datetime


def render_audience_volume_response_with_feedback(bot_msg, search_id):
    """Render audience volume response with feedback"""
    st.markdown(f"""
    <div class="bot-message">
        {bot_msg}
    </div>
    """, unsafe_allow_html=True)

    # Volume estimation feedback
    from .market_gap_renderer import render_analysis_feedback
    render_analysis_feedback(search_id, "audience_volume", "Audience Volume Analysis")
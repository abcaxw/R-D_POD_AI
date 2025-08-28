"""
Main Renderer
Coordinates all agent renderers and handles message routing
"""
import streamlit as st
from .benchmark_renderer import render_benchmark_response_with_feedback
from .market_gap_renderer import render_market_gap_response_with_feedback
from .idea_verification_renderer import render_idea_verification_response_with_feedback
from .audience_volume_renderer import render_audience_volume_response_with_feedback
from .smart_search_renderer import render_smart_search_response_with_feedback


def render_chat_messages_with_feedback():
    """Render chat messages with feedback system for all agent types"""
    chat_placeholder = st.empty()

    with chat_placeholder.container():
        if not st.session_state.chat_history:
            st.markdown("""
            <div style="text-align: center; padding: 2rem; color: #65676b;">
                <h4>👋 Chào mừng bạn đến với RnD Assistant!</h4>
                <p>Hãy bắt đầu bằng cách nhập câu hỏi của bạn bên dưới.</p>
                <p><em>VD: "Phân tích benchmark sản phẩm keychain Star Wars cho Dad"</em></p>
                <div style="background: #e8f5e8; padding: 15px; border-radius: 10px; margin-top: 20px;">
                    <strong>🎯 NEW: Feedback System!</strong><br>
                    <small>Rate images (👍👎) và comment descriptions để improve search quality</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for i, (user_msg, bot_msg) in enumerate(st.session_state.chat_history):
                # User message
                st.markdown(f"""
                <div class="user-message">
                    {user_msg}
                </div>
                """, unsafe_allow_html=True)

                # Bot message với feedback handling cho các agent types
                search_id = f"search_{i}_{hash(bot_msg)}"

                # Route to appropriate renderer based on response type
                route_message_to_renderer(bot_msg, search_id)


def route_message_to_renderer(bot_msg, search_id):
    """Route bot message to appropriate renderer based on content type"""

    # Smart Search Results (existing)
    if "Smart Search Results:" in bot_msg:
        render_smart_search_response_with_feedback(bot_msg, search_id)

    # Benchmark Analysis
    elif "Benchmark Analysis:" in bot_msg:
        render_benchmark_response_with_feedback(bot_msg, search_id)

    # Market Gap Analysis
    elif "Market Gap Analysis:" in bot_msg:
        render_market_gap_response_with_feedback(bot_msg, search_id)

    # Idea Verification
    elif "Idea Verification:" in bot_msg:
        render_idea_verification_response_with_feedback(bot_msg, search_id)

    # Audience Volume Estimation
    elif "Audience Volume Estimation:" in bot_msg:
        render_audience_volume_response_with_feedback(bot_msg, search_id)

    else:
        # Regular bot response
        st.markdown(f"""
        <div class="bot-message">
            {bot_msg}
        </div>
        """, unsafe_allow_html=True)
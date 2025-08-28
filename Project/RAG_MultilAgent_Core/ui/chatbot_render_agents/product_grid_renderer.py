"""
Product Grid Renderer
Handles rendering of product grids with feedback for any analysis type
"""
import streamlit as st
from datetime import datetime


def render_product_grid_with_feedback(products, search_id, analysis_type):
    """Render product grid with feedback for any analysis type"""
    if not products:
        return

    st.markdown("### 🖼️ Visual Results with Feedback")

    # Limit to 6 products for UI
    for i, product in enumerate(products[:6]):
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 1])

            with col1:
                image_url = product.get('image_url', '')
                if image_url and image_url != 'N/A':
                    try:
                        st.image(image_url, width=150)
                    except:
                        st.text("❌ Image failed")
                else:
                    st.text("🚫 No image")

            with col2:
                st.write(f"**{product.get('store', 'Unknown')}**")
                st.write(f"Platform: {product.get('platform', 'N/A')}")

                if analysis_type == "benchmark":
                    st.write(f"Engagement: {product.get('engagement_score', '0')}")
                elif analysis_type == "verification":
                    st.write(f"Similarity: {product.get('similarity', '0%')}")

                desc = product.get('description', '')
                if desc and desc != 'N/A':
                    st.write(f"Description: {desc[:100]}...")

            with col3:
                # Feedback buttons
                product_id = f"{search_id}_{analysis_type}_{i}"

                if st.button("👍", key=f"like_{product_id}"):
                    record_product_feedback(product_id, "like", product)
                    st.success("Liked!")

                if st.button("👎", key=f"dislike_{product_id}"):
                    record_product_feedback(product_id, "dislike", product)
                    st.info("Noted!")

        st.markdown("---")


def record_product_feedback(product_id, feedback_type, product_data):
    """Record feedback for products"""
    if 'product_feedback' not in st.session_state:
        st.session_state.product_feedback = {}

    st.session_state.product_feedback[product_id] = {
        'type': feedback_type,
        'timestamp': datetime.now(),
        'product': product_data
    }
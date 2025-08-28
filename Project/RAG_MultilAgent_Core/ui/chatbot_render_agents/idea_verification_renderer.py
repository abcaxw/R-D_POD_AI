"""
Idea Verification Renderer
Handles rendering of idea verification responses with feedback
"""
import streamlit as st
from datetime import datetime


def render_idea_verification_response_with_feedback(bot_msg, search_id):
    """Render idea verification response with feedback"""
    st.markdown(f"""
    <div class="bot-message">
        {bot_msg}
    </div>
    """, unsafe_allow_html=True)

    # Extract similar concepts/products for feedback
    products = extract_products_from_verification_response(bot_msg)
    if products:
        from .product_grid_renderer import render_product_grid_with_feedback
        render_product_grid_with_feedback(products, search_id, "verification")
    else:
        from .market_gap_renderer import render_analysis_feedback
        render_analysis_feedback(search_id, "idea_verification", "Idea Verification")


def extract_products_from_verification_response(response):
    """Extract similar concepts from verification response"""
    products = []
    lines = response.split('\n')

    current_product = {}
    in_concepts_section = False

    for line in lines:
        if "Top Similar Concepts" in line:
            in_concepts_section = True
            continue

        if in_concepts_section and line.startswith('**') and '. ' in line:
            if current_product:
                products.append(current_product)

            # Parse similar concept info
            parts = line.split(' - Similarity: ')
            if len(parts) >= 2:
                current_product = {
                    'store': parts[0].split('. ')[1].replace('**', ''),
                    'similarity': parts[1].replace('**', '')
                }
        elif current_product and '🔗 **Image:**' in line:
            current_product['image_url'] = line.split('🔗 **Image:**')[1].strip()
        elif current_product and '📝 **Description:**' in line:
            current_product['description'] = line.split('📝 **Description:**')[1].strip()
        elif current_product and '📱 **Platform:**' in line:
            current_product['platform'] = line.split('📱 **Platform:**')[1].strip()

    if current_product:
        products.append(current_product)

    return products
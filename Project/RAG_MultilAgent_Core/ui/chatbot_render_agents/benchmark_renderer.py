"""
Benchmark Analysis Renderer
Handles rendering of benchmark analysis responses with feedback
"""
import streamlit as st
from datetime import datetime


def render_benchmark_response_with_feedback(bot_msg, search_id):
    """Render benchmark analysis response with feedback"""
    st.markdown(f"""
    <div class="bot-message">
        {bot_msg}
    </div>
    """, unsafe_allow_html=True)

    # Extract and display products from benchmark analysis
    products = extract_products_from_benchmark_response(bot_msg)
    if products:
        from .product_grid_renderer import render_product_grid_with_feedback
        render_product_grid_with_feedback(products, search_id, "benchmark")


def extract_products_from_benchmark_response(response):
    """Extract products from benchmark analysis response"""
    products = []
    lines = response.split('\n')

    current_product = {}
    in_winners_section = False

    for line in lines:
        if "Top Winning Products" in line:
            in_winners_section = True
            continue

        if in_winners_section and line.startswith('**') and '. ' in line:
            if current_product:
                products.append(current_product)

            # Parse product info
            current_product = {
                'store': line.split('. ')[1].split(' - ')[0].replace('**', ''),
                'engagement_score': line.split(' - ')[1].split(' engagement')[0] if ' - ' in line else '0'
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
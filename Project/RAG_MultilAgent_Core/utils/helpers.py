"""
Helper utilities for Enhanced RnD Assistant
"""
import operator
from typing import List, Dict, Any, TypedDict, Annotated, Optional
from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class AgentState(TypedDict):
    """State management for the multi-agent workflow"""
    messages: Annotated[List, operator.add]
    query: str
    query_type: str  # "benchmark", "market_gap", "verify_idea", "audience_volume", "smart_search"
    search_type: Optional[str]  # "text_to_image", "image_to_image", "text_to_text"
    search_results: List[Dict[str, Any]]
    analysis_results: Dict[str, Any]
    final_answer: str
    metadata: Dict[str, Any]
    input_image: Optional[str]  # Base64 encoded image
    search_description: Optional[str]


def safe_int_convert(value) -> int:
    """Safely convert value to integer"""
    try:
        if isinstance(value, str):
            return int(value.replace(",", ""))
        return int(value) if value else 0
    except:
        return 0


def calculate_engagement_score(product: Dict) -> int:
    """Calculate engagement score for a product"""
    try:
        engagement = product.get("engagement", {})
        likes = safe_int_convert(engagement.get("like", 0))
        comments = safe_int_convert(engagement.get("comment", 0))
        shares = safe_int_convert(engagement.get("share", 0))
        return likes + comments * 5 + shares * 10
    except:
        return 0


def create_initial_state(query: str, input_image: Optional[str] = None) -> AgentState:
    """Create initial state for workflow"""
    return AgentState(
        messages=[HumanMessage(content=query)],
        query=query,
        query_type="",
        search_type=None,
        search_results=[],
        analysis_results={},
        final_answer="",
        metadata={"timestamp": datetime.now().isoformat()},
        input_image=input_image,
        search_description=None
    )


def format_product_display(product: Dict, index: int = 1) -> str:
    """Format product data for display"""
    engagement_score = calculate_engagement_score(product)
    similarity = product.get("similarity_score", 0)

    display = f"**{index}. {product.get('store', 'Unknown Store')}**\n"
    display += f"   - 🔗 **Image URL:** {product.get('image_url', 'N/A')}\n"
    display += f"   - 📝 **Description:** {product.get('description', 'N/A')}...\n"
    display += f"   - 📊 **Engagement:** {engagement_score:,}\n"
    display += f"   - 🎯 **Similarity:** {similarity:.2%}\n"
    display += f"   - 📱 **Platform:** {product.get('platform', 'N/A')}\n"
    display += f"   - 📅 **Date:** {product.get('date', 'N/A')}\n\n"

    return display


def deduplicate_products(products: List[Dict]) -> List[Dict]:
    """Remove duplicate products based on ID"""
    seen_ids = set()
    unique_products = []

    for product in products:
        product_id = product.get("id")
        if product_id and product_id not in seen_ids:
            seen_ids.add(product_id)
            unique_products.append(product)

    return unique_products


def validate_image_base64(image_base64: str) -> bool:
    """Validate base64 image string"""
    try:
        import base64
        import io
        from PIL import Image

        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        return True
    except Exception:
        return False


def get_top_items_from_dict(data: Dict, top_n: int = 10) -> List[tuple]:
    """Get top N items from dictionary sorted by value"""
    return sorted(data.items(), key=lambda x: x[1], reverse=True)[:top_n]


def format_list_for_display(items: List[str], max_items: int = 10) -> str:
    """Format list items for display with limit"""
    if not items:
        return "None"

    display_items = items[:max_items]
    result = ", ".join(display_items)

    if len(items) > max_items:
        result += f" (and {len(items) - max_items} more)"

    return result
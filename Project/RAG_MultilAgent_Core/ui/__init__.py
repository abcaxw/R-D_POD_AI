# UI Module for Milvus Product Analytics Dashboard
"""
UI modules for the Milvus Product Analytics Dashboard

Modules:
- chatbot_interface: Chatbot UI components
- filter_interface: Data filtering UI components
- metadata_analysis: Metadata analysis and visualization UI components (overview only)
"""

from .chatbot_interface import create_chatbot_interface
from .filter_interface import create_sidebar_filter, apply_filters_cached, create_sidebar_stats
from .metadata_analysis import (
    create_metadata_analysis_tab,
    create_metadata_tab_interface,
    get_metadata_fields,
    analyze_metadata_field
)

__all__ = [
    'create_chatbot_interface',
    'create_sidebar_filter',
    'apply_filters_cached',
    'create_sidebar_stats',
    'create_metadata_analysis_tab',
    'create_metadata_tab_interface',
    'get_metadata_fields',
    'analyze_metadata_field'
]
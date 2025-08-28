import streamlit as st


def load_custom_css():
    """Load tất cả CSS styles cho dashboard"""
    st.markdown("""
    <style>
        .metric-card {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin: 0.5rem 0;
        }
        .main-header {
            background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            color: white;
            margin-bottom: 2rem;
        }
        .metadata-section {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 1.5rem;
            border-radius: 15px;
            margin: 1rem 0;
            border-left: 5px solid #667eea;
        }
        .chart-container {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 0.5rem 0;
        }
        .chat-message {
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 10px;
            max-width: 80%;
        }
        .user-message {
            background-color: #e3f2fd;
            margin-left: auto;
            text-align: right;
        }
        .assistant-message {
            background-color: #f5f5f5;
            margin-right: auto;
        }
        .chat-container {
            height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 1rem;
            background-color: white;
        }

        /* Chat Interface Styles */
        .chat-container {
            height: 500px;
            overflow-y: auto;
            padding: 1rem;
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 15px;
            margin-bottom: 1rem;
            display: flex;
            flex-direction: column;
        }

        /* Message Bubbles */
        .user-message {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 16px;
            border-radius: 18px 18px 5px 18px;
            margin: 8px 0 8px auto;
            max-width: 75%;
            word-wrap: break-word;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        .assistant-message {
            background: white;
            color: #333;
            padding: 12px 16px;
            border-radius: 18px 18px 18px 5px;
            margin: 8px auto 8px 0;
            max-width: 95%;
            word-wrap: break-word;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
        }

        /* Grid Layout Styles */
        .search-results-container {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 15px;
            margin: 1rem 0;
        }

        .search-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 1.5rem;
        }

        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .product-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            border: 1px solid #e0e0e0;
        }

        .product-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }

        .product-header {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #dee2e6;
        }

        .product-rank {
            background: #667eea;
            color: white;
            font-size: 0.75rem;
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            display: inline-block;
            margin-bottom: 0.5rem;
        }

        .product-store {
            font-weight: 600;
            color: #495057;
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
        }

        .product-meta {
            font-size: 0.75rem;
            color: #6c757d;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .platform-badge {
            background: #e3f2fd;
            color: #1565c0;
            padding: 0.125rem 0.5rem;
            border-radius: 8px;
            font-size: 0.7rem;
            font-weight: 500;
        }

        .product-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            background: #f8f9fa;
        }

        .no-image-placeholder {
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #6c757d;
            font-size: 0.9rem;
        }

        .product-content {
            padding: 1rem;
        }

        .product-description {
            color: #495057;
            font-size: 0.85rem;
            line-height: 1.4;
            margin-bottom: 0.75rem;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .similarity-score {
            background: linear-gradient(90deg, #28a745, #20c997);
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            border-radius: 8px;
            margin-bottom: 0.75rem;
            display: inline-block;
        }

        .engagement-stats {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f8f9fa;
            padding: 0.5rem;
            border-radius: 8px;
            margin-top: 0.5rem;
        }

        .engagement-item {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            font-size: 0.75rem;
            color: #495057;
        }

        .engagement-icon {
            font-size: 0.9rem;
        }

        .total-score {
            font-size: 0.7rem;
            color: #6c757d;
            font-weight: 600;
        }

        /* Features Info */
        .features-info {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }

        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 8px;
            margin-top: 8px;
        }

        .feature-item {
            background: rgba(255,255,255,0.1);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
        }

        /* Typing Indicator */
        .typing-indicator {
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 18px 18px 18px 5px;
            padding: 12px 16px;
            margin: 8px auto 8px 0;
            max-width: 75%;
            color: #65676b;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .typing-dots {
            display: flex;
            gap: 3px;
        }

        .typing-dot {
            width: 6px;
            height: 6px;
            background: #65676b;
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out;
        }

        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }

        @keyframes typing {
            0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
            40% { transform: scale(1); opacity: 1; }
        }

        /* Scrollbar Styling */
        .chat-container::-webkit-scrollbar {
            width: 6px;
        }

        .chat-container::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }

        .chat-container::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }

        .chat-container::-webkit-scrollbar-thumb:hover {
            background: #a1a1a1;
        }

        /* Responsive grid for mobile */
        @media (max-width: 768px) {
            .products-grid {
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 0.75rem;
            }
        }

        @media (max-width: 480px) {
            .products-grid {
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)
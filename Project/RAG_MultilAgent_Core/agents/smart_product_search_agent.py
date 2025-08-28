"""
Enhanced Smart product search agent với flexible filter recognition
Không có narrow mapping - sử dụng AI để nhận diện filters linh hoạt
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from agents.base_agent import BaseAgent
from tools.search_tools import (
    search_by_description_tool,
    search_by_image_tool,
    search_multimodal_tool
)
from config.settings import Config


class SmartProductSearchAgent(BaseAgent):
    """Agent for smart product search with flexible filter recognition"""

    def __init__(self):
        super().__init__(temperature=0.2)
        self.vision_llm = ChatOpenAI(
            model=Config.VISION_MODEL,
            temperature=0.2,
            api_key=""
        )
        # Khởi tạo metadata mappings (giữ nguyên cho backward compatibility)
        self.metadata_mappings = self._init_metadata_mappings()

    def _init_metadata_mappings(self) -> Dict[str, Dict[str, List[str]]]:
        """Khởi tạo metadata mappings (giữ nguyên từ code cũ)"""
        return {
            "main_subject": {
                "Family": ["family", "gia đình", "relatives", "họ hàng"],
                "Police": ["police", "cảnh sát", "officer", "công an"],
                "Halloween": ["halloween", "ma quỷ", "scary", "kinh dị", "pumpkin", "bí ngô"],
                "Christmas": ["christmas", "noel", "giáng sinh", "santa", "xmas"],
                "Mom": ["mom", "mother", "mẹ", "mama", "mommy"],
                "Dad": ["dad", "father", "bố", "papa", "daddy"],
                "Teacher": ["teacher", "giáo viên", "educator", "thầy", "cô"],
                "Doctor": ["doctor", "bác sĩ", "nurse", "y tá", "medical"],
                "Love": ["love", "yêu", "tình yêu", "romantic", "lãng mạn"],
                "Pet": ["pet", "thú cưng", "dog", "chó", "cat", "mèo"],
                "Sports": ["sports", "thể thao", "football", "basketball", "soccer"],
                "Music": ["music", "âm nhạc", "guitar", "piano", "song"]
            },
            "product_type": {
                "Desk Plaque": ["plaque", "bảng", "desk", "bàn làm việc"],
                "Mug": ["mug", "cốc", "cup", "ly"],
                "T-Shirt": ["tshirt", "shirt", "áo", "clothing"],
                "Canvas": ["canvas", "tranh", "painting", "wall art"],
                "Pillow": ["pillow", "gối", "cushion", "throw pillow"],
                "Keychain": ["keychain", "móc khóa", "key ring"],
                "Tumbler": ["tumbler", "bottle", "chai", "water bottle"],
                "Frame": ["frame", "khung", "photo frame", "khung ảnh"]
            },
            "recipient": {
                "Mom": ["mom", "mother", "mẹ", "mama", "mommy"],
                "Dad": ["dad", "father", "bố", "papa", "daddy"],
                "Grandma": ["grandma", "grandmother", "bà", "ngoại", "bà ngoại"],
                "Grandpa": ["grandpa", "grandfather", "ông", "nội", "ông nội"],
                "Wife": ["wife", "vợ", "spouse", "partner"],
                "Husband": ["husband", "chồng", "spouse", "partner"],
                "Daughter": ["daughter", "con gái", "girl"],
                "Son": ["son", "con trai", "boy"],
                "Sister": ["sister", "chị", "em gái"],
                "Brother": ["brother", "anh", "em trai"],
                "Teacher": ["teacher", "giáo viên", "thầy", "cô"],
                "Friend": ["friend", "bạn", "buddy", "pal"]
            }
        }

    async def _extract_filters_with_ai(self, user_query: str) -> Dict[str, Any]:
        """
        Sử dụng AI để nhận diện filters từ user query một cách linh hoạt
        Không có narrow mapping - AI tự hiểu và trích xuất
        """
        # FIX: Lấy thời gian hiện tại
        current_time = datetime.now().strftime("%d/%m/%Y")

        filter_extraction_prompt = f"""
    Bạn là một AI chuyên phân tích yêu cầu tìm kiếm sản phẩm. Hãy phân tích câu truy vấn sau và trích xuất các điều kiện lọc (filters).
    Thời gian hiện tại: {current_time}

    NHIỆM VỤ: Từ câu truy vấn của người dùng, hãy nhận diện và trích xuất:

    1. **NAME_STORE (Tên cửa hàng)**:
       - Tìm các tên thương hiệu, cửa hàng, shop
       - Ví dụ: "SUN", "SIB", "SIV", "FIB", etc
       - Chú ý: Có thể viết hoa, viết thường, hoặc viết tắt

    2. **PLATFORM (Nền tảng)**:
       - Tìm các nền tảng bán hàng, mạng xã hội
       - Ví dụ: "Facebook", "Instagram", "TikTok", "Shopee", "Lazada", "Website", etc

    3. **DATE_RANGE & TIME_FILTERS (Khoảng thời gian)**:
       - CHỈ trích xuất nếu câu truy vấn CÓ ĐỀ CẬP RÕ RÀNG về thời gian
       - Bao gồm các từ khóa thời gian như:

       **Ngày tháng cụ thể:**
       - Ngày chính xác: "25/8/2025", "15 tháng 3", "ngày 10"
       - Khoảng ngày: "từ 1/8 đến 15/8", "từ hôm qua đến hôm nay"

       **Tháng/Năm:**
       - Tháng cụ thể: "tháng 8", "tháng 8/2025", "08/2025"
       - Khoảng tháng: "từ tháng 6 đến tháng 8"
       - Năm: "năm 2024", "2025", "từ năm 2023"

       **Thời gian tương đối:**
       - Gần đây: "hôm nay", "hôm qua", "tuần này", "tuần trước", "tháng này", "tháng trước"
       - Khoảng thời gian: "3 ngày qua", "2 tuần gần đây", "6 tháng trước"
       - Chu kỳ: "quý này", "nửa đầu năm", "cuối năm"

       **Mùa/Dịp:**
       - Mùa: "mùa hè", "mùa đông"
       - Dịp lễ: "Tết", "Noel", "Black Friday"
       - Sự kiện: "khai trương", "sale cuối năm"

       **Thời điểm trong ngày:**
       - Buổi: "sáng nay", "chiều hôm qua"
       - Giờ: "8h sáng", "15:30"

    QUAN TRỌNG - ĐIỀU KIỆN THỜI GIAN:
    - CHỈ trích xuất thời gian nếu câu truy vấn CÓ ĐỀ CẬP TRỰC TIẾP về thời gian
    - Sử dụng thời gian hiện tại ({current_time}) để tính toán thời gian tương đối
    - Nếu KHÔNG tìm thấy bất kỳ từ khóa thời gian nào → KHÔNG tạo ra date_range, date_after, date_before
    - Định dạng về ngày và tháng luôn luôn có 2 số (ví dụ: 1/8/2025,23/2/2024 thành 01/08/2025, 23/02/2024,...)
    - Hãy linh hoạt với cách diễn đạt khác nhau
    - Chú ý cả tiếng Việt và tiếng Anh

    Câu truy vấn: "{user_query}"

    VÍ DỤ:
    - "tìm áo christmas" → KHÔNG có date filter
    - "tìm áo christmas tháng 12" → CÓ date filter
    - "sản phẩm của SIB" → KHÔNG có date filter, có name_store
    - "đơn hàng hôm nay" → CÓ date filter

    Trả về JSON với format sau (CHỈ BAO GỒM những field CÓ THÔNG TIN TRONG QUERY):
    {{
        "name_store": ["tên_store_1", "tên_store_2"],
        "platform": ["platform_1", "platform_2"],
        "date_range": ["DD/MM/YYYY", "DD/MM/YYYY"],
        "date_after": "DD/MM/YYYY",
        "date_before": "DD/MM/YYYY"
    }}

    Nếu không có filter nào, trả về: {{}}
    """

        try:
            # Gọi AI để phân tích
            response = await self.llm.ainvoke([HumanMessage(content=filter_extraction_prompt)])
            ai_response = response.content.strip()

            # Trích xuất JSON từ response
            import json
            import re

            # Tìm JSON block trong response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response)
            print(f"AI Response: {ai_response}")
            print(f"JSON Match: {json_match}")

            if json_match:
                json_str = json_match.group()
                try:
                    extracted_filters = json.loads(json_str)

                    # Validate và clean up filters - THÊM KIỂM TRA CHẶT CHẼ HÔN
                    cleaned_filters = {}

                    # Kiểm tra name_store
                    if 'name_store' in extracted_filters and extracted_filters['name_store']:
                        if isinstance(extracted_filters['name_store'], list) and extracted_filters['name_store']:
                            cleaned_filters['name_store'] = extracted_filters['name_store']

                    # Kiểm tra platform
                    if 'platform' in extracted_filters and extracted_filters['platform']:
                        if isinstance(extracted_filters['platform'], list) and extracted_filters['platform']:
                            cleaned_filters['platform'] = extracted_filters['platform']

                    # Xử lý date filters - THÊM VALIDATION CHẶT CHẼ
                    if 'date_range' in extracted_filters and extracted_filters['date_range']:
                        if isinstance(extracted_filters['date_range'], list) and len(
                                extracted_filters['date_range']) == 2:
                            # Kiểm tra xem có phải là ngày hợp lệ không
                            date1, date2 = extracted_filters['date_range']
                            if self._is_valid_date_string(date1) and self._is_valid_date_string(date2):
                                cleaned_filters['date_range'] = tuple(extracted_filters['date_range'])

                    if 'date_after' in extracted_filters and extracted_filters['date_after']:
                        if self._is_valid_date_string(extracted_filters['date_after']):
                            cleaned_filters['date_after'] = extracted_filters['date_after']

                    if 'date_before' in extracted_filters and extracted_filters['date_before']:
                        if self._is_valid_date_string(extracted_filters['date_before']):
                            cleaned_filters['date_before'] = extracted_filters['date_before']

                    # THÊM KIỂM TRA CUỐI: Nếu query không có từ khóa thời gian, loại bỏ date filters
                    if not self._contains_time_keywords(user_query):
                        # Loại bỏ tất cả date filters nếu không có từ khóa thời gian
                        cleaned_filters.pop('date_range', None)
                        cleaned_filters.pop('date_after', None)
                        cleaned_filters.pop('date_before', None)
                        print(f"No time keywords found in query, removed date filters")

                    print(f"Extracted filters: {cleaned_filters}")
                    return cleaned_filters

                except json.JSONDecodeError as e:
                    print(f"Cannot parse AI response as JSON: {json_str}, Error: {str(e)}")
                    return {}
            else:
                print(f"No JSON found in AI response: {ai_response}")
                return {}

        except Exception as e:
            print(f"Error in AI filter extraction: {str(e)}")
            return {}

    def _is_valid_date_string(self, date_str: str) -> bool:
        """Kiểm tra xem string có phải là ngày hợp lệ không"""
        if not isinstance(date_str, str):
            return False

        try:
            # Kiểm tra format DD/MM/YYYY
            import re
            if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
                day, month, year = map(int, date_str.split('/'))
                # Kiểm tra tính hợp lệ của ngày tháng
                if 1 <= month <= 12 and 1 <= day <= 31 and year >= 2020:
                    return True
        except:
            pass
        return False

    def _contains_time_keywords(self, query: str) -> bool:
        """Kiểm tra xem query có chứa từ khóa thời gian không"""
        query_lower = query.lower()

        # Danh sách từ khóa thời gian tiếng Việt và tiếng Anh
        time_keywords = [
            # Ngày tháng cụ thể
            'ngày', 'tháng', 'năm', 'day', 'month', 'year',

            # Thời gian tương đối
            'hôm nay', 'hôm qua', 'today', 'yesterday',
            'tuần này', 'tuần trước', 'this week', 'last week',
            'tháng này', 'tháng trước', 'this month', 'last month',
            'năm nay', 'năm trước', 'this year', 'last year',

            # Khoảng thời gian
            'từ', 'đến', 'from', 'to', 'between',
            'trước', 'sau', 'before', 'after',

            # Chu kỳ thời gian
            'quý', 'quarter', 'nửa đầu', 'nửa cuối',
            'đầu năm', 'cuối năm', 'beginning', 'end',

            # Dịp đặc biệt (có thể coi là thời gian)
            'tết', 'noel', 'christmas', 'black friday',
            'khai trương', 'sale', 'giảm giá',

            # Mùa
            'mùa hè', 'mùa đông', 'mùa xuân', 'mùa thu',
            'summer', 'winter', 'spring', 'autumn', 'fall',

            # Pattern ngày tháng
            r'\d{1,2}/\d{1,2}', r'\d{1,2}-\d{1,2}',  # DD/MM, DD-MM
        ]

        # Kiểm tra từ khóa thường
        for keyword in time_keywords:
            if keyword.startswith('r\''):  # Regex pattern
                import re
                pattern = keyword[2:-1]  # Remove r' and '
                if re.search(pattern, query_lower):
                    return True
            else:
                if keyword in query_lower:
                    return True

        # Kiểm tra pattern ngày tháng năm
        import re
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # DD/MM/YYYY
            r'\d{1,2}-\d{1,2}-\d{4}',  # DD-MM-YYYY
            r'\d{4}',  # Year only nếu > 2020
        ]

        for pattern in date_patterns:
            if re.search(pattern, query):
                return True

        return False

    def _analyze_text_metadata(self, text: str) -> Dict[str, List[str]]:
        """Phân tích text để trích xuất metadata (giữ nguyên từ code cũ)"""
        text_lower = text.lower().strip()
        detected_metadata = {}

        field_display_names = {
            "main_subject": "Chủ Đề Chính",
            "product_type": "Loại Sản Phẩm",
            "recipient": "Người Nhận",
        }

        for category, items in self.metadata_mappings.items():
            detected_values = []

            for item_name, keywords in items.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        detected_values.append(item_name)
                        break

            if detected_values:
                display_name = field_display_names.get(category, category)
                detected_metadata[display_name] = list(set(detected_values))

        return detected_metadata

    def _format_metadata_description(self, metadata: Dict[str, List[str]]) -> str:
        """Format metadata thành description dạng cấu trúc"""
        if not metadata:
            return ""

        description_parts = []
        description_parts.append("# Thông Tin Sản Phẩm Được Phân Tích")

        for field_name, values in metadata.items():
            values_str = ", ".join(values)
            description_parts.append(f"- **{field_name}**: {values_str}")

        return "\n".join(description_parts)

    def _is_image_url(self, text: str) -> bool:
        """Kiểm tra xem text có phải là URL hình ảnh không"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        text_lower = text.lower().strip()

        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        if re.search(url_pattern, text_lower):
            return any(ext in text_lower for ext in image_extensions)

        return False

    def _is_base64_image(self, text: str) -> bool:
        """Kiểm tra xem text có phải là base64 image không"""
        text = text.strip()
        if text.startswith('data:image/'):
            return True
        if len(text) > 100 and re.match(r'^[A-Za-z0-9+/=]+$', text):
            return True
        return False

    async def determine_search_type(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Xác định loại tìm kiếm và extract filters với AI"""
        query = state["query"].lower()
        original_query = state["query"]
        has_image = state.get("input_image") is not None

        # *** BƯỚC MỚI: Extract filters bằng AI ***
        extracted_filters = await self._extract_filters_with_ai(original_query)
        if extracted_filters:
            state["extracted_filters"] = extracted_filters
            filter_summary = []
            if 'name_store' in extracted_filters:
                filter_summary.append(f"Store: {', '.join(extracted_filters['name_store'])}")
            if 'platform' in extracted_filters:
                filter_summary.append(f"Platform: {', '.join(extracted_filters['platform'])}")
            if 'date_range' in extracted_filters:
                filter_summary.append(f"Date: {extracted_filters['date_range'][0]} - {extracted_filters['date_range'][1]}")
            if 'date_after' in extracted_filters:
                filter_summary.append(f"After: {extracted_filters['date_after']}")
            if 'date_before' in extracted_filters:
                filter_summary.append(f"Before: {extracted_filters['date_before']}")

            state["filter_summary"] = " | ".join(filter_summary)
        else:
            state["extracted_filters"] = {}
            state["filter_summary"] = ""

        # Phân tích metadata từ text query (giữ nguyên)
        detected_metadata = self._analyze_text_metadata(original_query)
        if detected_metadata:
            state["detected_metadata"] = detected_metadata
            state["metadata_description"] = self._format_metadata_description(detected_metadata)
            metadata_context = self._format_metadata_description(detected_metadata)
            state["enriched_query"] = f"{original_query}\n\n{metadata_context}"
        else:
            state["enriched_query"] = original_query

        # Logic xác định search type (giữ nguyên từ code cũ)
        has_image_in_query = self._is_image_url(original_query) or self._is_base64_image(original_query)

        if has_image and any(keyword in query for keyword in ["tương tự", "giống", "similar", "tìm sản phẩm tương tự"]):
            search_type = "image_to_image"
        elif has_image_in_query and any(keyword in query for keyword in ["tương tự", "giống", "similar", "tìm sản phẩm tương tự"]):
            search_type = "url_to_image"
            if self._is_image_url(original_query):
                url_match = re.search(r'https?://[^\s<>"]+', original_query)
                if url_match:
                    state["image_url"] = url_match.group()
                    remaining_text = original_query.replace(state["image_url"], "").strip()
                    state["query"] = remaining_text if remaining_text else "tìm sản phẩm tương tự"
        elif has_image and any(keyword in query for keyword in ["mô tả", "describe", "phân tích", "này là gì"]):
            search_type = "image_to_text"
        elif has_image_in_query and any(keyword in query for keyword in ["mô tả", "describe", "phân tích", "này là gì"]):
            search_type = "url_to_text"
            if self._is_image_url(original_query):
                url_match = re.search(r'https?://[^\s<>"]+', original_query)
                if url_match:
                    state["image_url"] = url_match.group()
                    remaining_text = original_query.replace(state["image_url"], "").strip()
                    state["query"] = remaining_text if remaining_text else "mô tả sản phẩm"
        elif any(keyword in query for keyword in ["tìm hình", "show image", "hình ảnh của"]):
            search_type = "text_to_image"
        elif has_image and len(query.strip()) > 5:
            search_type = "multimodal_search"
        elif has_image_in_query and len(original_query.replace(self._extract_url(original_query), "").strip()) > 5:
            search_type = "multimodal_url_search"
            if self._is_image_url(original_query):
                url_match = re.search(r'https?://[^\s<>"]+', original_query)
                if url_match:
                    state["image_url"] = url_match.group()
                    remaining_text = original_query.replace(state["image_url"], "").strip()
                    state["query"] = remaining_text
        elif has_image_in_query:
            search_type = "url_to_image"
            if self._is_image_url(original_query):
                url_match = re.search(r'https?://[^\s<>"]+', original_query)
                if url_match:
                    state["image_url"] = url_match.group()
                    remaining_text = original_query.replace(state["image_url"], "").strip()
                    if remaining_text:
                        state["query"] = remaining_text
                    else:
                        state["query"] = "tìm sản phẩm tương tự"
        else:
            search_type = "text_to_text"

        state["search_type"] = search_type

        # Log với thông tin filters và metadata
        log_parts = [f"Xác định loại tìm kiếm: {search_type}"]
        if state.get("filter_summary"):
            log_parts.append(f"Filters: {state['filter_summary']}")
        if detected_metadata:
            log_parts.append(f"Metadata: {list(detected_metadata.keys())}")

        state["messages"].append(AIMessage(content=" | ".join(log_parts)))
        return state

    def _extract_url(self, text: str) -> str:
        """Extract URL from text"""
        url_match = re.search(r'https?://[^\s<>"]+', text)
        return url_match.group() if url_match else ""

    async def execute_smart_search(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Thực hiện tìm kiếm thông minh với filters được extract bởi AI"""
        search_type = state["search_type"]
        query = state.get("enriched_query", state["query"])

        # *** SỬ DỤNG FILTERS ĐƯỢC EXTRACT BỞI AI ***
        filters = state.get("extracted_filters", {})

        if search_type == "text_to_image":
            results = search_by_description_tool.invoke({
                "description": query,
                "filters": filters if filters else None
            })
            state["search_results"] = results

        elif search_type == "image_to_image":
            if state.get("input_image"):
                results = search_by_image_tool.invoke({
                    "image_base64": state["input_image"],
                    "filters": filters if filters else None
                })
                state["search_results"] = results
            else:
                state["search_results"] = [{"error": "Không có hình ảnh input"}]

        elif search_type == "url_to_image":
            if state.get("image_url"):
                try:
                    import requests
                    import base64

                    response = requests.get(state["image_url"])
                    if response.status_code == 200:
                        image_base64 = base64.b64encode(response.content).decode('utf-8')
                        results = search_by_image_tool.invoke({
                            "image_base64": image_base64,
                            "filters": filters if filters else None
                        })
                        state["search_results"] = results
                    else:
                        state["search_results"] = [{"error": f"Không thể tải hình ảnh từ URL: {response.status_code}"}]
                except Exception as e:
                    state["search_results"] = [{"error": f"Lỗi khi xử lý URL hình ảnh: {str(e)}"}]
            else:
                state["search_results"] = [{"error": "Không có URL hình ảnh"}]

        elif search_type == "image_to_text":
            if state.get("input_image"):
                description = await self._image_to_text_description(state["input_image"])
                state["search_description"] = description
                enhanced_description = f"{description}\n\n{query}" if state.get("metadata_description") else description
                results = search_by_description_tool.invoke({
                    "description": enhanced_description,
                    "filters": filters if filters else None
                })
                state["search_results"] = results
            else:
                state["search_description"] = "Không có hình ảnh để mô tả"
                state["search_results"] = []

        elif search_type == "url_to_text":
            if state.get("image_url"):
                try:
                    import requests
                    import base64

                    response = requests.get(state["image_url"])
                    if response.status_code == 200:
                        image_base64 = base64.b64encode(response.content).decode('utf-8')
                        description = await self._image_to_text_description(image_base64)
                        state["search_description"] = description
                        enhanced_description = f"{description}\n\n{query}" if state.get(
                            "metadata_description") else description
                        results = search_by_description_tool.invoke({
                            "description": enhanced_description,
                            "filters": filters if filters else None
                        })
                        state["search_results"] = results
                    else:
                        state["search_description"] = f"Không thể tải hình ảnh: {response.status_code}"
                        state["search_results"] = []
                except Exception as e:
                    state["search_description"] = f"Lỗi xử lý hình ảnh: {str(e)}"
                    state["search_results"] = []
            else:
                state["search_description"] = "Không có URL hình ảnh"
                state["search_results"] = []

        elif search_type == "multimodal_search":
            if state.get("input_image"):
                search_text = state["query"]
                if state.get("metadata_description"):
                    search_text = f"{state['query']}\n\nContext: {state['metadata_description']}"

                results = search_multimodal_tool.invoke({
                    "text": search_text,
                    "image_base64": state["input_image"],
                    "top_k": 100,
                    "filters": filters if filters else None
                })
                state["search_results"] = results
            else:
                state["search_results"] = [{"error": "Không có hình ảnh input cho multimodal search"}]

        elif search_type == "multimodal_url_search":
            if state.get("image_url"):
                try:
                    import requests
                    import base64

                    response = requests.get(state["image_url"])
                    if response.status_code == 200:
                        image_base64 = base64.b64encode(response.content).decode('utf-8')
                        search_text = state["query"]
                        if state.get("metadata_description"):
                            search_text = f"{state['query']}\n\nContext: {state['metadata_description']}"

                        results = search_multimodal_tool.invoke({
                            "text": search_text,
                            "image_base64": image_base64,
                            "top_k": 100,
                            "filters": filters if filters else None
                        })
                        state["search_results"] = results
                    else:
                        state["search_results"] = [{"error": f"Không thể tải hình ảnh từ URL: {response.status_code}"}]
                except Exception as e:
                    state["search_results"] = [{"error": f"Lỗi khi xử lý URL trong multimodal search: {str(e)}"}]
            else:
                state["search_results"] = [{"error": "Không có URL hình ảnh cho multimodal search"}]

        else:  # text_to_text with metadata enhancement
            results = search_by_description_tool.invoke({"description": query, "filters": filters if filters else None})
            state["search_results"] = results

        # Log kết quả với thông tin metadata
        metadata_info = ""
        if state.get("detected_metadata"):
            metadata_count = len(state["detected_metadata"])
            metadata_info = f" (với {metadata_count} metadata fields)"

        filter_info = ""
        if filters:
            filter_info = f" (với {len(filters)} filters)"

        state["messages"].append(
            AIMessage(content=f"Hoàn thành {search_type} search với {len(state.get('search_results', []))} kết quả{metadata_info}{filter_info}"))
        return state

    async def _image_to_text_description(self, image_base64: str) -> str:
        """Convert image to text description using vision model"""
        try:
            prompt = "Mô tả chi tiết sản phẩm trong hình ảnh này, bao gồm màu sắc, kiểu dáng, và đặc điểm nổi bật."

            # Sử dụng vision model để phân tích hình ảnh
            messages = [
                HumanMessage(content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ])
            ]

            response = await self.vision_llm.ainvoke(messages)
            return response.content
        except Exception as e:
            return f"Không thể phân tích hình ảnh: {str(e)}"

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process smart search - determine type, analyze metadata and execute"""
        state = await self.determine_search_type(state)
        return await self.execute_smart_search(state)

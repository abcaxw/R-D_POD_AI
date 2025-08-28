import psycopg2
import os
import json
import requests
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from enum import Enum
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta
import uuid
import numpy as np
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import time
from embedding_service import EmbeddingService
import ollama
import torch
import re
import concurrent.futures
from threading import Lock
import queue
import threading
import io

# Configuration
class ModelProvider(Enum):
    QWEN_VL = "qwen_vl"

@dataclass
class ProductLabel:
    """Cấu trúc label sản phẩm theo file PDF"""
    image_url: str
    image_recipient: List[str]
    target_audience: List[str]
    usage_purpose: List[str]
    occasion: List[str]
    niche_theme: List[str]
    sentiment_tone: List[str]
    message_type: List[str]
    personalization_type: List[str]
    product_type: List[str]
    placement_display_context: List[str]
    design_style: List[str]
    color_aesthetic: List[str]
    trademark_level: str
    main_subject: List[str]
    text: List[str]


@dataclass
class ProductRecord:
    """Cấu trúc record để insert vào Milvus"""
    id_sanpham: str
    image: str
    date: str
    like: str
    comment: str
    share: str
    link_redirect: str
    platform: str
    name_store: str
    description: str
    metadata: dict
    image_vector: List[float]
    description_vector: List[float]


class StreamingProductPipeline:
    """Pipeline streaming: Crawl → Label → Embedding → Insert ngay lập tức"""

    def __init__(self,
                 db_config: Dict[str, str],
                 qwen_model: str = "qwen2.5vl:latest",
                 milvus_host: str = "10.10.4.25",
                 milvus_port: str = "19530",
                 max_workers: int = 1,
                 insert_batch_size: int = 5):
        """
        Khởi tạo streaming pipeline

        Args:
            db_config: Cấu hình database PostgreSQL
            qwen_model: Qwen2.5-VL model name
            milvus_host: Milvus host
            milvus_port: Milvus port
            max_workers: Số thread xử lý song song
            insert_batch_size: Số records trong mỗi batch insert
        """
        # Database config
        self.db_config = db_config
        self.db_connection = None

        # AI Labeler
        self.qwen_model = qwen_model
        self.max_workers = max_workers
        self.insert_batch_size = insert_batch_size
        self._lock = Lock()

        # Embedding service
        print("🔧 Khởi tạo Jina v4 Embedding Service...")
        self.embedding_service = EmbeddingService()
        self.embedding_dim = self.embedding_service.embedding_dim

        # Milvus config
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = "product_collection_v4"
        self.collection = None

        # Cache và queues cho streaming
        self.image_cache = {}
        self.cache_lock = Lock()
        
        # Queue cho streaming insert
        self.ready_records_queue = queue.Queue()
        self.insert_stats_lock = Lock()
        
        # Statistics tracking
        self.stats = {
            'processed_count': 0,
            'inserted_count': 0,
            'failed_count': 0,
            'insert_batches': 0,
            'inserted_ids': [],
            'failed_records': []
        }

        # Log thông tin
        model_info = self.embedding_service.get_model_info()
        print(f"🤖 Embedding Model: {model_info['model_name']}")
        print(f"📊 Embedding Dimensions: {model_info['embedding_dimension']}")
        print(f"🔧 Device: {model_info['device']}")
        print(f"🦙 Qwen2.5-VL Model: {self.qwen_model}")
        print(f"🚀 Max Workers: {self.max_workers}")
        print(f"📦 Insert Batch Size: {self.insert_batch_size}")

        # Initialize connections
        self._connect_db()
        self._connect_milvus()
        self._setup_collection()

    def _connect_db(self) -> bool:
        """Kết nối đến PostgreSQL database"""
        try:
            self.db_connection = psycopg2.connect(**self.db_config)
            print("✅ Kết nối PostgreSQL thành công")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối database: {e}")
            return False

    def _connect_milvus(self):
        """Kết nối tới Milvus"""
        try:
            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port
            )
            print("✅ Kết nối Milvus thành công")
        except Exception as e:
            raise Exception(f"❌ Lỗi kết nối Milvus: {str(e)}")

    def _create_collection_schema(self):
        """Tạo schema cho collection"""
        fields = [
            FieldSchema(name="id_sanpham", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=100),
            FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="description_vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="image", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=5000),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="date", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="like", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="comment", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="share", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="link_redirect", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="platform", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="name_store", dtype=DataType.VARCHAR, max_length=500)
        ]

        schema = CollectionSchema(
            fields=fields,
            description=f"Streaming collection với embedding {self.embedding_dim}D"
        )
        return schema

    def _setup_collection(self):
        """Tạo hoặc load collection"""
        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                print(f"✅ Load collection '{self.collection_name}' thành công")
            else:
                schema = self._create_collection_schema()
                self.collection = Collection(self.collection_name, schema)
                self._create_indexes()
                print(f"✅ Tạo collection '{self.collection_name}' thành công với {self.embedding_dim}D vectors")

            self.collection.load()

        except Exception as e:
            raise Exception(f"❌ Lỗi setup collection: {str(e)}")

    def _create_indexes(self):
        """Tạo index cho vector fields"""
        nlist = min(self.embedding_dim, 1024)

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": nlist}
        }

        self.collection.create_index(
            field_name="image_vector",
            index_params=index_params,
            index_name="image_vector_index"
        )

        self.collection.create_index(
            field_name="description_vector",
            index_params=index_params,
            index_name="description_vector_index"
        )
        print(f"✅ Tạo indexes thành công với nlist={nlist}")

    # === DUPLICATE CHECK METHODS ===
    def check_ids_exist_batch(self, id_list: List[str]) -> Dict[str, bool]:
        """Kiểm tra nhiều ID cùng lúc"""
        try:
            if not id_list:
                return {}

            batch_size = 100
            all_results = {}

            for i in range(0, len(id_list), batch_size):
                batch_ids = id_list[i:i + batch_size]
                id_conditions = [f'id_sanpham == "{id_val}"' for id_val in batch_ids]
                expr = " or ".join(id_conditions)

                results = self.collection.query(
                    expr=expr,
                    output_fields=["id_sanpham"],
                    limit=len(batch_ids)
                )

                existing_ids = {result["id_sanpham"] for result in results}
                batch_results = {id_val: id_val in existing_ids for id_val in batch_ids}
                all_results.update(batch_results)

            return all_results

        except Exception as e:
            print(f"⚠️  Lỗi kiểm tra batch IDs: {str(e)}")
            return {id_val: False for id_val in id_list}

    def filter_existing_records(self, raw_data_list: List[Dict[str, Any]]) -> tuple:
        """Lọc bỏ các record đã tồn tại"""
        try:
            if not raw_data_list:
                return [], [], 0

            print(f"🔍 Kiểm tra trùng lặp cho {len(raw_data_list)} records...")

            id_list = [record.get('id_sanpham', '') for record in raw_data_list if record.get('id_sanpham')]

            if not id_list:
                return raw_data_list, [], 0

            existence_map = self.check_ids_exist_batch(id_list)

            new_records = []
            existing_records = []

            for record in raw_data_list:
                id_sanpham = record.get('id_sanpham', '')
                if id_sanpham and existence_map.get(id_sanpham, False):
                    existing_records.append(record)
                else:
                    new_records.append(record)

            duplicate_count = len(existing_records)

            print(f"✅ Kết quả kiểm tra:")
            print(f"   📦 Records mới: {len(new_records)}")
            print(f"   🔄 Records trùng lặp: {duplicate_count}")

            return new_records, existing_records, duplicate_count

        except Exception as e:
            print(f"❌ Lỗi khi lọc records: {str(e)}")
            return raw_data_list, [], 0

    # === CRAWL DATA METHODS ===
    def crawl_data_by_date_range(self, start_date: str, end_date: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Crawl data từ database theo khoảng thời gian"""
        if not self.db_connection:
            if not self._connect_db():
                return []

        try:
            cursor = self.db_connection.cursor()

            query = """
            SELECT 
                COALESCE(product_id::text, CONCAT('SP_', SUBSTRING(MD5(RANDOM()::text), 1, 8))) as id_sanpham,
                COALESCE(image, '') as image,
                COALESCE(CAST(published_at AS text), CAST(NOW() AS text)) as date,
                ROUND(impression * (0.01 + RANDOM() * 0.05))::int::text as like,
                ROUND(impression * (0.001 + RANDOM() * 0.01))::int::text as comment,
                ROUND(impression * (0.0005 + RANDOM() * 0.005))::int::text as share,
                COALESCE(link, '') as link_redirect,
                COALESCE(gp_code, 'Website') as platform,
                COALESCE(store, 'unknown') as name_store,
                COALESCE(title, '') as title,
                COALESCE(spend::text, '0') as spend,
                COALESCE(clicks::text, '0') as clicks,
                COALESCE(unique_atc::text, '0') as unique_atc,
                COALESCE(impression::text, '0') as impression,
                COALESCE(unique_clicks::text, '0') as unique_clicks,
                COALESCE(reach::text, '0') as reach,
                COALESCE(quantity::text, '0') as quantity
            FROM ai_craw.product_marketing_summary
            WHERE published_at BETWEEN %s AND %s
            AND image IS NOT NULL 
            AND image != ''
            ORDER BY published_at DESC
            LIMIT %s
            """


            cursor.execute(query, (start_date, end_date, limit))
            columns = [desc[0] for desc in cursor.description]
            results = []

            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                results.append(row_dict)

            cursor.close()
            print(f"✅ Crawl được {len(results)} records từ {start_date} đến {end_date}")
            return results

        except Exception as e:
            print(f"❌ Lỗi khi crawl data: {e}")
            return []

    # === QWEN2.5-VL LABELING METHODS ===
    def _create_qwen_prompt(self) -> str:
        """Prompt cho Qwen2.5-VL"""
        return """# 🎯 Advanced Product Analysis Prompt for AI Vision Models

You are an expert product analyst with deep understanding of consumer behavior, market segmentation, and product positioning. Your task is to analyze product images with sophisticated reasoning and comprehensive market insight.

---

## 🧠 Analysis Methodology

**Think Step by Step:**
1. **Initial Visual Assessment** - What do you see? What's the primary product?
2. **Context Clues Analysis** - What visual elements suggest target demographics?
3. **Market Positioning** - How is this product positioned in the market?
4. **Consumer Psychology** - What emotional needs does this address?
5. **Niche Market Identification** - What specific communities would connect with this?

---

## 📋 Comprehensive Labeling Framework

### 1. **Image Recipient Analysis** 
*Who is the intended receiver of this gift/product?*

**Reasoning Process:**
- Analyze visual symbols, colors, themes, and messaging
- Consider age indicators, gender associations, role representations
- Look for cultural, professional, or lifestyle markers

**Flexible Categories:** Mom, Dad, Wife, Husband, Son, Daughter, Kids, Grandma, Grandpa, Girlfriend, Boyfriend, Sister, Brother, Teacher, Coach, Boss, Colleague, Friend, Pet Owner, Veteran, Nurse, Doctor, etc.

### 2. **Target Audience Identification**
*Who is likely to PURCHASE this product?*

**Deep Analysis:**
- Who has the emotional motivation to buy this?
- What relationship dynamics are at play?
- Consider purchasing power and decision-making patterns
- Analyze the emotional story this product tells

**Think Beyond Basic Demographics:** Consider specific communities, professions, hobbies, life stages, and relationships.

### 3. **Usage Purpose - Multi-Dimensional Analysis**
*Analyze ALL potential uses, not just the obvious ones*

**Framework:**
- **Primary Function:** What is the product's main utility?
- **Emotional Function:** What emotional need does it serve?
- **Social Function:** How does it express identity or relationships?
- **Situational Function:** When and where would it be used?

**Categories to Consider:**
- **Gift Giving:** Present, Memorial, Celebration, Milestone Recognition
- **Home Applications:** Bedroom Comfort, Living Space Decor, Kitchen Utility, Bathroom Personal Care
- **Personal Expression:** Daily Wear, Professional Image, Hobby Display, Identity Statement
- **Functional Use:** Work Tools, Hobby Equipment, Health & Wellness, Organization
- **Seasonal/Temporal:** Holiday Specific, Weather Related, Life Stage Specific

### 4. **Occasion Analysis - Think Broader**
*When would someone give or use this product?*

**Consider:**
- Traditional holidays and celebrations
- Personal milestones and achievements
- Relationship moments and anniversaries
- Professional recognition events
- Seasonal and cultural occasions
- "Just because" moments of appreciation

### 5. **Niche/Theme - Deep Market Segmentation**
*What specific communities, interests, or identities does this serve?*

**Advanced Segmentation Thinking:**
- **Lifestyle Niches:** Fitness enthusiasts, outdoor adventurers, homebodies, minimalists
- **Professional Communities:** Healthcare workers, teachers, first responders, entrepreneurs
- **Hobby & Interest Groups:** Pet lovers, gamers, book readers, crafters, musicians
- **Life Stages:** New parents, empty nesters, students, retirees
- **Values & Beliefs:** Environmental consciousness, family values, spiritual beliefs
- **Cultural & Social:** Military families, multicultural households, LGBTQ+ community

### 6. **Sentiment/Tone Analysis**
*What emotional resonance does this product create?*

**Emotional Intelligence Assessment:**
- **Positive Emotions:** Love, Joy, Pride, Comfort, Inspiration, Humor, Nostalgia
- **Relationship Dynamics:** Appreciation, Gratitude, Support, Celebration
- **Personal Identity:** Confidence, Self-Expression, Belonging, Achievement
- **Comfort & Security:** Peace, Warmth, Safety, Familiarity

### 7. **Message Type Classification**
*How does the product communicate?*

- **No Text/Visual Only:** Pure imagery, symbols, or artistic expression
- **Direct Quotes:** Inspirational sayings, humorous phrases, emotional statements
- **Personal Signature:** "From [Name] to [Name]" style messages
- **Identity Declaration:** "World's Best Mom," profession-based titles
- **Symbolic Communication:** Icons, metaphors, cultural references

### 8. **Personalization Analysis**
*How customizable or personal is this product?*

- **Name Personalization:** Can add specific names
- **Photo Integration:** Custom photo uploads
- **Text Customization:** Custom messages or quotes
- **Date/Milestone:** Specific dates or achievements
- **Generic/Universal:** One-size-fits-all messaging

### 9. **Product Type - Comprehensive Categorization**
*What exactly is this product and its variations?*

**Think Holistically:** Consider size variations, material options, related products in the same category.

### 10. **Placement/Display Context Analysis**
*Where would this product live in someone's life?*

**Environmental Psychology:**
- **Personal Spaces:** Bedroom, bathroom, personal workspace
- **Social Spaces:** Living room, kitchen, dining areas
- **Professional Settings:** Office desk, workplace display
- **Mobile/Portable:** Car, travel, everyday carry
- **Decorative Integration:** Wall display, shelf accent, centerpiece

### 11. **Design Style - Aesthetic Intelligence**
*What design language and aesthetic choices are employed?*

**Style Analysis:**
- **Cultural Influences:** Vintage, retro, modern, traditional
- **Artistic Movements:** Minimalist, maximalist, bohemian, industrial
- **Technical Execution:** Hand-drawn, digital art, photography, 3D rendering
- **Emotional Design:** Whimsical, elegant, bold, subtle, playful

### 12. **Color Aesthetic - Psychological Impact**
*What do the color choices communicate?*

**Color Psychology:**
- Consider cultural associations
- Analyze emotional impact
- Understand demographic preferences
- Recognize seasonal or thematic relevance

### 13. **Trademark Level Assessment**
*How much does this resemble existing brands or intellectual property?*

**Evaluation Scale:**
- **No TM:** Completely original design
- **Slight TM:** Minor resemblance to existing brands
- **TM Resemblance:** Clear similarity to trademarked content
- **Direct TM:** Obvious trademark usage

### 14. **Main Subject - Visual Elements Printed/Displayed on Product UPDATED**
*What specific objects, images, or symbols are printed, displayed, or depicted ON the product itself?*

**Critical Focus: PRINTED/VISUAL CONTENT ANALYSIS**
- **Look for visual elements that are printed, embroidered, engraved, or displayed ON the product surface**

**Detailed Analysis Framework:**
- **Natural Elements:** Moon, stars, sun, flowers (roses, sunflowers, daisies), trees, leaves, mountains, ocean waves, clouds, rainbows
- **Animals & Creatures:** Dogs, cats, birds, butterflies, lions, elephants, unicorns, dragons, fish, deer
- **People & Characters:** Family portraits, cartoon characters, silhouettes, faces, hands, children, couples
- **Objects & Items:** Hearts, crosses, anchors, keys, crowns, musical notes, cars, houses, books, tools
- **Symbols & Icons:** Religious symbols, zodiac signs, flags, badges, logos, geometric shapes, tribal patterns
- **Abstract Art:** Mandala patterns, geometric designs, watercolor splashes, brush strokes, digital art

**Analysis Questions:**
1. What is the MAIN visual element printed on this product?
2. Who is the person in the picture on the product? (if any)
3. Are there SECONDARY visual elements supporting the main design?
4. What style are these visual elements rendered in? (realistic, cartoon, abstract, minimalist)
5. Do the visual elements tell a story or convey a specific message?
6. Are there multiple visual elements creating a scene or composition?

### 15. **Text Analysis - Complete Transcription**
*Record ALL visible text with context understanding*

- Capture exact wording
- Note text hierarchy and emphasis
- Understand linguistic tone and style
- Consider cultural or demographic language choices

---

## 🎯 Output Requirements

**Critical Instructions:**
1. **Think Before You Label:** Spend mental effort analyzing, don't just pattern-match
2. **Be Specific:** Avoid generic terms when specific ones better capture the niche
3. **Multiple Perspectives:** Consider different ways to interpret the same product
4. **Cultural Sensitivity:** Recognize diverse cultural contexts and preferences
5. **Market Reality:** Base analysis on real consumer behavior patterns
6. **MAIN SUBJECT FOCUS:** Always analyze what's PRINTED/DISPLAYED on the product, NOT the product itself

**Response Format:**
Return ONLY the JSON structure below, but ensure each field reflects deep analytical thinking:

```json
{
  "image_recipient": ["specific_recipient_1", "specific_recipient_2"],
  "target_audience": ["specific_buyer_1", "specific_buyer_2"], 
  "usage_purpose": ["purpose_1", "purpose_2", "purpose_3"],
  "occasion": ["occasion_1", "occasion_2"],
  "niche_theme": ["specific_niche_1", "specific_niche_2"],
  "sentiment_tone": ["tone_1", "tone_2"],
  "message_type": ["message_type"],
  "personalization_type": ["personalization_type"],
  "product_type": ["product_type"],
  "placement_display_context": ["context_1", "context_2"],
  "design_style": ["style_1", "style_2"],
  "color_aesthetic": ["color_1", "color_2"],
  "trademark_level": "assessment",
  "main_subject": ["printed_element_1", "printed_element_2", "printed_element_3"],
  "text": ["exact_text_1", "exact_text_2"]
}
```

**Quality Standards:**
- Each label should reflect genuine insight, not surface-level observation
- Consider multiple valid interpretations when they exist
- Prioritize specificity over generality
- Ensure labels would be actionable for marketing and product development
- Think like a consumer psychologist, not just a visual descriptor
- For main_subject: Focus ONLY on printed/visual content, not the product base

---

## 🔍 Self-Check Questions

Before finalizing your analysis, ask:
1. "Would someone from this niche community recognize this product as 'for them'?"
2. "Do my labels capture the unique positioning of this product?"
3. "Am I thinking beyond obvious categories to find deeper market segments?"
4. "Would a marketer find these labels useful for targeting?"
5. "Have I considered cultural and demographic diversity in my analysis?"
6. "Am I analyzing what's PRINTED ON the product, not the product itself?"


Remember: The goal is sophisticated market intelligence, not just visual description."""


    def _download_image_cached(self, url: str) -> bytes:
        """Download image với caching"""
        with self.cache_lock:
            if url in self.image_cache:
                return self.image_cache[url]

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            image_bytes = response.content

            with self.cache_lock:
                self.image_cache[url] = image_bytes

            return image_bytes
        except Exception as e:
            raise Exception(f"Lỗi download ảnh: {str(e)}")

    def _extract_json_from_qwen_response(self, content: str) -> Dict:
        """Extract JSON từ Qwen2.5-VL response"""
        try:
            content = content.strip()
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)

            raise Exception("No valid JSON found in response")

        except Exception as e:
            print(f"⚠️  JSON parsing error: {str(e)}")
            raise Exception(f"Failed to parse JSON: {str(e)}")

    def _smart_resize_image(self, image_bytes: bytes, max_width: int = 1024, max_height: int = 1024, quality: int = 85) -> bytes:
        """
        Smart resize ảnh để giảm dung lượng mà vẫn giữ chất lượng
        
        Args:
            image_bytes: Dữ liệu ảnh dạng bytes
            max_width: Chiều rộng tối đa (default: 1024px - phù hợp cho AI vision)
            max_height: Chiều cao tối đa (default: 1024px)
            quality: Chất lượng JPEG (default: 85)
        
        Returns:
            bytes: Dữ liệu ảnh đã được tối ưu
        """
        try:
            # Mở ảnh từ bytes
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Lấy kích thước gốc
                original_width, original_height = img.size
                original_size = len(image_bytes)
                
                print(f"📸 Ảnh gốc: {original_width}x{original_height} - {original_size/1024:.1f} KB")
                
                # Kiểm tra xem có cần resize không
                if original_width > max_width or original_height > max_height:
                    # Tính tỷ lệ để giữ nguyên aspect ratio
                    ratio = min(max_width/original_width, max_height/original_height)
                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
                    
                    # Resize với thuật toán LANCZOS (chất lượng cao)
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    print(f"🔄 Resize xuống: {new_width}x{new_height}")
                else:
                    img_resized = img.copy()
                    print("✅ Kích thước phù hợp, không cần resize")
                
                # Chuyển sang RGB nếu cần (để hỗ trợ JPEG)
                if img_resized.mode in ('RGBA', 'P'):
                    # Nếu có alpha channel, tạo background trắng
                    if img_resized.mode == 'RGBA':
                        background = Image.new('RGB', img_resized.size, (255, 255, 255))
                        background.paste(img_resized, mask=img_resized.split()[-1])
                        img_resized = background
                    else:
                        img_resized = img_resized.convert('RGB')
                
                # Lưu vào BytesIO với tối ưu hóa
                output_buffer = io.BytesIO()
                img_resized.save(output_buffer, 
                            format='JPEG',
                            quality=quality,
                            optimize=True,
                            progressive=True)
                
                optimized_bytes = output_buffer.getvalue()
                optimized_size = len(optimized_bytes)
                
                # Tính phần trăm giảm dung lượng
                reduction = ((original_size - optimized_size) / original_size) * 100
                print(f"💾 Ảnh tối ưu: {optimized_size/1024:.1f} KB - Giảm {reduction:.1f}%")
                
                return optimized_bytes
                
        except Exception as e:
            print(f"⚠️ Lỗi khi tối ưu ảnh: {e}")
            # Nếu có lỗi, trả về ảnh gốc
            return image_bytes

    def _analyze_with_qwen_vl(self, image_url: str) -> Dict:
        """Phân tích với Qwen2.5-VL model với Smart Resize"""
        try:
            print(f"🔍 Đang phân tích: {image_url}")
            
            # Download ảnh
            image_bytes = self._download_image_cached(image_url)
            print(f"📥 Tải ảnh thành công: {len(image_bytes)/1024:.1f} KB")
            
            # Smart resize để tối ưu hóa
            optimized_image_bytes = self._smart_resize_image(
                image_bytes, 
                max_width=512,    # Kích thước phù hợp cho vision model
                max_height=512, 
                quality=90         # Chất lượng cao cho AI analysis
            )
            
            # Encode base64
            image_base64 = base64.b64encode(optimized_image_bytes).decode('utf-8')
            
            # Tạo prompt
            prompt = self._create_qwen_prompt()
            
            print("🤖 Đang gửi cho Qwen2.5-VL...")
            
            # Gửi request với cấu hình tối ưu
            response = ollama.generate(
                model=self.qwen_model,
                prompt=prompt,
                images=[image_base64],
                options={
                    'temperature': 0.0,
                    'top_p': 0.9,
                    'num_ctx': 4096,
                    'num_predict': 1024,
                    'num_gpu': -1,        # Force sử dụng GPU
                    'main_gpu': 0,
                    'gpu_layers': -1,     # Tất cả layers lên GPU
                    'num_thread': 8,      # Số thread CPU hỗ trợ
                    'num_batch': 512,     # Batch size
                    'low_vram': False,    # Không giới hạn VRAM
                    'f16_kv': True,       # FP16 cho cache
                    'use_mmap': True,     # Memory mapping
                    'mlock': True,        # Lock model trong RAM
                }
            )
            
            content = response['response'].strip()
            result = self._extract_json_from_qwen_response(content)
            
            print("✅ Phân tích hoàn thành!")
            return result
            
        except Exception as e:
            print(f"❌ Qwen2.5-VL error for {image_url}: {str(e)}")
            raise Exception(f"Qwen2.5-VL analysis failed: {str(e)}")

    def label_image_with_qwen(self, image_url: str) -> ProductLabel:
        """Đánh label cho 1 ảnh sản phẩm với Qwen2.5-VL"""
        try:
            result = self._analyze_with_qwen_vl(image_url)

            return ProductLabel(
                image_url=image_url,
                image_recipient=result.get('image_recipient', []),
                target_audience=result.get('target_audience', []),
                usage_purpose=result.get('usage_purpose', []),
                occasion=result.get('occasion', []),
                niche_theme=result.get('niche_theme', []),
                sentiment_tone=result.get('sentiment_tone', []),
                message_type=result.get('message_type', []),
                personalization_type=result.get('personalization_type', []),
                product_type=result.get('product_type', []),
                placement_display_context=result.get('placement_display_context', []),
                design_style=result.get('design_style', []),
                color_aesthetic=result.get('color_aesthetic', []),
                trademark_level=result.get('trademark_level', 'No TM'),
                main_subject=result.get('main_subject', []),
                text=result.get('text', [])
            )

        except Exception as e:
            print(f"❌ Labeling failed for {image_url}: {str(e)}")
            raise Exception(f"Image labeling failed: {str(e)}")

    def _generate_vectors(self, text: str, image_url: str = None) -> tuple:
        """Tạo embedding vectors"""
        image_vector, text_vector = self.embedding_service._generate_vectors(
            text=text,
            image_url=image_url
        )
        return image_vector, text_vector

    def _create_description(self, label: ProductLabel) -> str:
        """Tạo description markdown"""
        def format_list(items: List[str]) -> str:
            if not items:
                return "Unknown"
            return ", ".join(items[:3])

        description = f"""# Mô Tả Sản Phẩm

## Thông Tin Cơ Bản
- **Chủ Thể Chính**: {format_list(label.main_subject)}
- **Loại Sản Phẩm**: {format_list(label.product_type)}
- **Mức Độ Thương Hiệu**: {label.trademark_level}

## Đối Tượng & Mục Đích
- **Người Nhận**: {format_list(label.image_recipient)}
- **Người Mua**: {format_list(label.target_audience)}
- **Mục Đích Sử Dụng**: {format_list(label.usage_purpose)}
- **Dịp Sử Dụng**: {format_list(label.occasion)}

## Phân Loại Sản Phẩm
- **Chủ Đề/Ngách**: {format_list(label.niche_theme)}
- **Cảm Xúc/Tông Điệu**: {format_list(label.sentiment_tone)}
- **Loại Thông Điệp**: {format_list(label.message_type)}
- **Cá Nhân Hóa**: {format_list(label.personalization_type)}
- **Nội Dung Chữ In**: {format_list(label.text)}

## Thiết Kế & Trưng Bày
- **Bối Cảnh Trưng Bày**: {format_list(label.placement_display_context)}
- **Phong Cách Thiết Kế**: {format_list(label.design_style)}
- **Thẩm Mỹ Màu Sắc**: {format_list(label.color_aesthetic)}

## Tóm Tắt
{format_list(label.product_type)} này có hình ảnh là một {format_list(label.main_subject)} được thiết kế dành cho {format_list(label.image_recipient)}, phù hợp cho {format_list(label.occasion)} với phong cách {format_list(label.design_style)} và tông màu {format_list(label.color_aesthetic)}.
"""
        return description

    # === STREAMING INSERT METHODS ===
    def _streaming_insert_worker(self):
        """Background worker để insert records liên tục"""
        batch_buffer = []
        
        while True:
            try:
                # Lấy record từ queue (timeout 5s)
                try:
                    record = self.ready_records_queue.get(timeout=5)
                    if record is None:  # Signal để kết thúc
                        break
                    batch_buffer.append(record)
                except queue.Empty:
                    # Timeout - insert batch hiện tại nếu có
                    if batch_buffer:
                        self._insert_batch_immediate(batch_buffer)
                        batch_buffer = []
                    continue

                # Insert khi đủ batch size hoặc khi receive None signal
                if len(batch_buffer) >= self.insert_batch_size:
                    self._insert_batch_immediate(batch_buffer)
                    batch_buffer = []

            except Exception as e:
                print(f"❌ Lỗi trong streaming insert worker: {e}")

        # Insert batch cuối cùng nếu có
        if batch_buffer:
            self._insert_batch_immediate(batch_buffer)

    def _insert_batch_immediate(self, records: List[ProductRecord]):
        """Insert batch records ngay lập tức vào Milvus"""
        try:
            if not records:
                return

            # Chuẩn bị data cho batch insert
            ids = [record.id_sanpham for record in records]
            image_vectors = [record.image_vector for record in records]
            description_vectors = [record.description_vector for record in records]
            images = [record.image for record in records]
            descriptions = [record.description for record in records]
            metadatas = [record.metadata for record in records]
            dates = [record.date for record in records]
            likes = [record.like for record in records]
            comments = [record.comment for record in records]
            shares = [record.share for record in records]
            link_redirects = [record.link_redirect for record in records]
            platforms = [record.platform for record in records]
            name_stores = [record.name_store for record in records]

            data = [
                ids, image_vectors, description_vectors, images, descriptions, metadatas,
                dates, likes, comments, shares, link_redirects, platforms, name_stores
            ]

            # Insert vào Milvus
            mr = self.collection.insert(data)
            self.collection.flush()

            # Update statistics thread-safe
            with self.insert_stats_lock:
                self.stats['inserted_count'] += len(records)
                self.stats['insert_batches'] += 1
                self.stats['inserted_ids'].extend(ids)

            print(f"💾 ✅ Inserted batch: {len(records)} records (Total: {self.stats['inserted_count']})")

        except Exception as e:
            print(f"❌ Lỗi insert batch: {str(e)}")
            with self.insert_stats_lock:
                self.stats['failed_count'] += len(records)
                for record in records:
                    self.stats['failed_records'].append(record.id_sanpham)
    def save_product_to_db(self, record):
        """Save ProductRecord to ai_craw.data_label table in database"""
        try:
            # Kết nối DB
            remote_db_connection = psycopg2.connect(
                host='45.79.189.110',
                database='ai_db',
                user='ai_engineer',
                password='StrongPassword123',
                port=5432
            )
            cursor = remote_db_connection.cursor()

            # Tạo schema nếu chưa có
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ai_craw;")

            # Tạo bảng nếu chưa có (bổ sung date_created để khớp với insert)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_craw.data_label (
                    id SERIAL PRIMARY KEY,
                    id_sanpham VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    date_created TIMESTAMP,
                    platform VARCHAR(200),
                    name_store VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tạo index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_label_id_sanpham 
                ON ai_craw.data_label(id_sanpham);
            """)

            # Insert/Update record
            cursor.execute("""
                INSERT INTO ai_craw.data_label (
                    id_sanpham, description, date_created, platform, name_store
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id_sanpham) DO UPDATE SET
                    description = EXCLUDED.description,
                    date_created = EXCLUDED.date_created,
                    platform = EXCLUDED.platform,
                    name_store = EXCLUDED.name_store,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                record.id_sanpham,
                record.description,
                record.date,
                record.platform,
                record.name_store
            ))

            remote_db_connection.commit()
            cursor.close()
            remote_db_connection.close()

            print(f"✅ Database saved: {record.id_sanpham}")
            return True

        except Exception as e:
            print(f"❌ Error saving to remote database: {e}")
            try:
                if 'remote_db_connection' in locals():
                    remote_db_connection.rollback()
                    remote_db_connection.close()
            except:
                pass
            return False
    def _process_and_queue_record(self, raw_data: Dict[str, Any]) -> bool:
        """Xử lý record và đưa vào queue để insert"""
        try:
            start = time.time()
            image_url = raw_data.get('image', '')
            if not image_url:
                return False

            # 1. Label với Qwen2.5-VL
            label = self.label_image_with_qwen(image_url)
            metadata = asdict(label)

            # 2. Tạo description
            description = self._create_description(label)


            # 3. Generate vectors
            image_vector, description_vector = self._generate_vectors(description, image_url)

            # 4. Tạo ProductRecord
            record = ProductRecord(
                id_sanpham=raw_data.get('id_sanpham', f"SP_{uuid.uuid4().hex[:8]}"),
                image_vector=image_vector,
                description_vector=description_vector,
                image=image_url,
                description=description,
                metadata=metadata,
                date=raw_data.get('date', ''),
                like=raw_data.get('like', '0'),
                comment=raw_data.get('comment', '0'),
                share=raw_data.get('share', '0'),
                link_redirect=raw_data.get('link_redirect', ''),
                platform=raw_data.get('platform', ''),
                name_store=raw_data.get('name_store', '')
            )
            # đẩy dữ liệu lên database
            self.save_product_to_db(record)
            # 5. Đưa record vào queue để insert
            self.ready_records_queue.put(record)
            
            print(f"End insert {time.time() - start}")

            # Update processed count
            with self.insert_stats_lock:
                self.stats['processed_count'] += 1

            return True

        except Exception as e:
            print(f"❌ Lỗi xử lý record {raw_data.get('id_sanpham', 'unknown')}: {str(e)}")
            with self.insert_stats_lock:
                self.stats['failed_count'] += 1
                self.stats['failed_records'].append(raw_data.get('id_sanpham', 'unknown'))
            return False

    # === STREAMING PIPELINE METHODS ===
    def run_streaming_pipeline(self, start_date: str, end_date: str, limit: int = 1000) -> Dict[str, Any]:
        """
        Chạy streaming pipeline: Process + Insert liên tục

        Args:
            start_date: Ngày bắt đầu (YYYY-MM-DD)
            end_date: Ngày kết thúc (YYYY-MM-DD)
            limit: Số lượng record tối đa

        Returns:
            Dictionary chứa thống kê kết quả
        """
        print("🚀 BẮT ĐẦU STREAMING PIPELINE VỚI QWEN2.5-VL")
        print(f"📅 Thời gian: {start_date} → {end_date}")
        print(f"📊 Giới hạn: {limit} records")
        print(f"🤖 Model: {self.qwen_model}")
        print(f"⚡ Workers: {self.max_workers}")
        print(f"📦 Insert batch size: {self.insert_batch_size}")
        print("-" * 80)

        start_time = time.time()

        # Reset statistics
        with self.insert_stats_lock:
            self.stats = {
                'start_time': datetime.now().isoformat(),
                'crawled_count': 0,
                'duplicate_count': 0,
                'processed_count': 0,
                'inserted_count': 0,
                'failed_count': 0,
                'insert_batches': 0,
                'skipped_duplicates': [],
                'inserted_ids': [],
                'failed_records': [],
                'total_time_seconds': 0
            }

        try:
            # STEP 1: Crawl data
            print("📥 STEP 1: Crawl data từ database...")
            raw_data_list = self.crawl_data_by_date_range(start_date, end_date, limit)

            if not raw_data_list:
                print("⚠️  Không có data để xử lý")
                return self.stats

            self.stats['crawled_count'] = len(raw_data_list)
            print(f"✅ Crawl được {len(raw_data_list)} records")

            # STEP 2: Filter duplicates
            print("🔍 STEP 2: Kiểm tra và lọc bỏ records trùng lặp...")

            new_records, existing_records, duplicate_count = self.filter_existing_records(raw_data_list)

            self.stats['duplicate_count'] = duplicate_count
            self.stats['skipped_duplicates'] = [record.get('id_sanpham', 'unknown') for record in existing_records]

            if not new_records:
                print("⚠️  Tất cả records đã tồn tại, không có gì để xử lý")
                return self.stats

            print(f"✅ Sẽ xử lý {len(new_records)} records mới")

            # STEP 3: Start streaming insert worker
            print("💾 STEP 3: Khởi động streaming insert worker...")
            insert_thread = threading.Thread(target=self._streaming_insert_worker)
            insert_thread.daemon = True
            insert_thread.start()

            # STEP 4: Parallel processing với streaming insert
            print(f"🤖 STEP 4: Streaming processing với Qwen2.5-VL...")

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tất cả tasks
                future_to_data = {
                    executor.submit(self._process_and_queue_record, raw_data): raw_data
                    for raw_data in new_records
                }

                # Monitor progress
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_data):
                    completed_count += 1
                    raw_data = future_to_data[future]
                    
                    try:
                        success = future.result(timeout=180)
                        if success:
                            print(f"✅ [{completed_count}/{len(new_records)}] Processed & Queued: {raw_data.get('id_sanpham', 'unknown')}")
                        else:
                            print(f"❌ [{completed_count}/{len(new_records)}] Failed: {raw_data.get('id_sanpham', 'unknown')}")
                    
                    except concurrent.futures.TimeoutError:
                        print(f"⏰ [{completed_count}/{len(new_records)}] Timeout: {raw_data.get('id_sanpham', 'unknown')}")
                    except Exception as e:
                        print(f"❌ [{completed_count}/{len(new_records)}] Error: {raw_data.get('id_sanpham', 'unknown')} - {str(e)}")

            # STEP 5: Signal insert worker to finish và chờ
            print("🏁 STEP 5: Hoàn tất xử lý, chờ insert các records còn lại...")
            self.ready_records_queue.put(None)  # Signal to stop
            insert_thread.join(timeout=60)  # Chờ tối đa 60s

            print("✅ Streaming pipeline hoàn thành!")

        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng trong streaming pipeline: {str(e)}")

        finally:
            # Tính toán thống kê cuối cùng
            end_time = time.time()
            self.stats['total_time_seconds'] = round(end_time - start_time, 2)
            self.stats['end_time'] = datetime.now().isoformat()

            # Log kết quả cuối cùng
            print("=" * 80)
            print("🎊 STREAMING PIPELINE HOÀN THÀNH!")
            print(f"📊 THỐNG KÊ TỔNG KẾT:")
            print(f"   📥 Crawl: {self.stats['crawled_count']} records")
            print(f"   🔄 Trùng lặp (bỏ qua): {self.stats['duplicate_count']} records")
            print(f"   🆕 Records mới: {len(new_records) if 'new_records' in locals() else 0} records")
            print(f"   🤖 Xử lý thành công: {self.stats['processed_count']} records")
            print(f"   💾 Insert thành công: {self.stats['inserted_count']} records")
            print(f"   📦 Số batch inserts: {self.stats['insert_batches']} batches")
            print(f"   ❌ Thất bại: {self.stats['failed_count']} records")
            print(f"   ⏱️  Tổng thời gian: {self.stats['total_time_seconds']}s")

            # Tính tỉ lệ thành công
            new_records_count = len(new_records) if 'new_records' in locals() else max(
                self.stats['crawled_count'] - self.stats['duplicate_count'], 1)
            success_rate = self.stats['inserted_count'] / max(new_records_count, 1) * 100
            print(f"   📈 Tỉ lệ thành công: {success_rate:.1f}%")

            # Tính tốc độ xử lý
            if self.stats['total_time_seconds'] > 0:
                processing_rate = self.stats['inserted_count'] / self.stats['total_time_seconds']
                print(f"   🚄 Tốc độ insert: {processing_rate:.2f} records/second")

            # Hiển thị collection stats
            try:
                total_entities = self.collection.num_entities
                print(f"   💾 Tổng entities trong Milvus: {total_entities}")
            except:
                pass

            print("=" * 80)
            return self.stats

    # === SINGLE RECORD PROCESSING ===
    def process_single_record_streaming(self, raw_data: Dict[str, Any]) -> bool:
        """Xử lý 1 record và insert ngay lập tức"""
        try:
            success = self._process_and_queue_record(raw_data)
            
            # Đợi cho đến khi queue empty (record đã được insert)
            while not self.ready_records_queue.empty():
                time.sleep(0.1)
                
            return success
            
        except Exception as e:
            print(f"❌ Lỗi xử lý single record: {str(e)}")
            return False

    # === UTILITY METHODS ===
    def save_stats_to_json(self, stats: Dict[str, Any], filename: str = None):
        """Lưu thống kê vào file JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"streaming_pipeline_stats_{timestamp}.json"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"💾 Đã lưu thống kê vào: {filename}")
        except Exception as e:
            print(f"❌ Lỗi lưu file: {e}")

    def get_real_time_stats(self) -> Dict[str, Any]:
        """Lấy thống kê real-time"""
        with self.insert_stats_lock:
            return self.stats.copy()

    def clear_cache(self):
        """Clear image cache"""
        with self.cache_lock:
            self.image_cache.clear()
        print("🧹 Đã clear image cache")

    def close_connections(self):
        """Đóng tất cả kết nối"""
        try:
            if self.db_connection:
                self.db_connection.close()
                print("✅ Đã đóng kết nối PostgreSQL")
        except:
            pass

    # === MONITORING METHODS ===
    def start_progress_monitor(self, total_records: int, interval: int = 10):
        """Start background thread để monitor progress"""
        def monitor():
            while True:
                time.sleep(interval)
                stats = self.get_real_time_stats()
                processed = stats['processed_count']
                inserted = stats['inserted_count']
                failed = stats['failed_count']
                
                if processed >= total_records:
                    break
                    
                print(f"📊 Progress: Processed={processed}/{total_records}, Inserted={inserted}, Failed={failed}")
        
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        return monitor_thread


def main_streaming_pipeline():
    """
    Hàm main với streaming pipeline - Insert ngay sau embedding
    """
    print("🚀 KHỞI ĐỘNG STREAMING PRODUCT PIPELINE")
    print("💡 Đặc điểm: Insert ngay sau khi embedding xong từng record")
    print("=" * 60)

    # ========== CONFIGURATION ==========
    # Database config

    os.environ['OLLAMA_NUM_GPU'] = '0'
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    db_config = {
        'host': '45.79.189.110',
        'database': 'ai_db',
        'user': 'ai_engineer',
        'password': 'StrongPassword123',
        'port': 5432
    }

    # Qwen2.5-VL model config
    qwen_model = "qwen2.5vl:latest"

    # Streaming config
    max_workers = 1  # Số workers xử lý song song
    insert_batch_size = 5  # Batch size nhỏ để insert nhanh hơn

    # Milvus config
    milvus_host = "10.10.4.25"
    milvus_port = "19530"

    # ========== THỜI GIAN CRAWL ==========
    start_date = "2022-10-10"
    end_date = "2024-10-10"

    # ========== CÀI ĐẶT PIPELINE ==========
    limit = 20000 # Test với ít records trước

    try:
        # Khởi tạo streaming pipeline
        print("🔧 Khởi tạo Streaming Pipeline...")
        pipeline = StreamingProductPipeline(
            db_config=db_config,
            qwen_model=qwen_model,
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            max_workers=max_workers,
            insert_batch_size=insert_batch_size
        )

        print("✅ Streaming Pipeline khởi tạo thành công!")

        # Kiểm tra model
        try:
            test_response = ollama.generate(
                model=qwen_model,
                prompt="Hello",
                options={'num_predict': 5}
            )
            print(f"✅ Qwen2.5-VL model '{qwen_model}' sẵn sàng!")
        except Exception as e:
            print(f"❌ Lỗi model '{qwen_model}': {e}")
            print("💡 Hướng dẫn cài đặt:")
            print(f"   ollama pull {qwen_model}")
            return

        # Chạy streaming pipeline
        print(f"🎯 Bắt đầu streaming processing từ {start_date} đến {end_date}")
        print("💡 Records sẽ được insert ngay sau khi embedding xong!")

        stats = pipeline.run_streaming_pipeline(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        # Lưu thống kê
        pipeline.save_stats_to_json(stats)

        # Clear cache
        pipeline.clear_cache()

        # Hiển thị kết quả tóm tắt
        print("\n🎊 KẾT QUẢ STREAMING PIPELINE:")
        print(f"✅ Thành công: {stats['inserted_count']}/{stats['crawled_count']} records")
        print(f"🔄 Trùng lặp: {stats['duplicate_count']} records")
        print(f"📦 Insert batches: {stats['insert_batches']} batches")
        print(f"⏱️  Thời gian: {stats['total_time_seconds']}s")

        if stats['total_time_seconds'] > 0:
            rate = stats['inserted_count'] / stats['total_time_seconds']
            print(f"🚄 Tốc độ: {rate:.2f} records/second")

        if stats['inserted_ids']:
            print(f"📦 Sample inserted IDs:")
            for i, record_id in enumerate(stats['inserted_ids'][:3]):
                print(f"   {i + 1}. {record_id}")
            if len(stats['inserted_ids']) > 3:
                print(f"   ... và {len(stats['inserted_ids']) - 3} records khác")

        print("\n🌟 Ưu điểm Streaming Pipeline:")
        print("✅ Insert ngay sau khi embedding → Tiết kiệm memory")
        print("✅ Real-time feedback → Biết kết quả ngay lập tức")
        print("✅ Fault tolerance → Lỗi 1 record không ảnh hưởng các record khác")
        print("✅ Parallel processing → Tốc độ cao với multiple workers")

    except Exception as e:
        print(f"❌ LỖI NGHIÊM TRỌNG: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        try:
            pipeline.close_connections()
        except:
            pass

        print("\n👋 Streaming Pipeline kết thúc!")




if __name__ == "__main__":

    main_streaming_pipeline()

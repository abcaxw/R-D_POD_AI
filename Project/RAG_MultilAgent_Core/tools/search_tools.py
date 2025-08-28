"""
Enhanced Search tools for RnD Assistant
Optimized search_by_description_tool with advanced text processing
"""
import base64
import io
import tempfile
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from langchain_core.tools import tool
from PIL import Image

from database.milvus_manager import milvus_manager


class SearchQueryProcessor:
    """Advanced query processor for product descriptions"""

    # Vietnamese-English mapping for product categories
    CATEGORY_MAPPINGS = {
        'mũ': ['cap', 'hat'],
        'nón': ['cap', 'hat'],
        'bảng': ['plaque', 'desk plaque'],
        'biển': ['plaque', 'desk plaque'],
        'trang trí': ['decor', 'decoration'],
        'quà tặng': ['gift'],
        'sinh nhật': ['birthday'],
        'thể thao': ['sports', 'basketball'],
        'bóng rổ': ['basketball'],
        'logo': ['logo', 'mascot'],
        'đội': ['team'],
        'con gái': ['daughter'],
        'con trai': ['son'],
        'trẻ em': ['kids', 'children'],
        'cha': ['father', 'dad'],
        'mẹ': ['mother', 'mom'],
        'vợ': ['wife'],
        'chồng': ['husband'],
        'đồng nghiệp': ['colleagues']
    }

    # Key attributes hierarchy for structured products
    ATTRIBUTE_HIERARCHY = {
        'product_type': ['cap', 'hat', 'desk plaque', 'plaque'],
        'subject': ['basketball team logo', 'mascot', 'logo'],
        'recipient': ['daughter', 'son', 'kids', 'children'],
        'giver': ['from mother', 'from father', 'from wife', 'from husband', 'from colleagues', 'from daughter', 'from son', 'from spouse'],
        'occasion': ['birthday', 'christmas', 'father\'s day', 'mother\'s day', 'valentine\'s day', 'anniversaries'],
        'theme': ['basketball', 'sports'],
        'colors': ['orange', 'blue', 'pink', 'red', 'green', 'yellow', 'black', 'white'],
        'style': ['elegant', 'sports theme', 'sentimental', 'energetic'],
        'text_content': ['champs', 'okc', 'thunder', 'oklahoma city thunder', '2025'],
        'brand_level': ['tm resemblance']
    }

    @classmethod
    def extract_key_attributes(cls, description: str) -> Dict[str, List[str]]:
        """Extract structured attributes from description"""
        description_lower = description.lower()
        extracted = defaultdict(list)

        for category, keywords in cls.ATTRIBUTE_HIERARCHY.items():
            for keyword in keywords:
                if keyword.lower() in description_lower:
                    extracted[category].append(keyword)

        return dict(extracted)

    @classmethod
    def expand_query_terms(cls, query: str) -> List[str]:
        """Expand query with synonyms and related terms"""
        query_lower = query.lower()
        expanded_terms = [query]

        # Add Vietnamese-English mappings
        for vn_term, en_terms in cls.CATEGORY_MAPPINGS.items():
            if vn_term in query_lower:
                expanded_terms.extend(en_terms)

        # Add attribute-based expansions
        for category, keywords in cls.ATTRIBUTE_HIERARCHY.items():
            for keyword in keywords:
                if keyword.lower() in query_lower or any(word in keyword.lower() for word in query_lower.split()):
                    # Add related terms from same category
                    related_terms = [k for k in keywords if k != keyword][:3]  # Limit to 3 related terms
                    expanded_terms.extend(related_terms)

        return list(set(expanded_terms))  # Remove duplicates

    @classmethod
    def create_structured_query(cls, query: str) -> str:
        """Create a structured query that emphasizes important attributes"""
        attributes = cls.extract_key_attributes(query)
        expanded_terms = cls.expand_query_terms(query)

        # Build priority-based query
        priority_parts = []

        # High priority: product type and main subject
        if 'product_type' in attributes:
            priority_parts.append(f"Product: {', '.join(attributes['product_type'])}")
        if 'subject' in attributes:
            priority_parts.append(f"Subject: {', '.join(attributes['subject'])}")

        # Medium priority: recipient and occasion
        if 'recipient' in attributes:
            priority_parts.append(f"For: {', '.join(attributes['recipient'])}")
        if 'occasion' in attributes:
            priority_parts.append(f"Occasion: {', '.join(attributes['occasion'])}")

        # Lower priority: style and colors
        if 'theme' in attributes:
            priority_parts.append(f"Theme: {', '.join(attributes['theme'])}")
        if 'style' in attributes:
            priority_parts.append(f"Style: {', '.join(attributes['style'])}")

        # Combine original query with structured parts
        structured_query = query
        if priority_parts:
            structured_query += " | " + " | ".join(priority_parts)

        # Add expanded terms for better matching
        expanded_unique = [term for term in expanded_terms if term.lower() not in query.lower()][:100]
        if expanded_unique:
            structured_query += f" Related: {', '.join(expanded_unique)}"

        return structured_query

    @classmethod
    def score_results(cls, results: List[Dict], original_query: str) -> List[Dict]:
        """Post-process and score results based on attribute matching"""
        query_attributes = cls.extract_key_attributes(original_query)

        for result in results:
            if 'description' in result or 'text' in result:
                result_text = result.get('description', result.get('text', ''))
                result_attributes = cls.extract_key_attributes(result_text)

                # Calculate attribute match score
                total_matches = 0
                total_possible = 0

                for category, query_values in query_attributes.items():
                    total_possible += len(query_values)
                    if category in result_attributes:
                        matches = len(set(query_values) & set(result_attributes[category]))
                        total_matches += matches

                # Calculate match percentage
                match_score = total_matches / max(total_possible, 1) if total_possible > 0 else 0
                result['attribute_match_score'] = match_score
                result['matched_attributes'] = {
                    category: list(set(query_attributes[category]) & set(result_attributes.get(category, [])))
                    for category in query_attributes
                    if category in result_attributes and set(query_attributes[category]) & set(result_attributes.get(category, []))
                }

        # Sort by combined score (original similarity attribute matching)
        return sorted(results, key=lambda x: (
            x.get('attribute_match_score', 0) * 0.3 +
            x.get('similarity', 0) * 0.7
        ), reverse=True)


@tool
def search_by_description_tool(description: str, top_k: int = 100,
                               use_enhanced_processing: bool = True,
                               filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Tìm kiếm sản phẩm và hình ảnh dựa trên mô tả text với xử lý nâng cao và filtering

    Args:
        description: Mô tả sản phẩm cần tìm
        top_k: Số lượng kết quả trả về
        use_enhanced_processing: Sử dụng xử lý nâng cao (mặc định True)
        filters: Dict chứa filters cho date, name_store, platform

    Returns:
        List kết quả đã được tối ưu và sắp xếp theo độ phù hợp
    """
    try:
        if use_enhanced_processing:
            processor = SearchQueryProcessor()
            enhanced_query = processor.create_structured_query(description)
            results = milvus_manager.search_by_text_description(enhanced_query, top_k * 2, filters)
            scored_results = processor.score_results(results, description)
            return scored_results[:top_k]
        else:
            return milvus_manager.search_by_text_description(description, top_k, filters)

    except Exception as e:
        return [{"error": f"Error in enhanced description search: {str(e)}"}]

@tool
def multi_strategy_search_tool(query: str, strategies: List[str] = None, top_k: int = 100,
                               filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Thực hiện tìm kiếm đa chiến lược và kết hợp kết quả với filtering

    Args:
        query: Câu truy vấn
        strategies: Danh sách chiến lược ['exact', 'expanded', 'structured', 'fuzzy']
        top_k: Số kết quả cho mỗi chiến lược
        filters: Dict chứa filters cho date, name_store, platform
    """
    if strategies is None:
        strategies = ['exact', 'expanded', 'structured']

    results = {}
    processor = SearchQueryProcessor()

    try:
        if 'exact' in strategies:
            results['exact'] = milvus_manager.search_by_text_description(query, top_k, filters)

        if 'expanded' in strategies:
            expanded_terms = processor.expand_query_terms(query)
            expanded_query = ' '.join(expanded_terms)
            results['expanded'] = milvus_manager.search_by_text_description(expanded_query, top_k, filters)

        if 'structured' in strategies:
            structured_query = processor.create_structured_query(query)
            results['structured'] = milvus_manager.search_by_text_description(structured_query, top_k, filters)

        if 'fuzzy' in strategies:
            attributes = processor.extract_key_attributes(query)
            fuzzy_query = ' '.join([' '.join(values) for values in attributes.values()])
            if fuzzy_query:
                results['fuzzy'] = milvus_manager.search_by_text_description(fuzzy_query, top_k, filters)

        # Combine and deduplicate results
        all_results = []
        seen_ids = set()

        for strategy, strategy_results in results.items():
            for result in strategy_results:
                result_id = result.get('id', str(hash(str(result))))
                if result_id not in seen_ids:
                    result['strategy'] = strategy
                    all_results.append(result)
                    seen_ids.add(result_id)

        final_results = processor.score_results(all_results, query)

        return {
            'combined_results': final_results[:top_k],
            'strategy_results': results,
            'total_unique_results': len(all_results),
            'applied_filters': filters,
            'query_analysis': {
                'original_query': query,
                'extracted_attributes': processor.extract_key_attributes(query),
                'expanded_terms': processor.expand_query_terms(query),
                'structured_query': processor.create_structured_query(query)
            }
        }

    except Exception as e:
        return {"error": f"Error in multi-strategy search: {str(e)}"}


@tool
def smart_product_search_tool(query: str, context: Dict[str, Any] = None, top_k: int = 100,
                              filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Tìm kiếm thông minh với ngữ cảnh bổ sung và filtering

    Args:
        query: Truy vấn chính
        context: Ngữ cảnh bổ sung như {'user_preferences', 'previous_searches', 'filter_preferences'}
        top_k: Số kết quả trả về
        filters: Dict chứa filters cho date, name_store, platform
    """
    try:
        processor = SearchQueryProcessor()
        enhanced_query = query

        if context:
            if 'user_preferences' in context:
                prefs = context['user_preferences']
                pref_terms = []
                for category, values in prefs.items():
                    if isinstance(values, list):
                        pref_terms.extend(values)
                    else:
                        pref_terms.append(str(values))
                if pref_terms:
                    enhanced_query += f" User preferences: {', '.join(pref_terms)}"

            if 'filters' in context:
                filter_terms = []
                for key, value in context['filters'].items():
                    filter_terms.append(f"{key}: {value}")
                if filter_terms:
                    enhanced_query += f" Filters: {', '.join(filter_terms)}"

        results = search_by_description_tool(enhanced_query, top_k * 2, True, filters)

        if context and 'must_have_attributes' in context:
            must_have = context['must_have_attributes']
            filtered_results = []

            for result in results:
                result_text = result.get('description', result.get('text', '')).lower()
                if all(attr.lower() in result_text for attr in must_have):
                    filtered_results.append(result)

            results = filtered_results

        return results[:top_k]

    except Exception as e:
        return [{"error": f"Error in smart product search: {str(e)}"}]


@tool
def search_by_image_tool(image_base64: str, top_k: int = 100,
                         filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Tìm kiếm sản phẩm tương tự dựa trên hình ảnh input với filtering

    Args:
        image_base64: Hình ảnh base64
        top_k: Số kết quả trả về
        filters: Dict chứa filters cho date, name_store, platform
    """
    try:
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        image_vector = milvus_manager.get_image_vector(image)
        return milvus_manager.search_by_image_vector(image_vector, top_k, filters)
    except Exception as e:
        return [{"error": f"Error processing image: {str(e)}"}]


@tool
def search_by_image_url_tool(image_url: str, top_k: int = 100,
                             filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Tìm kiếm sản phẩm tương tự dựa trên URL hình ảnh với filtering

    Args:
        image_url: URL hình ảnh
        top_k: Số kết quả trả về
        filters: Dict chứa filters cho date, name_store, platform
    """
    try:
        return milvus_manager.search_by_image_url(image_url, top_k, filters)
    except Exception as e:
        return [{"error": f"Error processing image URL: {str(e)}"}]


@tool
def search_multimodal_tool(text: str = "", image_base64: str = "", top_k: int = 100,
                           filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Tìm kiếm đa phương thức: tìm theo ảnh trước, sau đó lọc theo text với filtering

    Args:
        text: Mô tả text để lọc kết quả
        image_base64: Hình ảnh dạng base64 để tìm kiếm chính
        top_k: Số lượng kết quả trả về
        filters: Dict chứa filters cho date, name_store, platform
    """
    try:
        image_url = None

        if image_base64:
            image_data = base64.b64decode(image_base64)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(image_data)
                image_url = tmp_file.name

        processed_text = text
        if text:
            processor = SearchQueryProcessor()
            processed_text = processor.create_structured_query(text)

        results = milvus_manager.search_multimodal(
            text=processed_text,
            image_url=image_url,
            top_k=top_k,
            filters=filters
        )

        if image_url and os.path.exists(image_url):
            os.unlink(image_url)

        return results

    except Exception as e:
        return [{"error": f"Error in multimodal search: {str(e)}"}]


@tool
def search_products_with_filters_tool(query: str, filters: Dict[str, Any], top_k: int = 100) -> List[Dict]:
    """
    Tìm kiếm sản phẩm với filters cho phân tích chuyên sâu

    Args:
        query: Truy vấn tìm kiếm
        filters: Dict chứa filters cho date, name_store, platform
        top_k: Số kết quả trả về
    """
    processor = SearchQueryProcessor()
    enhanced_query = processor.create_structured_query(query)
    query_vector = milvus_manager.get_query_vector(enhanced_query)
    return milvus_manager.search_products(query_vector, top_k, filters)


@tool
def batch_search_descriptions_tool(descriptions: List[str], top_k: int = 100) -> List[List[Dict]]:
    """
    Tìm kiếm batch cho nhiều mô tả text cùng lúc với xử lý nâng cao

    Returns:
        List các kết quả tìm kiếm cho từng mô tả
    """
    try:
        processor = SearchQueryProcessor()
        enhanced_descriptions = [processor.create_structured_query(desc) for desc in descriptions]
        return milvus_manager.batch_search_texts(enhanced_descriptions, top_k)
    except Exception as e:
        return [[{"error": f"Error in batch search: {str(e)}"}] for _ in descriptions]


@tool
def batch_search_images_tool(image_urls: List[str], top_k: int = 100,
                             filters: Optional[Dict[str, Any]] = None) -> List[List[Dict]]:
    """
    Tìm kiếm batch cho nhiều hình ảnh cùng lúc với filtering

    Args:
        image_urls: Danh sách URL hình ảnh
        top_k: Số kết quả cho mỗi hình ảnh
        filters: Dict chứa filters cho date, name_store, platform

    Returns:
        List các kết quả tìm kiếm cho từng hình ảnh
    """
    try:
        return milvus_manager.batch_search_images(image_urls, top_k, filters)
    except Exception as e:
        return [[{"error": f"Error in batch image search: {str(e)}"}] for _ in image_urls]


@tool
def similarity_comparison_tool(text1: str, text2: str, image1_base64: str = "", image2_base64: str = "",
                               filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    So sánh độ tương đồng giữa hai sản phẩm (text và/hoặc hình ảnh)

    Args:
        text1, text2: Mô tả sản phẩm 1 và 2
        image1_base64, image2_base64: Hình ảnh base64 của sản phẩm 1 và 2
        filters: Dict chứa filters (để tìm sản phẩm tương tự khi cần)

    Returns:
        Dictionary chứa các điểm tương đồng khác nhau
    """
    try:
        embedding_service = milvus_manager.embedding_service
        image1_url = None
        image2_url = None

        if image1_base64:
            image_data1 = base64.b64decode(image1_base64)
            with tempfile.NamedTemporaryFile(delete=False, suffix='_1.jpg') as tmp_file:
                tmp_file.write(image_data1)
                image1_url = tmp_file.name

        if image2_base64:
            image_data2 = base64.b64decode(image2_base64)
            with tempfile.NamedTemporaryFile(delete=False, suffix='_2.jpg') as tmp_file:
                tmp_file.write(image_data2)
                image2_url = tmp_file.name

        processor = SearchQueryProcessor()
        enhanced_text1 = processor.create_structured_query(text1) if text1 else text1
        enhanced_text2 = processor.create_structured_query(text2) if text2 else text2

        img_vec1, text_vec1 = embedding_service.embed_multimodal(enhanced_text1, image1_url)
        img_vec2, text_vec2 = embedding_service.embed_multimodal(enhanced_text2, image2_url)

        import numpy as np

        text_similarity = np.dot(text_vec1, text_vec2) / (np.linalg.norm(text_vec1) * np.linalg.norm(text_vec2))

        # Image similarity (if both images provided)
        image_similarity = None
        if image1_base64 and image2_base64:
            image_similarity = np.dot(img_vec1, img_vec2) / (np.linalg.norm(img_vec1) * np.linalg.norm(img_vec2))

        # Overall similarity (weighted average)
        if image_similarity is not None:
            overall_similarity = 0.5 * text_similarity + 0.5 * image_similarity
        else:
            overall_similarity = text_similarity

        # Attribute-based similarity analysis
        attr_analysis = {}
        if text1 and text2:
            attrs1 = processor.extract_key_attributes(text1)
            attrs2 = processor.extract_key_attributes(text2)

            for category in set(attrs1.keys()) | set(attrs2.keys()):
                vals1 = set(attrs1.get(category, []))
                vals2 = set(attrs2.get(category, []))

                if vals1 or vals2:
                    intersection = len(vals1 & vals2)
                    union = len(vals1 | vals2)
                    attr_similarity = intersection / union if union > 0 else 0
                    attr_analysis[category] = {
                        'similarity': attr_similarity,
                        'common_attributes': list(vals1 & vals2),
                        'unique_to_first': list(vals1 - vals2),
                        'unique_to_second': list(vals2 - vals1)
                    }

        # Clean up temporary files
        for temp_file in [image1_url, image2_url]:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return {
            "text_similarity": float(text_similarity),
            "image_similarity": float(image_similarity) if image_similarity is not None else None,
            "overall_similarity": float(overall_similarity),
            "attribute_analysis": attr_analysis,
            "interpretation": {
                "text": "Rất tương đồng" if text_similarity > 0.8 else "Tương đồng" if text_similarity > 0.6 else "Ít tương đồng",
                "image": ("Rất tương đồng" if image_similarity and image_similarity > 0.8 else
                         "Tương đồng" if image_similarity and image_similarity > 0.6 else
                         "Ít tương đồng" if image_similarity else "Không có hình ảnh để so sánh"),
                "overall": "Rất tương đồng" if overall_similarity > 0.8 else "Tương đồng" if overall_similarity > 0.6 else "Ít tương đồng"
            }
        }

    except Exception as e:
        return {"error": f"Error in similarity comparison: {str(e)}"}


@tool
def get_embedding_info_tool() -> Dict[str, Any]:
    """Lấy thông tin về model embedding đang sử dụng"""
    try:
        return milvus_manager.get_model_info()
    except Exception as e:
        return {"error": f"Error getting model info: {str(e)}"}


@tool
def find_trend_clusters_tool(descriptions: List[str], similarity_threshold: float = 0.7,
                             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Tìm các cluster/nhóm sản phẩm tương đồng từ danh sách mô tả với filtering
    Hữu ích để phát hiện trend và phân nhóm sản phẩm

    Args:
        descriptions: Danh sách mô tả sản phẩm
        similarity_threshold: Ngưỡng tương đồng để gom nhóm
        filters: Dict chứa filters cho date, name_store, platform
    """
    try:
        from collections import defaultdict

        embedding_service = milvus_manager.embedding_service
        processor = SearchQueryProcessor()

        enhanced_descriptions = [processor.create_structured_query(desc) for desc in descriptions]
        embeddings = embedding_service.embed_texts_batch(enhanced_descriptions, normalize=True)

        import numpy as np
        clusters = []
        used_indices = set()

        for i, emb1 in enumerate(embeddings):
            if i in used_indices:
                continue

            cluster = [i]
            used_indices.add(i)

            for j, emb2 in enumerate(embeddings[i + 1:], i + 1):
                if j in used_indices:
                    continue

                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

                if similarity >= similarity_threshold:
                    cluster.append(j)
                    used_indices.add(j)

            cluster_attributes = defaultdict(set)
            for idx in cluster:
                attrs = processor.extract_key_attributes(descriptions[idx])
                for category, values in attrs.items():
                    cluster_attributes[category].update(values)

            clusters.append({
                "cluster_id": len(clusters),
                "indices": cluster,
                "descriptions": [descriptions[idx] for idx in cluster],
                "size": len(cluster),
                "common_attributes": {k: list(v) for k, v in cluster_attributes.items()},
                "dominant_theme": max(cluster_attributes.items(), key=lambda x: len(x[1]))[
                    0] if cluster_attributes else "unknown"
            })

        return {
            "total_clusters": len(clusters),
            "clusters": clusters,
            "similarity_threshold": similarity_threshold,
            "largest_cluster_size": max(cluster["size"] for cluster in clusters) if clusters else 0,
            "cluster_themes": [cluster["dominant_theme"] for cluster in clusters],
            "applied_filters": filters
        }

    except Exception as e:
        return {"error": f"Error in trend clustering: {str(e)}"}

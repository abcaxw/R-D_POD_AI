"""
Enhanced Milvus database manager với filter linh hoạt
Updated để hỗ trợ flexible filtering cho date, name_store, platform
"""
from typing import List, Dict, Any, Union, Optional
import json
from datetime import datetime

from pymilvus import connections, Collection, utility
from PIL import Image
import numpy as np

from config.settings import Config
from database.embedding_service import EmbeddingService

class SingleCollectionMilvusManager:
    """Manages single collection Milvus operations with flexible filtering"""

    def __init__(self):
        self.collection = None
        self.embedding_service = EmbeddingService()
        print(f"🔧 Initialized MilvusManager with Jina v4")
        print(f"📊 Embedding dimensions: {self.embedding_service.embedding_dim}")

    def connect(self):
        """Connect to Milvus and load the single collection"""
        connections.connect(
            alias="default",
            host=Config.MILVUS_HOST,
            port=Config.MILVUS_PORT
        )

        if utility.has_collection(Config.COLLECTION_NAME):
            self.collection = Collection(Config.COLLECTION_NAME)
            self.collection.load()
            print(f"✅ Collection {Config.COLLECTION_NAME} loaded successfully!")
        else:
            raise Exception(f"Collection {Config.COLLECTION_NAME} not found!")

    def _build_filter_expression(self, filters: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Build filter expression từ dictionary filters

        Args:
            filters: Dict có thể chứa:
                - 'name_store': string hoặc list strings
                - 'platform': string hoặc list strings
                - 'date_range': tuple (start_date, end_date) dạng 'DD/MM/YYYY'
                - 'date_after': string 'DD/MM/YYYY'
                - 'date_before': string 'DD/MM/YYYY'

        Returns:
            Filter expression string hoặc None
        """
        if not filters:
            return None

        conditions = []

        # Name Store Filter
        if 'name_store' in filters and filters['name_store']:
            name_stores = filters['name_store']
            if isinstance(name_stores, str):
                name_stores = [name_stores]

            # Tạo conditions cho từng store
            store_conditions = []
            for store in name_stores:
                store_conditions.append(f'name_store == "{store}"')

            if store_conditions:
                if len(store_conditions) == 1:
                    conditions.append(store_conditions[0])
                else:
                    conditions.append(f"({' or '.join(store_conditions)})")

        # Platform Filter
        if 'platform' in filters and filters['platform']:
            platforms = filters['platform']
            if isinstance(platforms, str):
                platforms = [platforms]

            platform_conditions = []
            for platform in platforms:
                platform_conditions.append(f'platform == "{platform}"')

            if platform_conditions:
                if len(platform_conditions) == 1:
                    conditions.append(platform_conditions[0])
                else:
                    conditions.append(f"({' or '.join(platform_conditions)})")

        # Date Filters
        if 'date_range' in filters and filters['date_range']:
            start_date, end_date = filters['date_range']
            start_formatted = self._format_date_for_milvus(start_date)
            end_formatted = self._format_date_for_milvus(end_date)
            conditions.append(f'date >= "{start_formatted}" and date <= "{end_formatted}"')

        elif 'date_after' in filters and filters['date_after']:
            start_formatted = self._format_date_for_milvus(filters['date_after'])
            conditions.append(f'date >= "{start_formatted}"')

        elif 'date_before' in filters and filters['date_before']:
            end_formatted = self._format_date_for_milvus(filters['date_before'])
            conditions.append(f'date <= "{end_formatted}"')

        # Combine all conditions
        if conditions:
            return ' and '.join(conditions)

        return None

    def _format_date_for_milvus(self, date_str: str) -> str:
        """
        Convert date từ DD/MM/YYYY sang format phù hợp với Milvus

        Args:
            date_str: Date string dạng 'DD/MM/YYYY'

        Returns:
            Formatted date string
        """
        try:
            # Parse DD/MM/YYYY
            dt = datetime.strptime(date_str.strip(), '%d/%m/%Y')
            # Return YYYY-MM-DD format for Milvus
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            # Nếu không parse được, try format khác
            try:
                dt = datetime.strptime(date_str.strip(), '%Y-%m-%d')
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                # Fallback to original string
                return date_str.strip()

    def search_products(self, query_vector: List[float], top_k: int = Config.TOP_K,
                        filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        Universal search function với flexible filtering
        """
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 12}
        }

        output_fields = [
            "id_sanpham", "description", "metadata", "date", "image",
            "like", "comment", "share", "platform", "name_store"
        ]

        # Build filter expression
        filter_expr = self._build_filter_expression(filters)

        results = self.collection.search(
            data=[query_vector],
            anns_field="description_vector",
            param=search_params,
            limit=top_k,
            output_fields=output_fields,
            expr=filter_expr
        )

        return self._format_search_results(results)

    def search_by_text_description(self, description: str, top_k: int = Config.TOP_K,
                                   filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Search products by text description với filtering"""
        query_vector = self.get_query_vector(description)
        return self.search_products(query_vector, top_k, filters)

    def search_by_image_vector(self, image_vector: List[float], top_k: int = Config.TOP_K,
                               filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Search by image vector với filtering"""
        try:
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 12}
            }

            output_fields = [
                "id_sanpham", "description", "metadata", "date", "image",
                "like", "comment", "share", "platform", "name_store"
            ]

            filter_expr = self._build_filter_expression(filters)

            results = self.collection.search(
                data=[image_vector],
                anns_field="image_vector",
                param=search_params,
                limit=top_k,
                output_fields=output_fields,
                expr=filter_expr
            )

            return self._format_search_results(results)

        except Exception as e:
            print(f"Image vector search failed, falling back to description vector: {e}")
            return self.search_products(image_vector, top_k, filters)

    def search_by_image_url(self, image_url: str, top_k: int = Config.TOP_K,
                            filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Search by image URL với filtering"""
        try:
            image_vector = self.embedding_service.embed_image(image_url, normalize_output=True)
            return self.search_by_image_vector(image_vector.tolist(), top_k, filters)
        except Exception as e:
            print(f"Error in image URL search: {e}")
            return []

    def search_multimodal(self, text: str = "", image_url: str = "",
                          top_k: int = Config.TOP_K,
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Sequential multimodal search với filtering"""
        try:
            if image_url:
                image_candidates = self.search_by_image_url(image_url, top_k * 2, filters)

                if text and image_candidates:
                    text_vector = self.embedding_service.embed_text(text, normalize_output=True)

                    for candidate in image_candidates:
                        desc_vector = self.get_query_vector(candidate['description'])
                        text_sim = np.dot(text_vector, desc_vector) / (
                                np.linalg.norm(text_vector) * np.linalg.norm(desc_vector)
                        )
                        candidate['text_similarity'] = text_sim

                    image_candidates.sort(key=lambda x: x['text_similarity'], reverse=True)
                    return image_candidates[:top_k]

                return image_candidates[:top_k]

            elif text:
                return self.search_by_text_description(text, top_k, filters)

            return []

        except Exception as e:
            print(f"Error in multimodal search: {e}")
            return []

    def search_with_filters(self, query_vector: List[float], filters: Dict[str, Any],
                            top_k: int = Config.TOP_K) -> List[Dict]:
        """Legacy method - redirect to new search_products"""
        return self.search_products(query_vector, top_k, filters)

    def batch_search_texts(self, texts: List[str], top_k: int = Config.TOP_K,
                           filters: Optional[Dict[str, Any]] = None) -> List[List[Dict]]:
        """Batch search với filtering"""
        try:
            text_vectors = self.embedding_service.embed_texts_batch(texts, normalize=True)

            results = []
            for vector in text_vectors:
                search_result = self.search_products(vector.tolist(), top_k, filters)
                results.append(search_result)

            return results

        except Exception as e:
            print(f"Error in batch text search: {e}")
            return [[] for _ in texts]

    def batch_search_images(self, image_urls: List[str], top_k: int = Config.TOP_K,
                            filters: Optional[Dict[str, Any]] = None) -> List[List[Dict]]:
        """Batch image search với filtering"""
        try:
            image_vectors = self.embedding_service.embed_images_batch(image_urls, normalize=True)

            results = []
            for vector in image_vectors:
                search_result = self.search_by_image_vector(vector.tolist(), top_k, filters)
                results.append(search_result)

            return results

        except Exception as e:
            print(f"Error in batch image search: {e}")
            return [[] for _ in image_urls]

    def _format_search_results(self, results) -> List[Dict]:
        """Format search results to include image URLs and all necessary data"""
        products = []
        for hits in results:
            for hit in hits:
                product_data = {
                    "id": hit.entity.get("id_sanpham"),
                    "description": hit.entity.get("description"),
                    "image_url": hit.entity.get("image"),
                    "metadata": hit.entity.get("metadata"),
                    "engagement": {
                        "like": hit.entity.get("like"),
                        "comment": hit.entity.get("comment"),
                        "share": hit.entity.get("share")
                    },
                    "platform": hit.entity.get("platform"),
                    "store": hit.entity.get("name_store"),
                    "date": hit.entity.get("date"),
                    "similarity_score": hit.score
                }
                products.append(product_data)
        return products

    def get_query_vector(self, text: str) -> List[float]:
        """Convert text to vector embedding using Jina v4"""
        try:
            text_vector = self.embedding_service.embed_text(text, normalize_output=True)
            return text_vector.tolist()
        except Exception as e:
            print(f"Error generating text vector: {e}")
            return [0.0] * self.embedding_service.embedding_dim

    def get_image_vector(self, image_data: Union[str, bytes, Image.Image]) -> List[float]:
        """Convert image to vector embedding using Jina v4"""
        try:
            if isinstance(image_data, str):
                image_vector = self.embedding_service.embed_image(image_data, normalize_output=True)
            elif isinstance(image_data, bytes):
                from io import BytesIO
                pil_image = Image.open(BytesIO(image_data))
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file_path = tmp_file.name
                pil_image.save(tmp_file_path)
                image_vector = self.embedding_service.embed_image(tmp_file_path, normalize_output=True)
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            elif isinstance(image_data, Image.Image):
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file_path = tmp_file.name
                image_data.save(tmp_file_path)
                image_vector = self.embedding_service.embed_image(tmp_file_path, normalize_output=True)
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            else:
                raise ValueError(f"Unsupported image data type: {type(image_data)}")

            return image_vector.tolist()

        except Exception as e:
            print(f"Error generating image vector: {e}")
            return [0.0] * self.embedding_service.embedding_dim

    def get_model_info(self) -> Dict[str, Any]:
        """Get embedding model information"""
        return {
            "embedding_service": self.embedding_service.get_model_info(),
            "milvus_collection": Config.COLLECTION_NAME,
            "vector_dimensions": self.embedding_service.embedding_dim
        }

# Global instance
milvus_manager = SingleCollectionMilvusManager()

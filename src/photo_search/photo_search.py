#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-25 16:39:10
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 11:00:11
# -*- coding: utf-8 -*-
"""
Photo search class for querying indexed photos.

Supports visual similarity search, text search, metadata filtering,
and hybrid queries combining multiple criteria.
"""

from pathlib import Path
from typing import List, Dict, Optional, Union
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, MatchAny, MatchText,
    Range, GeoBoundingBox, GeoPoint, SearchRequest
)

from photo_index.embedding_generator import EmbeddingGenerator
from common.utils import Utils
from common.config import (
    QDRANT_PATH, QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, MODEL_PATH, DEVICE
)


class PhotoSearch:
    """Search interface for indexed photos."""
    
    def __init__(
        self,
        qdrant_path: Optional[str] = QDRANT_PATH,
        qdrant_host: Optional[str] = QDRANT_HOST,
        qdrant_port: Optional[int] = QDRANT_PORT,
        collection_name: str = COLLECTION_NAME,
        model_path: str = MODEL_PATH,
        device: str = DEVICE
    ):
        """Initialize the photo searcher.
        
        Args:
            qdrant_path: Path to Qdrant local storage (if using local mode)
            qdrant_host: Qdrant server host (if using server mode)
            qdrant_port: Qdrant server port (if using server mode)
            collection_name: Name of the collection
            model_path: Path to vision model
            device: Device for model ("cuda" or "cpu")
        """
        self.collection_name = collection_name
        
        # Connect to Qdrant (try server first, fall back to local)
        if qdrant_host and qdrant_port:
            try:
                print(f"Attempting to connect to Qdrant server: {qdrant_host}:{qdrant_port}")
                self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
                # Test connection
                self.client.get_collections()
                print(f"✓ Connected to Qdrant server")
            except Exception as e:
                print(f"Warning: Could not connect to Qdrant server: {e}")
                if qdrant_path:
                    print(f"Falling back to Qdrant local storage: {qdrant_path}")
                    self.client = QdrantClient(path=qdrant_path)
                else:
                    raise ValueError("Cannot connect to server and no local path specified")
        elif qdrant_path:
            print(f"Connecting to Qdrant local storage: {qdrant_path}")
            self.client = QdrantClient(path=qdrant_path)
        else:
            raise ValueError("Must specify either (qdrant_host and qdrant_port) or qdrant_path in config.py")
        
        # Initialize embedding generator (lazy loaded)
        self._embedding_generator = None
        self._model_path = model_path
        self._device = device
    
    @property
    def embedding_generator(self) -> EmbeddingGenerator:
        """Lazy load the embedding generator."""
        if self._embedding_generator is None:
            print("Loading vision model...")
            self._embedding_generator = EmbeddingGenerator(
                self._model_path,
                self._device
            )
        return self._embedding_generator
    
    def search_by_image(
        self,
        image_path: Union[str, Path],
        limit: int = 10,
        filters: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Search for visually similar photos.
        
        Args:
            image_path: Path to query image
            limit: Number of results to return
            filters: Optional Qdrant filters
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of search results with scores and payloads
        """
        image_path = Path(image_path)
        
        # Generate embedding for query image
        embedding = self.embedding_generator.generate_embedding(image_path)
        
        return self.search_by_embedding(
            embedding,
            limit=limit,
            filters=filters,
            score_threshold=score_threshold
        )
    
    def search_by_embedding(
        self,
        embedding: np.ndarray,
        limit: int = 10,
        filters: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Search using a pre-computed embedding.
        
        Args:
            embedding: Query embedding vector
            limit: Number of results to return
            filters: Optional Qdrant filters
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of search results with scores and payloads
        """
        # Search in Qdrant using query_points (qdrant-client 1.16.0+ local mode)
        try:
            # Try query_points (newer versions with local storage)
            query_result = self.client.query_points(
                collection_name=self.collection_name,
                query=embedding.tolist(),
                query_filter=filters,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )
            results = query_result.points if hasattr(query_result, 'points') else query_result
        except AttributeError:
            # Fallback to search (older remote API)
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=embedding.tolist(),
                    query_filter=filters,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True
                )
            except AttributeError:
                # Last resort - search_batch
                from qdrant_client.models import SearchRequest
                results = self.client.search_batch(
                    collection_name=self.collection_name,
                    requests=[SearchRequest(
                        vector=embedding.tolist(),
                        filter=filters,
                        limit=limit,
                        score_threshold=score_threshold,
                        with_payload=True
                    )]
                )[0]
        
        return self._format_results(results)
    
    def search_by_text(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Filter] = None,
        search_fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search photos by text in descriptions.

        Prioritizes person_names matches over description matches to avoid
        partial matches like "eli" in "helicopter".

        Args:
            query: Text query
            limit: Number of results to return
            filters: Optional Qdrant filters
            search_fields: Fields to search in (default: description fields)

        Returns:
            List of matching photos
        """
        if search_fields is None:
            # Default: search in description fields, keywords, and person names
            search_fields = [
                'description_parsed.objects',
                'description_parsed.materials',
                'description_parsed.setting',
                'description_parsed.visual_attributes',
                'ai_keywords',
                'user_keywords',
                'person_names'
            ]

        # Two-phase search: prioritize person_names to avoid partial text matches
        # Phase 1: Search only in person_names if it's in the search fields
        person_results = []
        if 'person_names' in search_fields:
            person_filter = Filter(
                should=[
                    FieldCondition(
                        key='person_names',
                        match=MatchAny(any=[query.lower()])
                    )
                ]
            )

            # Combine with any existing filters
            if filters:
                person_filter.must = filters.must if filters.must else []

            person_results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=person_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

        # Phase 2: If we have enough person_names results, return those
        # Otherwise, search in all fields
        if len(person_results) >= limit:
            return self._format_results(person_results, include_score=False)

        # Build text search filter for remaining fields
        text_conditions = []
        for field in search_fields:
            if field == 'person_names':
                # Already searched, add to get any additional matches
                text_conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchAny(any=[query.lower()])
                    )
                )
            else:
                # Other fields are strings, use MatchText
                text_conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchText(text=query.lower())
                    )
                )

        # Combine with any existing filters
        if filters:
            combined_filter = Filter(
                must=filters.must if filters.must else [],
                should=text_conditions
            )
        else:
            combined_filter = Filter(should=text_conditions)

        # Scroll through all matching results
        all_results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=combined_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )

        # Deduplicate and prioritize: person_names matches first, then others
        seen_guids = set()
        final_results = []

        # Add person_names matches first
        for result in person_results:
            guid = result.payload.get('guid')
            if guid not in seen_guids:
                seen_guids.add(guid)
                final_results.append(result)

        # Add remaining matches
        for result in all_results:
            guid = result.payload.get('guid')
            if guid not in seen_guids:
                seen_guids.add(guid)
                final_results.append(result)
                if len(final_results) >= limit:
                    break

        return self._format_results(final_results[:limit], include_score=False)
    
    def search_hybrid(
        self,
        image_path: Optional[Union[str, Path]] = None,
        text_query: Optional[str] = None,
        filters: Optional[Filter] = None,
        limit: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Hybrid search combining visual similarity and text/metadata.
        
        Args:
            image_path: Optional query image for visual similarity
            text_query: Optional text query
            filters: Optional metadata filters
            limit: Number of results
            score_threshold: Minimum similarity score for image search
            
        Returns:
            List of search results
        """
        # Build combined filters
        combined_filter = filters
        
        # Add text query if provided
        if text_query:
            text_conditions = [
                FieldCondition(
                    key=field,
                    match=MatchAny(any=[text_query.lower()])
                )
                for field in [
                    'description_parsed.objects',
                    'description_parsed.materials',
                    'description_parsed.setting',
                    'description_parsed.visual_attributes'
                ]
            ]
            
            if combined_filter:
                if not combined_filter.should:
                    combined_filter.should = []
                combined_filter.should.extend(text_conditions)
            else:
                combined_filter = Filter(should=text_conditions)
        
        # If image provided, do visual similarity search with filters
        if image_path:
            return self.search_by_image(
                image_path,
                limit=limit,
                filters=combined_filter,
                score_threshold=score_threshold
            )
        
        # Otherwise, just filter-based search
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=combined_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        return self._format_results(results, include_score=False)
    
    def get_photo_by_guid(self, guid: str) -> Optional[Dict]:
        """Retrieve a photo by its GUID.
        
        Args:
            guid: Photo GUID
            
        Returns:
            Photo payload or None if not found
        """
        point_id = Utils.guid_to_point_id(guid)
        
        results = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[point_id],
            with_payload=True,
            with_vectors=False
        )
        
        if results:
            return results[0].payload
        return None
    
    def get_photo_by_path(self, file_path: Union[str, Path]) -> Optional[Dict]:
        """Retrieve a photo by its file path.
        
        Args:
            file_path: Path to photo file
            
        Returns:
            Photo payload or None if not found
        """
        guid = Utils.get_photo_guid(Path(file_path))
        return self.get_photo_by_guid(guid)
    
    def search_similar_to_guid(
        self,
        guid: str,
        limit: int = 10,
        filters: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Find photos similar to a photo identified by GUID.
        
        Args:
            guid: GUID of the reference photo
            limit: Number of results to return
            filters: Optional Qdrant filters
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of similar photos
        """
        # Get the photo's point ID
        point_id = Utils.guid_to_point_id(guid)
        
        # Retrieve the point with its vector
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[point_id],
            with_payload=False,
            with_vectors=True
        )
        
        if not points:
            raise ValueError(f"Photo with GUID {guid} not found in collection")
        
        # Get the embedding vector
        embedding = np.array(points[0].vector)
        
        # Search for similar photos
        results = self.search_by_embedding(
            embedding,
            limit=limit + 1,  # +1 because the photo itself will be in results
            filters=filters,
            score_threshold=score_threshold
        )
        
        # Filter out the original photo from results
        filtered_results = [r for r in results if r['guid'] != guid]
        
        return filtered_results[:limit]
    
    def get_facets(
        self,
        field: str,
        filters: Optional[Filter] = None,
        limit: int = 100
    ) -> Dict[str, int]:
        """Get unique values and counts for a field.
        
        Args:
            field: Field to get facets for
            filters: Optional filters to apply first
            limit: Max results to scan
            
        Returns:
            Dictionary of {value: count}
        """
        facets = {}
        
        # Scroll through collection
        offset = None
        scanned = 0
        
        while scanned < limit:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filters,
                limit=min(100, limit - scanned),
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            if not results:
                break
            
            # Extract field values
            for result in results:
                value = self._get_nested_field(result.payload, field)
                if value is not None:
                    if isinstance(value, list):
                        for v in value:
                            facets[v] = facets.get(v, 0) + 1
                    else:
                        facets[value] = facets.get(value, 0) + 1
            
            scanned += len(results)
            
            if offset is None:
                break
        
        return dict(sorted(facets.items(), key=lambda x: x[1], reverse=True))
    
    def get_stats(self) -> Dict:
        """Get collection statistics.
        
        Returns:
            Dictionary with collection stats
        """
        collection_info = self.client.get_collection(self.collection_name)
        
        return {
            'total_photos': collection_info.points_count,
            'vector_dimension': collection_info.config.params.vectors.size,
            'indexed_count': collection_info.points_count
        }
    
    def _format_results(
        self,
        results: List,
        include_score: bool = True
    ) -> List[Dict]:
        """Format search results into consistent structure.
        
        Args:
            results: Raw Qdrant results
            include_score: Whether to include similarity score
            
        Returns:
            List of formatted result dictionaries
        """
        formatted = []
        
        for result in results:
            item = {
                'guid': result.payload.get('guid'),
                'file_path': result.payload.get('file_path'),
                'file_name': result.payload.get('file_name'),
                'date_taken': result.payload.get('exif', {}).get('date_taken'),
                'description': result.payload.get('description_parsed'),
                'location': result.payload.get('location'),
                'payload': result.payload  # Full payload for detailed view
            }
            
            if include_score and hasattr(result, 'score'):
                item['score'] = result.score
            
            formatted.append(item)
        
        return formatted
    
    def _get_nested_field(self, obj: Dict, field: str):
        """Get nested field value using dot notation.
        
        Args:
            obj: Dictionary to search
            field: Field path (e.g., 'exif.camera_make')
            
        Returns:
            Field value or None
        """
        parts = field.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current


# Filter builder helpers
class FilterBuilder:
    """Helper class to build Qdrant filters easily."""
    
    @staticmethod
    def by_date_range(start_date: str, end_date: str) -> Filter:
        """Filter by date range.
        
        Args:
            start_date: ISO format date string
            end_date: ISO format date string
            
        Returns:
            Qdrant Filter
        """
        return Filter(
            must=[
                FieldCondition(
                    key='exif.date_taken',
                    range=Range(
                        gte=start_date,
                        lte=end_date
                    )
                )
            ]
        )
    
    @staticmethod
    def by_location(city: Optional[str] = None, 
                    state: Optional[str] = None,
                    country: Optional[str] = None) -> Filter:
        """Filter by location.
        
        Args:
            city: City name
            state: State name
            country: Country name
            
        Returns:
            Qdrant Filter
        """
        conditions = []
        
        if city:
            conditions.append(
                FieldCondition(
                    key='location.city',
                    match=MatchValue(value=city)
                )
            )
        if state:
            conditions.append(
                FieldCondition(
                    key='location.state',
                    match=MatchValue(value=state)
                )
            )
        if country:
            conditions.append(
                FieldCondition(
                    key='location.country',
                    match=MatchValue(value=country)
                )
            )
        
        return Filter(must=conditions) if conditions else None
    
    @staticmethod
    def by_camera(make: Optional[str] = None,
                  model: Optional[str] = None) -> Filter:
        """Filter by camera.
        
        Args:
            make: Camera make
            model: Camera model
            
        Returns:
            Qdrant Filter
        """
        conditions = []
        
        if make:
            conditions.append(
                FieldCondition(
                    key='exif.camera_make',
                    match=MatchValue(value=make)
                )
            )
        if model:
            conditions.append(
                FieldCondition(
                    key='exif.camera_model',
                    match=MatchValue(value=model)
                )
            )
        
        return Filter(must=conditions) if conditions else None
    
    @staticmethod
    def by_description_contains(keywords: List[str]) -> Filter:
        """Filter by keywords in description.
        
        Args:
            keywords: List of keywords to search for
            
        Returns:
            Qdrant Filter
        """
        conditions = []
        
        for keyword in keywords:
            conditions.append(
                FieldCondition(
                    key='description_parsed.objects',
                    match=MatchAny(any=[keyword.lower()])
                )
            )
        
        return Filter(should=conditions)
    
    @staticmethod
    def combine_filters(*filters: Filter) -> Filter:
        """Combine multiple filters with AND logic.
        
        Args:
            *filters: Variable number of Filter objects
            
        Returns:
            Combined Filter
        """
        all_conditions = []
        
        for f in filters:
            if f and f.must:
                all_conditions.extend(f.must)
        
        return Filter(must=all_conditions) if all_conditions else None

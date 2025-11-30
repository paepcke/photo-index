#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-28 15:09:25
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-29 12:31:03
"""Face search functionality for finding similar faces."""

from pathlib import Path
from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from logging_service import LoggingService
from photo_index.face_detector import FaceDetector


class FaceSearcher:
    """Search for faces using InsightFace embeddings in Qdrant."""

    def __init__(
        self,
        qdrant_client: QdrantClient,
        faces_collection_name: str = 'photo_faces'
    ):
        """Initialize face searcher.

        Args:
            qdrant_client: Qdrant client instance
            faces_collection_name: Name of the faces collection
        """
        self.qdrant_client = qdrant_client
        self.faces_collection_name = faces_collection_name
        self.face_detector = FaceDetector()
        self.log = LoggingService()

    def search_by_photo(
        self,
        photo_path: Path,
        face_index: int = 0,
        limit: int = 20,
        score_threshold: float = 0.5
    ) -> List[Dict]:
        """Search for similar faces using a face from a photo.

        Args:
            photo_path: Path to photo containing the face to search for
            face_index: Index of face in photo (0=largest, 1=second largest, etc.)
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of face results with photo info and similarity scores
        """
        # Detect faces in the query photo
        detected_faces = self.face_detector.detect_faces(photo_path)

        if not detected_faces or face_index >= len(detected_faces):
            return []

        # Get the embedding for the specified face
        query_embedding = detected_faces[face_index].embedding

        # Search in Qdrant
        results = self.qdrant_client.search(
            collection_name=self.faces_collection_name,
            query_vector=query_embedding.tolist(),
            limit=limit,
            score_threshold=score_threshold
        )

        # Format results
        face_results = []
        for result in results:
            face_results.append({
                'photo_guid': result.payload['photo_guid'],
                'photo_path': result.payload['photo_path'],
                'photo_filename': result.payload['photo_filename'],
                'face_index': result.payload['face_index'],
                'bbox': result.payload['bbox'],
                'confidence': result.payload['confidence'],
                'person_name': result.payload['person_name'],
                'similarity_score': result.score
            })

        return face_results

    def search_by_person_name(
        self,
        person_name: str,
        limit: int = 100
    ) -> List[Dict]:
        """Search for all faces tagged with a specific person name.

        Args:
            person_name: Name of the person to search for
            limit: Maximum number of results

        Returns:
            List of face results
        """
        # Use Qdrant filter to search by person_name
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="person_name",
                    match=MatchValue(value=person_name)
                )
            ]
        )

        results = self.qdrant_client.scroll(
            collection_name=self.faces_collection_name,
            scroll_filter=filter_condition,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )

        # Format results (scroll returns tuple of (records, offset))
        records, _ = results
        face_results = []
        for record in records:
            face_results.append({
                'photo_guid': record.payload['photo_guid'],
                'photo_path': record.payload['photo_path'],
                'photo_filename': record.payload['photo_filename'],
                'face_index': record.payload['face_index'],
                'bbox': record.payload['bbox'],
                'confidence': record.payload['confidence'],
                'person_name': record.payload['person_name']
            })

        return face_results

    def tag_face(
        self,
        photo_guid: str,
        face_index: int,
        person_name: str
    ) -> bool:
        """Tag a detected face with a person's name.

        Args:
            photo_guid: GUID of the photo containing the face
            face_index: Index of the face in the photo
            person_name: Name to tag the face with

        Returns:
            True if successful, False otherwise
        """
        try:
            from common.utils import Utils

            # Find the face point by combining photo GUID and face index
            face_id = Utils.guid_to_point_id(f"{photo_guid}_face_{face_index}")

            # Update the face payload
            self.qdrant_client.set_payload(
                collection_name=self.faces_collection_name,
                payload={'person_name': person_name},
                points=[face_id]
            )

            # Also update the photo's payload with all person names for text search
            self._update_photo_person_names(photo_guid)

            return True

        except Exception as e:
            self.log.err(f"Error tagging face: {e}")
            return False

    def _update_photo_person_names(self, photo_guid: str):
        """Update the photo's payload with list of all tagged person names.

        Args:
            photo_guid: GUID of the photo
        """
        try:
            from common.utils import Utils

            # Get all faces for this photo
            faces = self.get_faces_for_photo(photo_guid)

            # Collect unique person names (excluding None)
            # Store in lowercase for case-insensitive search
            person_names = set()
            for face in faces:
                if face['person_name']:
                    person_names.add(face['person_name'].lower())

            # Update the photo's payload in photo_embeddings collection
            photo_point_id = Utils.guid_to_point_id(photo_guid)
            self.qdrant_client.set_payload(
                collection_name='photo_embeddings',
                payload={'person_names': list(person_names)},
                points=[photo_point_id]
            )

        except Exception as e:
            self.log.err(f"Error updating photo person names: {e}")

    def get_faces_for_photo(
        self,
        photo_guid: str
    ) -> List[Dict]:
        """Get all detected faces for a specific photo.

        Args:
            photo_guid: GUID of the photo

        Returns:
            List of face records
        """
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="photo_guid",
                    match=MatchValue(value=photo_guid)
                )
            ]
        )

        results = self.qdrant_client.scroll(
            collection_name=self.faces_collection_name,
            scroll_filter=filter_condition,
            limit=100,
            with_payload=True,
            with_vectors=False
        )

        # Format results
        records, _ = results
        face_results = []
        for record in records:
            face_results.append({
                'face_index': record.payload['face_index'],
                'bbox': record.payload['bbox'],
                'confidence': record.payload['confidence'],
                'person_name': record.payload['person_name']
            })

        # Sort by face_index
        face_results.sort(key=lambda x: x['face_index'])

        return face_results

    def get_all_person_names(self) -> List[str]:
        """Get list of all unique person names that have been tagged.

        Returns:
            List of person names (excluding None)
        """
        # Scroll through all faces and collect unique person names
        person_names = set()
        offset = None

        while True:
            records, offset = self.qdrant_client.scroll(
                collection_name=self.faces_collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            for record in records:
                person_name = record.payload.get('person_name')
                if person_name:
                    person_names.add(person_name)

            if offset is None:
                break

        return sorted(list(person_names))

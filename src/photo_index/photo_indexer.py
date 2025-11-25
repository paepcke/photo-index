#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-24 17:42:14

"""
Main photo indexing system. Instead of CLI args, uses
config.py file in same directory as this file.

Usage (after adjusting config.py):

    src/photo_indexer/photo_indexer.py
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from logging_service import LoggingService
from photo_index.utils import timed, Utils

from photo_index.config import (
    PHOTO_DIR, QDRANT_PATH, COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT,
    EMBEDDING_DIM, MODEL_NAME, DEVICE, BATCH_SIZE, EMBEDDING_DIM, 
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, MODEL_PATH, GEN_IMG_DESCRIPTIONS,
    IMG_DESC_PROMPT
)
from photo_index.exif_utils import ExifExtractor
from photo_index.embedding_generator import EmbeddingGenerator
from photo_index.geocoding import Geocoder
from photo_index.mac_metadata import MacMetadataExtractor

class PhotoIndexer:
    """Main photo indexing class that coordinates all indexing operations."""
    
    def __init__(
        self,
        photo_dir: str = PHOTO_DIR,
        qdrant_path: str = QDRANT_PATH,
        collection_name: str = COLLECTION_NAME,
        model_name: str = MODEL_NAME,
        device: str = DEVICE,
        batch_size: int = BATCH_SIZE,
        enable_geocoding: bool = True
    ):
        """Initialize the photo indexer.
        
        Args:
            photo_dir: Directory containing photos to index
            qdrant_path: Path for Qdrant local storage
            collection_name: Name of the Qdrant collection
            model_name: HuggingFace model name for embeddings
            device: Device to run model on
            batch_size: Batch size for processing
            enable_geocoding: Whether to enable GPS to location conversion
        """
        self.photo_dir = Path(photo_dir)
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.enable_geocoding = enable_geocoding

        self.log = LoggingService()
        
        # Initialize components
        self.log.info("Initializing indexer components...")
        
        # Qdrant client
        self.qdrant_client = QdrantClient(path=qdrant_path)
        
        # EXIF extractor
        self.exif_extractor = ExifExtractor()
        
        # Mac metadata extractor
        self.mac_metadata_extractor = MacMetadataExtractor() 

        # Geocoder (only if enabled)
        self.geocoder = None
        if self.enable_geocoding:
            try:
                self.geocoder = Geocoder()
            except Exception as e:
                self.log.err(f"Warning: Could not initialize geocoder: {e}")
                self.log.err("Continuing without geocoding functionality")
                self.enable_geocoding = False        
        
        # Embedding generator
        self.embedding_generator = EmbeddingGenerator(MODEL_PATH, device)
        
        # Get actual embedding dimension from model
        self.embedding_dim = EMBEDDING_DIM if EMBEDDING_DIM else self.embedding_generator.get_embedding_dim()
        
        # Initialize collection
        self._init_collection()
        
        self.log.info("Indexer initialized successfully")
    
    def _init_collection(self):
        """Initialize or recreate the Qdrant collection."""
        collections = self.qdrant_client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)
        
        if collection_exists:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            existing_dim = collection_info.config.params.vectors.size
            
            if existing_dim != self.embedding_dim:
                points_count = collection_info.points_count
                
                # Warn if deleting data
                if points_count > 0:
                    self.log.warn(f"WARNING: Collection has {points_count} indexed photos!")
                    self.log.warn(f"Dimension mismatch: existing={existing_dim}, need={self.embedding_dim}")
                    response = input("Delete and recreate? (yes/no): ")
                    if response.lower() != 'yes':
                        raise RuntimeError("Collection dimension mismatch. Aborting.")
                else:
                    self.log.err(f"Dimension mismatch: existing={existing_dim}, need={self.embedding_dim}")
                
                # Delete regardless of points_count
                self.log.info(f"Deleting and recreating collection...")
                self.qdrant_client.delete_collection(self.collection_name)
                collection_exists = False
            else:
                self.log.info(f"Collection '{self.collection_name}' exists with correct dimension")
        
        if not collection_exists:
            self.log.info(f"Creating collection with dimension {self.embedding_dim}...")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            self.log.info("Collection created")
    
    def find_photos(self) -> List[Path]:
        """Find all photo files in the photo directory.
        
        Returns:
            List of paths to photo files
        """
        self.log.info(f"Scanning {self.photo_dir} for photos...")
        
        photo_paths = []
        for ext in IMAGE_EXTENSIONS:
            photo_paths.extend(self.photo_dir.rglob(f"*{ext}"))
        
        # Filter out AppleDouble files
        photo_paths = [p for p in photo_paths if not p.name.startswith('._')]
        
        self.log.info(f"Found {len(photo_paths)} photos")
        return sorted(photo_paths)
    
    def index_photo(self, photo_path: Path) -> Optional[Dict]:
        """Index a single photo.
        
        Args:
            photo_path: Path to the photo file
            
        Returns:
            Dictionary containing indexed data or None on failure
        """
        try:
            # Generate stable GUID based on file content
            photo_guid = Utils.get_photo_guid(photo_path)
            
            # Generate embedding
            #with timed(f'Embedding {photo_path.name}', self.log):
            #    embedding = self.embedding_generator.generate_embedding(photo_path)
            embedding = self.embedding_generator.generate_embedding(photo_path)

            # If requested, also generate image descriptions
            description = None
            if GEN_IMG_DESCRIPTIONS == 1:
                retried_once = False
                prompt = IMG_DESC_PROMPT
                while True:
                    description = self.embedding_generator.generate_description(
                        photo_path,
                        prompt=prompt
                        )
                    if description:
                        try:
                            description_parsed = json.loads(description)
                            # All good, no retry:
                            break
                        except json.JSONDecodeError as e:
                            self.description_failures += 1
                            # Log the bad JSON
                            # self.log.warn(f"JSON parse failed for {photo_path.name}")
                            # self.log.warn(f"  Error at position {e.pos}: {e.msg}")
                            # self.log.warn(f"  Raw description length: {len(description)} chars")
                                                
                            # Try to fix common issues
                            description_parsed = self._try_fix_json(description)
                            if description_parsed:
                                self.description_failures_fixed += 1
                                self.log.info(f"  ✓ Auto-fixed JSON for {photo_path.name}")
                                # All good, no retry:
                                break
                            else:
                                self.log.warn(f"  ✗ Could not auto-fix JSON")
                                if not retried_once:
                                    # Retry once asking the model, with a correction request:
                                    prompt = (f'I gave you the following prompt:"{IMG_DESC_PROMPT}" for this image. You returned the following description:\n'
                                            f'{description}\n'
                                            'You see that this is not proper JSON. Can you try again? '
                                            'No text other than JSON!'
                                            )
                                    retried_once = True
                                    self.log.warn("  Retrying model for correction...")
                                    continue
                                # We retried once; give up:
                                # Write to file for inspection
                                bad_json_file = Path(f"/tmp/bad_json_{photo_path.stem}.txt")
                                bad_json_file.write_text(f"Photo: {photo_path}\n\nError after retry: {e}\n\nJSON:\n{description}")
                                self.log.warn(f"  Saved to: {bad_json_file}")
                                break

            
            # Extract EXIF
            #with timed(f'EXIF {photo_path.name}', self.log):
            #    exif_data = self.exif_extractor.extract_exif(photo_path)
            exif_data = self.exif_extractor.extract_exif(photo_path)
            
            # Extract Mac metadata
            mac_metadata = self.mac_metadata_extractor.extract_metadata(photo_path)
            
            # Get location from GPS if available
            location = None
            if self.enable_geocoding and self.geocoder and exif_data['gps']:
                gps = exif_data['gps']
                if 'latitude' in gps and 'longitude' in gps:
                    location = self.geocoder.get_location(
                        gps['latitude'],
                        gps['longitude']
                    )                    
                                
            # Build payload
            payload = {
                'guid': photo_guid,  # ADD: Stable unique identifier
                'file_path': str(photo_path),
                'file_name': photo_path.name,
                'file_size': photo_path.stat().st_size,
                'indexed_at': datetime.now().isoformat(),
                
                # Image description (if generated)
                'description': description,  # description of photo as raw output from model
                'description_parsed': description_parsed,
                
                # EXIF data
                'exif': {
                    'camera_make': exif_data['camera_make'],
                    'camera_model': exif_data['camera_model'],
                    'date_taken': exif_data['date_taken'],
                    'width': exif_data['width'],
                    'height': exif_data['height'],
                    'iso': exif_data['iso'],
                    'focal_length': exif_data['focal_length'],
                    'aperture': exif_data['aperture'],
                    'exposure_time': exif_data['exposure_time'],
                },
                
                # GPS data
                'gps': exif_data['gps'],
                'location': location,
                
                # Mac metadata
                'mac_metadata': mac_metadata,
            }
            
            return {
                'path': photo_path,
                'guid': photo_guid,  # ADD: Include GUID in result
                'embedding': embedding,
                'payload': payload
            }
            
        except Exception as e:
            self.log.err(f"Error indexing {photo_path}: {e}")
            return None

    def index_batch(self, photo_paths: List[Path], time_report_every: int = 100) -> List[PointStruct]:
        """Index a batch of photos.
        
        Args:
            photo_paths: List of photo paths to index
            time_report_every: number of photos to process before reporting elapsed time (for the batch)
            
        Returns:
            List of Qdrant points
        """
        points = []
    
        for i, photo_path in enumerate(photo_paths):
            result = self.index_photo(photo_path)
            if result:
                # Use GUID-based point ID
                point_id = Utils.guid_to_point_id(result['guid'])  # CHANGE: Use GUID
                
                point = PointStruct(
                    id=point_id,
                    vector=result['embedding'].tolist(),
                    payload=result['payload']
                )
                
                points.append(point)
        
        return points
    
    def index_all(self, force_reindex: bool = False, time_report_every: int = 100):
        """Index all photos in the photo directory.
        
        Args:
            force_reindex: If True, reindex all photos. Otherwise skip already indexed.
            time_report_every: number of photos to process before reporting elapsed time for that batch.
        """
        # Find all photos
        photo_paths = self.find_photos()
        
        if not photo_paths:
            self.log.warn("No photos found to index")
            return
        
        # Get already indexed photos if not forcing reindex
        indexed_paths = set()
        if not force_reindex:
            indexed_paths = self._get_indexed_paths()
            photo_paths = [p for p in photo_paths if str(p) not in indexed_paths]
            self.log.info(f"Skipping {len(indexed_paths)} already indexed photos")
        
        if not photo_paths:
            self.log.info("All photos already indexed")
            return
        
        self.log.info(f"Indexing {len(photo_paths)} photos...")
        
        # Process in batches
        #for i in tqdm(range(0, len(photo_paths), self.batch_size), desc="Indexing batches"):
        num_photos = len(photo_paths)
        # No model-generated image descriptions that are
        # JSON parsable:
        self.description_failures = 0
        # No failures fixed yet either:
        self.description_failures_fixed = 0
        with timed('indexing all photos') as timer:
            for i in range(0, num_photos, self.batch_size):
                batch = photo_paths[i:i + self.batch_size]
                points = self.index_batch(batch, time_report_every=time_report_every)
                timer.progress(i+self.batch_size, every=self.batch_size, total=num_photos)
                
                if points:
                    # Upload to Qdrant
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
        log_msg = (f"Indexing complete! Indexed {len(photo_paths)} photos.")                    
        if GEN_IMG_DESCRIPTIONS:
            log_msg = (f"Indexing complete! Indexed {len(photo_paths)} photos. "
                       f"\n    Malformed img descriptions: {self.description_failures}"
                       f"\n    Fixed img descriptions:     {self.description_failures_fixed}"
                       f"\n    Total missing descriptions: {self.description_failures - self.description_failures_fixed}"
            )
        self.log.info(log_msg)

        self._print_stats()
    
    def _get_indexed_paths(self) -> set:
        """Get set of already indexed photo paths.
        
        Returns:
            Set of file paths that are already indexed
        """
        try:
            # Scroll through all points to get file paths
            indexed_paths = set()
            offset = None
            
            while True:
                records, offset = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                for record in records:
                    if 'file_path' in record.payload:
                        indexed_paths.add(record.payload['file_path'])
                
                if offset is None:
                    break
            
            return indexed_paths
            
        except Exception as e:
            self.log.err(f"Error getting indexed paths: {e}")
            return set()
    
    def _print_stats(self):
        """Print indexing statistics."""
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            print(f"\nCollection stats:")
            print(f"  Total points: {collection_info.points_count}")
            print(f"  Vector dimension: {self.embedding_dim}")
        except Exception as e:
            print(f"Error getting stats: {e}")

    def _try_fix_json(self, json_str: str) -> Optional[dict]:
        """Attempt to fix common JSON formatting issues."""
        import re
        
        fixes = [
            ('leading_text', lambda s: s[s.find('{'):] if '{' in s else s),
            ('trailing_text', lambda s: s[:s.rfind('}')+1] if '}' in s else s),
            ('remove_escaped_newlines', lambda s: s.replace('\\n', '')),
            ('markdown', lambda s: re.sub(r'```json\s*|\s*```', '', s)),
            ('whitespace', lambda s: s.strip()),
            ('trailing_brace', lambda s: re.sub(r',\s*}', '}', s)),
            ('trailing_bracket', lambda s: re.sub(r',\s*]', ']', s)),
        ]
        
        current = json_str
        
        for name, fix_func in fixes:
            try:
                current = fix_func(current)
            except Exception as e:
                self.log.warn(f"    Exception in fix '{name}': {e} (applying next fix(s))")
                continue
        
        # Now try to parse
        try:
            result = json.loads(current)
            self.log.debug(f"    ✓ Successfully parsed JSON")
            return result
        except json.JSONDecodeError as e:
            self.log.debug(f"    ✗ Parse failed after all fixes: {e.msg} at position {e.pos}")
            return None


    def reindex_photo(self, photo_path: Path):
        """Reindex a specific photo (update existing entry)."""
        result = self.index_photo(photo_path)
        
        if result:
            point_id = Utils.guid_to_point_id(result['guid'])  # CHANGE
            
            point = PointStruct(
                id=point_id,
                vector=result['embedding'].tolist(),
                payload=result['payload']
            )
            
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            self.log.info(f"Reindexed: {photo_path.name}")

    def delete_photo(self, photo_path: Path):
        """Delete a photo from the index."""
        photo_guid = Utils.get_photo_guid(photo_path)  # CHANGE
        point_id = Utils.guid_to_point_id(photo_guid)
        
        self.qdrant_client.delete(
            collection_name=self.collection_name,
            points_selector=[point_id]
        )
        
        self.log.info(f"Deleted from index: {photo_path.name}")

def main():
    """Main entry point for the indexer."""
    # Create indexer
    indexer = PhotoIndexer()
    
    # Index all photos
    with timed('Index all', LoggingService()):
        #******indexer.index_all(force_reindex=False)
        indexer.index_all(force_reindex=True, time_report_every=50)
        #******indexer.index_all(force_reindex=False, time_report_every=50)


if __name__ == "__main__":
    main()

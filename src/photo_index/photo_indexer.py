#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-27 10:04:46
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 21:30:14
"""Main photo indexing system."""

from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from logging_service import LoggingService

from common.config import (
    PHOTO_DIR, QDRANT_PATH, COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT,
    EMBEDDING_DIM, MODEL_NAME, DEVICE, BATCH_SIZE, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    GEN_IMG_DESCRIPTIONS, IMG_DESC_PROMPT
)
from photo_index.exif_utils import ExifExtractor
from photo_index.embedding_generator import EmbeddingGenerator
from photo_index.mac_metadata import MacMetadataExtractor
from photo_index.geocoding import Geocoder
from common.utils import Utils

try:
    from description_parser import DescriptionParser
except ImportError:
    # Description parser might not exist or we parse inline
    DescriptionParser = None


class PhotoIndexer:
    """Main photo indexing class that coordinates all indexing operations."""
    
    def __init__(
        self,
        photo_dir: str = PHOTO_DIR,
        qdrant_path: Optional[str] = QDRANT_PATH,
        qdrant_host: Optional[str] = QDRANT_HOST,
        qdrant_port: Optional[int] = QDRANT_PORT,
        collection_name: str = COLLECTION_NAME,
        model_name: str = MODEL_NAME,
        device: str = DEVICE,
        batch_size: int = BATCH_SIZE,
        enable_geocoding: bool = True
    ):
        """Initialize the photo indexer.
        
        Args:
            photo_dir: Directory containing photos to index
            qdrant_path: Path for Qdrant local storage (if using local mode)
            qdrant_host: Qdrant server host (if using server mode)
            qdrant_port: Qdrant server port (if using server mode)
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

        self.description_failures = 0
        self.description_failures_fixed = 0
        self.description_second_chance = 0
        
        # Initialize components
        self.log.info("Initializing indexer components...")
        
        # Qdrant client (try server first, fall back to local)
        if qdrant_host and qdrant_port:
            try:
                self.log.info(f"Attempting to connect to Qdrant server: {qdrant_host}:{qdrant_port}")
                self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
                # Test connection
                self.qdrant_client.get_collections()
                self.log.info(f"✓ Connected to Qdrant server")
            except Exception as e:
                self.log.warn(f"Warning: Could not connect to Qdrant server: {e}")
                if qdrant_path:
                    self.log.info(f"Falling back to Qdrant local storage: {qdrant_path}")
                    self.qdrant_client = QdrantClient(path=qdrant_path)
                else:
                    raise ValueError("Cannot connect to server and no local path specified")
        elif qdrant_path:
            self.log.info(f"Connecting to Qdrant local storage: {qdrant_path}")
            self.qdrant_client = QdrantClient(path=qdrant_path)
        else:
            raise ValueError("Must specify either (qdrant_host and qdrant_port) or qdrant_path in config.py")
        
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
                self.log.warn(f"Warning: Could not initialize geocoder: {e}")
                self.log.info("Continuing without geocoding functionality")
                self.enable_geocoding = False
        
        # Embedding generator
        self.embedding_generator = EmbeddingGenerator(model_name, device)
        
        # Get actual embedding dimension from model
        self.embedding_dim = self.embedding_generator.get_embedding_dim()
        
        # Initialize collection
        self._init_collection()
        
        self.log.info("Indexer initialized successfully")
    
    def _init_collection(self):
        """Initialize or recreate the Qdrant collection."""
        # Check if collection exists
        collections = self.qdrant_client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)
        
        if collection_exists:
            self.log.info(f"Collection '{self.collection_name}' already exists")
            # Optionally recreate or continue
        else:
            self.log.info(f"Creating collection '{self.collection_name}'...")
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
            # Generate GUID
            guid = Utils.get_photo_guid(photo_path)
            
            # Generate embedding
            embedding = self.embedding_generator.generate_embedding(photo_path)
            
            # Generate description (if requested in config)
            description = None
            description_parsed = None
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
                            # Success! No retry needed
                            break
                        except json.JSONDecodeError as e:
                            self.description_failures += 1
                            
                            # Try to fix common issues
                            description_parsed = Utils.try_fix_json(description)
                            if description_parsed:
                                self.description_failures_fixed += 1
                                self.log.info(f"  ✓ Auto-fixed JSON for {photo_path.name}")
                                # Success! No retry needed
                                break
                            else:
                                self.log.info(f"  ✗ Could not auto-fix JSON for {photo_path.name}")
                                if not retried_once:
                                    # Retry once with correction request
                                    prompt = (f'I gave you the following prompt: "{IMG_DESC_PROMPT}" for this image. '
                                             f'You returned: {description}\n'
                                             'This is not proper JSON. Can you try again? '
                                             'No text other than JSON!')
                                    retried_once = True
                                    self.log.info("  Retrying with correction request...")
                                    self.description_second_chance += 1
                                    continue
                                # We retried; give up and save bad JSON
                                bad_json_file = Path(f"/tmp/bad_json_{photo_path.stem}.txt")
                                bad_json_file.write_text(
                                    f"Photo: {photo_path}\n\nError: {e}\n\nJSON:\n{description}"
                                )
                                self.log.info(f"  Saved bad JSON to: {bad_json_file}")
                                break
                    else:
                        # No description returned
                        break
            else:
                # GEN_IMG_DESCRIPTIONS is disabled, use empty description
                description = ""
                description_parsed = {
                    'objects': [],
                    'materials': [],
                    'setting': [],
                    'visual_attributes': []
                }
            
            # Extract EXIF
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
                'guid': guid,
                'file_path': str(photo_path),
                'file_name': photo_path.name,
                'file_size': photo_path.stat().st_size,
                'indexed_at': datetime.now().isoformat(),
                
                # Description
                'description': description,
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
                'embedding': embedding,
                'payload': payload
            }
            
        except Exception as e:
            self.log.err(f"Error indexing {photo_path}: {e}")
            return None
    
    def _parse_description_inline(self, description: str) -> Dict:
        """Parse description inline when DescriptionParser not available.
        
        Args:
            description: JSON description string
            
        Returns:
            Parsed description dictionary
        """
        try:
            # Try to extract JSON from description
            if '{' in description and '}' in description:
                start = description.index('{')
                end = description.rindex('}') + 1
                json_str = description[start:end]
                parsed = json.loads(json_str)
                
                return {
                    'objects': parsed.get('objects', []),
                    'materials': parsed.get('materials', []),
                    'setting': parsed.get('setting', []),
                    'visual_attributes': parsed.get('visual_attributes', [])
                }
        except:
            pass
        
        # Fallback: empty parsed description
        return {
            'objects': [],
            'materials': [],
            'setting': [],
            'visual_attributes': []
        }
    
    def index_batch(self, photo_paths: List[Path]) -> List[PointStruct]:
        """Index a batch of photos.
        
        Args:
            photo_paths: List of photo paths to index
            
        Returns:
            List of Qdrant points
        """
        points = []
        
        for i, photo_path in enumerate(photo_paths):
            result = self.index_photo(photo_path)
            
            if result:
                # Create Qdrant point using GUID
                guid = result['payload']['guid']
                point_id = Utils.guid_to_point_id(guid)
                
                point = PointStruct(
                    id=point_id,
                    vector=result['embedding'].tolist(),
                    payload=result['payload']
                )
                
                points.append(point)
        
        return points
    
    def index_all(self, force_reindex: bool = False):
        """Index all photos in the photo directory.
        
        Args:
            force_reindex: If True, reindex all photos. Otherwise skip already indexed.
        """
        # Find all photos
        photo_paths = self.find_photos()
        
        if not photo_paths:
            self.log.info("No photos found to index")
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
        
        # Initialize description failure counters
        self.description_failures = 0
        self.description_failures_fixed = 0
        
        # Process in batches
        for i in tqdm(range(0, len(photo_paths), self.batch_size), desc="Indexing batches"):
            batch = photo_paths[i:i + self.batch_size]
            points = self.index_batch(batch)
            
            if points:
                # Upload to Qdrant
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
        
        # Completion message with stats
        log_msg = f"Indexing complete! Indexed {len(photo_paths)} photos"
        if GEN_IMG_DESCRIPTIONS == 1:
            log_msg += (f"\n  Malformed descriptions: {self.description_failures}"
                       f"\n   Auto-fixed: {self.description_failures_fixed}"
                       f"\n   Second chances: {self.description_second_chance}"
                       f"\n   Total missing: {self.description_failures - self.description_failures_fixed}")
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
            self.log.info(f"\nCollection stats:")
            self.log.info(f"  Total points: {collection_info.points_count}")
            self.log.info(f"  Vector dimension: {self.embedding_dim}")
            
            # Print geocoding stats if enabled
            if self.geocoder:
                geo_stats = self.geocoder.get_stats()
                self.log.info(f"\nGeocoding stats:")
                self.log.info(f"  Total requests: {geo_stats['total_requests']}")
                self.log.info(f"  API calls: {geo_stats['api_calls']}")
                self.log.info(f"  Cache hits: {geo_stats['cache_hits']}")
                self.log.info(f"  Cache size: {geo_stats['cache_size']}")
        except Exception as e:
            self.log.info(f"Error getting stats: {e}")
    
    def reindex_photo(self, photo_path: Path):
        """Reindex a specific photo (update existing entry).
        
        Args:
            photo_path: Path to the photo to reindex
        """
        result = self.index_photo(photo_path)
        
        if result:
            point_id = hash(str(result['path'])) % (2**63)
            
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
        """Delete a photo from the index.
        
        Args:
            photo_path: Path to the photo to delete
        """
        point_id = hash(str(photo_path)) % (2**63)
        
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
    indexer.index_all(force_reindex=False)


if __name__ == "__main__":
    main()

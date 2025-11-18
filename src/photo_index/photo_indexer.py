"""Main photo indexing system."""

from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from config import (
    PHOTO_DIR, QDRANT_PATH, COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT,
    EMBEDDING_DIM, MODEL_NAME, DEVICE, BATCH_SIZE, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from exif_utils import ExifExtractor
from embedding_generator import EmbeddingGenerator
from mac_metadata import MacMetadataExtractor


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
        
        # Initialize components
        print("Initializing indexer components...")
        
        # Qdrant client
        self.qdrant_client = QdrantClient(path=qdrant_path)
        
        # EXIF extractor
        self.exif_extractor = ExifExtractor()
        
        # Mac metadata extractor
        self.mac_metadata_extractor = MacMetadataExtractor()
        
        # Embedding generator
        self.embedding_generator = EmbeddingGenerator(model_name, device)
        
        # Get actual embedding dimension from model
        self.embedding_dim = self.embedding_generator.get_embedding_dim()
        
        # Initialize collection
        self._init_collection()
        
        print("Indexer initialized successfully")
    
    def _init_collection(self):
        """Initialize or recreate the Qdrant collection."""
        # Check if collection exists
        collections = self.qdrant_client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)
        
        if collection_exists:
            print(f"Collection '{self.collection_name}' already exists")
            # Optionally recreate or continue
        else:
            print(f"Creating collection '{self.collection_name}'...")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            print("Collection created")
    
    def find_photos(self) -> List[Path]:
        """Find all photo files in the photo directory.
        
        Returns:
            List of paths to photo files
        """
        print(f"Scanning {self.photo_dir} for photos...")
        
        photo_paths = []
        for ext in IMAGE_EXTENSIONS:
            photo_paths.extend(self.photo_dir.rglob(f"*{ext}"))
        
        # Filter out AppleDouble files
        photo_paths = [p for p in photo_paths if not p.name.startswith('._')]
        
        print(f"Found {len(photo_paths)} photos")
        return sorted(photo_paths)
    
    def index_photo(self, photo_path: Path) -> Optional[Dict]:
        """Index a single photo.
        
        Args:
            photo_path: Path to the photo file
            
        Returns:
            Dictionary containing indexed data or None on failure
        """
        try:
            # Generate embedding
            embedding = self.embedding_generator.generate_embedding(photo_path)
            
            # Extract EXIF
            exif_data = self.exif_extractor.extract_exif(photo_path)
            
            # Extract Mac metadata
            mac_metadata = self.mac_metadata_extractor.extract_metadata(photo_path)
            
            # Get location from GPS if available
            location = None
            if self.enable_geocoding and exif_data['gps']:
                gps = exif_data['gps']
                if 'latitude' in gps and 'longitude' in gps:
                    location = self.exif_extractor.get_location_name(
                        gps['latitude'],
                        gps['longitude']
                    )
            
            # Build payload
            payload = {
                'file_path': str(photo_path),
                'file_name': photo_path.name,
                'file_size': photo_path.stat().st_size,
                'indexed_at': datetime.now().isoformat(),
                
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
            print(f"Error indexing {photo_path}: {e}")
            return None
    
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
                # Create Qdrant point
                point_id = hash(str(result['path'])) % (2**63)  # Generate consistent ID
                
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
            print("No photos found to index")
            return
        
        # Get already indexed photos if not forcing reindex
        indexed_paths = set()
        if not force_reindex:
            indexed_paths = self._get_indexed_paths()
            photo_paths = [p for p in photo_paths if str(p) not in indexed_paths]
            print(f"Skipping {len(indexed_paths)} already indexed photos")
        
        if not photo_paths:
            print("All photos already indexed")
            return
        
        print(f"Indexing {len(photo_paths)} photos...")
        
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
        
        print(f"Indexing complete! Indexed {len(photo_paths)} photos")
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
            print(f"Error getting indexed paths: {e}")
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
            
            print(f"Reindexed: {photo_path.name}")
    
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
        
        print(f"Deleted from index: {photo_path.name}")


def main():
    """Main entry point for the indexer."""
    # Create indexer
    indexer = PhotoIndexer()
    
    # Index all photos
    indexer.index_all(force_reindex=False)


if __name__ == "__main__":
    main()

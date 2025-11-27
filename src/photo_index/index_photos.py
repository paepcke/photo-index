# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-25 16:09:09
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 11:02:50
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced photo indexer with incremental indexing support.

Usage:
    index_photos.py                              # Index new photos only
    index_photos.py --force                      # Reindex everything
    index_photos.py --file /path/to/photo.jpg    # Index single file
    index_photos.py --since 2024-11-18           # Index photos from date
    index_photos.py --dry-run                    # Preview what would be indexed
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional

# Assuming photo_indexer package structure
from photo_index.photo_indexer import PhotoIndexer
from common.utils import Utils
from common.config import PHOTO_DIR


def check_photo_indexed(indexer: PhotoIndexer, photo_path: Path) -> bool:
    """Check if a photo is already indexed by GUID.
    
    Args:
        indexer: PhotoIndexer instance
        photo_path: Path to photo file
        
    Returns:
        True if photo is indexed, False otherwise
    """
    try:
        guid = Utils.get_photo_guid(photo_path)
        point_id = Utils.guid_to_point_id(guid)
        
        # Try to retrieve the point
        results = indexer.qdrant_client.retrieve(
            collection_name=indexer.collection_name,
            ids=[point_id],
            with_payload=False,
            with_vectors=False
        )
        
        return len(results) > 0
        
    except Exception as e:
        print(f"Error checking if {photo_path.name} is indexed: {e}")
        return False


def get_indexed_guids(indexer: PhotoIndexer) -> Set[str]:
    """Get set of all indexed photo GUIDs.
    
    Args:
        indexer: PhotoIndexer instance
        
    Returns:
        Set of GUIDs
    """
    guids = set()
    
    try:
        offset = None
        while True:
            records, offset = indexer.qdrant_client.scroll(
                collection_name=indexer.collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            if not records:
                break
            
            for record in records:
                if 'guid' in record.payload:
                    guids.add(record.payload['guid'])
            
            if offset is None:
                break
                
    except Exception as e:
        print(f"Error getting indexed GUIDs: {e}")
    
    return guids


def filter_photos_by_date(photos: List[Path], since_date: datetime) -> List[Path]:
    """Filter photos by modification date.
    
    Args:
        photos: List of photo paths
        since_date: Only include photos modified after this date
        
    Returns:
        Filtered list of photos
    """
    filtered = []
    
    for photo in photos:
        try:
            mtime = datetime.fromtimestamp(photo.stat().st_mtime)
            if mtime >= since_date:
                filtered.append(photo)
        except Exception as e:
            print(f"Warning: Could not check date for {photo.name}: {e}")
            # Include it anyway to be safe
            filtered.append(photo)
    
    return filtered


def index_single_file(
    indexer: PhotoIndexer,
    file_path: Path,
    force: bool = False,
    dry_run: bool = False
) -> bool:
    """Index a single photo file.
    
    Args:
        indexer: PhotoIndexer instance
        file_path: Path to photo file
        force: Force reindex even if already indexed
        dry_run: Don't actually index, just show what would happen
        
    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False
    
    # Check if already indexed
    if not force and check_photo_indexed(indexer, file_path):
        print(f"Already indexed: {file_path.name}")
        if not dry_run:
            print("Use --force to reindex")
        return True
    
    if dry_run:
        print(f"Would index: {file_path.name}")
        return True
    
    print(f"Indexing: {file_path.name}")
    
    try:
        # Index the photo
        result = indexer.index_photo(file_path)
        
        if result:
            # Create and upload point
            from qdrant_client.models import PointStruct
            
            point_id = Utils.guid_to_point_id(result['payload']['guid'])
            
            point = PointStruct(
                id=point_id,
                vector=result['embedding'].tolist(),
                payload=result['payload']
            )
            
            indexer.qdrant_client.upsert(
                collection_name=indexer.collection_name,
                points=[point]
            )
            
            print(f"✓ Successfully indexed: {file_path.name}")
            return True
        else:
            print(f"✗ Failed to index: {file_path.name}")
            return False
            
    except Exception as e:
        print(f"✗ Error indexing {file_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def index_incremental(
    indexer: PhotoIndexer,
    force: bool = False,
    since_date: Optional[datetime] = None,
    dry_run: bool = False
):
    """Index photos incrementally.
    
    Args:
        indexer: PhotoIndexer instance
        force: Force reindex of all photos
        since_date: Only index photos modified after this date
        dry_run: Preview what would be indexed without actually indexing
    """
    # Find all photos
    print(f"Scanning {indexer.photo_dir}...")
    photo_paths = indexer.find_photos()
    
    if not photo_paths:
        print("No photos found to index")
        return
    
    print(f"Found {len(photo_paths)} total photos")
    
    # Filter by date if requested
    if since_date:
        print(f"Filtering photos modified since {since_date.date()}...")
        photo_paths = filter_photos_by_date(photo_paths, since_date)
        print(f"  → {len(photo_paths)} photos match date filter")
    
    # Skip already indexed unless forcing
    if not force:
        print("Checking which photos are already indexed...")
        indexed_guids = get_indexed_guids(indexer)
        print(f"  → {len(indexed_guids)} photos already in index")
        
        # Filter out already indexed
        to_index = []
        for photo in photo_paths:
            try:
                guid = Utils.get_photo_guid(photo)
                if guid not in indexed_guids:
                    to_index.append(photo)
            except Exception as e:
                print(f"Warning: Could not check {photo.name}: {e}")
                to_index.append(photo)  # Include it to be safe
        
        photo_paths = to_index
        print(f"  → {len(photo_paths)} new photos to index")
    
    if not photo_paths:
        print("\n✓ All photos already indexed. Use --force to reindex.")
        return
    
    if dry_run:
        print(f"\n[DRY RUN] Would index {len(photo_paths)} photos:")
        for i, photo in enumerate(photo_paths[:20], 1):
            print(f"  {i}. {photo.name}")
        if len(photo_paths) > 20:
            print(f"  ... and {len(photo_paths) - 20} more")
        print("\nRun without --dry-run to actually index these photos.")
        return
    
    # Index photos
    print(f"\nIndexing {len(photo_paths)} photos...")
    
    from tqdm import tqdm
    from qdrant_client.models import PointStruct
    
    success_count = 0
    error_count = 0
    
    # Process in batches
    batch_size = indexer.batch_size
    
    for i in tqdm(range(0, len(photo_paths), batch_size), desc="Processing batches"):
        batch = photo_paths[i:i + batch_size]
        points = []
        
        for photo_path in batch:
            try:
                result = indexer.index_photo(photo_path)
                
                if result:
                    point_id = Utils.guid_to_point_id(result['payload']['guid'])
                    
                    point = PointStruct(
                        id=point_id,
                        vector=result['embedding'].tolist(),
                        payload=result['payload']
                    )
                    
                    points.append(point)
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"\nError processing {photo_path.name}: {e}")
                error_count += 1
        
        # Upload batch to Qdrant
        if points:
            try:
                indexer.qdrant_client.upsert(
                    collection_name=indexer.collection_name,
                    points=points
                )
            except Exception as e:
                print(f"\nError uploading batch to Qdrant: {e}")
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Indexing complete!")
    print(f"  ✓ Successfully indexed: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description='Index photos with incremental support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index new photos only (default)
  %(prog)s
  
  # Force reindex everything
  %(prog)s --force
  
  # Index single file
  %(prog)s --file /raid/photos/IMG_4681.JPG
  
  # Force reindex single file
  %(prog)s --file /raid/photos/IMG_4681.JPG --force
  
  # Index photos modified since a date
  %(prog)s --since 2024-11-18
  
  # Preview what would be indexed
  %(prog)s --dry-run
  %(prog)s --since 2024-11-20 --dry-run
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='Index a single photo file'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reindex even if already indexed'
    )
    parser.add_argument(
        '--since',
        type=str,
        help='Only index photos modified since this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be indexed without actually indexing'
    )
    parser.add_argument(
        '--photo-dir',
        type=str,
        default=PHOTO_DIR,
        help=f'Photo directory (default: {PHOTO_DIR})'
    )
    
    args = parser.parse_args()
    
    # Parse since date if provided
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format '{args.since}'. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Initialize indexer
    print("Initializing photo indexer...")
    indexer = PhotoIndexer(photo_dir=args.photo_dir)
    
    # Single file mode
    if args.file:
        file_path = Path(args.file)
        success = index_single_file(indexer, file_path, args.force, args.dry_run)
        sys.exit(0 if success else 1)
    
    # Incremental indexing mode
    index_incremental(indexer, args.force, since_date, args.dry_run)


if __name__ == '__main__':
    main()

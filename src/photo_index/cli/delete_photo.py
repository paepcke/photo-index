#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-23 17:38:52
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 11:03:51
# -*- coding: utf-8 -*-
"""
Delete photos from the index and optionally from disk.

Usage:
    delete_photo.py /path/to/photo.jpg
    delete_photo.py --delete-file /path/to/photo.jpg
    delete_photo.py -d -y /path/to/photo1.jpg /path/to/photo2.jpg
"""

import argparse
import sys
from pathlib import Path
from qdrant_client import QdrantClient

from common.utils import Utils
from common.config import QDRANT_PATH, COLLECTION_NAME


def confirm_deletion(photo_paths, delete_from_disk):
    """Ask user to confirm deletion."""
    print("\nYou are about to delete:")
    print("-" * 70)
    for path in photo_paths:
        print(f"  {path}")
    print("-" * 70)
    print(f"From index: YES")
    print(f"From disk: {'YES' if delete_from_disk else 'NO'}")
    print()
    
    response = input("Confirm deletion? (yes/no): ").strip().lower()
    return response == 'yes'


def delete_photo_from_index(client, photo_path, collection_name):
    """Delete a photo from the Qdrant index."""
    try:
        # Generate GUID and point ID
        photo_guid = Utils.get_photo_guid(photo_path)
        point_id = Utils.guid_to_point_id(photo_guid)
        
        # Check if it exists
        points = client.retrieve(
            collection_name=collection_name,
            ids=[point_id],
            with_payload=False,
            with_vectors=False
        )
        
        if not points:
            print(f"Warning: {photo_path.name} not found in index", file=sys.stderr)
            return False
        
        # Delete from index
        client.delete(
            collection_name=collection_name,
            points_selector=[point_id]
        )
        
        return True
        
    except Exception as e:
        print(f"Error deleting {photo_path.name} from index: {e}", file=sys.stderr)
        return False


def delete_photo_from_disk(photo_path):
    """Delete a photo file from disk."""
    try:
        photo_path.unlink()
        return True
    except Exception as e:
        print(f"Error deleting {photo_path.name} from disk: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Delete photos from index and optionally from disk'
    )
    parser.add_argument(
        'photo_paths',
        type=str,
        nargs='+',
        help='Paths to photo files to delete'
    )
    parser.add_argument(
        '-d', '--delete-file',
        action='store_true',
        help='Also delete the file from disk (requires confirmation)'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--qdrant-path',
        type=str,
        default=QDRANT_PATH,
        help=f'Qdrant storage path (default: {QDRANT_PATH})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    # Validate all photo paths
    photo_paths = []
    for path_str in args.photo_paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Warning: Photo not found: {path}", file=sys.stderr)
            continue
        photo_paths.append(path)
    
    if not photo_paths:
        print("Error: No valid photo paths provided", file=sys.stderr)
        sys.exit(1)
    
    # Confirm deletion (unless --yes flag)
    if not args.yes and not args.dry_run:
        if not confirm_deletion(photo_paths, args.delete_file):
            print("Deletion cancelled")
            sys.exit(0)
    
    if args.dry_run:
        print("\nDRY RUN - No files will be deleted")
        print("-" * 70)
    
    # Connect to Qdrant
    client = QdrantClient(path=args.qdrant_path)
    
    # Delete photos
    deleted_from_index = 0
    deleted_from_disk = 0
    
    for photo_path in photo_paths:
        print(f"Processing: {photo_path.name}")
        
        # Delete from index
        if args.dry_run:
            print(f"  Would delete from index")
        else:
            if delete_photo_from_index(client, photo_path, COLLECTION_NAME):
                print(f"  ✓ Deleted from index")
                deleted_from_index += 1
            else:
                print(f"  ✗ Failed to delete from index")
        
        # Delete from disk if requested
        if args.delete_file:
            if args.dry_run:
                print(f"  Would delete from disk")
            else:
                if delete_photo_from_disk(photo_path):
                    print(f"  ✓ Deleted from disk")
                    deleted_from_disk += 1
                else:
                    print(f"  ✗ Failed to delete from disk")
    
    # Summary
    print("\n" + "=" * 70)
    if args.dry_run:
        print("DRY RUN COMPLETE")
        print(f"Would delete {len(photo_paths)} photo(s) from index")
        if args.delete_file:
            print(f"Would delete {len(photo_paths)} photo(s) from disk")
    else:
        print("DELETION COMPLETE")
        print(f"Deleted from index: {deleted_from_index}/{len(photo_paths)}")
        if args.delete_file:
            print(f"Deleted from disk: {deleted_from_disk}/{len(photo_paths)}")
    print("=" * 70)


if __name__ == "__main__":
    main()

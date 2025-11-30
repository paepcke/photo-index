#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-29 11:45:00
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-29 11:45:00
"""
Cleanup orphaned entries from the photo index.

This tool scans the index and removes entries for photos that no longer exist on disk.
Useful for maintaining index integrity after photos have been deleted outside the indexer.

Usage:
    # Dry run (show what would be deleted)
    ./cleanup_index.py --dry-run

    # Actually remove orphaned entries (includes faces by default)
    ./cleanup_index.py

    # Remove orphaned entries but keep orphaned face entries
    ./cleanup_index.py --skip-faces
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

from common.config import QDRANT_PATH, QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME


def connect_to_qdrant() -> QdrantClient:
    """Connect to Qdrant (try server first, fall back to local)."""
    if QDRANT_HOST and QDRANT_PORT:
        try:
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            # Test connection
            client.get_collections()
            print(f"Connected to Qdrant server at {QDRANT_HOST}:{QDRANT_PORT}")
            return client
        except Exception as e:
            print(f"Could not connect to Qdrant server: {e}")
            print(f"Falling back to local storage at {QDRANT_PATH}")
            return QdrantClient(path=QDRANT_PATH)
    else:
        print(f"Using local Qdrant storage at {QDRANT_PATH}")
        return QdrantClient(path=QDRANT_PATH)


def find_orphaned_entries(
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME
) -> List[Tuple[int, str, str]]:
    """Find all index entries where the photo file no longer exists.

    Args:
        client: Qdrant client
        collection_name: Name of the collection to scan

    Returns:
        List of tuples: (point_id, file_path, file_name)
    """
    print(f"\nScanning collection '{collection_name}' for orphaned entries...")

    orphaned = []
    total_scanned = 0

    # Scroll through all points in the collection
    offset = None
    batch_size = 100

    while True:
        # Fetch a batch of points
        points, next_offset = client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=batch_size,
            with_payload=True,
            with_vectors=False
        )

        if not points:
            break

        # Check each point
        for point in points:
            total_scanned += 1

            file_path_str = point.payload.get('file_path')
            file_name = point.payload.get('file_name', 'unknown')

            if not file_path_str:
                print(f"Warning: Point {point.id} has no file_path in payload")
                continue

            file_path = Path(file_path_str)

            # Check if file exists
            if not file_path.exists():
                orphaned.append((point.id, file_path_str, file_name))
                if len(orphaned) % 10 == 0:
                    print(f"  Found {len(orphaned)} orphaned entries so far...")

        # Update offset for next batch
        offset = next_offset
        if offset is None:
            break

        # Progress update
        if total_scanned % 1000 == 0:
            print(f"  Scanned {total_scanned} entries...")

    print(f"✓ Scanned {total_scanned} total entries")
    print(f"✓ Found {len(orphaned)} orphaned entries")

    return orphaned


def find_orphaned_faces(
    client: QdrantClient,
    photo_guids: List[str]
) -> List[int]:
    """Find face entries associated with deleted photos.

    Args:
        client: Qdrant client
        photo_guids: List of photo GUIDs that were deleted

    Returns:
        List of face point IDs to delete
    """
    if not photo_guids:
        return []

    print(f"\nScanning 'photo_faces' collection for associated face entries...")

    faces_collection = 'photo_faces'
    orphaned_faces = []

    # Check if faces collection exists
    try:
        client.get_collection(faces_collection)
    except Exception:
        print(f"  Collection '{faces_collection}' does not exist, skipping face cleanup")
        return []

    # Scroll through all face points
    offset = None
    batch_size = 100
    total_scanned = 0

    while True:
        points, next_offset = client.scroll(
            collection_name=faces_collection,
            offset=offset,
            limit=batch_size,
            with_payload=True,
            with_vectors=False
        )

        if not points:
            break

        for point in points:
            total_scanned += 1
            photo_guid = point.payload.get('photo_guid')

            if photo_guid in photo_guids:
                orphaned_faces.append(point.id)

        offset = next_offset
        if offset is None:
            break

        if total_scanned % 1000 == 0:
            print(f"  Scanned {total_scanned} face entries...")

    print(f"✓ Scanned {total_scanned} face entries")
    print(f"✓ Found {len(orphaned_faces)} orphaned face entries")

    return orphaned_faces


def delete_orphaned_entries(
    client: QdrantClient,
    point_ids: List[int],
    collection_name: str,
    dry_run: bool = False
) -> int:
    """Delete orphaned entries from the collection.

    Args:
        client: Qdrant client
        point_ids: List of point IDs to delete
        collection_name: Name of the collection
        dry_run: If True, don't actually delete

    Returns:
        Number of entries deleted
    """
    if not point_ids:
        return 0

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(point_ids)} entries from '{collection_name}'")
        return 0

    print(f"\nDeleting {len(point_ids)} orphaned entries from '{collection_name}'...")

    # Delete in batches to avoid overwhelming Qdrant
    batch_size = 100
    deleted = 0

    for i in range(0, len(point_ids), batch_size):
        batch = point_ids[i:i + batch_size]

        try:
            client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=batch)
            )
            deleted += len(batch)

            if deleted % 500 == 0:
                print(f"  Deleted {deleted}/{len(point_ids)} entries...")

        except Exception as e:
            print(f"Error deleting batch: {e}")
            continue

    print(f"✓ Deleted {deleted} entries")
    return deleted


def main():
    parser = argparse.ArgumentParser(
        description='Remove orphaned entries from the photo index'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--skip-faces',
        action='store_true',
        help='Skip removal of associated face entries (by default, orphaned faces are also removed)'
    )
    parser.add_argument(
        '--collection',
        default=COLLECTION_NAME,
        help=f'Collection name to clean up (default: {COLLECTION_NAME})'
    )

    args = parser.parse_args()

    # Connect to Qdrant
    try:
        client = connect_to_qdrant()
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}", file=sys.stderr)
        sys.exit(1)

    # Find orphaned entries
    orphaned = find_orphaned_entries(client, args.collection)

    if not orphaned:
        print("\n✓ No orphaned entries found. Index is clean!")
        return

    # Display orphaned entries
    print(f"\nOrphaned entries (photos no longer on disk):")
    for i, (point_id, file_path, file_name) in enumerate(orphaned[:20], 1):
        print(f"  {i}. {file_name}")
        print(f"     Path: {file_path}")

    if len(orphaned) > 20:
        print(f"  ... and {len(orphaned) - 20} more")

    # Extract point IDs and GUIDs for deletion
    point_ids = [entry[0] for entry in orphaned]

    # Handle face entries (by default, unless --skip-faces is specified)
    if not args.skip_faces:
        # We need to get the GUIDs from the orphaned entries
        # Scroll again to get the full payloads
        photo_guids = []
        offset = None

        print("\nRetrieving GUIDs of orphaned photos...")
        while True:
            points, next_offset = client.scroll(
                collection_name=args.collection,
                offset=offset,
                limit=100,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            for point in points:
                if point.id in point_ids:
                    guid = point.payload.get('guid')
                    if guid:
                        photo_guids.append(guid)

            offset = next_offset
            if offset is None:
                break

        print(f"✓ Retrieved {len(photo_guids)} GUIDs")

        # Find associated face entries
        orphaned_faces = find_orphaned_faces(client, photo_guids)
    else:
        orphaned_faces = []

    # Delete orphaned entries
    if args.dry_run:
        print(f"\n[DRY RUN] Would delete {len(point_ids)} photo entries")
        if orphaned_faces:
            print(f"[DRY RUN] Would delete {len(orphaned_faces)} associated face entries")
        print("\nRun without --dry-run to actually perform the cleanup.")
    else:
        # Confirm deletion
        if len(point_ids) > 0:
            response = input(f"\nDelete {len(point_ids)} orphaned entries? [y/N]: ")
            if response.lower() != 'y':
                print("Cancelled.")
                return

        # Delete photos
        deleted_photos = delete_orphaned_entries(
            client,
            point_ids,
            args.collection,
            dry_run=False
        )

        # Delete faces
        deleted_faces = 0
        if orphaned_faces:
            deleted_faces = delete_orphaned_entries(
                client,
                orphaned_faces,
                'photo_faces',
                dry_run=False
            )

        print(f"\n✓ Cleanup complete!")
        print(f"  Deleted {deleted_photos} photo entries")
        if deleted_faces:
            print(f"  Deleted {deleted_faces} face entries")


if __name__ == "__main__":
    main()

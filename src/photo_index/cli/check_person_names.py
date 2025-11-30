# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 09:16:08
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-30 09:16:24
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnostic script to check if person_names are being stored in photo payloads."""

import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qdrant_client import QdrantClient
from common.utils import Utils
from logging_service import LoggingService

def main():
    """Check the person_names field for a specific photo."""

    log = LoggingService()

    # Get photo GUID from command line or use a default
    if len(sys.argv) > 1:
        photo_guid = sys.argv[1]
    else:
        print("Usage: python check_person_names.py <photo_guid>")
        print("\nOr run without args to see all photos with person_names:")
        photo_guid = None

    # Connect to Qdrant
    client = QdrantClient(host="localhost", port=6333)

    if photo_guid:
        # Check specific photo
        try:
            point_id = Utils.guid_to_point_id(photo_guid)

            # Retrieve the photo point
            result = client.retrieve(
                collection_name='photo_embeddings',
                ids=[point_id],
                with_payload=True,
                with_vectors=False
            )

            if result:
                payload = result[0].payload
                print(f"\n=== Photo GUID: {photo_guid} ===")
                print(f"Point ID: {point_id}")
                print(f"\nFull payload keys: {list(payload.keys())}")

                # Check for person_names field
                if 'person_names' in payload:
                    print(f"\n✓ person_names field EXISTS")
                    print(f"  Type: {type(payload['person_names'])}")
                    print(f"  Value: {payload['person_names']}")
                else:
                    print(f"\n✗ person_names field DOES NOT EXIST")

                # Also show other relevant fields
                if 'file_name' in payload:
                    print(f"\nFile name: {payload['file_name']}")
                if 'description_parsed' in payload:
                    print(f"\nDescription parsed keys: {list(payload.get('description_parsed', {}).keys())}")

            else:
                print(f"Photo with GUID {photo_guid} not found in photo_embeddings collection")

        except Exception as e:
            log.err(f"Error retrieving photo: {e}")
            import traceback
            traceback.print_exc()
    else:
        # Scroll through all photos and show ones with person_names
        print("\n=== Scanning all photos for person_names field ===\n")

        offset = None
        photos_with_names = []
        total_photos = 0

        while True:
            result = client.scroll(
                collection_name='photo_embeddings',
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = result

            if not points:
                break

            for point in points:
                total_photos += 1
                if 'person_names' in point.payload and point.payload['person_names']:
                    photos_with_names.append({
                        'guid': point.payload.get('guid', 'unknown'),
                        'file_name': point.payload.get('file_name', 'unknown'),
                        'person_names': point.payload['person_names']
                    })

            if next_offset is None:
                break

            offset = next_offset

        print(f"Total photos scanned: {total_photos}")
        print(f"Photos with person_names: {len(photos_with_names)}\n")

        if photos_with_names:
            for photo in photos_with_names:
                print(f"GUID: {photo['guid']}")
                print(f"  File: {photo['file_name']}")
                print(f"  Names: {photo['person_names']}")
                print()
        else:
            print("No photos found with person_names field populated")
            print("\nThis explains why search isn't working - the field is not being set!")

if __name__ == '__main__':
    main()

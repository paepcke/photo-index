#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Show the indexed payload for a photo from Qdrant.

Usage:
    show_index.py /path/to/photo.jpg
    show_index.py --json /path/to/photo.jpg
"""

import argparse
import sys
from pathlib import Path
import json
from qdrant_client import QdrantClient

from photo_index.utils import Utils
from photo_index.config import QDRANT_PATH, COLLECTION_NAME


def format_payload(payload, indent=0):
    """Format payload for readable display."""
    output = []
    indent_str = "  " * indent
    
    for key, value in payload.items():
        if isinstance(value, dict):
            output.append(f"{indent_str}{key}:")
            output.append(format_payload(value, indent + 1))
        elif isinstance(value, list):
            output.append(f"{indent_str}{key}: {value}")
        elif value is None:
            output.append(f"{indent_str}{key}: (none)")
        else:
            # Truncate long strings
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            output.append(f"{indent_str}{key}: {value}")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description='Show indexed payload for a photo'
    )
    parser.add_argument(
        'photo_path',
        type=str,
        help='Path to the photo file'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--qdrant-path',
        type=str,
        default=QDRANT_PATH,
        help=f'Qdrant storage path (default: {QDRANT_PATH})'
    )
    
    args = parser.parse_args()
    
    # Validate photo path
    photo_path = Path(args.photo_path)
    if not photo_path.exists():
        print(f"Error: Photo not found: {photo_path}", file=sys.stderr)
        sys.exit(1)
    
    # Generate GUID for the photo
    photo_guid = Utils.get_photo_guid(photo_path)
    point_id = Utils.guid_to_point_id(photo_guid)
    
    # Connect to Qdrant
    client = QdrantClient(path=args.qdrant_path)
    
    # Retrieve the point
    try:
        points = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            print(f"Error: Photo not found in index: {photo_path}", file=sys.stderr)
            print(f"  GUID: {photo_guid}", file=sys.stderr)
            print(f"  Point ID: {point_id}", file=sys.stderr)
            sys.exit(1)
        
        payload = points[0].payload
        
        if args.json:
            # Output as JSON
            print(json.dumps(payload, indent=2))
        else:
            # Format for reading
            print(f"\nIndexed data for: {photo_path.name}")
            print("=" * 70)
            print(f"GUID: {photo_guid}")
            print(f"Point ID: {point_id}")
            print("-" * 70)
            print(format_payload(payload))
            print("=" * 70)
            
    except Exception as e:
        print(f"Error retrieving from Qdrant: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

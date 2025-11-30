#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate and print description for a photo using Llama Vision model.

Usage:
    get_description.py /path/to/photo.jpg
    get_description.py --prompt "Describe the mood" /path/to/photo.jpg
"""

import argparse
import sys
from pathlib import Path
import json

from photo_index.embedding_generator import EmbeddingGenerator
from common.config import MODEL_PATH, DEVICE, IMG_DESC_PROMPT


def main():
    parser = argparse.ArgumentParser(
        description='Generate description for a photo'
    )
    parser.add_argument(
        'photo_path',
        type=str,
        help='Path to the photo file'
    )
    parser.add_argument(
        '-p', '--prompt',
        type=str,
        default=None,
        help='Custom prompt (default: use config prompt)'
    )
    parser.add_argument(
        '--raw',
        action='store_true',
        help='Print raw output without formatting'
    )
    
    args = parser.parse_args()
    
    # Validate photo path
    photo_path = Path(args.photo_path)
    if not photo_path.exists():
        print(f"Error: Photo not found: {photo_path}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize generator
    print(f"Loading model...", file=sys.stderr)
    generator = EmbeddingGenerator(MODEL_PATH, DEVICE)
    
    # Generate description
    print(f"Generating description for {photo_path.name}...", file=sys.stderr)
    description = generator.generate_description(
        photo_path, 
        prompt=args.prompt
    )
    
    if args.raw:
        # Just print the raw output
        print(description)
    else:
        # Try to parse and pretty-print JSON
        try:
            desc_dict = json.loads(description)
            print(f"\nDescription for: {photo_path.name}")
            print("=" * 60)
            print(json.dumps(desc_dict, indent=2))
        except json.JSONDecodeError:
            # Not JSON, just print as text
            print(f"\nDescription for: {photo_path.name}")
            print("=" * 60)
            print(description)


if __name__ == "__main__":
    main()

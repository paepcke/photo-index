#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLI tool for searching indexed photos.

Usage:
    search_cli.py --image query.jpg --limit 10
    search_cli.py --text "dog" --location-city "San Francisco"
    search_cli.py --hybrid --image query.jpg --text "sunset"
    search_cli.py --facets location.city
"""

import argparse
import sys
from pathlib import Path
import json
from datetime import datetime

from photo_search import PhotoSearch, FilterBuilder


def format_result(result: dict, index: int, verbose: bool = False):
    """Format a search result for display."""
    lines = []
    lines.append(f"\n[{index}] {result['file_name']}")
    lines.append(f"    Path: {result['file_path']}")
    
    if 'score' in result:
        lines.append(f"    Similarity: {result['score']:.3f}")
    
    if result.get('date_taken'):
        lines.append(f"    Date: {result['date_taken']}")
    
    if result.get('location'):
        loc = result['location']
        location_str = loc.get('formatted_address', '')
        if not location_str and loc.get('city'):
            parts = [loc.get('city'), loc.get('state'), loc.get('country')]
            location_str = ', '.join(filter(None, parts))
        if location_str:
            lines.append(f"    Location: {location_str}")
    
    if result.get('description') and verbose:
        desc = result['description']
        if isinstance(desc, dict):
            lines.append(f"    Objects: {', '.join(desc.get('objects', []))}")
            lines.append(f"    Setting: {', '.join(desc.get('setting', []))}")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Search indexed photos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find similar images
  %(prog)s --image /path/to/query.jpg --limit 20
  
  # Search by text
  %(prog)s --text "dog beach sunset" --limit 10
  
  # Filter by location
  %(prog)s --location-city "San Francisco" --location-state "California"
  
  # Filter by date range
  %(prog)s --date-from 2024-01-01 --date-to 2024-12-31
  
  # Hybrid search
  %(prog)s --hybrid --image query.jpg --text "outdoor" --date-from 2024-01-01
  
  # Get facets
  %(prog)s --facets location.city
  %(prog)s --facets exif.camera_make
  
  # Show stats
  %(prog)s --stats
        """
    )
    
    # Search type
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument(
        '--image', '-i',
        type=str,
        help='Path to query image (visual similarity search)'
    )
    search_group.add_argument(
        '--text', '-t',
        type=str,
        help='Text query (search in descriptions)'
    )
    search_group.add_argument(
        '--hybrid',
        action='store_true',
        help='Hybrid search (combine --image and/or --text with filters)'
    )
    search_group.add_argument(
        '--facets',
        type=str,
        help='Get unique values for a field (e.g., location.city, exif.camera_make)'
    )
    search_group.add_argument(
        '--stats',
        action='store_true',
        help='Show collection statistics'
    )
    
    # Filters
    filter_group = parser.add_argument_group('filters')
    filter_group.add_argument(
        '--location-city',
        type=str,
        help='Filter by city'
    )
    filter_group.add_argument(
        '--location-state',
        type=str,
        help='Filter by state'
    )
    filter_group.add_argument(
        '--location-country',
        type=str,
        help='Filter by country'
    )
    filter_group.add_argument(
        '--date-from',
        type=str,
        help='Filter by date from (ISO format: YYYY-MM-DD)'
    )
    filter_group.add_argument(
        '--date-to',
        type=str,
        help='Filter by date to (ISO format: YYYY-MM-DD)'
    )
    filter_group.add_argument(
        '--camera-make',
        type=str,
        help='Filter by camera make'
    )
    filter_group.add_argument(
        '--camera-model',
        type=str,
        help='Filter by camera model'
    )
    
    # Output options
    output_group = parser.add_argument_group('output')
    output_group.add_argument(
        '--limit', '-l',
        type=int,
        default=10,
        help='Number of results (default: 10)'
    )
    output_group.add_argument(
        '--score-threshold',
        type=float,
        help='Minimum similarity score (0-1)'
    )
    output_group.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )
    output_group.add_argument(
        '--paths-only',
        action='store_true',
        help='Output only file paths (one per line)'
    )
    
    args = parser.parse_args()
    
    # Initialize searcher
    searcher = PhotoSearch()
    
    # Show stats
    if args.stats:
        stats = searcher.get_stats()
        print("\nCollection Statistics:")
        print(f"  Total photos: {stats['total_photos']}")
        print(f"  Vector dimension: {stats['vector_dimension']}")
        return
    
    # Build filters
    filters = []
    
    if args.location_city or args.location_state or args.location_country:
        location_filter = FilterBuilder.by_location(
            city=args.location_city,
            state=args.location_state,
            country=args.location_country
        )
        if location_filter:
            filters.append(location_filter)
    
    if args.date_from or args.date_to:
        date_from = args.date_from if args.date_from else '1900-01-01'
        date_to = args.date_to if args.date_to else '2100-12-31'
        filters.append(FilterBuilder.by_date_range(date_from, date_to))
    
    if args.camera_make or args.camera_model:
        camera_filter = FilterBuilder.by_camera(
            make=args.camera_make,
            model=args.camera_model
        )
        if camera_filter:
            filters.append(camera_filter)
    
    combined_filter = FilterBuilder.combine_filters(*filters) if filters else None
    
    # Execute search
    try:
        # Facet query
        if args.facets:
            print(f"\nGetting facets for: {args.facets}")
            facets = searcher.get_facets(args.facets, filters=combined_filter, limit=1000)
            
            if args.json:
                print(json.dumps(facets, indent=2))
            else:
                print(f"\nFound {len(facets)} unique values:")
                for value, count in list(facets.items())[:args.limit]:
                    print(f"  {value}: {count}")
            return
        
        # Image similarity search
        if args.image:
            image_path = Path(args.image)
            if not image_path.exists():
                print(f"Error: Image not found: {image_path}", file=sys.stderr)
                sys.exit(1)
            
            print(f"\nSearching for images similar to: {image_path.name}")
            results = searcher.search_by_image(
                image_path,
                limit=args.limit,
                filters=combined_filter,
                score_threshold=args.score_threshold
            )
        
        # Text search
        elif args.text:
            print(f"\nSearching for: '{args.text}'")
            results = searcher.search_by_text(
                args.text,
                limit=args.limit,
                filters=combined_filter
            )
        
        # Hybrid search
        elif args.hybrid:
            image_path = Path(args.image) if args.image else None
            if image_path and not image_path.exists():
                print(f"Error: Image not found: {image_path}", file=sys.stderr)
                sys.exit(1)
            
            print(f"\nHybrid search:")
            if image_path:
                print(f"  Image: {image_path.name}")
            if args.text:
                print(f"  Text: '{args.text}'")
            
            results = searcher.search_hybrid(
                image_path=image_path,
                text_query=args.text,
                filters=combined_filter,
                limit=args.limit,
                score_threshold=args.score_threshold
            )
        
        else:
            print("Error: Must specify --image, --text, --hybrid, --facets, or --stats", file=sys.stderr)
            parser.print_help()
            sys.exit(1)
        
        # Output results
        if not results:
            print("\nNo results found.")
            return
        
        print(f"\nFound {len(results)} results:")
        print("=" * 70)
        
        if args.json:
            # JSON output
            print(json.dumps(results, indent=2))
        elif args.paths_only:
            # Just file paths
            for result in results:
                print(result['file_path'])
        else:
            # Formatted output
            for i, result in enumerate(results, 1):
                print(format_result(result, i, verbose=args.verbose))
        
        print("=" * 70)
        
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

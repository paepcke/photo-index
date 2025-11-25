#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
List unique values in your photo collection.

Usage:
    list_values.py --field location.city
    list_values.py --field description_parsed.objects
    list_values.py --all-fields
"""

import argparse
import sys
from photo_search import PhotoSearch


# Common fields that users might want to explore
COMMON_FIELDS = {
    'location': [
        'location.city',
        'location.state',
        'location.country',
    ],
    'description': [
        'description_parsed.objects',
        'description_parsed.materials',
        'description_parsed.setting',
        'description_parsed.visual_attributes',
    ],
    'camera': [
        'exif.camera_make',
        'exif.camera_model',
    ],
    'dates': [
        'exif.date_taken',
    ]
}


def list_all_common_fields(searcher, limit=100):
    """List values for all common fields."""
    for category, fields in COMMON_FIELDS.items():
        print(f"\n{'=' * 70}")
        print(f"{category.upper()}")
        print(f"{'=' * 70}")
        
        for field in fields:
            print(f"\n{field}:")
            print("-" * 70)
            
            try:
                facets = searcher.get_facets(field, limit=limit)
                
                if not facets:
                    print("  (no values)")
                    continue
                
                # Show top values
                for value, count in list(facets.items())[:20]:
                    print(f"  {value}: {count}")
                
                if len(facets) > 20:
                    print(f"  ... and {len(facets) - 20} more")
                
                print(f"\nTotal unique values: {len(facets)}")
                
            except Exception as e:
                print(f"  Error: {e}")


def list_field(searcher, field, limit=100, show_all=False):
    """List values for a specific field."""
    print(f"\n{field}")
    print("=" * 70)
    
    try:
        facets = searcher.get_facets(field, limit=limit)
        
        if not facets:
            print("No values found")
            return
        
        # Determine how many to show
        display_count = len(facets) if show_all else min(100, len(facets))
        
        for value, count in list(facets.items())[:display_count]:
            print(f"{value}: {count}")
        
        if len(facets) > display_count:
            remaining = len(facets) - display_count
            print(f"\n... and {remaining} more (use --show-all to see everything)")
        
        print(f"\nTotal unique values: {len(facets)}")
        print(f"Total photos with this field: {sum(facets.values())}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def show_available_fields():
    """Show all available common fields."""
    print("\nCommonly used fields:")
    print("=" * 70)
    
    for category, fields in COMMON_FIELDS.items():
        print(f"\n{category.upper()}:")
        for field in fields:
            print(f"  {field}")
    
    print("\n" + "=" * 70)
    print("\nYou can use any field from the indexed data.")
    print("Examples:")
    print("  list_values.py --field location.city")
    print("  list_values.py --field description_parsed.objects")
    print("  list_values.py --field exif.camera_make")
    print("\nTo see all common fields with their values:")
    print("  list_values.py --all-fields")


def main():
    parser = argparse.ArgumentParser(
        description='List unique values in photo collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all cities
  %(prog)s --field location.city
  
  # List all objects found in photos
  %(prog)s --field description_parsed.objects
  
  # List all camera makes
  %(prog)s --field exif.camera_make
  
  # Show all values (not just top 100)
  %(prog)s --field location.city --show-all
  
  # List all common fields
  %(prog)s --all-fields
  
  # Show what fields are available
  %(prog)s --show-fields
        """
    )
    
    parser.add_argument(
        '--field', '-f',
        type=str,
        help='Field to list values for (e.g., location.city, description_parsed.objects)'
    )
    parser.add_argument(
        '--all-fields',
        action='store_true',
        help='List values for all common fields'
    )
    parser.add_argument(
        '--show-fields',
        action='store_true',
        help='Show available fields'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all values (not just top 100)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help='Maximum number of photos to scan (default: 1000)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    
    args = parser.parse_args()
    
    # Show available fields
    if args.show_fields:
        show_available_fields()
        return
    
    # Initialize searcher
    print("Loading collection...", file=sys.stderr)
    searcher = PhotoSearch()
    
    # List all common fields
    if args.all_fields:
        list_all_common_fields(searcher, limit=args.limit)
        return
    
    # List specific field
    if args.field:
        if args.json:
            import json
            facets = searcher.get_facets(args.field, limit=args.limit)
            print(json.dumps(facets, indent=2))
        else:
            list_field(searcher, args.field, limit=args.limit, show_all=args.show_all)
        return
    
    # No arguments - show help
    parser.print_help()
    print("\n")
    show_available_fields()


if __name__ == "__main__":
    main()

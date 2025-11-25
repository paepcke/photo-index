#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extract and display EXIF data from a photo.

Usage:
    get_exif.py /path/to/photo.jpg
    get_exif.py --json /path/to/photo.jpg
    get_exif.py --gps /path/to/photo.jpg
"""

import argparse
import sys
from pathlib import Path
import json

from photo_index.exif_utils import ExifExtractor
from photo_index.geocoding import Geocoder


def format_exif(exif_data, include_raw=False):
    """Format EXIF data for readable display."""
    output = []
    
    # Camera info
    if exif_data['camera_make'] or exif_data['camera_model']:
        output.append("Camera:")
        if exif_data['camera_make']:
            output.append(f"  Make: {exif_data['camera_make']}")
        if exif_data['camera_model']:
            output.append(f"  Model: {exif_data['camera_model']}")
        output.append("")
    
    # Date
    if exif_data['date_taken']:
        output.append(f"Date Taken: {exif_data['date_taken']}")
        output.append("")
    
    # Image dimensions
    if exif_data['width'] and exif_data['height']:
        output.append("Image Size:")
        output.append(f"  Width: {exif_data['width']}px")
        output.append(f"  Height: {exif_data['height']}px")
        output.append(f"  Orientation: {exif_data['orientation']}")
        output.append("")
    
    # Exposure settings
    if any([exif_data['iso'], exif_data['focal_length'], 
            exif_data['aperture'], exif_data['exposure_time']]):
        output.append("Exposure Settings:")
        if exif_data['iso']:
            output.append(f"  ISO: {exif_data['iso']}")
        if exif_data['focal_length']:
            output.append(f"  Focal Length: {exif_data['focal_length']}mm")
        if exif_data['aperture']:
            output.append(f"  Aperture: f/{exif_data['aperture']}")
        if exif_data['exposure_time']:
            output.append(f"  Exposure Time: {exif_data['exposure_time']}s")
        output.append("")
    
    # GPS
    if exif_data['gps']:
        gps = exif_data['gps']
        output.append("GPS:")
        if 'latitude' in gps and 'longitude' in gps:
            output.append(f"  Latitude: {gps['latitude']:.6f}")
            output.append(f"  Longitude: {gps['longitude']:.6f}")
            if gps.get('altitude'):
                output.append(f"  Altitude: {gps['altitude']}m")
        output.append("")
    
    # Raw EXIF (if requested)
    if include_raw and exif_data['raw_exif']:
        output.append("Raw EXIF Tags:")
        for key, value in sorted(exif_data['raw_exif'].items()):
            # Truncate long values
            if isinstance(value, str) and len(value) > 60:
                value = value[:60] + "..."
            output.append(f"  {key}: {value}")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description='Extract EXIF data from a photo'
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
        '--raw',
        action='store_true',
        help='Include all raw EXIF tags'
    )
    parser.add_argument(
        '--gps',
        action='store_true',
        help='Include geocoded location (requires API key)'
    )
    
    args = parser.parse_args()
    
    # Validate photo path
    photo_path = Path(args.photo_path)
    if not photo_path.exists():
        print(f"Error: Photo not found: {photo_path}", file=sys.stderr)
        sys.exit(1)
    
    # Extract EXIF
    extractor = ExifExtractor()
    exif_data = extractor.extract_exif(photo_path)
    
    # Geocode if requested
    location = None
    if args.gps and exif_data['gps']:
        gps = exif_data['gps']
        if 'latitude' in gps and 'longitude' in gps:
            try:
                geocoder = Geocoder()
                location = geocoder.get_location(
                    gps['latitude'],
                    gps['longitude']
                )
            except Exception as e:
                print(f"Warning: Geocoding failed: {e}", file=sys.stderr)
    
    if args.json:
        # Output as JSON
        output = {
            'exif': exif_data,
            'location': location
        }
        print(json.dumps(output, indent=2))
    else:
        # Format for reading
        print(f"\nEXIF data for: {photo_path.name}")
        print("=" * 70)
        print(format_exif(exif_data, include_raw=args.raw))
        
        if location:
            print("Location (Geocoded):")
            print(f"  {location.get('formatted_address', 'Unknown')}")
            if location.get('city'):
                print(f"  City: {location['city']}")
            if location.get('state'):
                print(f"  State: {location['state']}")
            if location.get('country'):
                print(f"  Country: {location['country']}")
            print("")
        
        print("=" * 70)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-19 10:08:26
"""EXIF data extraction and GPS utilities."""

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import pillow_heif

# Register HEIF opener
pillow_heif.register_heif_opener()

class ExifExtractor:
    """Extract and process EXIF data from images."""
    
    def __init__(self, geocoding_user_agent: str = "photo_indexer"):
        pass
    
    def extract_exif(self, image_path: Path) -> Dict:
        """Extract EXIF data from an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing EXIF data and parsed GPS coordinates
        """
        try:
            with Image.open(image_path) as img:
                exif_data = img._getexif()
                
                if not exif_data:
                    return self._empty_exif()
                
                # Parse EXIF tags
                parsed_exif = {}
                gps_info = {}
                
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    
                    if tag_name == "GPSInfo":
                        gps_info = self._parse_gps_info(value)
                    else:
                        # Convert to serializable format
                        parsed_exif[tag_name] = self._serialize_value(value)
                
                # Extract key metadata
                result = {
                    'camera_make': parsed_exif.get('Make'),
                    'camera_model': parsed_exif.get('Model'),
                    'date_taken': self._parse_datetime(parsed_exif.get('DateTimeOriginal') or parsed_exif.get('DateTime')),
                    'width': parsed_exif.get('ExifImageWidth') or img.width,
                    'height': parsed_exif.get('ExifImageHeight') or img.height,
                    'orientation': parsed_exif.get('Orientation'),
                    'iso': parsed_exif.get('ISOSpeedRatings'),
                    'focal_length': parsed_exif.get('FocalLength'),
                    'aperture': parsed_exif.get('FNumber'),
                    'exposure_time': parsed_exif.get('ExposureTime'),
                    'gps': gps_info,
                    'raw_exif': parsed_exif
                }
                
                return result
                
        except Exception as e:
            print(f"Error extracting EXIF from {image_path}: {e}")
            return self._empty_exif()
    
    def _empty_exif(self) -> Dict:
        """Return empty EXIF structure."""
        return {
            'camera_make': None,
            'camera_model': None,
            'date_taken': None,
            'width': None,
            'height': None,
            'orientation': None,
            'iso': None,
            'focal_length': None,
            'aperture': None,
            'exposure_time': None,
            'gps': {},
            'raw_exif': {}
        }
    
    def _parse_gps_info(self, gps_data: Dict) -> Dict:
        """Parse GPS information from EXIF.
        
        Args:
            gps_data: Raw GPS data from EXIF
            
        Returns:
            Dictionary with parsed GPS coordinates
        """
        gps_parsed = {}
        
        for tag_id, value in gps_data.items():
            tag_name = GPSTAGS.get(tag_id, tag_id)
            gps_parsed[tag_name] = value
        
        # Convert to decimal degrees
        lat, lon = self._get_decimal_coordinates(gps_parsed)
        
        if lat is not None and lon is not None:
            return {
                'latitude': lat,
                'longitude': lon,
                'altitude': gps_parsed.get('GPSAltitude'),
                'raw': gps_parsed
            }
        
        return {}
    
    def _get_decimal_coordinates(self, gps_info: Dict) -> Tuple[Optional[float], Optional[float]]:
        """Convert GPS coordinates to decimal degrees.
        
        Args:
            gps_info: Parsed GPS information
            
        Returns:
            Tuple of (latitude, longitude) in decimal degrees
        """
        try:
            lat_dms = gps_info.get('GPSLatitude')
            lat_ref = gps_info.get('GPSLatitudeRef')
            lon_dms = gps_info.get('GPSLongitude')
            lon_ref = gps_info.get('GPSLongitudeRef')
            
            if not all([lat_dms, lat_ref, lon_dms, lon_ref]):
                return None, None
            
            lat = self._dms_to_decimal(lat_dms, lat_ref)
            lon = self._dms_to_decimal(lon_dms, lon_ref)
            
            return lat, lon
            
        except Exception:
            return None, None
    
    def _dms_to_decimal(self, dms: Tuple, ref: str) -> float:
        """Convert degrees, minutes, seconds to decimal degrees.
        
        Args:
            dms: Tuple of (degrees, minutes, seconds)
            ref: Reference (N/S for latitude, E/W for longitude)
            
        Returns:
            Decimal degree value
        """
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        if ref in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[str]:
        """Parse EXIF datetime string to ISO format.
        
        Args:
            datetime_str: EXIF datetime string (e.g., "2024:11:01 14:30:00")
            
        Returns:
            ISO format datetime string or None
        """
        if not datetime_str:
            return None
        
        try:
            # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
            dt = datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
            return dt.isoformat()
        except Exception:
            return datetime_str  # Return as-is if parsing fails
    
    def _serialize_value(self, value):
        """Convert EXIF values to JSON-serializable format."""
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                return str(value)
        elif isinstance(value, (tuple, list)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
            return value

# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-19 10:04:41
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-19 10:06:05

"""Geocoding using Google Maps API to convert GPS coordinates to location names."""

import requests
from pathlib import Path
from typing import Dict, Optional
import time
import json

class Geocoder:
    """Reverse geocoding using Google Maps Geocoding API."""
    
    GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    
    def __init__(self, api_key_path: str = None):
        """Initialize the geocoder.
        
        Args:
            api_key_path: Path to file containing Google Maps API key.
                         Defaults to $HOME/.ssh/googleMapsGeoCodingAPIKey.txt
        """
        if api_key_path is None:
            api_key_path = Path.home() / ".ssh" / "googleMapsGeoCodingAPIKey.txt"
        else:
            api_key_path = Path(api_key_path)
        
        # Read API key
        try:
            self.api_key = api_key_path.read_text().strip()
            print(f"Loaded Google Maps API key from {api_key_path}")
        except Exception as e:
            raise ValueError(f"Failed to read API key from {api_key_path}: {e}")
        
        # Cache for geocoding results
        self._cache = {}
        self._cache_hits = 0
        self._api_calls = 0
    
    def get_location(self, latitude: float, longitude: float) -> Optional[Dict]:
        """Convert GPS coordinates to location information.
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            
        Returns:
            Dictionary with location information or None on failure
        """
        # Check cache (round to 4 decimal places ~11m precision)
        cache_key = f"{latitude:.4f},{longitude:.4f}"
        
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        # Make API request
        try:
            params = {
                'latlng': f"{latitude},{longitude}",
                'key': self.api_key
            }
            
            response = requests.get(self.GOOGLE_GEOCODE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            self._api_calls += 1
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = self._parse_result(data['results'][0])
                
                # Cache the result
                self._cache[cache_key] = result
                
                return result
            
            elif data['status'] == 'ZERO_RESULTS':
                # Valid response but no results
                return None
            
            else:
                print(f"Geocoding API error: {data['status']}")
                if 'error_message' in data:
                    print(f"  Message: {data['error_message']}")
                return None
        
        except requests.exceptions.RequestException as e:
            print(f"Geocoding request failed for {latitude}, {longitude}: {e}")
            return None
        
        except Exception as e:
            print(f"Geocoding error for {latitude}, {longitude}: {e}")
            return None
    
    def _parse_result(self, result: Dict) -> Dict:
        """Parse Google Maps geocoding result.
        
        Args:
            result: First result from Google Maps API response
            
        Returns:
            Parsed location information
        """
        # Extract address components
        components = {}
        for component in result.get('address_components', []):
            types = component.get('types', [])
            name = component.get('long_name')
            
            if 'locality' in types:
                components['city'] = name
            elif 'administrative_area_level_1' in types:
                components['state'] = name
            elif 'administrative_area_level_2' in types:
                components['county'] = name
            elif 'country' in types:
                components['country'] = name
                components['country_code'] = component.get('short_name')
            elif 'postal_code' in types:
                components['postal_code'] = name
        
        # Get formatted address
        formatted_address = result.get('formatted_address')
        
        # Get place_id for reference
        place_id = result.get('place_id')
        
        return {
            'formatted_address': formatted_address,
            'city': components.get('city'),
            'county': components.get('county'),
            'state': components.get('state'),
            'country': components.get('country'),
            'country_code': components.get('country_code'),
            'postal_code': components.get('postal_code'),
            'place_id': place_id,
            'raw_components': components
        }
    
    def batch_geocode(self, coordinates: list) -> list:
        """Geocode multiple coordinates.
        
        Note: This makes individual API calls since Google Maps doesn't have
        a batch geocoding endpoint. Results are cached.
        
        Args:
            coordinates: List of (latitude, longitude) tuples
            
        Returns:
            List of location dictionaries (same order as input)
        """
        results = []
        
        for lat, lon in coordinates:
            result = self.get_location(lat, lon)
            results.append(result)
            
            # Small delay to be respectful of API limits
            # Google Maps allows ~50 req/sec, but we'll be conservative
            time.sleep(0.05)
        
        return results
    
    def get_stats(self) -> Dict:
        """Get geocoding statistics.
        
        Returns:
            Dictionary with cache and API call statistics
        """
        return {
            'cache_size': len(self._cache),
            'cache_hits': self._cache_hits,
            'api_calls': self._api_calls,
            'total_requests': self._cache_hits + self._api_calls
        }
    
    def save_cache(self, cache_path: str):
        """Save geocoding cache to disk.
        
        Args:
            cache_path: Path to save cache file
        """
        try:
            with open(cache_path, 'w') as f:
                json.dump(self._cache, f, indent=2)
            print(f"Saved geocoding cache to {cache_path} ({len(self._cache)} entries)")
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def load_cache(self, cache_path: str):
        """Load geocoding cache from disk.
        
        Args:
            cache_path: Path to cache file
        """
        try:
            with open(cache_path, 'r') as f:
                self._cache = json.load(f)
            print(f"Loaded geocoding cache from {cache_path} ({len(self._cache)} entries)")
        except FileNotFoundError:
            print(f"Cache file not found: {cache_path}")
        except Exception as e:
            print(f"Error loading cache: {e}")

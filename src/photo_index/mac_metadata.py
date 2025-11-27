# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 11:03:10
"""Extract metadata from Mac AppleDouble (._) files."""

import struct
from pathlib import Path
from typing import Dict, Optional
import xattr


class MacMetadataExtractor:
    """Extract metadata from Mac AppleDouble format files."""
    
    # AppleDouble magic numbers
    APPLEDOUBLE_MAGIC = 0x00051607
    APPLESINGLE_MAGIC = 0x00051600
    
    # Entry IDs
    ENTRY_DATA_FORK = 1
    ENTRY_RESOURCE_FORK = 2
    ENTRY_REAL_NAME = 3
    ENTRY_COMMENT = 4
    ENTRY_FINDER_INFO = 9
    
    def __init__(self):
        """Initialize the Mac metadata extractor."""
        pass
    
    def extract_metadata(self, file_path: Path) -> Dict:
        """Extract all available metadata from a file.
        
        This attempts to extract:
        1. Extended attributes (xattr)
        2. AppleDouble metadata from ._file if it exists
        
        Args:
            file_path: Path to the actual file (not the ._file)
            
        Returns:
            Dictionary containing all extracted metadata
        """
        metadata = {
            'xattr': self._extract_xattr(file_path),
            'appledouble': {}
        }
        
        # Check for corresponding AppleDouble file
        appledouble_path = file_path.parent / f"._{file_path.name}"
        if appledouble_path.exists():
            metadata['appledouble'] = self._parse_appledouble(appledouble_path)
        
        return metadata
    
    def _extract_xattr(self, file_path: Path) -> Dict:
        """Extract extended attributes from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary of extended attributes
        """
        try:
            attrs = {}
            for attr_name in xattr.listxattr(str(file_path)):
                try:
                    attr_value = xattr.getxattr(str(file_path), attr_name)
                    # Try to decode as UTF-8, otherwise store as hex
                    try:
                        attrs[attr_name] = attr_value.decode('utf-8')
                    except UnicodeDecodeError:
                        attrs[attr_name] = attr_value.hex()
                except Exception as e:
                    attrs[attr_name] = f"Error reading: {e}"
            
            return attrs
        except Exception as e:
            print(f"Error extracting xattr from {file_path}: {e}")
            return {}
    
    def _parse_appledouble(self, appledouble_path: Path) -> Dict:
        """Parse AppleDouble format file.
        
        AppleDouble format:
        - Header (26 bytes)
        - Entry descriptors (12 bytes each)
        - Entry data
        
        Args:
            appledouble_path: Path to the ._file
            
        Returns:
            Dictionary containing parsed AppleDouble data
        """
        try:
            with open(appledouble_path, 'rb') as f:
                data = f.read()
            
            # Check magic number
            magic = struct.unpack('>I', data[0:4])[0]
            if magic not in (self.APPLEDOUBLE_MAGIC, self.APPLESINGLE_MAGIC):
                return {'error': 'Invalid AppleDouble magic number'}
            
            # Read header
            version = struct.unpack('>I', data[4:8])[0]
            num_entries = struct.unpack('>H', data[24:26])[0]
            
            result = {
                'magic': hex(magic),
                'version': version,
                'entries': {}
            }
            
            # Read entry descriptors
            offset = 26
            entries = []
            for i in range(num_entries):
                entry_id = struct.unpack('>I', data[offset:offset+4])[0]
                entry_offset = struct.unpack('>I', data[offset+4:offset+8])[0]
                entry_length = struct.unpack('>I', data[offset+8:offset+12])[0]
                entries.append((entry_id, entry_offset, entry_length))
                offset += 12
            
            # Parse entries
            for entry_id, entry_offset, entry_length in entries:
                entry_data = data[entry_offset:entry_offset+entry_length]
                
                if entry_id == self.ENTRY_REAL_NAME:
                    result['entries']['real_name'] = entry_data.decode('utf-8', errors='ignore')
                elif entry_id == self.ENTRY_COMMENT:
                    result['entries']['comment'] = entry_data.decode('utf-8', errors='ignore')
                elif entry_id == self.ENTRY_FINDER_INFO:
                    result['entries']['finder_info'] = self._parse_finder_info(entry_data)
                elif entry_id == self.ENTRY_RESOURCE_FORK:
                    result['entries']['resource_fork_size'] = entry_length
                else:
                    result['entries'][f'entry_{entry_id}'] = {
                        'size': entry_length,
                        'data_preview': entry_data[:100].hex()
                    }
            
            return result
            
        except Exception as e:
            return {'error': f'Error parsing AppleDouble: {e}'}
    
    def _parse_finder_info(self, data: bytes) -> Dict:
        """Parse Finder Info structure.
        
        Args:
            data: Finder Info data (32 bytes)
            
        Returns:
            Dictionary with parsed Finder Info
        """
        if len(data) < 32:
            return {'error': 'Invalid Finder Info size'}
        
        try:
            # First 16 bytes: FinderInfo
            file_type = data[0:4].decode('ascii', errors='ignore')
            creator = data[4:8].decode('ascii', errors='ignore')
            flags = struct.unpack('>H', data[8:10])[0]
            location = struct.unpack('>HH', data[10:14])
            folder = struct.unpack('>H', data[14:16])[0]
            
            # Second 16 bytes: ExtendedFinderInfo
            # Contains additional info like label color, etc.
            
            return {
                'file_type': file_type.strip(),
                'creator': creator.strip(),
                'flags': hex(flags),
                'location': location,
                'folder': folder
            }
        except Exception as e:
            return {'error': f'Error parsing Finder Info: {e}'}

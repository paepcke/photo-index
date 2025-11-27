#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-26 18:52:29
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-27 10:46:54
# -*- coding: utf-8 -*-
"""
Test Qdrant server connection.

Usage:
    python test_qdrant_connection.py
"""

from qdrant_client import QdrantClient

def test_connection():
    """Test connection to Qdrant server."""
    
    print("Testing Qdrant server connection...")
    print("-" * 70)
    
    try:
        # Connect to server
        client = QdrantClient(host="localhost", port=6333)
        
        # Get collections
        collections = client.get_collections()
        
        print("✓ Connected to Qdrant server successfully!")
        print(f"  Host: localhost:6333")
        print(f"\nCollections found: {len(collections.collections)}")
        
        for collection in collections.collections:
            print(f"\n  Collection: {collection.name}")
            
            # Get collection info
            info = client.get_collection(collection.name)
            print(f"    Vectors: {info.points_count}")
            print(f"    Dimension: {info.config.params.vectors.size}")
            
        print("\n" + "=" * 70)
        print("✓ Qdrant server is working correctly!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"✗ Error connecting to Qdrant server:")
        print(f"  {e}")
        print("\nTroubleshooting:")
        print("  1. Is Docker running? Check with: sudo docker ps")
        print("  2. Is Qdrant container running?")
        print("     sudo docker ps | grep qdrant")
        print("  3. Try restarting container:")
        print("     sudo docker restart qdrant")
        return False


if __name__ == '__main__':
    test_connection()

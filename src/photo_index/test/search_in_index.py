#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-23 19:43:09
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-23 19:44:46

from qdrant_client import QdrantClient

photo_path = '/raid/photos_all/IMG_4810.JPG'

client = QdrantClient(path='/raid/qdrant_storage/photos')

# Get all points (or paginate if you have many)
points, _ = client.scroll(
    collection_name='photo_embeddings',
    limit=100,
    with_payload=True
)

# Find the one you want
for point in points:
    if point.payload.get('file_name') == photo_path:
        print('Found!')
        print('Description:', point.payload.get('description'))
        print('Description parsed:', point.payload.get('description_parsed'))
        break
else:
    print('Not found')

# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-19 12:43:45
"""Configuration for photo indexing system."""

# Paths
PHOTO_DIR = "/raid/photos"
QDRANT_PATH = "./qdrant_storage"  # Local storage path
COLLECTION_NAME = "photo_embeddings"

# Qdrant settings
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
EMBEDDING_DIM = 3584  # Llama 3.2-Vision 11B embedding dimension

# Model settings
MODEL_CACHE_DIR = "/data/huggingface"
MODEL_NAME = "meta-llama/Llama-3.2-11B-Vision-Instruct"
MODEL_PATH = "/data/huggingface/hub/models--meta-llama--Llama-3.2-11B-Vision-Instruct/snapshots/9eb2daaa8597bf192a8b0e73f848f3a102794df5"
DEVICE = "cuda"  # Use GPU
BATCH_SIZE = 8  # Adjust based on VRAM

# File extensions to process
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.heic', '.HEIC', '.JPG', '.JPEG'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.MP4', '.MOV', '.AVI'}

# Geocoding
GEOCODING_USER_AGENT = "photo_indexer"

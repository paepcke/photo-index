# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-24 10:14:13
"""Configuration for photo indexing system."""

# Actions
GEN_IMG_DESCRIPTIONS = 1

# Prompts
IMG_DESC_PROMPT = (
    "Analyze this image and extract metadata for a search index. "
    "Return ONLY a valid JSON object with NO additional text. "
    "List at most 5 items per category. Categories are 'objects', ",
    "'materials', 'setting', and 'visual_attributes'. "
    "Avoid repetition.\n In the following schema, the information in "
    "brackets are examples; feel free to insert your own there.\n"
    "Schema: "
    '{ "objects": ["item1", "item2"], '
    '  "materials": ["mat1", "mat2"], '
    '  "setting": ["location", "time"], '
    '  "visual_attributes": ["color1", "style1"] }\n'
    "Here is a good example:\n"
    "{\n"
    '  "objects": ["bag", "cable"],\n'
    '  "materials": ["plastic", "rubber"],\n'
    '  "setting": ["outdoor", "daytime"],\n'
    '  "visual_attributes": ["red", "white"]\n'
    "}\n\n"
    "Bad example1: it contains text in addition to the JSON object:\n"
    "Here is the extracted metadata in a JSON object:\n" 
    "{\n"
    '  "objects": ["bag", "cable"],\n'
    '  "materials": ["plastic", "rubber"],\n'
    '  "setting": ["outdoor", "daytime"],\n'
    '  "visual_attributes": ["red", "white"]\n'
    "}\n\n"
    "Bad example2: the format is not JSON:\n"
    "**Objects:**\n"
    "* A man\n"
    "* A light fixture\n"
    "    ...\n\n"
    )

# IMG_DESC_PROMPT = (
#                     "Analyze this image and extract metadata for a search index. "
#                     "Return the result strictly as a JSON object with no conversational "
#                     "text or markdown wrapping.\n"
#                     "Use the following schema: "
#                     "{ 'objects': ['list', 'of', 'items'],"
#                     "  'materials': ['list', 'of', 'materials'], "
#                     "  'setting': ['location', 'context'], "
#                     "  'visual_attributes': ['colors', 'lighting', 'style'] }"
#                   )

# Paths
PHOTO_DIR = "/raid/photos"
#******PHOTO_DIR = "/raid/photo_tmp"
QDRANT_PATH = "/raid/qdrant_storage/photos"  # Local storage path
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
EMBEDDING_DIM = 7680  # Llama 3.2-Vision 11B output dimension
OUTPUT_TOKENS = 100

# File extensions to process
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.heic', '.HEIC', '.JPG', '.JPEG'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.MP4', '.MOV', '.AVI'}

# Geocoding
GEOCODING_USER_AGENT = "photo_indexer"

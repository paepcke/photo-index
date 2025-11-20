# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-19 18:25:24
"""Image embedding generation using Llama 3.2-Vision model."""

import torch
from transformers import MllamaForConditionalGeneration, AutoProcessor
from PIL import Image
import pillow_heif
from pathlib import Path
from typing import List
import numpy as np

# Register HEIF opener
pillow_heif.register_heif_opener()


class EmbeddingGenerator:
    """Generate image embeddings using Llama 3.2-Vision model."""
    
    def __init__(self, model_path: str, device: str = "cuda"):
        """Initialize the embedding generator.
        
        Args:
            model_name: HuggingFace model name
            device: Device to run on ("cuda" or "cpu")
        """
        self.device = device
        self.model_path = model_path
        
        print(f"Loading model {model_path} on {device}...")
        
        # Load model and processor
        self.model = MllamaForConditionalGeneration.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map=device,
            local_files_only=True
        )
        
        self.processor = AutoProcessor.from_pretrained(
            model_path, 
            local_files_only=True
            )
        self.model.eval()
        
        print("Model loaded successfully")
    
    def generate_embedding(self, image_path: Path) -> np.ndarray:
        """Generate embedding for a single image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Numpy array containing the image embedding
        """
        try:
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')
            
            # Create a minimal text prompt (required for the model)
            text = "Describe this image."
            
            # Process image and text together
            inputs = self.processor(
                text=text,
                images=image,
                return_tensors="pt"
            )
            
            # Move all inputs to device
            inputs = {k: v.to(self.device) if isinstance(v, torch.Tensor) else v 
                    for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                # Get model outputs - this handles all the vision processing
                outputs = self.model(**inputs, output_hidden_states=True)
                
                # Extract vision embeddings from hidden states
                # Use the last hidden state and pool it
                hidden_states = outputs.hidden_states[-1]
                embedding = hidden_states.mean(dim=1).squeeze()
                
                # Convert to numpy
                embedding_np = embedding.cpu().float().numpy()
            
            return embedding_np
            
        except Exception as e:
            print(f"Error generating embedding for {image_path}: {e}")
            raise
        
    def generate_embeddings_batch(self, image_paths: List[Path]) -> List[np.ndarray]:
        """Generate embeddings for a batch of images.
        
        Args:
            image_paths: List of paths to image files
            
        Returns:
            List of numpy arrays containing embeddings
        """
        embeddings = []
        
        for image_path in image_paths:
            try:
                embedding = self.generate_embedding(image_path)
                embeddings.append(embedding)
            except Exception as e:
                print(f"Skipping {image_path} due to error: {e}")
                # Return zero vector on error
                embeddings.append(None)
        
        return embeddings
    
    def get_embedding_dim(self) -> int:
        """Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension
        """
        # For Llama 3.2-Vision 11B, the hidden size is 3584
        return self.model.config.vision_config.hidden_size

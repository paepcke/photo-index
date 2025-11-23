# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-22 18:20:32
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
            
            # Process only the image (no text)
            inputs = self.processor.image_processor(
                images=image,
                return_tensors="pt"
            )
            
            # Move inputs to device
            pixel_values = inputs['pixel_values'].to(self.device)
            aspect_ratio_ids = inputs['aspect_ratio_ids'].to(self.device)
            aspect_ratio_mask = inputs['aspect_ratio_mask'].to(self.device)
            
            # Generate embedding using vision model directly
            with torch.no_grad():
                # Call vision model with all required inputs
                vision_outputs = self.model.vision_model(
                    pixel_values=pixel_values,
                    aspect_ratio_ids=aspect_ratio_ids,
                    aspect_ratio_mask=aspect_ratio_mask
                )
                
                # Get hidden states: shape is [batch, num_images, tiles, seq_len, hidden_dim]
                hidden_states = vision_outputs[0]
                
                # Average over all dimensions except the last (hidden_dim)
                # This collapses: batch, images, tiles, and sequence length
                embedding = hidden_states.mean(dim=(0, 1, 2, 3))  # Results in shape [hidden_dim]
                
                # Convert to numpy
                embedding_np = embedding.cpu().float().numpy()
            
            return embedding_np
            
        except Exception as e:
            print(f"Error generating embedding for {image_path}: {e}")
            raise

            
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
        # Try to auto-detect by generating a dummy embedding
        try:
            import tempfile
            from PIL import Image
            
            # Create a small test image
            test_img = Image.new('RGB', (100, 100), color='red')
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                test_img.save(f.name)
                test_path = Path(f.name)
            
            # Generate embedding to get actual dimension
            embedding = self.generate_embedding(test_path)
            test_path.unlink()  # Delete temp file
            
            return embedding.shape[0]
        except Exception as e:
            print(f"Warning: Could not auto-detect embedding dimension: {e}")
            print("Using default value of 7680")
            return 7680

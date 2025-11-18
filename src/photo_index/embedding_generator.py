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
    
    def __init__(self, model_name: str, device: str = "cuda"):
        """Initialize the embedding generator.
        
        Args:
            model_name: HuggingFace model name
            device: Device to run on ("cuda" or "cpu")
        """
        self.device = device
        self.model_name = model_name
        
        print(f"Loading model {model_name} on {device}...")
        
        # Load model and processor
        self.model = MllamaForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map=device,
        )
        
        self.processor = AutoProcessor.from_pretrained(model_name)
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
            
            # Process image
            inputs = self.processor(
                images=image,
                return_tensors="pt"
            ).to(self.device)
            
            # Generate embedding using vision encoder
            with torch.no_grad():
                # Get vision encoder outputs
                vision_outputs = self.model.vision_model(
                    pixel_values=inputs['pixel_values']
                )
                
                # Use the pooled output (CLS token equivalent)
                # For Llama Vision, we'll use mean pooling of the last hidden state
                hidden_states = vision_outputs.last_hidden_state
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

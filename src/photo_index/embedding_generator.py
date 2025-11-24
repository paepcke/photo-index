# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-18 15:27:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-24 09:56:00
"""Image embedding generation using Llama 3.2-Vision model."""

import torch
from transformers import MllamaForConditionalGeneration, AutoProcessor, GenerationConfig
from PIL import Image
import pillow_heif
from pathlib import Path
from typing import List
import numpy as np

from logging_service import LoggingService

from photo_index.config import IMG_DESC_PROMPT, OUTPUT_TOKENS

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

        self.log = LoggingService()
        
        self.log.info(f"Loading model {model_path} on {device}...")
        
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
        
        self.log.info("Model loaded successfully")
    

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
            self.log.err(f"Error generating embedding for {image_path}: {e}")
            raise

            
        except Exception as e:
            self.log.err(f"Error generating embedding for {image_path}: {e}")
            raise        

    def generate_description(self, image_path: Path, prompt: str = None) -> str:
        """Generate a text description of the image contents.
        
        Args:
            image_path: Path to the image file
            prompt: Optional custom prompt. If None, uses default object detection prompt.
            
        Returns:
            Text description of the image
        """
        try:
            # Load image
            image = Image.open(image_path).convert('RGB')
            
            # Default prompt optimized for object detection and description
            if prompt is None:
                prompt = IMG_DESC_PROMPT
            
            # Format as a chat message (Llama format)
            messages = [
                {
                    "role": "user", 
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            # Apply chat template
            input_text = self.processor.apply_chat_template(
                messages, 
                add_generation_prompt=True
            )
            
            # Process with the properly formatted text
            inputs = self.processor(
                image,
                input_text,
                return_tensors="pt",
                add_special_tokens=False
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate description
            gen_config = GenerationConfig(
                max_new_tokens=OUTPUT_TOKENS,
                do_sample=False,
                temperature=None,
                top_p=None,
                pad_token_id=self.processor.tokenizer.pad_token_id,
                eos_token_id=self.processor.tokenizer.eos_token_id
            )            
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    generation_config=gen_config
                )
            
            # Decode - get only the new tokens
            generated_text = self.processor.decode(
                output_ids[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )
            
            return generated_text.strip()
            
        except Exception as e:
            self.log.err(f"Error generating description for {image_path}: {e}")
            import traceback
            self.log.err(traceback.format_exc())
            return ""

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
                self.log.err(f"Skipping {image_path} due to error: {e}")
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
            self.log.warn(f"Warning: Could not auto-detect embedding dimension: {e}")
            self.log.info("Using default value of 7680")
            return 7680

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Face detection and recognition using InsightFace buffalo_l model."""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# Set model path before importing insightface
os.environ['INSIGHTFACE_HOME'] = '/data/insightface_models'

from insightface.app import FaceAnalysis


@dataclass
class DetectedFace:
    """Container for detected face information."""
    embedding: np.ndarray  # 512-dim normalized embedding
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float
    face_index: int  # Index of face in photo (0=largest, 1=second largest, etc.)


class FaceDetector:
    """Detect and embed faces using InsightFace buffalo_l model."""

    def __init__(self):
        """Initialize face detection model with GPU support."""
        self.app = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the InsightFace model (lazy loading)."""
        try:
            self.app = FaceAnalysis(
                name='buffalo_l',
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            # det_size=(640, 640) balances speed and accuracy
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            print("FaceDetector initialized with buffalo_l model on GPU")
        except Exception as e:
            print(f"Error initializing FaceDetector: {e}")
            raise

    def detect_faces(self, image_path: Path) -> List[DetectedFace]:
        """Detect all faces in an image and return embeddings.

        Args:
            image_path: Path to image file

        Returns:
            List of DetectedFace objects, sorted by size (largest first)
        """
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                print(f"Failed to load image: {image_path}")
                return []

            # Detect faces
            faces = self.app.get(img)

            if len(faces) == 0:
                return []

            # Sort by bounding box area (largest first)
            faces_sorted = sorted(
                faces,
                key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]),
                reverse=True
            )

            # Convert to DetectedFace objects
            detected_faces = []
            for idx, face in enumerate(faces_sorted):
                detected_face = DetectedFace(
                    embedding=face.normed_embedding,  # Already normalized
                    bbox=face.bbox.astype(int).tolist(),
                    confidence=float(face.det_score),
                    face_index=idx
                )
                detected_faces.append(detected_face)

            return detected_faces

        except Exception as e:
            print(f"Error detecting faces in {image_path}: {e}")
            return []

    def get_face_count(self, image_path: Path) -> int:
        """Quick count of faces in image without full processing."""
        faces = self.detect_faces(image_path)
        return len(faces)

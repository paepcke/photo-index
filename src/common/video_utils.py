# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-01 14:43:53
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-01 15:01:56

import numpy as np
import cv2

# ------------------- Context Manager VideoStream -----------------

class VideoStream:
    '''
    Context manager for video streams such as a .mov file 
    or a camera. 
    Usage:
        with VideoStream(<video-file>) as cap:
            
    '''
    def __init__(self, source=0):
        """
        :param source: 0 for webcam, or a string path for a video file.
        """
        self.source = source
        self.cap = None

    def __enter__(self):
        # 1. Acquire the resource
        self.cap = cv2.VideoCapture(self.source)
        
        # 2. Check if opened successfully
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video source: {self.source}")
            
        # 3. Return the resource to be used in the 'as' clause
        return self.cap

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 4. Release the resource (this runs even if the code crashes)
        if self.cap:
            self.cap.release()
        return False # propagate exceptions

# ------------------- Class VideoUtils -----------------

class VideoUtils:

    @staticmethod
    def frame_to_jpeg(frame: np.ndarray, fpath: str):
        # The function returns True if the file was successfully written, False otherwise.
        success = cv2.imwrite(fpath, frame)
        if not success:
            raise IOError(f"Could not save frame to file {fpath}")

    @staticmethod 
    def get_frame_fingerprint(frame: np.ndarray):
        """
        Creates a color histogram fingerprint for a given frame.
        Using HSV is better than RGB as it separates luma (brightness) from chroma.
        """
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Calculate histogram: 
        # Channels [0, 1] = Hue and Saturation (we ignore Value/Brightness to be robust)
        # Bins [50, 60] = Granularity of the comparison
        # Ranges [0, 180, 0, 256] = Standard HSV ranges
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        
        # Normalize the histogram so image size doesn't matter
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist

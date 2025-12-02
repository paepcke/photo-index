# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 16:45:08
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-01 18:29:47

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter
import cv2

from logging_service import LoggingService

from common.video_utils import VideoStream, VideoUtils

class SceneChangeDetector:
    """
    Detects significant scene changes in a time-series of 'content_val' 
    by applying Gaussian smoothing and filtering peaks based on prominence.
    Usage:
      detector = SceneChangeDetector(scene_cur_values, vid_path)
      scenes = detector.detect_scenes()
      detector.frames() # to get the frame images for saving.
                        # Frames are ordered to correspond to
                        # the rows in the returned scenes df.
    """

    # Similarity of frame fingerprints above which two
    # frames are considered duplicates:
    SIMILARITY_THRESHOLD = 0.9

    def __init__(
            self,
            time_series: {pd.DataFrame | str},
            vid_path: str,
            sigma: int = 3, 
            min_prominence: float = 3.0, 
            min_height: float = 4.0,
            change_magnitude_col: str = 'content_val') -> pd.DataFrame:
        """
        Initializes the detector with key parameters.

        :param time_series: either path to a .csv file, or a Pandas dataframe
        :param vid_path: path to the video for lifting frames.
        :param sigma: The standard deviation (spread) of the Gaussian filter. 
                         Higher sigma means more smoothing.
        :param min_prominence: Minimum required prominence for a peak 
                         to be considered a scene change. (Key for filtering spikes)
        :param min_height: Minimum absolute value a peak must reach. 
                         (Used to ensure the detected peak is high enough, like 5.0)
        :data_col: column in .csv file or dataframe that holds the frame change
                         quantification data.
        """
        self.vid_path = vid_path
        self.sigma = sigma
        self.min_prominence = min_prominence
        self.min_height = min_height
        self.smoothed_data = None
        self.scene_change_indices = None
        self.change_magnitude_col = change_magnitude_col

        self.log = LoggingService()

        if type(time_series) == str:
            try:
                self.time_series = pd.read_csv(time_series)
            except Exception as e:
                raise FileNotFoundError(f"Could not open .csv file {time_series}")
        elif type(time_series) == pd.DataFrame:
            self.time_series = time_series 
        else:
            raise TypeError(f"Data must be a dataframe or path to .csv file, not {time_series}")
        
        # Can we find the content values column?
        if self.change_magnitude_col not in self.time_series.columns.tolist():
            raise ValueError(f"Dataframe column {self.change_magnitude_col} not found among columns in {self.time_series}")
        
        # Determine the window size for the Gaussian kernel (e.g., 6*sigma + 1)
        # 3stds on left of distrib + 3stds on right of distrib ==> 6*sigma
        # The +1 makes the window odd to allow algnments around the mean:
        self.window_size = int(6 * self.sigma + 1)

    def detect_scenes(self):
        """
        Processes the time series to detect scene changes.

        Args:
            time_series (pd.DataFrame): DataFrame with time and value columns.
            val_column (str): The name of the column containing the current values.

        Returns:
            pd.DataFrame: A DataFrame containing the detected scene change times and values.
        """
        if not isinstance(self.time_series, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame.")
            
        data = self.time_series[self.change_magnitude_col].values
        
        # Apply Smoothing
        self.smoothed_data = self._apply_gaussian_smoothing(data)
        
        # Find Peaks (using prominence and height filters)
        # find_peaks returns indices of detected peaks
        # The properties will be a dict with keys 
        #      ['peak_heights', 'prominences', 'left_bases', 'right_bases']
        # These are the same lengths as the scene indices, and correspond
        # to them. 
        # The indices point to scene changes:
        indices, properties = find_peaks(
            self.smoothed_data, 
            height=self.min_height,          # Must be greater than min_height
            prominence=self.min_prominence   # Must have enough prominence
        )
        
        self.scene_change_indices = indices
        
        # Collect the rows that are scene changes:
        scenes = self.time_series.iloc[indices].copy()
        
        # Add the detected prominence and the smoothed value for context
        scenes['prominence'] = properties['prominences']
        scenes['smoothed_val'] = self.smoothed_data[indices]

        uniq_scenes = self.deduplicate(scenes, self.vid_path)
        return uniq_scenes

    def deduplicate(self, scenes: pd.DataFrame, video_path: str) -> pd.DataFrame:
        
        final_indices = []
        kept_histograms = []
        self.scene_frame_data = []
        
        # Open video to grab frames at specific indices
        with VideoStream(video_path) as cap:

            # Iterate through the peaks found by scipy
            ret: bool
            frame: np.ndarray
            for idx, scene_row in scenes.iterrows():
                # Jump to the frame index
                frame_num = int(scene_row['frame_number'])
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if not ret:
                    # Frame was identifies as a series, but
                    # could not be retrieved:
                    raise IOError((f"Frame {idx} in movie {video_path} identified as " 
                                   f"keyframe, but not readable from file"))

                # Calculate fingerprint
                current_hist = VideoUtils.get_frame_fingerprint(frame)
                
                # Check against ALREADY accepted scenes
                # Note: We check against *kept_histograms*, not just the previous one.
                if not self._is_duplicate(current_hist, 
                                          kept_histograms, 
                                          threshold=SceneChangeDetector.SIMILARITY_THRESHOLD):
                    final_indices.append(idx)
                    kept_histograms.append(current_hist)
                    # Remember the retrieved frames so client
                    # does not need to do it again when they
                    # save them as images
                    self.scene_frame_data.append(frame)
                else:
                    # Optional: Log that a scene was dropped
                    self.log.info(f"Scene {idx} in {self.vid_path} removed as duplicate")
        return scenes.loc[final_indices]

    def get_smoothed_values(self):
        """For clients of this class: the smoothed values array for plotting/analysis."""
        return self.smoothed_data
    
    def _apply_gaussian_smoothing(self, data):
        """Applies a 1D Gaussian filter to the input data."""
        
        smoothed = gaussian_filter(data, sigma=self.sigma, order=0, mode='reflect')
        return smoothed

    def _is_duplicate(self, 
                      new_hist, 
                      kept_histograms, 
                      threshold=None):
        """
        Compares new histogram against all kept histograms.
        Returns True if a match is found.
        """
        if threshold is None:
            threshold = SceneChangeDetector.SIMILARITY_THRESHOLD
            
        for kept_hist in kept_histograms:
            # Compare using Correlation method (1.0 is identical, 0.0 is different)
            similarity = cv2.compareHist(kept_hist, new_hist, cv2.HISTCMP_CORREL)
            if similarity > threshold:
                return True
        return False

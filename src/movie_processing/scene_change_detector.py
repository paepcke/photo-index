# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 16:45:08
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-04 15:38:26

from typing import Optional
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
            time_series_spec: {pd.DataFrame | pd.Series | str},
            vid_path: str,
            sigma: Optional[int] = 3, 
            min_prominence: Optional[float] = 3.0, 
            min_height: Optional[float] = 4.0,
            change_magnitude_col: Optional[str] = 'content_val') -> pd.DataFrame:
        """
        Initializes the detector with key parameters.
        The time_series_spec will be loaded into a df from file if the 
        path of a .csv is given. The loaded, or directly given
        df must include a column named as given by change_magnitude_col.
        Example, a df with columns:
            content_val    frame_number     timecode

        The pd.Series found by the above procedure will be available
        to callers in

              <scene-change-detector-instance>.time_series

        :param time_series_spec: either path to a .csv file, or a Pandas dataframe
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

        self.log = LoggingService()

        # Did we get the path to a .csv file, a dataframe with
        # one particular column being the relevant time series,
        # or directly the needed pd.Series?
        time_series_df = None
        if type(time_series_spec) == str:
            try:
                # Load .csv into df
                time_series_df = pd.read_csv(time_series_spec)
            except Exception as e:
                raise FileNotFoundError(f"Could not open .csv file {time_series_spec}")
        elif type(time_series_spec) == pd.DataFrame:
            time_series_df = time_series_spec
        elif type(time_series_spec) == pd.Series:
            # Got the desired Series directly
            self.time_series = time_series_spec
        else:
            raise TypeError(f"Data must be a dataframe or path to .csv file, not {time_series_spec}")
        
        # If we now have a df with the needed time series 
        # as one of its columns, get that column into a Series:
        if time_series_df is not None:
            # Can we find the content values column?
            if change_magnitude_col not in time_series_df.columns.tolist():
                raise ValueError(f"Dataframe column {change_magnitude_col} not found among columns in {self.time_series}")
            self.time_series = time_series_df[change_magnitude_col]
            
        # Determine the window size for the Gaussian kernel (e.g., 6*sigma + 1)
        # 3stds on left of distrib + 3stds on right of distrib ==> 6*sigma
        # The +1 makes the window odd to allow algnments around the mean:
        self.window_size = int(6 * self.sigma + 1)

    def detect_scenes(self, time_series: pd.Series) -> pd.DataFrame:
        """
        Processes the time series to detect scene changes.

        Args:
            time_series (pd.Series): DataFrame with time and value columns.
            val_column (str): The name of the column containing the current values.

        Returns:
            pd.DataFrame: A DataFrame containing the detected scene 
                change times and values.
        """
        if not isinstance(self.time_series, pd.Series):
            raise TypeError("Input must be a pandas Series.")
            
        # Apply Smoothing
        self.smoothed_data = self._apply_gaussian_smoothing(time_series)
        
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
        
        # Make a result df like:
        #    idx    frame_number   content_val    prominence    smoothed_val
        # Collect the rows that are scene changes.
        # This will be a pd.Series in which the index
        # values are the frame numbers, and the Series
        # values are the content_vals (i.e. frame change scores)
        scene_data = self.time_series.iloc[indices].copy()
        scenes = pd.DataFrame({
            'frame_number': scene_data.index,
            'prominence'  : properties['prominences'],
            'smoothed_content_val': self.smoothed_data[indices],
            'content_vals': scene_data.values
        })

        uniq_scenes = self.deduplicate(scenes, self.vid_path)
        return uniq_scenes

    def deduplicate(self, scenes: pd.DataFrame, video_path: str) -> pd.DataFrame:
        '''
        Removes duplicates from the given scenes df, and returns two items:
           1. A dataframe excerpted from the input scenes, in which near-duplicate 
              scenes are removed. Like:
                   frame_number  prominence  smoothed_content_val  content_vals
                0            27    4.783040              9.630631      9.620940
                1           294    7.560820              9.915100     10.103290
                4          1180    3.769875             14.477572     14.661802
                5          1278    5.455810             10.201112     10.268808

           2. A pd.Series: where each value is the np.ndarray of one
              scene video frame; ready to be displayed or saved to file.
              The Series' index holds the frame numbers within the
              movie.
           

        ADDITIONALLY: provides in <scene-change-detector>.scene_frame_data 
        a pd.Series in scene_frame_data, in which 
        each value is the raw video frame of one scene. The index provides
        the frame numbers from which the images came. The name of the
        Series will be 'frame_images'.

        Callers can obtain save such a row as a movie file, or display it as
        a still image.

        :param scenes: the detected scenes
        :param video_path: path to the movie file
        :raises IOError: if movie can't be loaded
        :return: a new df with duplicate scenes eliminated.
        '''
        
        final_indices = []
        kept_histograms = []
        scene_frame_data = []
        
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
                    scene_frame_data.append(frame)
                else:
                    # Optional: Log that a scene was dropped
                    self.log.info(f"Scene {idx} in {self.vid_path} removed as duplicate")

        dedupped_scenes = scenes.loc[final_indices]
        # Turn the saved raw frames into a pd.Series w
        # where each value is a raw frame, and its index
        # value is the frame number
        self.scene_frame_data = pd.Series(
            data=scene_frame_data, 
            index=dedupped_scenes['frame_number'],
            name='frame_images'
            )

        return dedupped_scenes

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

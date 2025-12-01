# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 16:45:08
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-30 17:17:53

import numpy as np
import pandas as pd
from scipy.signal import gaussian, convolve, find_peaks

class SceneChangeDetector:
    """
    Detects significant scene changes in a time-series of 'current_val' 
    by applying Gaussian smoothing and filtering peaks based on prominence.
    Usage:
      detector = SceneChangeDetector(scene_cur_values)
      detector.detect_scenes()
      
    """

    def __init__(
            self,
            time_series: {pd.DataFrame | str},
            sigma: int = 3, 
            min_prominence: float = 3.0, 
            min_height: float = 4.0,
            change_magnitude_col: str = 'current_val'):
        """
        Initializes the detector with key parameters.

        :param time_series: either path to a .csv file, or a Pandas dataframe
        :param sigma: The standard deviation (spread) of the Gaussian filter. 
                         Higher sigma means more smoothing.
        :param min_prominence: Minimum required prominence for a peak 
                         to be considered a scene change. (Key for filtering spikes)
        :param min_height: Minimum absolute value a peak must reach. 
                         (Used to ensure the detected peak is high enough, like 5.0)
        :data_col: column in .csv file or dataframe that holds the frame change
                         quantification data.
        """
        self.sigma = sigma
        self.min_prominence = min_prominence
        self.min_height = min_height
        self.smoothed_data = None
        self.scene_change_indices = None
        self.change_magnitude_col = change_magnitude_col

        if type(time_series) == str:
            try:
                self.time_series = pd.read_csv(time_series)
            except Exception as e:
                raise FileNotFoundError(f"Could not open .csv file {time_series}")
        elif type(time_series) == pd.DataFrame:
            self.time_series = time_series 
        else:
            raise TypeError(f"Data must be a dataframe or path to .csv file, not {time_series}")
        
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
        
        # 1. Apply Smoothing
        self.smoothed_data = self._apply_gaussian_smoothing(data)
        
        # 2. Find Peaks (using prominence and height filters)
        # find_peaks returns indices of detected peaks
        indices, properties = find_peaks(
            self.smoothed_data, 
            height=self.min_height,          # Must be greater than min_height
            prominence=self.min_prominence   # Must have enough prominence
        )
        
        self.scene_change_indices = indices
        
        # 3. Compile Results
        results = self.time_series.iloc[indices].copy()
        
        # Add the detected prominence and the smoothed value for context
        results['prominence'] = properties['prominences']
        results['smoothed_val'] = self.smoothed_data[indices]
        
        return results

    def get_smoothed_values(self):
        """Returns the smoothed values array for plotting/analysis."""
        return self.smoothed_data
    
    def _apply_gaussian_smoothing(self, data):
        """Applies a 1D Gaussian filter to the input data."""
        
        # 1. Create the Gaussian kernel
        # We use a 1D Gaussian window from SciPy
        kernel = gaussian(self.window_size, std=self.sigma)
        
        # 2. Normalize the kernel so the area under the curve is 1
        kernel = kernel / np.sum(kernel)
        
        # 3. Convolve the kernel with the data (smoothing)
        # 'mode="same"' ensures the output array is the same length as the input
        smoothed = convolve(data, kernel, mode='same')
        
        return smoothed


# --- Example Usage ---

# 1. Create Synthetic Data (Simulating your scenario)
# Time is 1-second intervals
time = np.arange(0, 50, 1) 
# Baseline noise (low values)
values = np.random.uniform(0.5, 1.5, size=len(time)) 

# --- True Scene Change (The signal you WANT to detect) ---
# A broad, sustained peak around t=10
values[8:13] += [1.0, 3.0, 4.0, 3.5, 1.5]  # Peak at [t=10, 5.0]

# --- Transient Spikes (The noise you WANT to ignore) ---
# Rapid, isolated spikes (high value, low prominence)
values[25] += 8.0 # Spike at 9.5
values[35] += 7.0 # Spike at 8.5

df = pd.DataFrame({'time': time, 'current_val': values})

# 2. Initialize and Run Detector
# Initialized to detect peaks >= 4.0 and having prominence >= 3.0
detector = SceneChangeDetector(sigma=3, min_prominence=3.0, min_height=4.0)

detected_changes_df = detector.detect_scenes(df, val_column='current_val')

# 3. Output Results
print("## 📊 Detected Scene Changes (Filtered by Prominence and Height) ##")
print(detected_changes_df)

# You can now plot the original data, the smoothed data, and the detected points
# to visualize how the filtering works.

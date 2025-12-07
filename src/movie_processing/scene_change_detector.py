# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 16:45:08
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-07 15:42:13

from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter
import cv2
from skimage.metrics import structural_similarity as ssim

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
    SIMILARITY_THRESHOLD = 0.55

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
        # self.window_size = int(6 * self.sigma + 1)

    def detect_scenes(self, time_series: pd.Series) -> pd.DataFrame:
        """
        Processes the time series to detect scene changes.
        Returns dataframe like:
              
               frame_number  prominence  smoothed_content_val  content_vals      scene_frame
            0            27    4.783040              9.630631      9.620940    <img np.ndarray>
            1           294    7.560820              9.915100     10.103290    <img np.ndarray>
            4          1180    3.769875             14.477572     14.661802    <img np.ndarray>
            5          1278    5.455810             10.201112     10.268808    <img np.ndarray>

        Args:
            time_series (pd.Series): the movie's frame-by-frame change amount scores

        Returns:
            pd.DataFrame: A DataFrame containing the detected scene 
                change frames with associated change amount scores,
                and the scene image for each scene.
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
        # The frame_number entries will have turned into floats.
        # Make them ints again:
        scenes['frame_number'] = scenes['frame_number'].astype('int64')
        # Remove near-duplicate scenes, and add a column
        # 'scene_frame' with each scene's image data:
        if len(scenes) > 1:
            uniq_scenes = self.deduplicate(scenes, self.vid_path)
        else:
            uniq_scenes = scenes
            # The self.deduplicate() method adds raw frame
            # data as an additional column 'scene_frame'
            # We must add that col in this branch as well:
            frame_num = uniq_scenes.iloc[0]['frame_number']
            uniq_scenes['scene_frame'] = [VideoUtils.get_frame(self.vid_path, frame_num)]
        eliminated = len(scenes) - len(uniq_scenes)
        msg = f"Found {len(scenes)} scenes"
        if eliminated > 0:
            msg += f". After dedup: {len(uniq_scenes)}"
        self.log.info(msg)
        return uniq_scenes

    def deduplicate(self, scenes: pd.DataFrame, video_path: str
                    ) -> Tuple[pd.DataFrame, pd.Series]:
        '''
        Removes near-duplicates from the given scenes df. Returns a df
        with near-duplicate scene rows removed. A new column 
        called 'scene_frames' is added. Its values are np.ndarrays that
        are the scene images as lifted from the movie. They can
        be saved to a .jpg, or directly displayed on screen.

        :param scenes: the detected scenes
        :param video_path: path to the movie file
        :raises IOError: if movie can't be loaded
        :return: a new df with duplicate scenes eliminated, 
            and scene images column added
        '''
        self.log.info(f"Deduplicating {len(scenes)} scenes...")        
        kept_indices = []
        kept_frames = []
        all_scene_frame_numbers = []
        all_scene_frame_data = []
        # Range of pixel values; normally 0-255, when read
        # straight from a video. But could be 0-1.0, for instance
        # if normalized. We compute the proper range once, when
        # we have the first frame:
        data_range = None
        
        # Open video and grab frames at scene boundaries:
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
                # Do we have a pixel data range yet?
                if data_range is None:
                    data_range = self._pixel_data_range(frame)
                # Save the frame number and raw frame data
                all_scene_frame_numbers.append(scene_row['frame_number'])
                all_scene_frame_data.append(frame)

        # Remove near-duplicates:
        # Always keep the first candidate (frame and its frame index):
        kept_frames.append(all_scene_frame_data[0])
        kept_indices.append(all_scene_frame_numbers[0])

        # Compare each successive frame with each
        # of the previously accepted ones:
        if len(all_scene_frame_data) > 1:
            for frame_number, frame in zip(all_scene_frame_numbers[1:], all_scene_frame_data[1:]):
                # Here is where we apply image similarity analysis:
                #************
                #print(f"Frame {int(frame_number)} against {[int(frm) for frm in kept_indices]}")
                #************
                if self._is_duplicate(frame, 
                                      kept_frames, 
                                      self.SIMILARITY_THRESHOLD,
                                      ):
                    # Drop the duplicate
                    continue
                kept_frames.append(frame)
                kept_indices.append(frame_number)

        # Pick out the scene rows of scenes
        # that were accepted:
        dedupped_scenes = (scenes[scenes['frame_number'].isin(kept_indices)]).copy()
        # Turn the saved raw frames into a pd.Series
        # where each value is a raw frame, and its index
        # value is the frame number
        all_scene_frame_data = pd.Series(
            data=kept_frames, 
            index=dedupped_scenes['frame_number'],
            name='frame_image'
            )
        # Add the scene frames as a column called 'scene-frame'
        # to the scene information. Use map() because the scene_frame_data's
        # index matches the dedupped_scenes's *frame_number* column, NOT 
        # dedupped_scenes' index:
        dedupped_scenes['scene_frame'] = dedupped_scenes['frame_number'].map(all_scene_frame_data)
        return dedupped_scenes

    def get_smoothed_values(self):
        """For clients of this class: the smoothed values array for plotting/analysis."""
        return self.smoothed_data
    
    def _apply_gaussian_smoothing(self, data):
        """Applies a 1D Gaussian filter to the input data."""
        
        smoothed = gaussian_filter(data, sigma=self.sigma, order=0, mode='reflect')
        return smoothed

    def _is_duplicate(self,
                      new_frame: np.ndarray,
                      kept_frames: List[np.ndarray],
                      threshold: float = None,
                      ):

        for frame in kept_frames:
            similarity = self.composite_similarity(
                new_frame,
                frame,
            )
            if similarity > threshold:
                return True
        return False

    def composite_similarity(self, 
                             candidate_img: np.ndarray, 
                             reference_img: np.ndarray,
                             historgram_weight = 0.5,
                             win_size: int = 7,
                             data_range: int | float = 255,
                             ret_all=False
                             ) -> float | dict[str, float]:
        '''
        Given two images, return a similarity score between [0,1].
        The score is a weighted combination of structural 
        similarity, and hue, saturation histogram similarity.

        Structural similarity related parameters:
           - win_size is the size in pixels of a window
             that structural_similarity (ssim) slides across
             images as it examines. Number must be odd, and
             less than the smaller of the image edges
           - data_range is the largest number that a given
             pixel value can take. For images that is usually
             255, but maybe be 1.0 if the pixel values were
             were normalized to [0,1].
        Composition related parameters:
           - histogram weight: a number in [0,1.0] is the
             proportion to which the histogram similarity
             score figures into the final score.

        If ret_all is True, then instead of a single similarity
        score, returns a dict:
            {'similarity' : combined_similarity,
             'ssim_score': ssim_score,
             'histogram_score': hist_score
             }        
             
        :param candidate_img: image against which similarity is measured
        :param reference_img: the image being compared against candidate_img
        :param historgram_weight: weight of histogram score, defaults to 0.5
        :param win_size: window size for ssim, defaults to 7
        :param ret_all: return a dict of partial results instead
             of just one similarity score, defaults to False
        :return: either a single number in [0,1], or a dict of
            results by histogram and ssim scoring
        '''
        if win_size is None:
            try:
                # If black-white image, we get an 
                # exception, b/c the won't be a channel
                # dimension returned:
                height, width, num_channels = reference_img.shape
            except ValueError:
                height, width = reference_img.shape

            # The minimum of the images sides:
            min_dim = min(height, width)
            # Get size of window that similarity will slide 
            # over the frames:
            if min_dim < 7:
                # Win size must be odd. So:
                #   o If min_dim is 5 or 6, win_size will be 5
                #   o If min_dim is 3 or 4, win_size will be 3
                #   o If min_dim is 1 or 2, win_size will be 1 
                win_size = min_dim if min_dim % 2 != 0 else min_dim - 1
            else:
                # Use the default or another suitable odd value (e.g., 7)
                win_size = 7
        if data_range is None:
            data_range = self._pixel_data_range(reference_img)
            
        ssim_score = ssim(reference_img,
                            candidate_img, 
                            channel_axis=2 if len(reference_img.shape) > 2 else None,
                            win_size=win_size, 
                            data_range=data_range)
        fingerprint_ref = VideoUtils.get_frame_fingerprint(reference_img)
        fingerpring_cand = VideoUtils.get_frame_fingerprint(candidate_img)
        hist_score = cv2.compareHist(fingerprint_ref, fingerpring_cand, cv2.HISTCMP_CORREL)

        # Weighted combination
        ssim_weight = 1 - historgram_weight
        combined_similarity = ssim_weight * ssim_score + historgram_weight * hist_score
        if ret_all:
            return {'similarity' : combined_similarity,
                    'ssim_score': ssim_score,
                    'histogram_score': hist_score
                    }
        else:
            return combined_similarity

    def _pixel_data_range(self, frame: np.ndarray) -> int | float:
        '''
        Determine the difference between the minimum and maximum
        possible pixel values in the frame. Usually frames data
        is uint8, so the range is 255. But normalization manipulations
        can change that. 

        :param frame: video frame whose data range is to be found
        :raises ValueError: if non-standard frame format
        :return: a single number: the range of possible pixel values
        '''
        if frame.dtype == np.uint8:
            # Most common case for images read directly by OpenCV
            return 255

        elif frame.dtype == np.float32 or frame.dtype == np.float64:
            # This means we likely converted the frame after reading it.
            # Check the actual maximum value to infer the intended range
            if frame.max() <= 1.0:
                # Normalized float data (0.0 to 1.0)
                return 1.0
            else:
                # Unnormalized float data (0.0 to 255.0)
                return 255.0
        else:
            # Handle other unexpected dtypes, though unlikely for standard video frames
            raise ValueError(f"Unexpected frame dtype: {frame.dtype}")        

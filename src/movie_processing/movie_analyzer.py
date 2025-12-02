#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 12:55:10
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-01 18:23:43

"""
MovieAnalyzer - Analyze content values in video files, generating
suggested representative frames for summarizing the movie.

This tool uses PySceneDetect to analyze video content and provides:
- Statistical analysis of content values
- Histogram visualization
- Time-series visualization with interactive thumbnail preview
- Scene count threshold calculation
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from matplotlib.backend_bases import MouseEvent

# PySceneDetect imports
import pandas as pd
from scenedetect import detect, ContentDetector, split_video_ffmpeg
from scenedetect import open_video
from scenedetect.scene_manager import SceneManager
from scenedetect.stats_manager import StatsManager

from logging_service import LoggingService

from movie_processing.scene_change_detector import SceneChangeDetector

class MovieAnalyzer:
    """Analyze scene detection metrics for video files."""
    
    def __init__(self, 
                 video_path: str, 
                 scenecount_max: int | None = None, 
                 visuals: bool = True):
        """
        Initialize the MovieAnalyzer. Optionally show time charts of
        frame-by-frame changes. If scenecount_max is provided, no more
        than that number of scenes are identified. The reductions are 
        made by accepting only highly prominent frame change peaks.
        
        :param video_path: Path to the video file (.mp4, .mov, etc.)
        :param scenecount_max: optional limit on the number of scenes
        :param visuals: whether or not to show progress bars and charts
        """
        
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        self.scenecount_max = scenecount_max
        self.visuals = visuals
        
        self.log = LoggingService()
        
        self.video_stream = None
        self.scene_manager = None
        self.stats_manager = None
        self.raw_scene_change_vals: pd.DataFrame = None
        self.smooth_scene_change_vals: pd.DataFrame = None
        self.scenes: pd.DataFrame = None
        
    def analyze(self) -> List[np.ndarray]:
        """
        Run scene detection analysis on the video.
        Return a list of frames that display important
        scenes. Caller can use VideoUtils.show_frame(frame)
        or VideoUtils.frame_to_jpeg(frame, fname, metadata)
        """
        self.log.info(f"Analyzing video: {self.video_path}")
        
        # Initialize video stream
        self.video_stream = open_video(str(self.video_path))
        
        # Create scene manager and stats manager. The scene manager
        # coordinates the movie processing:
        self.stats_manager = StatsManager()
        self.scene_manager = SceneManager(self.stats_manager)
        
        # Add content detector. It computes visual frame-by-frame 
        # differences, and produces the values as a score list: content_vals.
        # The high threshold ensures that the detector records
        # all content_val values, rather than filtering those
        # below a threshold:
        self.scene_manager.add_detector(ContentDetector(threshold=99999.0))
        
        # Find raw frame-content-change values:
        self.scene_manager.detect_scenes(self.video_stream, show_progress=self.visuals)
        
        # Extract the raw content_val number from the stats manager:
        self.raw_scene_change_vals: pd.DataFrame = self._extract_content_values(self.stats_manager)

        # Smooth these values, and find peaks and prominences
        scene_detector = SceneChangeDetector(self.raw_scene_change_vals, 
                                             self.video_path)
        # Obtain a df with just scene change pointer, e.g. for just scenes:
        #  idx    content_val  frame_number  timecode   prominence  smoothed_val
        #  159     12.602648       160       5.333333    7.562601     12.153559
        #                          ...
        self.scenes = scene_detector.detect_scenes()
        # Since the scene_detector had to pull the frames, 
        # grab them, to have them available for clients of
        # this class
        self.scene_frames = scene_detector.scene_frame_data

        if self.scenecount_max is not None and len(self.scenes) > self.scenecount_max:
            # Reduce the number of scenes by prioritizing high-prominence 
            # peaks in the frame-by-frame differences:

            # Keep the original accessible
            self.all_scenes = self.scenes.copy()

            # Select the top N rows based on prominence
            # nlargest is generally faster/cleaner than sort_values().head() for this
            subset = self.scenes.nlargest(self.scenecount_max, 'prominence')

            # Sort back by index (or frame_number) to restore temporal order
            self.scenes = subset.sort_index()

            # Reset index to have a 0,1,2,... index
            self.scenes = self.scenes.reset_index(drop=True)           


        if self.visuals:
            # Just for plotting: get the smoothed content_vals:
            self.smooth_scene_change_vals = self.raw_scene_change_vals.copy()
            self.smooth_scene_change_vals['content_val'] = scene_detector.get_smoothed_values()

        self.log.info(f"Analysis complete. Detected {len(self.scenes)} scenes.")
        self.log.info(f"Analyzed {len(self.smooth_scene_change_vals)} frames.")

        return self.scene_frames
        
    def _extract_content_values(self, stats_manager) -> pd.DataFrame:
        '''
        Extract content_val data from the stats manager. Returns
        a dataframe with those raw, unsmoothed content_val scene 
        change numbers, with their frame number and timecodes.
        Dataframe columns:

            content_val, frame_number, timecode
               float        int          str

        The returned values need smoothing to be useful. They are
        the input to a scene_change_detector instance.

        :param stats_manager: scene detection statistics manager after 
            detect_scenes() was called on its enclosing scene_manager.
        :raises ValueError: if stats_manager does not contain data
        :return: places where frame content change is noteworthy
        :rtype: pd.DataFrame
        '''
    
        # Get the stats from the detector
        metrics = stats_manager._frame_metrics
        
        if not metrics:
            raise ValueError("No metrics data available. Run analyze() first.")
        
        # Extract content values, frame numbers, and timecodes
        content_vals = []
        frame_numbers = []
        timecodes = []
        
        for frame_num in sorted(metrics.keys()):
            if 'content_val' in metrics[frame_num]:
                content_vals.append(metrics[frame_num]['content_val'])
                frame_numbers.append(frame_num)
                # Convert frame to timecode (assuming we can get framerate)
                fps = self.video_stream.frame_rate
                timecodes.append(frame_num / fps)

        scene_change_vals_raw = pd.DataFrame(
            {
                'content_val': content_vals,
                'frame_number': frame_numbers,
                'timecode': timecodes
            }
        )
        return scene_change_vals_raw

    
    def get_statistics(self, frame_content_data: pd.DataFrame) -> dict:
        """
        Compute statistics on content values.

        Returns:
            Dictionary containing mean, median, std, min, max
        """
        if frame_content_data is None or len(frame_content_data) == 0:
            raise ValueError("No content values available. Run analyze() first.")
        
        vals = np.array(frame_content_data['content_val'])
        
        stats = {
            'mean': np.mean(vals),
            'median': np.median(vals),
            'std': np.std(vals),
            'min': np.min(vals),
            'max': np.max(vals),
            'count': len(vals)
        }
        
        return stats
    
    def print_statistics(self, frame_content_data: pd.DataFrame) -> None:
        """Print statistics to console."""
        stats = self.get_statistics(frame_content_data)
        
        print("\n=== Content Value Statistics ===")
        print(f"Mean:     {stats['mean']:.2f}")
        print(f"Median:   {stats['median']:.2f}")
        print(f"Std Dev:  {stats['std']:.2f}")
        print(f"Min:      {stats['min']:.2f}")
        print(f"Max:      {stats['max']:.2f}")
        print(f"Frames:   {stats['count']}")
        print(f"Scenes:   {len(self.scenes)}")
    
    def plot_timeseries(
            self, 
            timeseries_data: List[pd.DataFrame] | pd.DataFrame,
            labels: Optional[List[str]] = None,
            interactive: bool = True
        ) -> Figure:
        """
        Create and display content values over time.
        
        Args:
            timeseries_data: the one or more series to plot
            labels: optional labels for color legend
            interactive: If True, enable interactive thumbnail preview
            save_path: Optional path to save the figure
        """
        
        if type(timeseries_data) != list:
            timeseries_data = [timeseries_data]

        if type(labels) != list:
            labels = [labels]            

        # Handle case where labels are not provided
        if labels is None:
            labels = [f"FrameDiffs {i+1}" for i in range(len(timeseries_data))]        

        # Check if lists match length (Optional safety check)
        if len(timeseries_data) != len(labels):
            raise ValueError(f"{len(timeseries_data)} DataFrames but {len(labels)} labels provided.")

        fig, ax = plt.subplots(figsize=(14, 6))

        for timeseries, label in zip(timeseries_data, labels):
            # Plot content values
            ax.plot(
                timeseries['timecode'], 
                timeseries['content_val'],
                linewidth=1, 
                alpha=0.8,
                label=label
                )
        
        # Mark detected scenes
        for idx, scene in self.scenes.iterrows():
            scene_time = scene['timecode']
            ax.axvline(scene_time, color='r', alpha=0.3, linewidth=1, linestyle='--')
        
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Content Change Score')
        # Generate a title based on the labels provided or generic text
        subtitle_text = ", ".join(labels) if labels and len(labels) < 4 else "Multiple Series"
        ax.set_title(f'Content Change: {subtitle_text}\n{self.video_path.name} '
                     f'({len(self.scenes)} scenes detected)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if interactive:
            self._add_interactive_preview(fig, ax)
        # Show all plots at the end in main()
        #plt.show()
        return fig
    
    def _add_interactive_preview(self, fig, ax) -> None:
        """
        Add interactive movie frame thumbnail preview to the plot.
        
        Args:
            fig: Matplotlib figure
            ax: Matplotlib axis
        """
        # Create thumbnail display axis
        thumb_ax = fig.add_axes([0.72, 0.65, 0.25, 0.25])
        thumb_ax.axis('off')
        thumb_image = thumb_ax.imshow(np.zeros((100, 100, 3), dtype=np.uint8))
        
        # Open video for frame extraction
        cap = cv2.VideoCapture(str(self.video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        def on_mouse_move(event: MouseEvent) -> None:
            """Handle mouse movement to show thumbnail."""
            if event.inaxes != ax or event.xdata is None:
                return
            
            # Get time from mouse position
            time_sec = event.xdata
            frame_num = int(time_sec * fps)
            
            # Extract frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Resize for display
                h, w = frame_rgb.shape[:2]
                max_dim = 300
                if w > h:
                    new_w = max_dim
                    new_h = int(h * max_dim / w)
                else:
                    new_h = max_dim
                    new_w = int(w * max_dim / h)
                
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
                
                # Update thumbnail
                thumb_image.set_data(frame_resized)
                thumb_ax.set_title(f'Frame {frame_num}\nTime: {time_sec:.2f}s', 
                                 fontsize=9)
                fig.canvas.draw_idle()
        
        # Add cursor
        cursor = Cursor(ax, useblit=True, color='red', linewidth=1)
        
        # Connect mouse motion event
        fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)
        
        print("\n=== Interactive Mode ===")
        print("Move your mouse over the plot to see video thumbnails!")
        print("The red vertical lines indicate detected scene boundaries.")
    
    def save_stats_csv(self, output_path: str) -> None:
        """
        Save statistics to CSV file (similar to scenedetect CLI output).
        
        Args:
            output_path: Path for the output CSV file
        """
        if not self.raw_scene_change_vals:
            raise ValueError("No content values available. Run analyze() first.")

        self.raw_scene_change_vals.to_csv(output_path)       
        self.log.info(f"Stats saved to: {output_path}")

    def save_fig_and_data(self, fig_path, fig, **kwargs):
        '''
        Given a matplotlib figure, and associated data, save the figure
        as png, or other format, and save the data as .csv. The fig_path
        is the directory plus figure file. The extension determines the
        output format.
        Example:
             '/tmp/myMovieStatsTimes.png'

        The kwargs may provide any number of data arrays. Each
        kwarg key will be a column header. Corresponding value arrays
        will be columns. It is an error for the value arrays to have
        unequal lengths. Example for a **kwargs dict:
              {
                'content_val': [1,2,3],
                'timecode'   : [100,200,300]
              }

        The data will be saved in fig_path[without-ext].csv. In this example:
            /tmp/myMovieStatsStatsTimes.csv

        If fig_path or derived data destinations exist, they are overwritten\
        without warning.

        Directory will be created if needed.

        :param fig_path: path to figure save file
        :type fig_path: {str | Path}
        :param fig: Figure to save
        :type fig: Figure
        '''
        fig_path = Path(fig_path)
        dst_dir = Path(fig_path).parent 
        Path.mkdir(dst_dir, parents=True, exist_ok=True)

        # Save the plot
        fig.savefig(fig_path, dpi=150)

        # Save the data, if provided:
        if len(kwargs) > 0:
            data_path = fig_path.with_suffix('.csv')
            with open(data_path, 'w', newline='') as fd:
                writer = csv.writer(fd)
                writer.writerow(list(kwargs.keys()))
                writer.writerows(zip(*kwargs.values()))

def main():
    """Main entry point for the script."""

    #**************
    #sys.argv.extend(['--save-timeseries', '/home/paepcke/tmp/movies/multipleScenesTimes.png'])
    #sys.argv.extend(['--save-timeseries', '/home/paepcke/tmp/movies/moviePassingTruck.png'])
    sys.argv.extend(['--save-timeseries', '/home/paepcke/tmp/movies/drummers.png'])
    
    #sys.argv.append('/home/paepcke/tmp/movies/movieMultipleScenes.mp4')
    #sys.argv.append('/home/paepcke/tmp/movies/moviePassingTruck.mp4')
    sys.argv.append('/home/paepcke/Videos/drummers_IMG_7944.MOV')
    #**************

    log = LoggingService()

    parser = argparse.ArgumentParser(
        description='Analyze scene detection content values in video files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s movie.mp4
  %(prog)s movie.mp4 --scenecount 10
  %(prog)s movie.mp4 --threshold 30.0 --output stats.csv
        """
    )
    
    parser.add_argument('video', 
                        type=str, 
                        help='Path to video file')
    parser.add_argument('-c', '--scenecount',
                        default=None,
                        help='Limit on number of scenes; default: will find a reasonable number')
    parser.add_argument('-o', '--output', 
                        type=str,
                        help='Save statistics to CSV file')
    parser.add_argument('--no-visuals', 
                        action='store_true',
                        help='Disable time series charts and visual progress bars')
    parser.add_argument('--save-timeseries', 
                        type=str,
                        help='File where to save time series plots')
    
    args = parser.parse_args()

    legal_img_extensions = ['.png', '.jpg', '.jpeg', '.tiff', 'tif',
                            'bmp', 'rgba', 
                            '.pdf', '.ps', '.eps', '.svg', '.svgz',
                            '.pgf'
                            '.raw'
                            ]

    # Defaults is to show charts and progress bars:
    visuals   = not args.no_visuals
    save_path = args.save_timeseries

    if visuals \
        and save_path \
        and not Path(save_path).suffix in legal_img_extensions:
        print(f"Only these image extensions are supported: {legal_img_extensions}")
        sys.exit(1)

    try:
        # Create analyzer
        analyzer = MovieAnalyzer(args.video, scenecount_max=args.scenecount, visuals=visuals)
        analyzer.analyze()
        
        # Print statistics
        if analyzer.visuals:
            analyzer.print_statistics(analyzer.raw_scene_change_vals)
            analyzer.print_statistics(analyzer.smooth_scene_change_vals)
        
        # Save stats if requested
        if args.output:
            analyzer.save_stats_csv(args.output)
        
        if analyzer.visuals:
            # Create visualizations
            log.info("\nGenerating visualizations...")
            
            # Time series with optional interactive preview
            fig: plt.Figure = analyzer.plot_timeseries(
                    [analyzer.raw_scene_change_vals, 
                     analyzer.smooth_scene_change_vals
                    ],
                    labels=['raw data', 'smoothed'],
                    interactive=True
            )
            
            if save_path:
                analyzer.save_fig_and_data(
                    save_path,
                    fig, 
                    content_val_raw    = analyzer.raw_scene_change_vals['content_val'],
                    content_val_smooth = analyzer.smooth_scene_change_vals['content_val'],
                    time               = analyzer.raw_scene_change_vals['timecode'] # fractional secs
                    )
                log.info(f"Saved time value change time series to {save_path}/.csv")

            log.info("Waiting for user to close charts...")
            plt.show(block=False)
            while input("Press q to quit...") not in ['q', 'Q']:
                continue

    except Exception as e:
        log.err(f"Error: {e}")
        sys.exit(1)

    log.info("done.")


if __name__ == '__main__':
    main()

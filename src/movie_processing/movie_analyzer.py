#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 12:55:10
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-30 16:42:05

"""
MovieAnalyzer - Analyze scene detection content values in video files

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
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.widgets import Cursor
from matplotlib.backend_bases import MouseEvent

# PySceneDetect imports
from scenedetect import detect, ContentDetector, split_video_ffmpeg
from scenedetect import open_video
from scenedetect.scene_manager import SceneManager
from scenedetect.stats_manager import StatsManager

from logging_service import LoggingService

class MovieAnalyzer:
    """Analyze scene detection metrics for video files."""
    
    def __init__(self, video_path: str):
        """
        Initialize the MovieAnalyzer.
        
        Args:
            video_path: Path to the video file (.mp4, .mov, etc.)
        """
        
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        self.log = LoggingService()
        
        self.video_stream = None
        self.scene_manager = None
        self.stats_manager = None
        self.content_vals = []
        self.frame_numbers = []
        self.timecodes = []
        self.scenes = []
        
    def analyze(self, threshold: float = 27.0) -> None:
        """
        Run scene detection analysis on the video.
        
        Args:
            threshold: Content detection threshold (default: 27.0)
        """
        self.log.info(f"Analyzing video: {self.video_path}")
        
        # Initialize video stream
        self.video_stream = open_video(str(self.video_path))
        
        # Create scene manager and stats manager
        self.stats_manager = StatsManager()
        self.scene_manager = SceneManager(self.stats_manager)
        
        # Add content detector
        self.scene_manager.add_detector(ContentDetector(threshold=threshold))
        
        # Detect scenes
        self.scene_manager.detect_scenes(self.video_stream, show_progress=True)
        
        # Get detected scenes
        self.scenes = self.scene_manager.get_scene_list()
        
        # Extract content values from stats
        self._extract_content_values()
        
        self.log.info(f"Analysis complete. Detected {len(self.scenes)} scenes.")
        self.log.info(f"Analyzed {len(self.content_vals)} frames.")
        
    def _extract_content_values(self) -> None:
        """Extract content_val data from the stats manager."""
        # Get the stats from the detector
        metrics = self.stats_manager._frame_metrics
        
        if not metrics:
            raise ValueError("No metrics data available. Run analyze() first.")
        
        # Extract content values, frame numbers, and timecodes
        self.content_vals = []
        self.frame_numbers = []
        self.timecodes = []
        
        for frame_num in sorted(metrics.keys()):
            if 'content_val' in metrics[frame_num]:
                self.content_vals.append(metrics[frame_num]['content_val'])
                self.frame_numbers.append(frame_num)
                # Convert frame to timecode (assuming we can get framerate)
                fps = self.video_stream.frame_rate
                self.timecodes.append(frame_num / fps)
    
    def get_statistics(self) -> dict:
        """
        Compute statistics on content values.
        
        Returns:
            Dictionary containing mean, median, std, min, max
        """
        if not self.content_vals:
            raise ValueError("No content values available. Run analyze() first.")
        
        vals = np.array(self.content_vals)
        
        stats = {
            'mean': np.mean(vals),
            'median': np.median(vals),
            'std': np.std(vals),
            'min': np.min(vals),
            'max': np.max(vals),
            'count': len(vals)
        }
        
        return stats
    
    def print_statistics(self) -> None:
        """Print statistics to console."""
        stats = self.get_statistics()
        
        print("\n=== Content Value Statistics ===")
        print(f"Mean:     {stats['mean']:.2f}")
        print(f"Median:   {stats['median']:.2f}")
        print(f"Std Dev:  {stats['std']:.2f}")
        print(f"Min:      {stats['min']:.2f}")
        print(f"Max:      {stats['max']:.2f}")
        print(f"Frames:   {stats['count']}")
        print(f"Scenes:   {len(self.scenes)}")
    
    def compute_threshold_for_scene_count(self, target_scene_count: int) -> float:
        """
        Compute the threshold that would produce the target scene count.
        
        This uses binary search to find the appropriate threshold.
        
        Args:
            target_scene_count: Desired number of scenes
            
        Returns:
            Threshold value that produces approximately the target scene count
        """
        if not self.content_vals:
            raise ValueError("No content values available. Run analyze() first.")
        
        self.log.info(f"\nSearching for threshold to produce {target_scene_count} scenes...")
        
        # Binary search for the right threshold
        low, high = 0.0, 100.0
        best_threshold = 27.0
        best_diff = float('inf')
        
        for _ in range(20):  # Max iterations
            mid = (low + high) / 2
            
            # Test this threshold
            test_video = open_video(str(self.video_path))
            test_manager = SceneManager()
            test_manager.add_detector(ContentDetector(threshold=mid))
            test_manager.detect_scenes(test_video, show_progress=False)
            scene_count = len(test_manager.get_scene_list())
            
            diff = abs(scene_count - target_scene_count)
            
            if diff < best_diff:
                best_diff = diff
                best_threshold = mid
            
            self.log.info(f"  Threshold {mid:.2f} -> {scene_count} scenes (target: {target_scene_count})")
            
            if scene_count < target_scene_count:
                high = mid
            elif scene_count > target_scene_count:
                low = mid
            else:
                best_threshold = mid
                break
        
        self.log.info(f"\nBest threshold: {best_threshold:.2f} (produces {scene_count} scenes)")
        return best_threshold
    
    def plot_histogram(self, bins: int = 50, save_path: Optional[str] = None) -> None:
        """
        Create and display a histogram of content values.
        
        Args:
            bins: Number of histogram bins
            save_path: Optional path to save the figure
        """
        if not self.content_vals:
            raise ValueError("No content values available. Run analyze() first.")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(self.content_vals, bins=bins, edgecolor='black', alpha=0.7)
        ax.axvline(np.mean(self.content_vals), color='r', linestyle='--', 
                   label=f'Mean: {np.mean(self.content_vals):.2f}')
        ax.axvline(np.median(self.content_vals), color='g', linestyle='--',
                   label=f'Median: {np.median(self.content_vals):.2f}')
        
        ax.set_xlabel('Content Value')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Content Value Distribution\n{self.video_path.name}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            self.save_fig_and_data(save_path, plt)
            self.log.info(f"Histogram saved to: {save_path}")
        
        # Show all plots at the end, in main()
        # plt.show()
    
    def plot_timeseries(self, interactive: bool = True, 
                       save_path: Optional[str] = None) -> None:
        """
        Create and display content values over time.
        
        Args:
            interactive: If True, enable interactive thumbnail preview
            save_path: Optional path to save the figure
        """
        if not self.content_vals:
            raise ValueError("No content values available. Run analyze() first.")
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Plot content values
        ax.plot(self.timecodes, self.content_vals, linewidth=0.8, alpha=0.7)
        
        # Mark detected scenes
        for scene in self.scenes:
            scene_time = scene[0].get_seconds()
            ax.axvline(scene_time, color='r', alpha=0.3, linewidth=1)
        
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Content Value')
        ax.set_title(f'Content Value Over Time\n{self.video_path.name} '
                    f'({len(self.scenes)} scenes detected)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            self.save_fig_and_data(
                save_path, 
                plt, 
                content_val= self.content_vals,
                time= self.timecodes # secs
                )
            self.log.info(f"Saved time value change time series to {save_path}/.csv")
        
        if interactive:
            self._add_interactive_preview(fig, ax)
        
        # Show all plots at the end in main()
        #plt.show()
    
    def _add_interactive_preview(self, fig, ax) -> None:
        """
        Add interactive thumbnail preview to the plot.
        
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
        if not self.content_vals:
            raise ValueError("No content values available. Run analyze() first.")
        
        import csv
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Frame Number', 'Timecode', 'Content Val'])
            
            for frame, time, val in zip(self.frame_numbers, self.timecodes, 
                                       self.content_vals):
                writer.writerow([frame, f'{time:.3f}', f'{val:.4f}'])
        
        self.log.info(f"Stats saved to: {output_path}")

    def save_fig_and_data(self, fig_path, plt, **kwargs):
        '''
        Given a matplotlib figure, and associated data, save the figure
        as png, or other format, and save the data as .csv. The fig_path
        is the directory plus figure file. The extension determines the
        output format.
        Example:
             '/tmp/myMovieStatsTimes.png'
        the kwargs may provide any number of data arrays. The each
        kwarg key will be a column header. Corresponding value arrays
        will be columns. It is an error for the value arrays to have
        unequal lengths.

        The data will be saved in fig_path[without-ext].csv. In this example:
            /tmp/myMovieStatsStatsTimes.csv

        If fig_path or derived data destinations exist, they are overwritten\
        without warning.

        Directory will be created if needed.

        :param fig_path: path to figure save file
        :type fig_path: {str | Path}
        :param plt: matplotlib figure
        :type plt: Figure
        '''
        fig_path = Path(fig_path)
        dst_dir = Path(fig_path).parent 
        Path.mkdir(dst_dir, parents=True, exist_ok=True)

        # Save the plot
        plt.savefig(fig_path, dpi=150)

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
    sys.argv.extend(['--save-timeseries', '/home/paepcke/tmp/movies/multipleScenesTimes.png'])
    sys.argv.append('/home/paepcke/tmp/movies/movieMultipleScenes.mp4')
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
                        help='Target number of scenes (will compute optimal threshold)')
    parser.add_argument('-t', '--threshold', 
                        type=float, default=27.0,
                        help='Content detection threshold (default: 27.0)')
    parser.add_argument('-o', '--output', 
                        type=str,
                        help='Save statistics to CSV file')
    parser.add_argument('--hist-bins', 
                        type=int, 
                        default=50,
                        help='Number of bins for histogram (default: 50)')
    parser.add_argument('--no-interactive', 
                        action='store_true',
                        help='Disable interactive thumbnail preview')
    parser.add_argument('--save-histogram', 
                        type=str,
                        help='Save histogram to file')
    parser.add_argument('--save-timeseries', 
                        type=str,
                        help='Save time series plot to file')
    
    args = parser.parse_args()

    legal_img_extensions = ['.png', '.jpg', '.jpeg', '.tiff', 'tif',
                            'bmp', 'rgba', 
                            '.pdf', '.ps', '.eps', '.svg', '.svgz',
                            '.pgf'
                            '.raw'
                            ]
    if args.save_histogram and not Path(args.save_histogram).suffix in legal_img_extensions:
        print(f"Only these image extensions are supported: {legal_img_extensions}")
        sys.exit(1)

    if args.save_timeseries and not Path(args.save_timeseries).suffix in legal_img_extensions:
        print(f"Only these image extensions are supported: {legal_img_extensions}")
        sys.exit(1)
    
    try:
        # Create analyzer
        analyzer = MovieAnalyzer(args.video)
        
        # Run analysis
        if args.scenecount:
            # Find optimal threshold for target scene count
            optimal_threshold = analyzer.compute_threshold_for_scene_count(
                args.scenecount
            )
            # Re-analyze with optimal threshold
            analyzer.analyze(threshold=optimal_threshold)
        else:
            analyzer.analyze(threshold=args.threshold)
        
        # Print statistics
        analyzer.print_statistics()
        
        # Save stats if requested
        if args.output:
            analyzer.save_stats_csv(args.output)
        
        # Create visualizations
        log.info("\nGenerating visualizations...")
        
        # Histogram
        analyzer.plot_histogram(bins=args.hist_bins, 
                               save_path=args.save_histogram)
        
        # Time series with optional interactive preview
        analyzer.plot_timeseries(interactive=not args.no_interactive,
                                save_path=args.save_timeseries)
        
    except Exception as e:
        log.err(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    log.info("Waiting for user to close charts...")
    plt.show(block=True)
    log.info("All charts closed---done.")


if __name__ == '__main__':
    main()

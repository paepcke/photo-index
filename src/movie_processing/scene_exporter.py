#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-30 10:06:48
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-30 11:40:21

import argparse
import sys
import json
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.scene_manager import save_images
import cv2

from logging_service import LoggingService

class MovieSceneExporter:
    # --- Class Constants ---
    SUPPORTED_EXTENSIONS = {
        '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv', '.flv', '.ts'
    }
    DEFAULT_THRESHOLD = 27.0
    DEFAULT_IMAGE_FORMAT = 'jpeg'
    
    def __init__(self, 
                 root_dir, 
                 out_dir=None, 
                 prefix="", 
                 max_size_mb=None, 
                 max_time_min=None, 
                 threshold=None):
        self.root_dir = Path(root_dir)
        self.out_dir = Path(out_dir) if out_dir else None
        self.prefix = prefix
        self.max_size_mb = max_size_mb
        self.max_time_min = max_time_min
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

        self.log = LoggingService()

    def get_detailed_stats(self, file_path):
        """
        Uses ffprobe to extract detailed JSON metadata about the video file.
        Returns a dictionary of cleaned stats or None on failure.
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,codec_name,r_frame_rate',
                '-show_entries', 'format=size,duration',
                '-of', 'json',
                str(file_path)
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            
            # Extract Format info
            fmt = data.get('format', {})
            stream = data.get('streams', [{}])[0]
            
            # Calculate size in MB
            size_bytes = float(fmt.get('size', 0))
            size_mb = size_bytes / (1024 * 1024)
            
            # Calculate Duration
            duration_sec = float(fmt.get('duration', 0))
            
            # Calculate FPS (evaluates strings like "30000/1001")
            fps_str = stream.get('r_frame_rate', '0/0')
            if '/' in fps_str:
                num, den = map(float, fps_str.split('/'))
                fps = num / den if den > 0 else 0
            else:
                fps = float(fps_str)

            return {
                'filename': file_path.name,
                'resolution': f"{stream.get('width')}x{stream.get('height')}",
                'codec': stream.get('codec_name', 'unknown'),
                'fps': round(fps, 2),
                'duration_sec': duration_sec,
                'duration_str': f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}",
                'size_mb': round(size_mb, 2)
            }
        except Exception as e:
            self.log.err(f"Error reading stats for {file_path.name}: {e}")
            return None

    def print_stats(self, target_files):
        """Prints a formatted table of stats for the provided files."""
        if not target_files:
            self.log.info("No video files found to analyze.")
            return

        # Header
        print(f"{'FILENAME':<40} | {'RES':<10} | {'CODEC':<8} | {'FPS':<6} | {'TIME':<7} | {'SIZE (MB)':<10}")
        print("-" * 95)

        for f in target_files:
            path = Path(f)
            if not path.exists():
                self.log.warn(f"File not found: {path}")
                continue
                
            stats = self.get_detailed_stats(path)
            if stats:
                print(f"{stats['filename']:<40} | {stats['resolution']:<10} | "
                      f"{stats['codec']:<8} | {stats['fps']:<6} | "
                      f"{stats['duration_str']:<7} | {stats['size_mb']:<10}")
            else:
                print(f"{path.name:<40} | [Error reading metadata]")

    def get_video_duration(self, file_path):
        """Lightweight duration check for filtering logic."""
        stats = self.get_detailed_stats(file_path)
        return stats['duration_sec'] if stats else None

    def find_videos(self):
        """Recursively finds all supported videos in root_dir."""
        if not self.root_dir.exists():
            self.log.err(f"Root directory does not exist: {self.root_dir}")
            return []
            
        return [p for p in self.root_dir.rglob('*') 
                if p.suffix.lower() in self.SUPPORTED_EXTENSIONS]

    def should_skip(self, file_path):
        # 1. Size Check
        if self.max_size_mb:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_size_mb:
                self.log.warn(f"Skipping {file_path.name}: Size {size_mb:.2f}MB > limit {self.max_size_mb}MB")
                return True

        # 2. Duration Check
        if self.max_time_min:
            duration_sec = self.get_video_duration(file_path)
            if duration_sec is None:
                return True 
            
            duration_min = duration_sec / 60
            if duration_min > self.max_time_min:
                self.log.warn(f"Skipping {file_path.name}: Duration {duration_min:.2f}min > limit {self.max_time_min}min")
                return True
                
        return False

    def process_video(self, file_path):
            if self.should_skip(file_path):
                return

            # Determine output folder
            folder_name = f"{file_path.stem}_scenes"
            target_dir = (self.out_dir / folder_name) if self.out_dir else (file_path.parent / folder_name)
            target_dir.mkdir(parents=True, exist_ok=True)

            self.log.info(f"Processing: {file_path.name}")

            try:
                # API: Open Video
                video = open_video(str(file_path))
                
                # API: Setup Manager & Detector
                scene_manager = SceneManager()
                scene_manager.add_detector(ContentDetector(threshold=self.threshold))
                
                # API: Detect
                scene_manager.detect_scenes(video, show_progress=True)
                scene_list = scene_manager.get_scene_list()
                
                # --- CASE 1: Scenes Found ---
                if scene_list:
                    self.log.info(f"  Found {len(scene_list)} scenes. Saving images...")
                    name_template = f"{self.prefix}$VIDEO_NAME-Scene-$SCENE_NUMBER-$IMAGE_NUMBER"
                    
                    save_images(
                        scene_list=scene_list,
                        video=video,
                        output_dir=str(target_dir),
                        image_name_template=name_template,
                        image_extension=self.DEFAULT_IMAGE_FORMAT
                    )

                # --- CASE 2: No Scenes Found (Fallback) ---
                else:
                    self.log.info("  No scene changes detected. Extracting middle frame as fallback...")
                    
                    # Handle duration types (int vs FrameTimecode)
                    if hasattr(video.duration, 'get_frames'):
                        total_frames = video.duration.get_frames()
                    else:
                        total_frames = int(video.duration)

                    mid_frame = total_frames // 2
                    
                    # Seek and Read using the open video object
                    video.seek(mid_frame)
                    frame_im = video.read()
                    
                    if frame_im is not None:
                        out_name = f"{self.prefix}{file_path.stem}_midframe.{self.DEFAULT_IMAGE_FORMAT}"
                        out_path = target_dir / out_name
                        
                        cv2.imwrite(str(out_path), frame_im)
                        self.log.info(f"  Saved fallback image: {out_name}")
                    else:
                        self.log.err("  Could not read middle frame.")

            except Exception as e:
                self.log.err(f"Failed to process {file_path.name}: {e}")

    def run_extraction(self):
        videos = self.find_videos()
        self.log.info(f"Found {len(videos)} videos in {self.root_dir}")
        for vid in videos:
            self.process_video(vid)


# --- CLI Handling ---

def parse_arguments():
    parser = argparse.ArgumentParser(description="Movie Scene Exporter & Analyzer")
    
    # Positional: Root (still required to initialize the class, even if using -s specific files)
    parser.add_argument('root', 
                        help="Root directory to search for movie files")
    
    # Options
    parser.add_argument('-o', '--outdir', 
                        default=None, 
                        help="Central output directory for extracted images.")
    parser.add_argument('--prefix', default="", 
                        help="Filename prefix for images.")
    
    # Limits
    parser.add_argument('--max-size', 
                        dest='max_size_mb', 
                        type=float, 
                        default=None, 
                        help="Skip processing files larger than X MB")
    parser.add_argument('--max-time', 
                        dest='max_time_min', 
                        type=float, 
                        default=None, 
                        help="Skip processing files longer than X minutes")
    
    # Tuning
    parser.add_argument('--threshold', 
                        type=float, 
                        default=MovieSceneExporter.DEFAULT_THRESHOLD, 
                        help=(f"Scene change decision intensity threshold " 
                              f"(default: {MovieSceneExporter.DEFAULT_THRESHOLD})"))

    # New: Show Stats Mode
    # nargs='*' means: "gather 0 or more arguments into a list"
    parser.add_argument('-s', '--show', 
                        nargs='*', 
                        default=None,
                        help=("Show stats for provided files. If no files, " 
                              "shows stats for all videos in directory. No processing done."))

    return parser.parse_args()

def main():

    #*************
    sys.argv.append('/home/paepcke/tmp/movies')
    #*************
    args = parse_arguments()

    if not Path.exists(Path(args.root)):
        print(f"Search root directory {args.root} does not exist; aborting")
        sys.exit(1)
        
    exporter = MovieSceneExporter(
        root_dir=args.root,
        out_dir=args.outdir,
        prefix=args.prefix,
        max_size_mb=args.max_size_mb,
        max_time_min=args.max_time_min,
        threshold=args.threshold
    )
    
    # Check if we are in "Show Stats" mode
    # args.show will be None if the flag wasn't used.
    # args.show will be [] if flag used but no args (e.g., -s)
    # args.show will be ['file1', 'file2'] if flag used with args.
    if args.show is not None:
        if len(args.show) > 0:
            # User provided specific files
            files_to_check = args.show
        else:
            # User provided -s but no files; check the whole root dir
            files_to_check = exporter.find_videos()
            
        exporter.print_stats(files_to_check)
        sys.exit(0) # Exit without extracting scenes

    # Otherwise, run normal extraction
    exporter.run_extraction()

if __name__ == "__main__":
    main()
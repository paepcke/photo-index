# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-04 09:51:40
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-06 15:04:52

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List
from common.video_utils import VideoUtils
from movie_processing.scene_change_detector import SceneChangeDetector
from movie_processing.movie_analyzer import MovieAnalyzer

import ffmpeg

class SceneDetectionTester:
    short_movie  = Path('~/tmp/movies/drummer_IMG_7944.MOV').expanduser()
    medium_movie = Path('~/tmp/movies/fiddler_IMG_5209.MOV').expanduser()
    long_movie   = Path('~/tmp/movies/wedding_IMG_7149.MOV').expanduser()

    def __init__(self):

        movie_dir = None
        try:
            #movie = self.medium_movie
            movie = self.long_movie
            #******
            #movie_dir = TemporaryDirectory(dir='/tmp', prefix='scene_detect_trials_')
            #mp4_movie_file = self.create_tst_movie(movie_dir.name)[0]
            #analyzer = MovieAnalyzer(movie, scenecount_max=None)
            analyzer = MovieAnalyzer(movie, scenecount_max_absolute=None)
            #analyzer = MovieAnalyzer(mp4_movie_file, scenecount_max=None)
            #******
            scenes_df = analyzer.analyze()
            # Save the frame images:
            fname_root = None
            if movie == self.short_movie:
                fname_root = 'drummers_'
            elif movie == self.medium_movie:
                fname_root = 'fiddler_'
            elif movie == self.long_movie:
                fname_root = 'wedding_'
            for i, img in enumerate(scenes_df['scene_frame']):
                if fname_root is not None:
                    fname = str(Path(f'~/tmp/{fname_root}_{i}.jpg').expanduser())
                    VideoUtils.frame_to_jpeg(img, fname)
                    print(f"One frame candidate to {fname}")
                VideoUtils.show_frame(img)
            while input("Type 'q' to quit...") != 'q':
                continue
        finally:
            if movie_dir is not None:
                movie_dir.cleanup()

    # -------------- Utilities ---------------
    def create_tst_movie(self, 
                         dest_dir: str, 
                         secs: int = 2, 
                         formats: List[str] | str = '.mp4'
                         ) -> List[str]:
        '''
        Create one or two short test videos. The
        types may be individual strings: '.mp4' or '.mov',
        or a list of the two.

        :parm dest_dirdir: directory where the files will be stored
        :param secs: duration in seconds, defaults to 2
        :param formats: format(s) of movies to generate defaults to '.mp4'
        '''
        if type(formats) == str:
            formats = [formats]

        movie_fnames = []
        for movie_format in formats:
            if movie_format == '.mp4':
                # Create an mp4 clip:
                mp4_filename = str(Path(dest_dir) / 'mp4_test_movie.mp4')

                # Video input
                video = ffmpeg.input(f'testsrc=duration={secs}:size=1280x720:rate=30', f='lavfi')
                # Audio input
                audio = ffmpeg.input(f'sine=frequency=1000:duration={secs}', f='lavfi')        

                (ffmpeg
                .output(video, audio, mp4_filename, pix_fmt='yuv420p')
                .overwrite_output()
                .run()
                )
                movie_fnames.append(mp4_filename)

            elif movie_format == '.mov':
                # And a Quicktime movie:
                qt_filename = str(Path(dest_dir) / 'qt_test_movie.mp4')

                (ffmpeg
                    .input(f'testsrc=duration={secs}:size=1280x720:rate=30', f='lavfi')
                    .output(qt_filename, pix_fmt='yuv420p')
                    .overwrite_output()
                    .run()
                )
                movie_fnames.append(qt_filename)
            else:
                raise TypeError(f"Movie formats can only be '.mp4' or '.mov', not {movie_format}")
        
        return movie_fnames
        
def main():
    SceneDetectionTester()        

if __name__ == "__main__":
    main()

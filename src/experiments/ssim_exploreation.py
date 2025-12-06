# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-06 11:11:45
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-06 15:07:29

import math
from pathlib import Path
from typing import List
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from skimage.transform import resize

from common.video_utils import VideoUtils

class SSIMExplorer:

    fnames_drummer = [
        '/tmp/drummers_initial.jpg',
        '/tmp/peds1_blue_hair.jpg',
        '/tmp/ped2_purple_shirt.jpg',
        '/tmp/ped3_close_woman.jpg',
        '/tmp/ped4_black_guy.jpg',
        '/tmp/drummers_closeup.jpg'
        ]
    fnames_fiddler = [
        str(Path('~/tmp/fiddler__0.jpg').expanduser()),
        str(Path('~/tmp/fiddler__1.jpg').expanduser()),
        str(Path('~/tmp/fiddler__2.jpg').expanduser()),
        str(Path('~/tmp/fiddler__3.jpg').expanduser()),
        str(Path('~/tmp/fiddler__4.jpg').expanduser()),
        str(Path('~/tmp/fiddler__5.jpg').expanduser()),
        str(Path('~/tmp/fiddler__6.jpg').expanduser())
        ]
    
    fnames_wedding = [
        str(Path('~/tmp/wedding__0.jpg').expanduser())
    ]
    
    def __init__(self, fname_list):
        self.fname_list = fname_list
        self.frames = [VideoUtils.read_img(fname) for fname in fname_list]
        self.win_sizes = self.get_win_sizes(6)
        self.reference_name = Path(fname_list[0]).stem

    def get_win_sizes(self, num_win_sizes=6):
        start_num = 7
        max_value = 1080
        start_num = 7
        diff_range = max_value - start_num
        num_gaps = num_win_sizes - 1
        d_max_float = diff_range / num_gaps
        common_difference = math.floor(d_max_float)
        if common_difference % 2 != 0:
            common_difference -= 1
        odd_win_sizes = [start_num + i * common_difference for i in range(num_win_sizes)]
        return odd_win_sizes

    def composite_similarity(self, 
                             candidate_img: np.ndarray, 
                             reference_img: np.ndarray,
                             historgram_weight = 0.5,
                             win_size=1077,
                             ret_all=False
                             ) -> float | dict[str, float]:
        ssim_score = ssim(reference_img,
                          candidate_img, 
                          channel_axis=2, 
                          win_size=win_size, 
                          data_range=255)
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

    def analyze_composite_sim(self, win_size=1077):
        for hist_weight in [0.1, 0.2, 0.3, 0.4, 0.5]:
            for i, frame in enumerate(self.frames[1:]):
                other_name = Path(self.fname_list[i+1]).stem
                print(f"hist_weight: {hist_weight} {other_name} against {self.reference_name}: ", end='')
                similarity = self.composite_similarity(frame, 
                                                       self.frames[0],
                                                       historgram_weight=hist_weight,
                                                       win_size=win_size
                                                       )
                print(similarity)

    def analyze_win_sizes(self, win_sizes):
        for win_size in win_sizes:
            for i, frame in enumerate(self.frames[1:]):
                other_name = Path(self.fname_list[i+1]).stem
                print(f"win: {win_size} {other_name} against {self.reference_name}: ", end='')
                similarity = ssim(
                    frame,
                    self.frames[0],
                    win_size=win_size,
                    channel_axis=2,
                    data_range=255
                )
                print(similarity)

def main():
    sim_explorer = SSIMExplorer(SSIMExplorer.fnames_drummer)
    sim_explorer.analyze_win_sizes(sim_explorer.win_sizes)
    sim_explorer.analyze_composite_sim(win_size=7)

    # Fiddler:
    sim_explorer = SSIMExplorer(SSIMExplorer.fnames_fiddler)
    sim_explorer.analyze_win_sizes(sim_explorer.win_sizes)
    sim_explorer.analyze_composite_sim(win_size=7)

if __name__ == "__main__":
    main()

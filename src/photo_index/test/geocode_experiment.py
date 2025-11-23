# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-21 16:33:01
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-22 13:10:27
from photo_index.geocoding import Geocoder


# ------------------------ Main ------------
if __name__ == '__main__':
    gcoder = Geocoder()
    khe_pyramid = (49.00922, 8.40394)
    addr = gcoder.get_location(*khe_pyramid)
    print(addr)
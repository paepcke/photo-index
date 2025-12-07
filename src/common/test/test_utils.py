# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-07 10:01:57
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-07 10:51:12


import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from common.utils import FileNamer


class UtilsTester(unittest.TestCase):

# --------------------- Tests ------------------

    def test_file_namer_mkdir(self):
        with TemporaryDirectory(dir='/tmp', prefix='file_namer_') as root:
            fnamer = FileNamer(root)
            new_dir_path = fnamer.mkdir('subdir1', cd=False)
            self.assertTrue(Path.exists(new_dir_path))
            self.assertTrue(os.path.exists(f"{root}/subdir1"))

            # Create a name conflict:
            new_dir_path = fnamer.mkdir('subdir1', cd=False)
            self.assertTrue(Path.exists(new_dir_path))
            self.assertTrue(os.path.exists(f"{root}/subdir1_1"))

    def test_file_namer_mkfile_nm(self):
        with TemporaryDirectory(dir='/tmp', prefix='file_namer_') as root:
            fnamer = FileNamer(root)
            full_path = fnamer.mkfile_nm('my_file.txt')
            Path.touch(full_path)
            self.assertTrue(Path.exists(full_path))
            self.assertTrue(os.path.exists(f"{root}/my_file.txt"))

            # Create a conflict:
            full_path1 = fnamer.mkfile_nm('my_file.txt')
            Path.touch(full_path1)
            self.assertTrue(Path.exists(full_path))
            self.assertTrue(os.path.exists(f"{root}/my_file_1.txt"))


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-02 14:48:37
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-02 17:53:57

import os
from pathlib import Path
import shutil
import unittest
from PIL import Image
from tempfile import TemporaryDirectory

from common.img_metadata_utils import ImgMDExplorer, FieldType

class MDUtilsTester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cur_dir = os.path.dirname(__file__)
        # Create self.jpg_filename and self.png_filename
        # containing test images:
        cls.create_tst_img()
        cls.tmp_dir = TemporaryDirectory(prefix='metadata_tsts', dir='/tmp')

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup() 

    def setUp(self):
        # Remove the test files from the temp dir:
        for file_path in Path(self.tmp_dir.name).iterdir():
            if file_path.is_file():  # Check if it's a file
                file_path.unlink()  # Delete the file
        # Copy fresh .jpg and .png files to the temp dir:
        shutil.copy(self.jpg_filename, self.tmp_dir.name)
        shutil.copy(self.png_filename, self.tmp_dir.name)

        # Get a metadata accessor:
        self.img_explorer = ImgMDExplorer()

    # ------------ Tests --------------

    def test_empty_jpeg_md(self):
        md = self.img_explorer.read_fields(self.jpg_filename)
        # We should have an array of one dict,
        # i.e. the fieds of self.jpg_filename:
        self.assertEqual(type(md), list)
        self.assertEqual(len(md), 1)
        fld_dict = md[0]
        # Some of the expected fields in the first
        # (and only) dict of the md array:
        #
        #    'File:FileType': 'JPEG', 
        #    'File:FileTypeExtension': 'JPG', 
        #    'File:MIMEType': 'image/jpeg',         
        self.assertEqual(type(fld_dict), dict)
        self.assertEqual(fld_dict['File:FileType'], 'JPEG')
        self.assertEqual(fld_dict['File:FileTypeExtension'], 'JPG')
        self.assertEqual(fld_dict['File:MIMEType'], 'image/jpeg')

    def test_empty_png_md(self):
        md = self.img_explorer.read_fields(self.png_filename)
        # We should have an array of one dict,
        # i.e. the fieds of self.jpg_filename:
        self.assertEqual(type(md), list)
        self.assertEqual(len(md), 1)
        fld_dict = md[0]
        # Some of the expected fields in the first
        # (and only) dict of the md array:
        #
        #    'File:FileType': 'PNG', 
        #    'File:FileTypeExtension': 'PNG', 
        #    'File:MIMEType': 'image/png',         
        self.assertEqual(type(fld_dict), dict)
        self.assertEqual(fld_dict['File:FileType'], 'PNG')
        self.assertEqual(fld_dict['File:FileTypeExtension'], 'PNG')
        self.assertEqual(fld_dict['File:MIMEType'], 'image/png')

    def test_one_fld_one_file(self):
        md = self.img_explorer.read_fields(
            self.jpg_filename,
            fld_nms='FileType',
            fld_type=FieldType.File
            )
        print(md)

    def test_bad_fld_nm(self):
        # File:FileType already specifies a group. So
        # specifying fields type EXIF is wrong
        with self.assertRaises(ValueError):
            md = self.img_explorer.read_fields(
                self.jpg_filename,
                fld_nms='File:FileType',
                fld_type=FieldType.EXIF
                )




    # ------------ Utilities --------------
    @classmethod
    def create_tst_img(cls):
        width = 100
        height = 50
        # Can be a color name or an RGB tuple, e.g., (255, 0, 0) for red
        color = "red"  

        # Create a new Image object
        # The first argument 'RGB' specifies the image mode (Red, Green, Blue)
        # The second argument is a tuple of (width, height)
        # The third argument is the background color
        try:
            # The internal representation:
            img = Image.new('RGB', (width, height), color)
            # Save as PNG
            cls.png_filename = os.path.join(cls.cur_dir,"png_image.png")
            img.save(cls.png_filename)

            # Save as JPG/JPEG
            cls.jpg_filename = os.path.join(cls.cur_dir,"jpg_image.jpg")
            # The 'quality' argument is for JPEG only (0-100, default is 75)
            img.save(cls.jpg_filename, 'jpeg', quality=95)

        except ImportError:
            print("Error: Pillow is not installed. Please run 'pip install Pillow'")
        except Exception as e:
            print(f"An error occurred: {e}")
        return (cls.png_filename, cls.jpg_filename)

# ------------------------ Main ------------
if __name__ == '__main__':
    unittest.main()
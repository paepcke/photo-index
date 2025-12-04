# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-02 14:48:37
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-03 16:59:09

import os
from pathlib import Path
import shutil
import unittest
from PIL import Image
from tempfile import TemporaryDirectory

import ffmpeg

from common.img_metadata_utils import ImgMDExplorer, FieldType, ExifToolWriteError
class MDUtilsTester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cur_dir = os.path.dirname(__file__)
        # Create self.jpg_filename and self.png_filename
        # containing test images:
        cls.create_tst_img()

        # Create .mp4 and .mov test movies
        cls.create_tst_mov()
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

        # Same for .mp4 and .mov movies:
        shutil.copy(self.mp4_filename, self.tmp_dir.name)
        shutil.copy(self.qt_filename, self.tmp_dir.name)

        # Get a metadata accessor:
        self.img_explorer = ImgMDExplorer()

    # ------------ Tests --------------

    def test_empty_jpeg_md(self):
        md = self.img_explorer.read_fields(self.jpg_filename)
        # We should have an array of one dict,
        # i.e. the fieds of self.jpg_filename:
        # Some of the expected fields in the first
        # (and only) dict of the md array:
        #
        #    'File:FileType': 'JPEG', 
        #    'File:FileTypeExtension': 'JPG', 
        #    'File:MIMEType': 'image/jpeg',         
        self.assertEqual(type(md), dict)
        self.assertEqual(md['File:FileType'], 'JPEG')
        self.assertEqual(md['File:FileTypeExtension'].lower(), 'jpg')
        self.assertEqual(md['File:MIMEType'], 'image/jpeg')

    def test_empty_png_md(self):
        md = self.img_explorer.read_fields(self.png_filename)
        # Some of the expected fields in the first
        # (and only) dict of the md array:
        #
        #    'File:FileType': 'PNG', 
        #    'File:FileTypeExtension': 'PNG', 
        #    'File:MIMEType': 'image/png',         
        self.assertEqual(type(md), dict)
        self.assertEqual(md['File:FileType'], 'PNG')
        self.assertEqual(md['File:FileTypeExtension'].lower(), 'png')
        self.assertEqual(md['File:MIMEType'], 'image/png')

    def test_one_fld_one_file(self):
        md = self.img_explorer.read_fields(
            self.jpg_filename,
            fld_nms='FileType',
            fld_type=FieldType.File
            )
        self.assertEqual(md['File:FileType'], 'JPEG')

    def test_two_flds_two_files(self):
        md = self.img_explorer.read_fields(
            [self.jpg_filename, self.png_filename],
            fld_nms='FileType',
            fld_type=FieldType.File
            )
        jpg_md = md[0]
        png_md = md[1]
        self.assertEqual(jpg_md['File:FileType'], 'JPEG')
        self.assertEqual(png_md['File:FileType'].lower(), 'png')

    def test_write_one_exif_fld(self):
    
        self.img_explorer.write_fields(
            self.jpg_filename,
            {'Make': 'my_camera'},
            fld_type=FieldType.EXIF
        )
        md = self.img_explorer.read_fields(
            self.jpg_filename,
            fld_nms='Make',
            fld_type=FieldType.EXIF
            )
        self.assertEqual(md['EXIF:Make'], 'my_camera')
        
    def test_write_multiple_custom_flds(self):
        self.img_explorer.write_fields(
            [self.jpg_filename, self.png_filename],
            {
                'SourceVideoPath': '/tmp/my_movie.mp4',
                'SourceVideoUID': 'abcde'
            },
            FieldType.DRESL
        )
        md = self.img_explorer.read_fields(
            [self.jpg_filename, self.png_filename],
            ['SourceVideoPath', 'SourceVideoUID'],
            fld_type=FieldType.DRESL
            )
        jpg_md = md[0]
        png_md = md[1]
        self.assertEqual(jpg_md['XMP:SourceVideoPath'], '/tmp/my_movie.mp4')
        self.assertEqual(jpg_md['XMP:SourceVideoUID'], 'abcde')
        self.assertEqual(png_md['XMP:SourceVideoPath'], '/tmp/my_movie.mp4')
        self.assertEqual(png_md['XMP:SourceVideoUID'], 'abcde')

    def test_write_exif_one_bad_fld(self):
        with self.assertRaises(ExifToolWriteError):
            # 'Camera' is not a legal EXIF field
            self.img_explorer.write_fields(
                self.jpg_filename,
                {'Camera': 'my_camera'},
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

    @classmethod
    def create_tst_mov(cls):

        # Create an mp4 est clip:
        
        cls.mp4_filename = os.path.join(cls.cur_dir,"mp4_movie.mp4")

        # Video input
        video = ffmpeg.input('testsrc=duration=2:size=1280x720:rate=30', f='lavfi')
        # Audio input
        audio = ffmpeg.input('sine=frequency=1000:duration=2', f='lavfi')        

        (ffmpeg
        .output(video, audio, cls.mp4_filename, pix_fmt='yuv420p')
        .overwrite_output()
        .run()
        )

        # And a Quicktime movie:
        cls.qt_filename = os.path.join(cls.cur_dir,"qt_movie.mov")

        (ffmpeg
            .input('testsrc=duration=2:size=1280x720:rate=30', f='lavfi')
            .output(cls.qt_filename, pix_fmt='yuv420p')
            .overwrite_output()
            .run()
        )        


# ------------------------ Main ------------
if __name__ == '__main__':
    unittest.main()
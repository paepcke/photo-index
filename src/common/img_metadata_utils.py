# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-02 10:17:49
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-02 17:35:15

from enum import Enum
from typing import List, Optional

from exiftool import ExifToolHelper

class FieldType(Enum):
    # Embedded metadata
    XMP          = 'XMP'
    EXIF         = 'EXIF'
    IPTC         = 'IPTC'
    GPS          = 'GPS'
    
    # File info
    File         = 'File'
    Composite    = 'Composite'
    
    # Format-specific
    JFIF         = 'JFIF'
    ICC_Profile  = 'ICC_Profile'
    PNG          = 'PNG'
    GIF          = 'GIF'
    Photoshop    = 'Photoshop'
    
    # Camera-specific
    MakerNotes   = 'MakerNotes'
    
    # Video
    QuickTime    = 'QuickTime'
    Matroska     = 'Matroska'
    
    # Documents
    PDF          = 'PDF'    

# ---------------------- Class ImgMDExplorer ------------
class ImgMDExplorer:
    '''
    Everything for reading and writing image metadata,
    like Exif, XMP (Extended Metadata Platform), or IPTC.
    Metadata returned from a freshly installed .jpg file:
[     {'SourceFile': '/home/.../jpg_image.jpg', 
      'ExifTool:ExifToolVersion': 12.76, 
      'File:FileName': 'jpg_image.jpg', 
      'File:Directory': '/home/.../src/common/test', 
      'File:FileSize': 743, 
      'File:FileModifyDate': '2025:12:02 16:37:55-08:00', 
      'File:FileAccessDate': '2025:12:02 16:38:06-08:00', 
      'File:FileInodeChangeDate': '2025:12:02 16:37:55-08:00', 
      'File:FilePermissions': 100664, 
      'File:FileType': 'JPEG', 
      'File:FileTypeExtension': 'JPG', 
      'File:MIMEType': 'image/jpeg', 
      'File:ImageWidth': 100, 
      'File:ImageHeight': 50, 
      'File:EncodingProcess': 0, 
      'File:BitsPerSample': 8, 
      'File:ColorComponents': 3, 
      'File:YCbCrSubSampling': '2 2', 
      'JFIF:JFIFVersion': '1 1', 
      'JFIF:ResolutionUnit': 0, 
      'JFIF:XResolution': 1, 
      'JFIF:YResolution': 1, 
      'Composite:ImageSize': '100 50', 
      'Composite:Megapixels': 0.005
   }]
 
    '''

    DEFAULT_NAMESPACE = 'http://dresl.com/xmp/photo_index/1.0/'

    #------------------------------------
    # Constructor
    #-------------------    

    def __init__(self, namespace: Optional[str] = None):
        '''
        XMP metadata is partitioned into namespaces.
        If caller has one, great. Else, use the default.
        Namespaces are not used for the other 
        metadata types.

        :param namespace: XMP namespace identifier, defaults to None
        :type namespace: str, optional
        '''

        if namespace is None:
            self.namespace = ImgMDExplorer.DEFAULT_NAMESPACE
        else:
            self.namespace = namespace
        
    #------------------------------------
    # read_field
    #-------------------

    def read_fields(
            self,
            files: str | List[str],
            fld_nms: Optional[str | List[str]] = None, 
            fld_type: Optional[FieldType.XMP] = None
            ) -> List[dict[str, str]]:
        '''
        Use for reading any of the metadata types.
        Can read a set of fields from multiple files
        at once. Also, can read all metadata of all
        types at once. Examples:

        All MD of any type from one file:
           ImgMDExplorer.read_fields('myfile.jpg')
        All MD of any type from several files:
           ImgMDExplorer.read_fields(['myfile1.jpg', 'myfile1.png'])
        All EXIF from a file:
           ImgMDExplorer.read_fields(['myfile1.jpg'],
                                     fld_type=FieldType.EXIF
                                     )
        Fields named 'foo' and 'bar' from XMP metadata:
           ImgMDExplorer.read_fields(['myfile1.jpg'],
                                     fld_nms=['foo', 'bar'],
                                     fld_type=FieldType.XMP
                                     )
                                              
        :param files: files from which to read the metadata
        :type files: str | List[str]
        :param fld_nms: names of metadata fields, without any prefixes
        :type fld_nms: Optional[str  |  List[str]]
        :param fld_type: from which kind of metadata to read.
            If None, read from all fields
        :type fld_type: FieldType, optional
        :raises IOError: if any of the reads from any of the files fails
        :raises NotImplementedError: for unimplemented metadata standards
        :return: list of dictionaries with results
        :rtype: List[dict[str, str]]
        '''

        if type(files) == str:
            files = [files]
        
        # Do they want all metadata from all fields?
        if fld_type is None:
            try:
                with ExifToolHelper() as et:
                    metadata = et.get_metadata(files)
                    return metadata
            except Exception as e:
                raise IOError(f"Could not get all the metadata from files {files}")
        
        # Want metadata of a particular field type
        # (XMP/EXIF/IPTC)

        # The fld_nms may be None here, that's OK.
        # But if a single fld name, make it a list:
        if type(fld_nms) == str:
            fld_nms = [fld_nms]

        # Prepare the field names, depending on 
        # which metadata type is wanted:
        
        if fld_type == FieldType.XMP:
            # Prefix fields names with namespace:
            if fld_nms is None:
                prefixed_fld_nms = ["XMP:all"]
            else:
                prefixed_fld_nms = [f"XMP:{self.namespace}:{tag}"
                                    for tag
                                    in fld_nms
                                    ]
        
        elif fld_type == FieldType.EXIF:
            if fld_nms is None:
                prefixed_fld_nms = ["EXIF:all"]
            else:
                # Just for clarity; not strictly necessary:
                prefixed_fld_nms = [f"EXIF:{tag}"
                                    for tag
                                    in fld_nms
                                    ]

        elif fld_type == FieldType.IPTC:
            if fld_nms is None:
                prefixed_fld_nms = ["IPTC:all"]
            else:
                # Just for clarity; not strictly necessary:
                prefixed_fld_nms = [f"IPTC:{tag}"
                                    for tag
                                    in fld_nms
                                    ]
        else:
            msg = f"Reading from metadata field type {fld_type} not implemented"
            raise NotImplementedError(msg)

        with ExifToolHelper() as et:
            try:
                metadata = et.get_tags(files, tags=prefixed_fld_nms)
            except Exception as e:
                msg = f"Could not get metadata fields {fld_nms} from file(s) {files}"
                raise IOError(msg)

        # Will have a list of dicts, one for
        # each file:
        return metadata
    
    #------------------------------------
    # write_fields
    #-------------------    

    def write_fields(
            self,
            files: str | List[str],
            content: dict[str, any],
            fld_type: Optional[FieldType] = FieldType.XMP):
        '''
        Write a set of key/value pairs to a particular
        metadata standard in one or more files. Defaults
        to using XMP. Example:
          
        Write the number 10 to the XMP field 'myfield':
          ImgMDExplorer.write_fields('image1.jpg',
                                     {'myfield': 10}
                                     )
        Write 10 to 'myfield', and a directory path to the
        'directory' field into the EXIF part of two images:
          ImgMDExplorer.write_fields(['image1.jpg', 'image2.jpg'],
                                     {'myfield': 10,
                                      'directory': '/myphotos/images'
                                     }
                                     FieldType.EXIF
                                     )

        :param files: destination paths
        :type files: str | List[str]
        :param content: dict of the key/value pairs. No XMP prefix for keys
        :type content: dict[str, str]
        :param fld_type: which metadata standard, defaults to FieldType.XMP
        :type fld_type: FieldType, optional
        :raises NotImplementedError: unknown metadata type
        :raises IOError: on failure
        '''

        if type(files) == str:
            files = [files]
        
        if FieldType == FieldType.XMP:
            # Prefix all keys with XMP:<namespace>:
            keys_prefixed = [f"XMP:{self.namespace}:{tag}"
                                for tag
                                in content.keys()
                                ]
        elif FieldType == FieldType.EXIF:
            keys_prefixed = [f"EXIF:{tag}"
                                for tag
                                in content.keys()
                                ]            
        else:
            msg = f"Writing to metadata field type {fld_type} not implemented"
            raise NotImplementedError(msg)
        
        # Make a new fieldNm/value dict with the prefixed keys:
        content_prefixed = {key_prefixed : val 
                            for key_prefixed, val 
                            in zip(keys_prefixed, content.values())
                            }
        with ExifToolHelper() as et:
            try:
                et.set_tags(files, content_prefixed)
            except Exception as e:
                fld_nms = list(content.keys())
                msg = "Could not write fields {fld_nms} to {files}"
                raise IOError(msg)

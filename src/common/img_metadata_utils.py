# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-02 10:17:49
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-02 18:55:46

from enum import Enum
from typing import List, Optional
from urllib.parse import urlparse
import re

from exiftool import ExifToolHelper
from exiftool.exceptions import ExifToolTagNameError

class FldElements(Enum):
    NAMESPACE = 0
    GROUP = 1
    FIELD_NAME = 2

class FldNmCompleteness(Enum):
    ERROR      = 0
    COMPLETE   = 1  # namespace, metadata group, and fld name present
    GROUPED    = 2  # metadata group and fld name present
    FIELD_ONLY = 3 # only the field name is present

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

    @classmethod
    def values(cls):
        # Get a set like: {<FieldType.PDF: 'PDF'>, <FieldType.IPTC: 'IPTC'>, <FieldType.EXIF: 'EXIF'>...}
        all_entries = set(FieldType)
        vals = [el.value for el in all_entries]
        return vals

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
        
        # Prefix fields names with namespace:
        md_grp = fld_type.value
        if fld_nms is None:
            prefixed_fld_nms = ["{md_grp}:all"]
        else:
            prefixed_fld_nms = [
                f"{md_grp}:{self.namespace}:{tag}" if not tag.startswith(md_grp) else "{self.namespace}:{tag}"
                for tag
                in fld_nms
                ]

        with ExifToolHelper() as et:
            try:
                metadata = et.get_tags(files, tags=prefixed_fld_nms)
            except ExifToolTagNameError as e:
                msg = f"Field type {fld_type.name} and one of tag(s) {fld_nms} don't match: {e}"
                raise ValueError(msg)
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

    #------------------------------------
    # _prep_fld_names
    #-------------------

    def _prep_fld_names(self, fld_type_default, fld_names):

        prepped_flds = []
        for fld in fld_names:
            # The different parts of field names like:
            # File:FileType
            # EXIF:Camera
            # <XMP-namespace>:<Group>:<Field-Name>
            # 
            completeness = self._get_fld_nm_completeness(fld)
            if completeness == FldNmCompleteness.COMPLETE:
                prepped_flds.append(fld)
                continue
            if completeness == FldNmCompleteness.****


            # Does the fld name start with a metadata group?
            first_el = elements[0]
            if first_el in md_groups or self._is_valid_xmp_namespace(first_el)
                # The element is already qualified

    #------------------------------------
    # _get_fld_nm_completeness
    #-------------------

    def _get_fld_nm_completeness(self, fld_spec):
        '''
        Returns FldNmCompleteness member:
           ERROR  if given field spec is malformed
           FIELD_ONLY if only an unqualified field name is provided
           GROUPED if a metadata group and fld name are provided


        :param fld_spec: _description_
        :type fld_spec: _type_
        :return: _description_
        :rtype: _type_
        '''
        elements = fld_spec.split(':')
        if len(elements) == 0:
            return FldNmCompleteness.FIELD_ONLY
        if len(elements) == 1:
            # Have <str>:<str>
            # So first element better be a legal metadata group:
            grp_el = elements[0]
            if grp_el in FieldType.values():
                return FldNmCompleteness.GROUPED
            else:
                return FldNmCompleteness.ERROR
        if len(elements) == 3:
            # First el must be an XMP namespace:
            ns = elements[0]
            if not self._is_valid_xmp_namespace(ns):
                return FldNmCompleteness.ERROR
            # Next part must be be md group:
            grp_el = elements[1]
            if grp_el in FieldType.values():
                return FldNmCompleteness.COMPLETE
            else:
                return FldNmCompleteness.ERROR
        else:
            # Too many elements:
            return FldNmCompleteness.ERROR



    #------------------------------------
    # _is_valid_xmp_namespace
    #-------------------

    def _is_valid_xmp_namespace(self, namespace: str, strict: bool = True) -> bool:
        """
        Test whether given string is a valide XMP namespace URI.
        
        Args:
            namespace: String to validate
            strict: If True, enforce XMP best practices
        """
        try:
            result = urlparse(namespace)
            
            # Must have a scheme
            if not result.scheme:
                return False
            
            if strict:
                # Common XMP schemes
                valid_schemes = ['http', 'https', 'urn']
                if result.scheme not in valid_schemes:
                    return False
                
                # XMP namespaces conventionally end with / or #
                if not (namespace.endswith('/') or namespace.endswith('#')):
                    return False
            
            return True
        except:

            return False
        
    #------------------------------------
    # _parse_fld_spec
    #-------------------        

    def _parse_fld_spec(self, fld_spec):
        completeness = self._get_fld_nm_completeness(fld_spec)
        fld_elements = fld_spec.split(':')
        if completeness == FldNmCompleteness.COMPLETE:
            return {
                'completeness' : completeness,
                'namespace'    : fld_elements[0],
                'group'        : fld_elements[1],
                'fld_nm'       : fld_elements[2]
            }
        elif completeness == FldNmCompleteness.GROUPED:
            return {
                'completeness' : completeness,                
                'group'        : fld_elements[0],
                'fld_nm'       : fld_elements[1]                
            }
        elif completeness == FldNmCompleteness.FIELD_ONLY:
            return {
                'completeness' : completeness,                
                'fld_nm'       : fld_elements[0]
            }
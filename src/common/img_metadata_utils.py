# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-12-02 10:17:49
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-03 14:43:15

from enum import Enum
from pathlib import Path
import subprocess
from typing import List, Optional
from urllib.parse import urlparse
import re

from exiftool import ExifToolHelper
from exiftool.exceptions import ExifToolTagNameError, ExifToolExecuteError

class ExifToolWriteError(Exception):
    """Raised when ExifTool returns an error while writing tags."""
    def __init__(self, message, diagnostics=None, file=None, tags=None):
        super().__init__(message)
        self.diagnostics = diagnostics
        self.file = file
        self.tags = tags

    def __str__(self):
        base = super().__str__()
        if self.diagnostics:
            return f"{base}\n\nDiagnostics:\n{self.diagnostics}"
        return base
class FldElements(Enum):
    NAMESPACE = 0
    GROUP = 1
    FIELD_NAME = 2

class FieldType(Enum):
    # Custom Photo Indexing
    DRESL        = 'XMP-dresl'
    # Embedded metadata
    XMP          = 'XMP'
    EXIF         = 'EXIF'
    IPTC         = 'IPTC'
    GPS          = 'GPS'
    DublinCore   = 'dc'
    
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

    DEFAULT_NAMESPACE = 'XMP-dresl'

    #------------------------------------
    # Constructor
    #-------------------    

    def __init__(self, config_file: Optional[str] = None):
        '''
        XMP metadata is partitioned into namespaces.
        If caller has one, great. Else, use the default.
        Namespaces are not used for the other 
        metadata types.

        :param config_file: XMP namespace initialization
        '''

        if config_file is None:
            cur_dir = Path(__file__).parent
            self.config_path = Path.joinpath(cur_dir, 'exiftool.config')
        
    #------------------------------------
    # read_field
    #-------------------

    def read_fields(
            self,
            files: str | List[str],
            fld_nms: Optional[str | List[str]] = None, 
            fld_type: Optional[FieldType.XMP] = None
            ) -> dict[str, str] | List[dict[str, str]]:
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
        Fields named 'Rating' and 'CreateDate' from XMP metadata:
           ImgMDExplorer.read_fields(['myfile1.jpg'],
                                     fld_nms=['Rating', 'CreateDate'],
                                     fld_type=FieldType.XMP
                                     )

        If metadata from only one file is requested, returns
        that file's metadata dict, else a list of md dicts.
                                                                                   
        :param files: files from which to read the metadata
        :param fld_nms: names of metadata fields, without any prefixes
        :param fld_type: from which kind of metadata to read.
            If None, read from all fields
        :raises IOError: if any of the reads from any of the files fails
        :raises NotImplementedError: for unimplemented metadata standards
        :return: list of dictionaries with results
        :rtype: List[dict[str, str]]
        '''
        # Single file -> list of files:
        if type(files) == str:
            files = [files]
        
        # Do they want all metadata from all fields?
        if fld_type is None:
            try:
                with ExifToolHelper(config_file=self.config_path) as et:
                    metadata = et.get_metadata(files)
                    return metadata if len(metadata) > 1 else metadata[0]
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
        prepped_fld_nms = self._prep_fld_names(fld_nms,
                                               fld_type_default=fld_type)        

        with ExifToolHelper(config_file=self.config_path) as et:
            try:
                metadata = et.get_tags(files, tags=prepped_fld_nms)
            except ExifToolTagNameError as e:
                msg = f"Field type {fld_type.name} and one of tag(s) {fld_nms} don't match: {e}"
                raise ValueError(msg)
            except Exception as e:
                msg = f"Could not get metadata fields {fld_nms} from file(s) {files}"
                raise IOError(msg)

        # Will have a list of dicts, one for
        # each file. If md of only only one file was requested,
        # return just one dict:
        if len(metadata) == 1:
            return metadata[0]
        else:
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
                                     FieldType.DRESL
                                     )

        :param files: destination paths
        :param content: dict of the key/value pairs. No XMP prefix for keys
        :param fld_type: which metadata standard, defaults to FieldType.XMP
        :raises ExifToolWriteError: if ExifTool reports an error
        '''

        if type(files) == str:
            files = [files]

        keys_prefixed = self._prep_fld_names(list(content.keys()),
                                             fld_type_default=fld_type
                                             )        
        
        # Make a new fieldNm/value dict with the prefixed keys:
        content_prefixed = {key_prefixed : val 
                            for key_prefixed, val 
                            in zip(keys_prefixed, content.values())
                            }
        # Throws error if anything goes wrong 
        # at any point in the loop through the
        # files:
        with ExifToolHelper(config_file=self.config_path) as et:
            for file_path in files:
                # Get detailed error msgs (the -v3):
                diagnostics = self._write_to_one_file(
                    et,
                    file_path,
                    content_prefixed
                )
            
    #------------------------------------
    # _write_to_one_file
    #-------------------

    def _write_to_one_file(self,
        et: ExifToolHelper,
        file_path: str,
        tags: dict,
        verbose: int = 2,
        overwrite: bool = True
        ):
        """
        Write a set of metadata safely, returning diagnostics 
        and structured results.

        :param et: An active ExifToolHelper instance (inside a `with` block)
        :param file_path: Path to the target file
        :param tags: Dict of tags to write
        :param verbose: Verbosity level for ExifTool (-v, -v2, etc.)
        :param overwrite: Whether to pass -overwrite_original
        :raises ExifToolWriteError: if ExifTool reports an error
        :return: dict with keys: 'ok', 'diagnostics', 'file', 'tags'
        """

        # Convert tags to ExifTool's "-TAG=VALUE" form
        args = []
        for tag, value in tags.items():
            args.append(f"-{tag}={value}")

        # ExifTool parameters
        params = ['-config', str(self.config_path)]
        if overwrite:
            params.append("-overwrite_original")

        # Verbosity level
        vflag = f"-v{verbose}" if verbose > 0 else "-v"
        params.append(vflag)

        # Final argument list: params + tag assignments + file path
        full_args = params + args + [file_path]

        # ---- Run the command with raw output (diagnostics included) ----
        try:
            output_lines = et.execute(*full_args)
            return True
        except ExifToolExecuteError as e:
                # FAILURE path — diagnostics available here
                diagnostics = e.stdout + "\n" + e.stderr
                raise ExifToolWriteError(
                    f"ExifTool failed while writing metadata to '{file_path}'.",
                    diagnostics=diagnostics.strip(),
                    file=file_path,
                    tags=tags
                )
        except Exception as e:
            # This captures Python-level issues (rare)
            raise ExifToolWriteError(
                f"Failed to execute ExifTool: {e}",
                diagnostics=None,
                file=file_path,
                tags=tags
            )

    #------------------------------------
    # _prep_fld_names
    #-------------------

    def _prep_fld_names(self, 
                        fld_names: List[str] | str,
                        fld_type_default: Optional[str] = None
                        ) -> List[str]:
        '''
        Given field type and a list of metadata field names,
        return a new list of field names that are modified to
        be legally passed to ExifToolHelper for reading/writing.
        Example:
            _prep_fld_names(['foo', 'bar])
                -> ['XMP-dresl:foo', 'XMP-dresl':bar']
            _prep_fld_names(['EXIF:ImageHeight', 'creator'], FieldType.DublinCore)
                <-> ['EXIF:ImageHeight', 'dc:creator']

        :param fld_type_default: the intended metadata standard
        :param fld_names: metadata field name(s) 
        :raises ValueError: for field names that cannot be resolved
        :return: _description_
        :rtype: _type_
        '''

        prepped_flds = []
        for fld in fld_names:
            # The different parts of field names like:
            # File:FileType
            # EXIF:Camera
            # <XMP-namespace>:<Group>:<Field-Name>
            # 
            fld_elements = self._parse_fld_spec(fld)
            if len(fld_elements) > 1:
                # Field is already completely qualified with
                # namespace and group, or with group:
                #    <ns>:<GroupName>:<FldName>
                # or <GroupName>:<FldName>
                prepped_flds.append(fld)
                continue
            else:
                # Field spec is just a field name. Prepend group
                # if provided:
                if fld_type_default is not None:
                    prepped_flds.append(f"{fld_type_default.value}:{fld}")
                else:
                    prepped_flds.append(fld)
                continue

        return prepped_flds

    #------------------------------------
    # _parse_fld_spec
    #-------------------        

    def _parse_fld_spec(self, fld_spec: str) -> dict[str, str]:
        '''
        Returns dict with the elements of the 
        given field spec:
            fld_nm, group, namespace.
        One, two, or all three of these may be present in the
        returned dict.
            
        :param fld_spec: metadata field name to examine
        :return: information on which parts of a metadata spec is included
            in the field spec
        '''
        fld_elements = fld_spec.split(':')
        if len(fld_elements) == 1:

            return {
                'fld_nm'       : fld_elements[0]
            }            
        if len(fld_elements) == 2:

            grp_el = fld_elements[0] 
            if grp_el not in FieldType.values():
                raise NotImplementedError(f"Metadata group {grp_el} in {fld_spec} is unknown")

            # Have <str>:<str>
            # So first element better be a legal metadata group:
            return {
                'group'        : grp_el,
                'fld_nm'       : fld_elements[1]                
            }

        if len(fld_elements) == 3:
            # First el must be an XMP namespace:
            ns = fld_elements[0]
            if not self._is_valid_xmp_namespace(ns):
                raise ValueError(f"The '{ns}' part of field {fld_spec} is not a proper XMP namespace")

            # Next part must be be md group:
            grp_el = fld_elements[1]
            if grp_el not in FieldType.values():
                raise NotImplementedError(f"Metadata group {grp_el} in {fld_spec} is unknown")
            return {
                'group'        : grp_el,
                'fld_nm'       : fld_elements[1],
                'namespace'    : ns
            }
            
        else:
            # Too many elements:
            raise ValueError(f"Metadata field {fld_spec} has too many colons (max is 3)")

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

# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-23 08:29:37
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-12-07 12:06:36

from pathlib import Path
import time
from datetime import datetime, timedelta

from contextlib import contextmanager
import hashlib
from typing import Callable

# --------------------- Context Managers ----------------

class BatchTimer:
    '''
    Helper class yielded by the context manager to track loop progress.
    Example of a client:
        timed('Process photos') as batchTimer:
            for i in num_photos:
                process_one_photo()
                batchTimer(progress(i, every=50, total=num_photos))

        The call to progress() prints a progress message every 50
        times through the loop.
    '''

    def __init__(self, label: str, log_func: Callable[[str], None]):
        '''
        Instance provides progress information for long-running client
        processes that provide intermittent progress information. When
        a client uses the 'timed' context manager, an instance of this
        class is returned to them. When they wish to report progress,
        they call the progress() method on this instance.

        Progress is in terms of code loops in the client, converted to
        time for status reports.

        :param label: short text describing the client's overall operation
        :type label: str
        :param log_func: function to call for printing progress. Could be
            a logger.info() method, or the built-in print() fucntion.
        :type log_func: Callable[[str], None]
        '''
        self.label = label
        self.start_time = time.perf_counter()
        self.batch_start_time = self.start_time
        self.log = log_func

    def progress(self, i: int, every: int = 50, total: int = None):
        """
        Checks if a batch report is needed, and logs it by calling 
        the log function if appropriate.
        
        :param i: Current loop index (0-based) of the client process.
        :param every: Report interval in counts through the client's operations loop
        :param total: Total number of items (required for ETA calculation). This
            is usually the total number of client loops required.
        """
        count = i + 1
        if count % every == 0:
            now = time.perf_counter()
            
            # Batch timing
            batch_duration = now - self.batch_start_time
            
            # Total stats for ETA
            total_elapsed = now - self.start_time
            avg_per_item = total_elapsed / count
            
            # Construct message parts
            #msg_parts = [f"  > {self.label} processed {count}"]
            msg_parts = [f"  > did {count}. "]
            msg_parts.append(f"batch of {every} in {timedelta(seconds=int(batch_duration))}")

            # Calculate ETA if total is provided
            if total:
                remaining_items = total - count
                eta_seconds = int(remaining_items * avg_per_item)
                eta_str = Utils.calendar_eta(eta_seconds)
                msg_parts.append(f"ETA: {eta_str}")

            # Log and reset batch timer
            self.log(" | ".join(msg_parts))
            self.batch_start_time = now

@contextmanager
def timed(label, log=None):
    '''
    Times the operation inside the with...
    Yields a BatchTimer object to allow reporting progress inside loops.

    Usage: Report overall time at end, but elapsed time every 50 items: 
         
         with timed("indexing photos", log=None) as timer:
             for i, photo in enumerate(photo_paths):
                 time.sleep(0.05) # Simulate work
                 # (Optionally; don't need to call this): report elapsed time for the last 50 items
                 timer.progress(i, every=50)

      Output:
      Starting indexing photos
        > indexing photos processed 50 | last 50 in 0:00:02
        > indexing photos processed 100 | last 50 in 0:00:02
      Finished indexing photos: 0:00:10 elapsed time      

    Usage: Report overall time at end, but elapsed time and ETA every 50 items:
          total_photos = len(photo_paths)
          with timed("indexing photos", log=None) as timer:
              for i, photo in enumerate(photo_paths):
                  time.sleep(0.1)
                  # Pass 'total' to get the ETA calculation
                  timer.progress(i, every=50, total=total_photos)
      Output:
      Starting indexing photos
        > indexing photos processed 50 | last 50 in 0:00:05 | ETA: 0:00:15
        > indexing photos processed 100 | last 50 in 0:00:05 | ETA: 0:00:10
      Finished indexing photos: 0:00:20 elapsed time      
    '''

    # Setup Logger
    if log is not None:
        log_func = log.info
    else:
        log_func = print

    # Announce starting
    log_func(f"Starting {label}")
    start = time.perf_counter()

    try:
        # Yield the helper object (injecting the dependencies)
        yield BatchTimer(label, start, log_func)
    finally:
        # Announce ending
        end = time.perf_counter()
        seconds = end - start
        elapsed_time = timedelta(seconds=int(seconds))
        log_func(f"Finished {label}: {elapsed_time} elapsed time")

# ---------------------- Class FileNamer -------------------

class FileNamer:
    '''
    Handles the chore of creating a unique file names that
    follow a consistent convention. Start with a base directory,
    such as /home/john/movies. A FileName instance is always in
    a working directory, just like a Unix/MacOS shell.

    Main methods:
         mkdir(prefix, cd=True)
         mkfile_nm(file_name)
         cd(new_dir)
         pwd()
    The mkdir() creates a directory <base_dir>/prefix. If such
    a directory already exists, creates <base_dir>/prefix_1, etc.
    If cd is True, cwd changes to the new directory.

    The mkfile_nm() method creates appropriate deduplicated file
    names in the cwd by adding '_<int>' to the file name before the
    given file name's extension, if there is one. Example: given
    my_file.jpg, the method tries <cwd>/my_file.jpg, <cwd>/my_file_1.jpg,
    etc.
    '''
    def __init__(self, base_dir: str | Path):

        # Standardize on internal values being Path instances,
        # rather than strings
        self.cwd = Path(base_dir)
        Path.mkdir(self.cwd, exist_ok=True)
        
    def mkdir(self, 
              prefix: str | Path,
              exist_ok: bool = False,
              cd: bool = False) -> Path:
        '''
        Create a directory under self.cwd with name <prefix>.
        If that name exists, try <prefix>_1, etc.
        If cd is True, then set self.cwd to the new directory.
        Return a Path object that is the new directory

        :param prefix: root name of new directory
        :param cd: whether to switch directory to the new one, defaults to True
        :return: the new directory
        '''
        counter = 1
        full_path = self.cwd / Path(prefix)
        nm = full_path
        if exist_ok and Path.exists(nm):
            if cd:
                self.cd(nm)
            return nm
        while Path.exists(nm):
            nm = Path(f"{str(full_path)}_{counter}")
        Path.mkdir(nm)
        if cd:
            self.cd(nm)
        return nm

    def mkfile_nm(self, nm: str | Path) -> Path:
        counter = 1
        nmp = self.cwd / Path(nm)
        suffix = nmp.suffix
        nm_no_suffix = nmp.with_suffix('')
        new_nm = nmp
        while Path.exists(new_nm):
            new_nm = Path(f"{str(nm_no_suffix)}_{counter}").with_suffix(suffix)
        return new_nm
    
    def cd(self, new_dir: str | Path) -> Path:
        self.cwd = Path(new_dir)
        return self.cwd

# ---------------------- Class Utils -------------------

class Utils:

    # --------------------- GUID Generation ----------------
    @staticmethod
    def get_photo_guid(photo_path) -> str:
        """Generate stable GUID based on file content.
        
        Uses SHA256 hash of file content, so the same photo will always
        have the same GUID, even if renamed or moved.
        
        Args:
            photo_path: Path to photo file
            
        Returns:
            16-character hex string (64 bits)
        """
        hasher = hashlib.sha256()
        with open(photo_path, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()[:16]  # 16 chars = 64 bits


    @staticmethod
    def guid_to_point_id(guid: str) -> int:
        """Convert GUID to Qdrant point ID (positive integer).
        
        Args:
            guid: Photo GUID (hex string)
            
        Returns:
            Positive integer for Qdrant point ID
        """
        return int(guid, 16) % (2**63)

    # ---------------------- JSON Fixing -------------------------

    @staticmethod
    def try_fix_json(json_str: str):
        """Attempt to fix common JSON formatting issues from LLM outputs.
        
        Applies a series of fix strategies to handle common malformed JSON
        from language models (extra text, markdown blocks, trailing commas, etc.)
        
        Args:
            json_str: Potentially malformed JSON string
            
        Returns:
            Parsed dict if successful, None otherwise
            
        Example:
            >>> bad_json = '```json\\n{"key": "value",}\\n```'
            >>> Utils.try_fix_json(bad_json)
            {'key': 'value'}
        """
        import re
        import json
        
        fixes = [
            ('leading_text', lambda s: s[s.find('{'):] if '{' in s else s),
            ('trailing_text', lambda s: s[:s.rfind('}')+1] if '}' in s else s),
            ('remove_escaped_newlines', lambda s: s.replace('\\n', '')),
            ('markdown', lambda s: re.sub(r'```json\s*|\s*```', '', s)),
            ('whitespace', lambda s: s.strip()),
            ('trailing_comma_brace', lambda s: re.sub(r',\s*}', '}', s)),
            ('trailing_comma_bracket', lambda s: re.sub(r',\s*]', ']', s)),
        ]
        
        current = json_str
        
        for name, fix_func in fixes:
            try:
                current = fix_func(current)
            except Exception:
                # Continue to next fix even if this one fails
                continue
        
        # Try to parse the fixed JSON
        try:
            return json.loads(current)
        except json.JSONDecodeError:
            return None

    # ---------------------- Miscellaneous -------------------------

    @staticmethod
    def calendar_eta(eta_seconds: int) -> str:
        '''
        Given a number of seconds into the future, return a 
        string that gives the actual local time of ETA.
        If on the same day, output is hh:mm:ss. If a day
        or more in the future, output in ISO format.

        Example 1: Short duration (same day)
        Assuming it is currently 10:00:00
            print(format_future_eta(3600))  
        
        Output: 11:00:00

        Example 2: Long duration (rolls over to tomorrow)
            print(format_future_eta(86400 + 3600)) 

        Output: 2023-10-27T11:00:00

        :param eta_seconds: numnber of seconds into the future
        :type eta_seconds: int
        :return: walltime
        :rtype: str
        '''
        # Get current local time
        now = datetime.now()
        
        # Calculate future time
        future_time = now + timedelta(seconds=eta_seconds)
        
        # Check if the date has changed
        if future_time.date() == now.date():
            # Same day: Return HH:MM:SS
            return future_time.strftime("%H:%M:%S")
        else:
            # Rollover (next day or later): Return ISO format
            # sep=' ' puts a space instead of 'T'
            # timespec='seconds' removes microseconds for cleaner output
            return future_time.isoformat(timespec='seconds')


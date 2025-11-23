# -*- coding: utf-8 -*-
# @Author: Andreas Paepcke
# @Date:   2025-11-23 08:29:37
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-11-23 12:01:20

import time
import datetime
from contextlib import contextmanager
import hashlib

# --------------------- Context Managers ----------------

import time
import datetime
from contextlib import contextmanager
from typing import Callable

class BatchTimer:
    """Helper class yielded by the context manager to track loop progress."""

    def __init__(self, label: str, start_time: float, log_func: Callable[[str], None]):
        self.label = label
        self.start_time = start_time
        self.batch_start_time = start_time
        self.log = log_func

    def progress(self, i: int, every: int = 50, total: int = None):
        """
        Checks if a batch report is needed.
        
        :param i: Current loop index (0-based)
        :param every: Report interval
        :param total: Total number of items (required for ETA calculation)
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
            msg_parts = [f"  > {self.label} processed {count}"]
            msg_parts.append(f"last {every} in {datetime.timedelta(seconds=int(batch_duration))}")

            # Calculate ETA if total is provided
            if total:
                remaining_items = total - count
                eta_seconds = int(remaining_items * avg_per_item)
                eta_str = str(datetime.timedelta(seconds=eta_seconds))
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
        elapsed_time = datetime.timedelta(seconds=int(seconds))
        log_func(f"Finished {label}: {elapsed_time} elapsed time")

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

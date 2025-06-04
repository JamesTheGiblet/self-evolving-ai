# utils\logger.py

import datetime
import traceback
from typing import Optional
from unittest.mock import patch

import pytest

def log(message: str, level: str = "INFO", source: Optional[str] = None, **kwargs):
    """
    Custom print-based logger.
    Handles 'exc_info' in kwargs to print traceback if True or an exception/tuple.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_message_parts = [f"[{timestamp}]", f"[{level.upper()}]"]
    
    # Add source if provided
    if source:
        log_message_parts.append(f"[{source}]")
    
    log_message_parts.append(f"- {message}")
    
    # Print the main log message
    print(" ".join(log_message_parts))
    
    # Handle exc_info for traceback
    exc_info_val = kwargs.get('exc_info')
    if exc_info_val:
        # If exc_info is True, print the current exception's traceback
        if exc_info_val is True:
            traceback.print_exc()
        # If exc_info is an exception tuple (type, value, tb)
        elif isinstance(exc_info_val, tuple) and len(exc_info_val) == 3:
            traceback.print_exception(*exc_info_val)
        # If exc_info is an exception instance
        elif isinstance(exc_info_val, BaseException):
            traceback.print_exception(type(exc_info_val), exc_info_val, exc_info_val.__traceback__)

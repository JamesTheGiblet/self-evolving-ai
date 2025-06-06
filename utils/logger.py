# utils\logger.py

import datetime
import traceback
from typing import Optional
import os
import sys

LOG_DIRECTORY = r"C:\Users\gilbe\Desktop\self-evolving-ai\logs"

def log(message: str, level: str = "INFO", source: Optional[str] = None, **kwargs):
    """
    Custom logger that prints to console and saves to a daily log file
    in the LOG_DIRECTORY.
    Handles 'exc_info' in kwargs to print traceback if True or an exception/tuple.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_message_parts = [f"[{timestamp}]", f"[{level.upper()}]"]
    
    # Add source if provided
    if source:
        log_message_parts.append(f"[{source}]")
    
    log_message_parts.append(f"- {message}")
    
    formatted_message = " ".join(log_message_parts)
    
    # Print the main log message to console
    print(formatted_message)
    
    # Save to log file
    try:
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
        log_file_name = f"{datetime.date.today().strftime('%Y-%m-%d')}.log"
        log_file_path = os.path.join(LOG_DIRECTORY, log_file_name)
        
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(formatted_message + "\n")
            
            # Handle exc_info for traceback in file
            exc_info_val_file = kwargs.get('exc_info', False)
            if exc_info_val_file:
                if exc_info_val_file is True:
                    # If True, print current exception information to file
                    traceback.print_exc(file=f)
                elif isinstance(exc_info_val_file, tuple) and len(exc_info_val_file) == 3:
                    # If an exception tuple (type, value, tb)
                    traceback.print_exception(*exc_info_val_file, file=f)
                elif isinstance(exc_info_val_file, BaseException):
                    # If an exception instance
                    traceback.print_exception(type(exc_info_val_file), exc_info_val_file, exc_info_val_file.__traceback__, file=f)
    except Exception as e:
        # If logging to file fails, print an error to console.
        # This uses print directly to avoid recursion if log() itself is the problem.
        err_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys.stderr.write(f"[{err_timestamp}] [LOGGER_FILE_ERROR] - Failed to write to log file: {e}\n")
        traceback.print_exc(file=sys.stderr) # Print traceback of the file logging error to stderr
    
    # Handle exc_info for traceback
    exc_info_val_console = kwargs.get('exc_info', False)
    if exc_info_val_console:
        # If exc_info is True, print the current exception's traceback
        if exc_info_val_console is True:
            traceback.print_exc()
        # If exc_info is an exception tuple (type, value, tb)
        elif isinstance(exc_info_val_console, tuple) and len(exc_info_val_console) == 3:
            traceback.print_exception(*exc_info_val_console)
        # If exc_info is an exception instance
        elif isinstance(exc_info_val_console, BaseException):
            traceback.print_exception(type(exc_info_val_console), exc_info_val_console, exc_info_val_console.__traceback__)

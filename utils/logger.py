# utils\logger.py

import datetime
import traceback
from typing import Optional
import os
import sys
import config # Import config to get PROJECT_ROOT_PATH

# Define log directory and file paths using config
LOG_DIRECTORY = os.path.join(config.PROJECT_ROOT_PATH, "logs")
SIMULATION_LOG_FILE = os.path.join(LOG_DIRECTORY, "simulation.log")
FAULT_LOG_FILE = os.path.join(LOG_DIRECTORY, "fault.log")

# Ensure log directories exist upon module load
try:
    # Ensure the common log directory exists
    os.makedirs(LOG_DIRECTORY, exist_ok=True)
except OSError as e:
    # If directory creation fails, print to stderr. Console logging will still work.
    sys.stderr.write(f"CRITICAL LOGGER SETUP ERROR: Could not create log directories: {e}\n")

def log(message: str, level: str = "INFO", source: Optional[str] = None, **kwargs):
    """
    Custom logger that prints to console and saves messages to specific log files
    based on severity:
    - INFO, DEBUG, WARNING, TRACE messages go to logs/simulation.log.
    - ERROR, CRITICAL messages go to fault.log in the 'logs' subdirectory.
    Handles 'exc_info' in kwargs to print traceback if True or an exception/tuple.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_message_parts = [f"[{timestamp}]", f"[{level.upper()}]"]
    
    # Add source if provided
    if source:
        log_message_parts.append(f"[{source}]")
    
    log_message_parts.append(f"- {message}")
    
    formatted_message = " ".join(log_message_parts)
    
    # Print the main log message to console (actual console, not redirected stdout)
    print(formatted_message)
    
    # Determine target log file based on level
    level_upper = level.upper()
    target_file_path = None

    if level_upper in ["ERROR", "CRITICAL"]:
        target_file_path = FAULT_LOG_FILE
    elif level_upper in ["INFO", "DEBUG", "WARNING", "TRACE"]: # TRACE and WARNING go to simulation.log
        target_file_path = SIMULATION_LOG_FILE
    # Other custom levels, if any, won't be logged to these specific files by default.

    if target_file_path:
        try:
            # Directories are ensured at module load time.
            with open(target_file_path, 'a', encoding='utf-8') as f:
                f.write(formatted_message + "\n")
                
                # Handle exc_info for traceback in the target file
                exc_info_val_file = kwargs.get('exc_info', False)
                if exc_info_val_file:
                    if exc_info_val_file is True:
                        traceback.print_exc(file=f)
                    elif isinstance(exc_info_val_file, tuple) and len(exc_info_val_file) == 3:
                        traceback.print_exception(*exc_info_val_file, file=f)
                    elif isinstance(exc_info_val_file, BaseException):
                        traceback.print_exception(type(exc_info_val_file), exc_info_val_file, exc_info_val_file.__traceback__, file=f)
        except Exception as e:
            # If logging to a specific file fails, print an error to stderr.
            # This uses sys.stderr.write directly to avoid recursion if log() itself is the problem.
            err_timestamp_fallback = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sys.stderr.write(f"[{err_timestamp_fallback}] [LOGGER_FILE_WRITE_ERROR] - Failed to write to log file {target_file_path}: {e}\n")
            # Optionally, print traceback of this specific file logging error to stderr
            # traceback.print_exc(file=sys.stderr) 
    
    # Handle exc_info for console traceback (original behavior)
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

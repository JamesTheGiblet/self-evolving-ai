import re
import os
import sys

# --- Configuration ---
# These paths will be constructed relative to the project root.
SOURCE_LOG_FILENAME = "simulation.log"  # The name of your main simulation log file
EXTRACTED_ERROR_LOG_SUBDIR = "logs"
EXTRACTED_ERROR_LOG_FILENAME = "simulation_critical_warnings_extracted.log"

# Log levels to extract (case-insensitive for matching)
TARGET_LEVELS = ["WARNING", "CRITICAL"]

def extract_log_level_from_line(line_content: str) -> str | None:
    """
    Extracts the log level from a log line based on the format:
    [YYYY-MM-DD HH:MM:SS] [LEVEL] - Message
    """
    # Regex to find the log level (e.g., INFO, WARNING) enclosed in the second pair of square brackets.
    # It looks for a timestamp-like pattern, then captures the level.
    match = re.search(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*\[([A-Z]+)\]", line_content.strip())
    if match:
        return match.group(1).upper() # Return the captured group (the level string) in uppercase
    return None

def process_simulation_log(source_log_full_path: str, error_log_full_path: str):
    """
    Reads the source log file, extracts lines with target levels (WARNING, CRITICAL),
    and writes them to the error log file.
    """
    extracted_entries_count = 0
    total_lines_processed = 0

    # Ensure the directory for the error log exists
    error_log_directory = os.path.dirname(error_log_full_path)
    if error_log_directory and not os.path.exists(error_log_directory):
        try:
            os.makedirs(error_log_directory)
            print(f"Successfully created directory: {error_log_directory}")
        except OSError as e:
            print(f"Fatal: Could not create directory {error_log_directory}: {e}. Cannot write error log.", file=sys.stderr)
            return

    possible_encodings = ['utf-8', 'cp1252', 'latin-1']  # Order of encodings to attempt
    successfully_processed = False
    final_used_encoding = "None"

    for enc in possible_encodings:
        print(f"Attempting to process log file with encoding: {enc}")
        try:
            with open(source_log_full_path, 'r', encoding=enc, errors='replace') as input_file, \
                 open(error_log_full_path, 'w', encoding='utf-8') as output_file:  # Always write output as UTF-8
                
                # Reset counters for this attempt
                current_extracted_count = 0
                current_total_lines = 0

                for line_content in input_file:  # line_content is already str due to text mode and errors='replace'
                    current_total_lines += 1
                    log_level = extract_log_level_from_line(line_content) 
                    
                    if log_level and log_level in TARGET_LEVELS:
                        output_file.write(line_content)  # line_content includes newline if present
                        current_extracted_count += 1
                
                # If we complete the loop without UnicodeDecodeError for this encoding
                extracted_entries_count = current_extracted_count
                total_lines_processed = current_total_lines
                successfully_processed = True
                final_used_encoding = enc
                print(f"Successfully processed log file using encoding: {enc}")
                break  # Exit the encoding trial loop

        except UnicodeDecodeError:
            print(f"Encoding {enc} failed during processing. Trying next encoding.", file=sys.stderr)
            continue 
        except FileNotFoundError:
            print(f"Fatal: The source log file was not found at '{source_log_full_path}'. Please check the path.", file=sys.stderr)
            return 
        except Exception as e:
            print(f"An unexpected error occurred while processing with encoding {enc}: {e}", file=sys.stderr)
            continue 

    if successfully_processed:
        print(f"\nLog processing finished.")
        print(f"Total lines read from source: {total_lines_processed}")
        print(f"Warning/Critical entries found and extracted: {extracted_entries_count}")
        print(f"Source log was read using encoding: {final_used_encoding}")
        print(f"Extracted errors/warnings written to: {error_log_full_path}")
    else:
        print(f"Fatal: Could not process the log file with any of the attempted encodings: {possible_encodings}. "
              "The extracted log file might be empty or incomplete.", file=sys.stderr)

if __name__ == "__main__":
    # Determine the project root directory.
    # Assumes this script is in a 'tools' subdirectory of the project root.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_candidate = os.path.abspath(os.path.join(script_dir, '..'))

    # Add the project root to sys.path to allow importing 'config'
    if project_root_candidate not in sys.path:
        sys.path.insert(0, project_root_candidate)

    current_project_root = project_root_candidate  # Default to this calculated path

    try:
        import config
        # If config.py is found and has PROJECT_ROOT_PATH, prefer it.
        if hasattr(config, 'PROJECT_ROOT_PATH'):
            current_project_root = config.PROJECT_ROOT_PATH
            print(f"Using PROJECT_ROOT_PATH from config.py: {current_project_root}")
        else:
            print("Warning: 'config.py' found, but 'PROJECT_ROOT_PATH' attribute is missing. "
                  f"Using calculated project root: {current_project_root}", file=sys.stderr)
    except ImportError:
        print("Warning: Could not import 'config.py'. "
              f"Using calculated project root: {current_project_root}", file=sys.stderr)

    source_log_path = os.path.join(current_project_root, SOURCE_LOG_FILENAME)
    error_log_path = os.path.join(current_project_root, EXTRACTED_ERROR_LOG_SUBDIR, EXTRACTED_ERROR_LOG_FILENAME)

    process_simulation_log(source_log_path, error_log_path)
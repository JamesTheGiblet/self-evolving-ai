# c:\Users\gilbe\Desktop\self-evolving-ai\reset_simulation.py

import os
import shutil

# Get the absolute path to the directory containing this script
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def delete_pycache_folders(root_dir):
    """
    Recursively delete all __pycache__ folders under the given root directory.
    """
    deleted_count = 0
    # Walk through all directories and subdirectories
    for root, dirs, files in os.walk(root_dir):
        # Check if __pycache__ exists in the current directory
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            try:
                # Remove the __pycache__ directory and its contents
                shutil.rmtree(pycache_path)
                print(f"Deleted: {pycache_path}")
                deleted_count += 1
            except OSError as e:
                print(f"Error deleting {pycache_path}: {e}")
    # Print summary of deletion
    if deleted_count == 0:
        print("No __pycache__ folders found to delete.")
    else:
        print(f"Successfully deleted {deleted_count} __pycache__ folder(s).")

def delete_identity_log(root_dir):
    """
    Delete the identity log file if it exists.
    """
    # Construct the path to the identity log file
    identity_log_path = os.path.join(root_dir, "identity_data", "identity_log.jsonl")
    # Check if the file exists before attempting to delete
    if os.path.exists(identity_log_path):
        try:
            os.remove(identity_log_path)
            print(f"Deleted: {identity_log_path}")
        except OSError as e:
            print(f"Error deleting {identity_log_path}: {e}")
    else:
        print(f"Identity log not found at {identity_log_path}. Nothing to delete.")

def delete_main_simulation_log(root_dir):
    """
    Delete the main simulation log file if it exists.
    """
    # Construct the path to the main simulation log file
    main_log_path = os.path.join(root_dir, "logs", "simulation.log")
    # Check if the file exists before attempting to delete
    if os.path.exists(main_log_path):
        try:
            os.remove(main_log_path)
            print(f"Deleted: {main_log_path}")
        except OSError as e:
            print(f"Error deleting {main_log_path}: {e}")
    else:
        print(f"Main simulation log not found at {main_log_path}. Nothing to delete.")

def clear_directory_contents(dir_path, dir_name_for_log):
    """
    Delete all files and subdirectories in the specified directory.
    """
    # Check if the directory exists and is a directory
    if os.path.exists(dir_path) and os.path.isdir(dir_path):
        print(f"Clearing contents of directory: {dir_path}")
        # Iterate over all items in the directory
        for item_name in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item_name)
            try:
                # Delete files and symbolic links
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    print(f"  Deleted file: {item_path}")
                # Recursively delete subdirectories
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  Deleted directory: {item_path}")
            except Exception as e:
                print(f"  Error deleting {item_path}: {e}")
        print(f"Finished clearing {dir_path}.")
    else:
        print(f"'{dir_name_for_log}' directory not found at {dir_path} or is not a directory. Nothing to clear.")

def clear_logs_directory(root_dir):
    """
    Clear all contents of the 'logs' directory.
    """
    logs_path = os.path.join(root_dir, "logs")
    clear_directory_contents(logs_path, "logs")

def clear_agent_outputs_directory(root_dir):
    """
    Clear all contents of the 'agent_outputs' directory.
    """
    agent_outputs_path = os.path.join(root_dir, "agent_outputs")
    clear_directory_contents(agent_outputs_path, "agent_outputs")

def clear_agent_data_directory(root_dir):
    """
    Clear all contents of the 'agent_data' directory.
    """
    agent_data_path = os.path.join(root_dir, "agent_data")
    clear_directory_contents(agent_data_path, "agent_data")

if __name__ == "__main__":
    # Print the project root directory for reference
    print(f"Project Root: {PROJECT_ROOT}")

    print("\n--- Deleting __pycache__ folders ---")
    delete_pycache_folders(PROJECT_ROOT)

    print("\n--- Deleting identity log ---")
    delete_identity_log(PROJECT_ROOT)

    print("\n--- Deleting main simulation log ---")
    delete_main_simulation_log(PROJECT_ROOT)

    print("\n--- Clearing 'logs' directory ---")
    clear_logs_directory(PROJECT_ROOT)

    print("\n--- Clearing 'agent_outputs' directory ---")
    clear_agent_outputs_directory(PROJECT_ROOT)

    print("\n--- Clearing 'agent_data' directory (other contents) ---")
    clear_agent_data_directory(PROJECT_ROOT)
    print("\nReset script finished.")

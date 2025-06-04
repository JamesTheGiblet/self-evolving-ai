# c:\Users\gilbe\Desktop\self-evolving-ai\reset_simulation.py

import os
import shutil

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def delete_pycache_folders(root_dir):
    """Recursively finds and deletes __pycache__ folders."""
    deleted_count = 0
    for root, dirs, files in os.walk(root_dir):
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache_path)
                print(f"Deleted: {pycache_path}")
                deleted_count += 1
            except OSError as e:
                print(f"Error deleting {pycache_path}: {e}")
    if deleted_count == 0:
        print("No __pycache__ folders found to delete.")
    else:
        print(f"Successfully deleted {deleted_count} __pycache__ folder(s).")

def delete_identity_log(root_dir):
    """Deletes the identity_log.jsonl file."""
    identity_log_path = os.path.join(root_dir, "identity_data", "identity_log.jsonl")
    if os.path.exists(identity_log_path):
        try:
            os.remove(identity_log_path)
            print(f"Deleted: {identity_log_path}")
        except OSError as e:
            print(f"Error deleting {identity_log_path}: {e}")
    else:
        print(f"Identity log not found at {identity_log_path}. Nothing to delete.")

def delete_main_simulation_log(root_dir):
    """Deletes the main simulation.log file."""
    # Assuming the main log file is named 'simulation.log' and is in the project root.
    # Adjust the name if your main log file has a different name or path.
    main_log_path = os.path.join(root_dir, "simulation.log")
    if os.path.exists(main_log_path):
        try:
            os.remove(main_log_path)
            print(f"Deleted: {main_log_path}")
        except OSError as e:
            print(f"Error deleting {main_log_path}: {e}")
    else:
        print(f"Main simulation log not found at {main_log_path}. Nothing to delete.")

if __name__ == "__main__":
    print(f"Project Root: {PROJECT_ROOT}")
    print("\n--- Deleting __pycache__ folders ---")
    delete_pycache_folders(PROJECT_ROOT)

    print("\n--- Deleting identity log ---")
    delete_identity_log(PROJECT_ROOT)
    print("\n--- Deleting main simulation log ---")
    delete_main_simulation_log(PROJECT_ROOT)
    print("\nReset script finished.")
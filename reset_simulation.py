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
    """Deletes the simulation.log file from the 'logs' directory."""
    main_log_path = os.path.join(root_dir, "logs", "simulation.log")
    if os.path.exists(main_log_path):
        try:
            os.remove(main_log_path)
            print(f"Deleted: {main_log_path}")
        except OSError as e:
            print(f"Error deleting {main_log_path}: {e}")
    else:
        print(f"Main simulation log not found at {main_log_path}. Nothing to delete.")

def clear_logs_directory(root_dir):
    """Deletes all files and subdirectories within the 'logs' directory."""
    logs_path = os.path.join(root_dir, "logs")
    if os.path.exists(logs_path) and os.path.isdir(logs_path):
        print(f"Clearing contents of directory: {logs_path}")
        for item_name in os.listdir(logs_path):
            item_path = os.path.join(logs_path, item_name)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    print(f"  Deleted file: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  Deleted directory: {item_path}")
            except Exception as e:
                print(f"  Error deleting {item_path}: {e}")
        print(f"Finished clearing {logs_path}.")
    else:
        print(f"'logs' directory not found at {logs_path} or is not a directory. Nothing to clear.")

def clear_agent_outputs_directory(root_dir):
    """Deletes all files and subdirectories within the 'agent_outputs' directory."""
    agent_outputs_path = os.path.join(root_dir, "agent_outputs")
    if os.path.exists(agent_outputs_path) and os.path.isdir(agent_outputs_path):
        print(f"Clearing contents of directory: {agent_outputs_path}")
        for item_name in os.listdir(agent_outputs_path):
            item_path = os.path.join(agent_outputs_path, item_name)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    print(f"  Deleted file: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  Deleted directory: {item_path}")
            except Exception as e:
                print(f"  Error deleting {item_path}: {e}")
        print(f"Finished clearing {agent_outputs_path}.")
    else:
        print(f"'agent_outputs' directory not found at {agent_outputs_path} or is not a directory. Nothing to clear.")

def clear_agent_data_directory(root_dir):
    """Deletes all files and subdirectories within the 'agent_data' directory."""
    agent_data_path = os.path.join(root_dir, "agent_data")
    if os.path.exists(agent_data_path) and os.path.isdir(agent_data_path):
        print(f"Clearing contents of directory: {agent_data_path}")
        # Note: The identity_log.jsonl file is located in the 'identity_data' directory
        # and is handled by the delete_identity_log() function.
        # This function, clear_agent_data_directory(), is responsible for clearing
        # all contents of the 'agent_data' directory itself.
        for item_name in os.listdir(agent_data_path):
            item_path = os.path.join(agent_data_path, item_name)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    print(f"  Deleted file: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  Deleted directory: {item_path}")
            except Exception as e:
                print(f"  Error deleting {item_path}: {e}")
        print(f"Finished clearing {agent_data_path}.")
    else:
        print(f"'agent_data' directory not found at {agent_data_path} or is not a directory. Nothing to clear.")

if __name__ == "__main__":
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

    # Note: delete_identity_log specifically targets identity_log.jsonl within agent_data.
    # clear_agent_data_directory will clear any other files/folders in agent_data.
    print("\n--- Clearing 'agent_data' directory (other contents) ---")
    clear_agent_data_directory(PROJECT_ROOT) # This will clear remaining contents
    print("\nReset script finished.")
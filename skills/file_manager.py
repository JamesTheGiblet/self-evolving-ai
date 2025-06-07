# skills/file_manager.py

import os
from typing import Dict, Any, Tuple, TYPE_CHECKING
from .base_skill import BaseSkillTool # Import BaseSkillTool
from utils.logger import log # Assuming logger is needed

# For type hinting core components to avoid circular imports at runtime
if TYPE_CHECKING:
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus

def list_directory(path: str) -> Tuple[bool, Dict[str, Any]]:
    """Lists directory contents. Returns (success_bool, result_dict)."""
    if not os.path.exists(path):
        return False, {"error_type": "path_not_found", "message": f"Directory '{path}' not found."}
    if not os.path.isdir(path):
        return False, {"error_type": "not_a_directory", "message": f"Path '{path}' is not a directory."}
    try:
        files = os.listdir(path)
        return True, {"files": files, "path": path}
    except PermissionError:
        return False, {"error_type": "permission_denied", "message": f"Permission denied to list directory '{path}'."}
    except Exception as e:
        return False, {"error_type": "list_error", "message": f"Error listing directory '{path}': {str(e)}"}

def read_file(path: str) -> Tuple[bool, Dict[str, Any]]:
    """Reads file content. Returns (success_bool, result_dict)."""
    if not os.path.exists(path):
        return False, {"error_type": "file_not_found", "message": f"File '{path}' not found."}
    if not os.path.isfile(path):
        return False, {"error_type": "not_a_file", "message": f"Path '{path}' is not a file."}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return True, {"content": content, "path": path}
    except PermissionError:
        return False, {"error_type": "permission_denied", "message": f"Permission denied to read file '{path}'."}
    except Exception as e:
        return False, {"error_type": "read_error", "message": f"Error reading file '{path}': {str(e)}"}

def write_file(path: str, content: str) -> Tuple[bool, Dict[str, Any]]:
    """Writes content to a file. Returns (success_bool, result_dict)."""
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(path)
        if parent_dir: # Check if path includes a directory
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, {"message": f"File '{path}' written successfully.", "path": path, "content_length": len(content)}
    except PermissionError:
        return False, {"error_type": "permission_denied", "message": f"Permission denied to write file '{path}'."}
    except Exception as e:
        return False, {"error_type": "write_error", "message": f"Error writing file '{path}': {str(e)}"}

class FileManager(BaseSkillTool):
    def __init__(self,
                 skill_config: Dict[str, Any],
                 knowledge_base: 'KnowledgeBase',
                 context_manager: 'ContextManager',
                 communication_bus: 'CommunicationBus',
                 agent_name: str,
                 agent_id: str,
                 **kwargs: Any):
        """
        Initializes the FileManager skill.

        Args:
            skill_config (dict): Configuration specific to this skill instance.
            knowledge_base (KnowledgeBase): Instance of the knowledge base.
            context_manager (ContextManager): Instance of the context manager.
            communication_bus (CommunicationBus): Instance of the communication bus.
            agent_name (str): Name of the agent this skill is associated with.
            agent_id (str): ID of the agent this skill is associated with.
        """
        super().__init__(skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id, **kwargs)
        log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}).", level="INFO")

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": "Manages files and directories, allowing for reading, writing, and listing contents.",
            "commands": {
                "list": {
                    "description": "Lists files and subdirectories in a specified directory.",
                    "args_usage": "<directory_path>",
                    "example": "list ./agent_data/",
                    "keywords": ["list files", "list directory", "show folder content", "ls", "dir", "browse files"]
                },
                "read": {
                    "description": "Reads the content of a specified file.",
                    "args_usage": "<filepath>",
                    "example": "read ./documents/report.txt",
                    "keywords": ["read file", "get file content", "open file", "view file", "cat"]
                },
                "write": {
                    "description": "Writes content to a specified file. Overwrites if file exists, creates if not (including parent directories).",
                    "args_usage": "<filepath> \"<content_to_write>\"",
                    "example": "write ./output/notes.txt \"This is an important note.\"",
                    "keywords": ["write file", "save file", "create file", "put content in file", "modify file", "edit file"]
                }
                # Future commands: "delete <filepath>", "create_directory <path>"
            }
        }

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Executes a file management command based on parsed arguments.
        Returns a JSON string via _create_json_response.
        """
        log(f"[{self.skill_name}] Executing with args: {args}", level="INFO")
        command_str_for_logging = " ".join(args)

        if not args:
            return self._build_response_dict(success=False, error="Empty command string.", data={"error_type": "invalid_command"})

        action = args[0].lower()
        
        try:
            if action == "list":
                if len(args) < 2:
                    return self._build_response_dict(success=False, error="'list' command requires a path.", data={"error_type": "invalid_arguments"})
                success, helper_output = list_directory(args[1])
                if success:
                    return self._build_response_dict(success=True, data=helper_output)
                else:
                    return self._build_response_dict(success=False, error=helper_output.get("message"), data={"error_type": helper_output.get("error_type")})

            elif action == "read":
                if len(args) < 2:
                    return self._build_response_dict(success=False, error="'read' command requires a path.", data={"error_type": "invalid_arguments"})
                success, helper_output = read_file(args[1])
                if success:
                    return self._build_response_dict(success=True, data=helper_output)
                else:
                    return self._build_response_dict(success=False, error=helper_output.get("message"), data={"error_type": helper_output.get("error_type")})

            elif action == "write":
                if len(args) < 3:
                    return self._build_response_dict(success=False, error="'write' command requires a path and content.", data={"error_type": "invalid_arguments"})
                # Content is args[2], shlex (in BaseSkill) handles quotes.
                success, helper_output = write_file(args[1], args[2])
                if success:
                    # For write, helper_output contains a success message.
                    # BaseSkill's _build_response_dict doesn't have a top-level "message" field,
                    # so we put it in data.
                    data_for_response = helper_output # helper_output is already a dict
                    return self._build_response_dict(success=True, data=data_for_response)
                else:
                    return self._build_response_dict(success=False, error=helper_output.get("message"), data={"error_type": helper_output.get("error_type")})

            else:
                return self._build_response_dict(success=False, error=f"Unknown file_manager action: '{action}'.", data={"error_type": "unknown_command"})
        except Exception as e:
            # Catch-all for unexpected errors during command parsing or execution
            log(f"[{self.skill_name}] Error during file operation '{command_str_for_logging}': {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error=f"Error processing command '{command_str_for_logging}': {str(e)}", data={"error_type": "execution_error"})

# Example usage (for testing)
# if __name__ == "__main__":
#     fm = FileManager()
#     print(fm.execute("list ./"))
#     print(fm.execute("read ./non_existent_file.txt"))
#     print(fm.execute('write ./agent_outputs/test_fm.txt "Hello from file manager!"'))
#     print(fm.execute("read ./agent_outputs/test_fm.txt"))
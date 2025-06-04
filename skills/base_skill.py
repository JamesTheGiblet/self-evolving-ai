# skills/base_skill.py
import json
import shlex
from typing import Optional, Dict, Any # Added Optional for type hinting
from utils.logger import log # Assuming logger might be useful here

class BaseSkillTool: # Renamed from BaseSkill
    """
    A base class for individual skill tools that parse commands and return JSON.
    """
    def __init__(self, skill_name: str):
        self.skill_name = skill_name

    def _build_response_dict(self, success: bool, data: Optional[dict] = None, error: Optional[str] = None, details: Optional[str] = None) -> Dict[str, Any]:
        """Creates a standardized response dictionary."""
        response = {"success": success}
        if data is not None:
            response["data"] = data
        if error is not None:
            response["error"] = error
        if details is not None: # Added details field
            response["details"] = details
        return response

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Placeholder for actual skill execution logic.
        Subclasses MUST override this method.
        It should return a dictionary, typically by using _build_response_dict.
        """
        log(f"[{self.skill_name}] _execute_skill not implemented.", level="ERROR", exc_info=True)
        return self._build_response_dict(
            success=False,
            error=f"Skill '{self.skill_name}' has not implemented the _execute_skill method."
        )

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Returns a dictionary describing the skill's commands,
        their arguments, and a brief description.
        This method SHOULD be overridden by subclasses to provide specific capabilities.
        Example structure:
        {
            "skill_name": self.skill_name,
            "description": "A brief description of what the skill does overall.",
            "commands": {
                "command_name_1": {
                    "description": "What this command does.",
                    "args_usage": "<arg1_name> [optional_arg2]",
                    "example": "command_name_1 foo bar",
                    "keywords": ["keyword1", "keyword2"] # Keywords to help identify this command
                },
            }
        }
        """
        log(f"Skill '{self.skill_name}' is using the default get_capabilities(). Override for better functionality.", level="WARN")
        return {"skill_name": self.skill_name, "description": "No specific capabilities defined.", "commands": {}}

    def execute(self, command_str: str) -> Dict[str, Any]:
        """
        Parses the command string and calls the skill-specific execution logic.
        This is the main entry point for a skill tool.
        """
        if not command_str.strip():
            return self._build_response_dict(success=False, error="No command provided.")
        try:
            args = shlex.split(command_str)
        except ValueError as e: # Handles shlex parsing errors (e.g., unclosed quotes)
            log(f"[{self.skill_name}] Command parsing error for '{command_str}': {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error="Command parsing error", details=str(e))
        
        return self._execute_skill(args)
# c:\Users\gilbe\Desktop\self-evolving-ai\skills\echo_skill.py
import json
from typing import List, Dict, Any
from skills.base_skill import BaseSkillTool # Assuming this is the correct path to your BaseSkillTool
from utils.logger import log

class EchoSkill(BaseSkillTool):
    """
    A simple skill that echoes back the provided input.
    """
    def __init__(self, knowledge_base=None, context_manager=None, communication_bus=None):
        # Define skill_name before calling super().__init__
        self.skill_name = "EchoSkill" 
        super().__init__(skill_name=self.skill_name) # Pass skill_name to BaseSkillTool
        
        # If EchoSkill (or other skills) need these instances for their own logic,
        # they should be stored as instance attributes here.
        # self.knowledge_base = knowledge_base
        # self.context_manager = context_manager
        # self.communication_bus = communication_bus
        
        self.description = "Echoes back the input string."
        self.commands = {
            "echo": self.echo_command
        }
        log(f"[{self.skill_name}] Skill initialized.", level="INFO")

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Returns a dictionary describing the skill's commands and capabilities.
        """
        return {
            "skill_name": self.skill_name,
            "description": self.description,
            "commands": {
                "echo": {
                    "description": "Echoes the provided arguments back.",
                    "args_usage": "<text_to_echo>",
                    "example": "echo Hello world",
                    "keywords": ["echo", "repeat", "say back"]
                }
                # Add other commands here if EchoSkill had more
            }
        }

    def echo_command(self, *args) -> Dict[str, Any]:
        """
        Echoes the provided arguments back.
        Usage: echo <text to echo>
        """
        if not args:
            # Use self._build_response_dict for standardized output
            # Assuming _build_response_dict is available from BaseSkillTool
            # and handles JSON dumping internally.
            return self._build_response_dict(success=False, error="No text provided to echo.")

        echo_text = " ".join(args)
        # Use self._build_response_dict
        return self._build_response_dict(success=True, data={"echoed_text": echo_text})

    # This method is called by BaseSkillTool.execute() after shlex.split
    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Executes a parsed command.
        """
        if not args:
            return self._build_response_dict(success=False, error="No command provided to _execute_skill.")

        command_name = args[0].lower() # Or keep case if significant
        
        if command_name == "echo":
            return self.echo_command(*args[1:]) # Pass remaining args
        else:
            # Use self._build_response_dict for standardized error handling
            return self._build_response_dict(success=False, error=f"Unknown command: {command_name}")

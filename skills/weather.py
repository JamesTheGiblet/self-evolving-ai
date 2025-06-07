# skills / weather.py

from typing import Dict, Any, TYPE_CHECKING
from .base_skill import BaseSkillTool # Import BaseSkillTool
from utils.logger import log # Assuming logger is needed

# For type hinting core components to avoid circular imports at runtime
if TYPE_CHECKING:
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus

def _get_current_weather(location: str) -> dict:
    """Placeholder function to simulate fetching weather data."""
    log(f"Simulating weather fetch for: {location}", level="DEBUG")
    return {"location": location, "temperature": "22C", "condition": "Sunny"}

class Weather(BaseSkillTool):
    def __init__(self,
                 skill_config: Dict[str, Any],
                 knowledge_base: 'KnowledgeBase',
                 context_manager: 'ContextManager',
                 communication_bus: 'CommunicationBus',
                 agent_name: str,
                 agent_id: str,
                 **kwargs: Any):
        """
        Initializes the Weather skill.

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
            "description": "Provides simulated weather information for a location.",
            "commands": {
                "weather": { # Assuming the command is implicitly 'weather' or the first arg is location
                    "description": "Gets the (simulated) current weather for a specified location.",
                    "args_usage": "<location_name>", # Or "weather <location_name>"
                    "example": "weather London  OR  London",
                    "keywords": ["weather", "forecast", "temperature", "climate", "how's the weather", "what's the weather in"]
                }
            }
        }

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Fetches weather for a given location based on parsed arguments.
        Expected format: "weather <location_name>" or just "<location_name>"
        """
        log(f"[{self.skill_name}] Executing with args: {args}", level="INFO")
        command_str_for_logging = " ".join(args)
        if not args:
            return self._build_response_dict(success=False, error="No location provided for weather skill.")

        command = args[0].lower()

        if command == "weather" and len(args) > 1:
            location = " ".join(args[1:])
        else:
            # If first word isn't "weather", or only one word, treat whole input as location
            location = " ".join(args)

        weather_data = _get_current_weather(location)
        return self._build_response_dict(success=True, data=weather_data)

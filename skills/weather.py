# skills / weather.py

from typing import Dict, Any
from .base_skill import BaseSkillTool # Import BaseSkillTool
from utils.logger import log # Assuming logger is needed

def _get_current_weather(location: str) -> dict:
    """Placeholder function to simulate fetching weather data."""
    log(f"Simulating weather fetch for: {location}", level="DEBUG")
    return {"location": location, "temperature": "22C", "condition": "Sunny"}

class Weather(BaseSkillTool):
    def __init__(self):
        super().__init__(skill_name="Weather")

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

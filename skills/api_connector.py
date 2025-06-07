# skills/api_connector.py

import json
import requests
import time # For retries
from typing import Dict, Any

from utils.logger import log
from .base_skill import BaseSkillTool # Corrected import

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1

def _fetch_from_api(url: str, params: Dict = None, headers: Dict = None) -> tuple[Dict[str, Any] | None, str | None]:
    """
    Fetches data from a given API URL with retry logic.
    Returns (json_response, error_message).
    """
    try:
        default_headers = {
            'User-Agent': 'SelfEvolvingAI/0.1' # Good practice to set a User-Agent
        }
        if headers:
            default_headers.update(headers)

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.get(url, params=params, headers=default_headers, timeout=10) # 10-second timeout
                log(f"[_fetch_from_api] URL: {url}, Attempt: {attempt + 1}, Status: {response.status_code}, Headers: {response.headers}", level="DEBUG")
                log(f"[_fetch_from_api] Raw response text (first 500 chars): {response.text[:500]}", level="DEBUG")
                
                if response.status_code == 429: # Too Many Requests
                    error_message = f"API rate limit hit for '{url}'. Status: {response.status_code}."
                    if attempt < MAX_RETRIES:
                        retry_after = int(response.headers.get("Retry-After", RETRY_DELAY_SECONDS * (attempt + 2)))
                        time.sleep(retry_after)
                        continue
                    else:
                        return None, error_message # Exhausted retries for rate limit

                response.raise_for_status()  # Raises an HTTPError for other bad responses (4XX or 5XX)
                return response.json(), None # Attempt to parse JSON
            
            except requests.exceptions.RequestException as e: # Includes network errors, timeouts, 5xx errors
                error_message = f"API request error for '{url}' (attempt {attempt + 1}/{MAX_RETRIES + 1}): {str(e)}"
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1)) # Simple incremental backoff
                else:
                    return None, error_message # Exhausted retries

    except requests.exceptions.RequestException as e: # Should be caught by inner loop mostly
        return None, f"Outer API request error for '{url}': {str(e)}"
    except json.JSONDecodeError as e:
        response_text_preview = "N/A (response object not available or text attribute missing)"
        if 'response' in locals() and hasattr(response, 'text'):
            response_text_preview = response.text[:200]
        return None, f"Failed to decode JSON response from '{url}': {str(e)}. Response text preview: {response_text_preview}"

class ApiConnector(BaseSkillTool): # Inherit from BaseSkillTool
    def __init__(self, skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id):
        """
        Initializes the ApiConnector skill.

        Args:
            skill_config (dict): Configuration specific to this skill instance.
            knowledge_base (KnowledgeBase): Instance of the knowledge base.
            context_manager (ContextManager): Instance of the context manager.
            communication_bus (CommunicationBus): Instance of the communication bus.
            agent_name (str): Name of the agent this skill is associated with.
            agent_id (str): ID of the agent this skill is associated with.
        """
        super().__init__(
            skill_config=skill_config,
            knowledge_base=knowledge_base,
            context_manager=context_manager,
            communication_bus=communication_bus,
            agent_name=agent_name,
            agent_id=agent_id
            # If ApiConnector had its own **kwargs to pass up, they would go here.
            # Currently, BaseSkillTool's **kwargs catches extras from skill_loader.
        )
        # You can store these arguments as instance variables if ApiConnector needs them later.
        # For example: self.skill_config = skill_config
        log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}).", level="INFO")

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": "Connects to various public APIs to fetch data like jokes, weather, and exchange rates.",
            "commands": {
                "get_joke": {
                    "description": "Fetches a random joke. Can specify category and parameters (e.g., 'Any?safe-mode', 'Programming', 'Christmas?type=single').",
                    "args_usage": "[category_and_params]",
                    "example": "get_joke Programming?safe-mode",
                    "keywords": ["joke", "funny", "laugh", "tell me a joke", "another joke"]
                },
                "get_weather": {
                    "description": "Fetches current weather for a given latitude and longitude.",
                    "args_usage": "<latitude> <longitude>",
                    "example": "get_weather 51.5074 -0.1278",
                    "keywords": ["weather", "forecast", "temperature", "climate", "how's the weather"]
                },
                "get_exchange_rate": {
                    "description": "Fetches exchange rates for a base currency, optionally against a target currency. Uses exchangerate-api.com.",
                    "args_usage": "<base_currency> [target_currency]",
                    "example": "get_exchange_rate USD EUR",
                    "keywords": ["exchange rate", "currency", "money", "forex", "rate", "convert currency"]
                }
            }
        }

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Executes API connection operations based on parsed arguments.
        Commands:
            get_joke [category_and_params]
            get_weather <latitude> <longitude>
            get_exchange_rate <base_currency> [target_currency]
            # Example: get_joke Any?safe-mode
        Always returns a dictionary via _build_response_dict.
        """
        log(f"[{self.skill_name}] Executing with args: {args}", level="INFO")
        command_str_for_logging = " ".join(args)

        if not args:
            return self._build_response_dict(success=False, error="No command provided to api_connector.")

        command = args[0].lower()

        try:
            if command == "get_joke":
                joke_api_url_base = "https://v2.jokeapi.dev/joke/"
                path_and_params = args[1] if len(args) > 1 else "Any?safe-mode"
                full_joke_api_url = joke_api_url_base + path_and_params
                
                data, error = _fetch_from_api(full_joke_api_url)
                if error:
                    return self._build_response_dict(success=False, error=error, data={"url_called": full_joke_api_url, "operation_status": "failure_get_joke"})
                else:
                    return self._build_response_dict(success=True, data={"url_called": full_joke_api_url, "joke_data": data, "operation_status": "success_get_joke"})
            
            elif command == "get_weather" and len(args) == 3:
                try:
                    latitude = float(args[1])
                    longitude = float(args[2])
                    weather_api_url = "https://api.open-meteo.com/v1/forecast"
                    params = {"latitude": latitude, "longitude": longitude, "current_weather": "true"}
                    data, error = _fetch_from_api(weather_api_url, params=params)
                    if error:
                        return self._build_response_dict(success=False, error=error, data={"latitude": latitude, "longitude": longitude, "operation_status": "failure_get_weather"})
                    else:
                        return self._build_response_dict(success=True, data={"latitude": latitude, "longitude": longitude, "weather_data": data, "operation_status": "success_get_weather"})
                except ValueError: # Handles float conversion errors for lat/lon
                    return self._build_response_dict(success=False, error="Invalid latitude or longitude format for get_weather.")
            
            elif command == "get_exchange_rate" and (len(args) == 2 or len(args) == 3):
                base_currency = args[1].upper()
                target_currency = args[2].upper() if len(args) == 3 else None
                exchange_api_url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
                
                data, error = _fetch_from_api(exchange_api_url)
                if error:
                    return self._build_response_dict(success=False, error=error, data={"base_currency": base_currency, "operation_status": "failure_get_exchange_rate"})
                else:
                    if target_currency and data.get("rates") and target_currency in data["rates"]:
                        return self._build_response_dict(success=True, data={"base_currency": base_currency, "target_currency": target_currency, "rate": data["rates"][target_currency], "operation_status": "success_get_exchange_rate"})
                    elif not target_currency: # Return all rates if no target is specified
                        return self._build_response_dict(success=True, data={"base_currency": base_currency, "all_rates": data.get("rates", {}), "operation_status": "success_get_exchange_rate"})
                    else: # Target currency specified but not found
                        return self._build_response_dict(success=False, error=f"Target currency '{target_currency}' not found in rates.", data={"base_currency": base_currency, "target_currency": target_currency, "available_rates_preview": list(data.get("rates", {}).keys())[:10], "operation_status": "failure_get_exchange_rate_target_not_found"})
            else:
                error_msg = f"Unknown command or incorrect arguments. Supported: 'get_joke [params]', 'get_weather <lat> <lon>', 'get_exchange_rate <base> [target]'. Received: '{command_str_for_logging}'"
                return self._build_response_dict(success=False, error=error_msg)
        except Exception as e: # Catch-all for unexpected errors during command processing
            log(f"[{self.skill_name}] Error during API operation '{command_str_for_logging}': {e}", level="ERROR", exc_info=True)
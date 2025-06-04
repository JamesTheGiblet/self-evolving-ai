# skills / calander.py

import datetime
from typing import Any, Dict
from .base_skill import BaseSkillTool # Import BaseSkillTool
from utils.logger import log # Assuming logger is needed

def _get_current_date() -> str:
    """Returns the current date as a string in YYYY-MM-DD format."""
    return datetime.date.today().isoformat()

def _validate_date(date_str: str) -> bool:
    """Check if the date string is a valid YYYY-MM-DD date."""
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

class Calendar(BaseSkillTool):
    def __init__(self, memory_store: dict): # Calendar now requires a memory store
        super().__init__(skill_name="Calendar")
        self.memory_store = memory_store # Store the shared memory object

    def _add_calendar_event(self, event_name: str, event_date: str) -> dict:
        """Adds an event to the in-memory calendar using self.memory_store."""
        calendar_events = self.memory_store.setdefault('calendar_events', {})
        date_events = calendar_events.setdefault(event_date, [])
        
        for event in date_events:
            if event.get("name") == event_name:
                return {"event_name": event_name, "date": event_date, "status": "failed_duplicate_event_on_date"}
                
        date_events.append({"name": event_name, "details": "No details provided"})
        return {"event_name": event_name, "date": event_date, "status": "scheduled"}

    def _list_events(self, event_date: str) -> list:
        """Lists events for a specific date from self.memory_store."""
        calendar_events = self.memory_store.get('calendar_events', {})
        return calendar_events.get(event_date, [])

    def _list_all_events(self) -> dict:
        """Lists all events from self.memory_store, grouped by date."""
        return self.memory_store.get('calendar_events', {})

    def _remove_event(self, event_name: str, event_date: str) -> dict:
        """Removes an event from self.memory_store."""
        calendar_events = self.memory_store.get('calendar_events', {})
        if not calendar_events or event_date not in calendar_events: # Check if calendar_events is None or empty
            # If the date itself isn't found, or if the calendar_events dict is empty/None
            return {"event_name": event_name, "date": event_date, "status": "failed_date_not_found"}

        date_events = calendar_events[event_date]
        event_found = False
        for i, event in enumerate(date_events):
            if event.get("name") == event_name:
                del date_events[i]
                event_found = True
                break
        
        return {"event_name": event_name, "date": event_date, "status": "removed" if event_found else "failed_event_not_found_on_date"}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": "Manages calendar events, allowing for adding, listing, and removing events.",
            "commands": {
                "current_date": {
                    "description": "Gets the current date.",
                    "args_usage": "",
                    "example": "current_date",
                    "keywords": ["today's date", "current date", "what day is it", "date now"]
                },
                "add_event": {
                    "description": "Adds an event to the calendar for a specific date.",
                    "args_usage": "\"<event_name>\" <yyyy-mm-dd>",
                    "example": "add_event \"Team Meeting\" 2024-07-15",
                    "keywords": ["add event", "schedule event", "new calendar entry", "book meeting"]
                },
                "list_events": {
                    "description": "Lists all events scheduled for a specific date.",
                    "args_usage": "<yyyy-mm-dd>",
                    "example": "list_events 2024-07-15",
                    "keywords": ["list events", "show events for date", "what's scheduled on", "view calendar for date"]
                },
                "list_all_events": {
                    "description": "Lists all scheduled events, grouped by date.",
                    "args_usage": "",
                    "example": "list_all_events",
                    "keywords": ["list all events", "show all scheduled events", "view entire calendar", "all appointments"]
                },
                "remove_event": {
                    "description": "Removes a specific event from a given date.",
                    "args_usage": "\"<event_name>\" <yyyy-mm-dd>",
                    "example": "remove_event \"Team Meeting\" 2024-07-15",
                    "keywords": ["remove event", "delete event", "cancel event", "unschedule"]
                }
            }
        }

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Executes calendar operations based on parsed arguments.
        Uses self.memory_store for event storage.
        """
        log.info(f"[{self.skill_name}] Executing with args: {args}")
        command_str_for_logging = " ".join(args)

        if not args:
            return self._build_response_dict(success=False, error="No command provided. Supported: 'current_date', 'add_event', 'list_events', 'list_all_events', 'remove_event'.")

        command = args[0].lower()

        try:
            if command == "current_date":
                return self._build_response_dict(success=True, data={"current_date": _get_current_date()})
            elif command == "add_event":
                if len(args) != 3:
                    return self._build_response_dict(success=False, error="Incorrect arguments for 'add_event'. Usage: add_event \"<event_name>\" <yyyy-mm-dd>")
                event_name, event_date = args[1], args[2]
                if not _validate_date(event_date):
                    return self._build_response_dict(success=False, error=f"Invalid date format '{event_date}'. Use YYYY-MM-DD.")
                result = self._add_calendar_event(event_name, event_date) # Uses self.memory_store
                return self._build_response_dict(success="failed" not in result.get("status", ""), data=result)
            elif command == "list_events":
                if len(args) != 2:
                    return self._build_response_dict(success=False, error="Incorrect arguments for 'list_events'. Usage: list_events <yyyy-mm-dd>")
                event_date = args[1]
                if not _validate_date(event_date):
                    return self._build_response_dict(success=False, error=f"Invalid date format '{event_date}'. Use YYYY-MM-DD.")
                events = self._list_events(event_date) # Uses self.memory_store
                return self._build_response_dict(success=True, data={"date": event_date, "events": events})
            elif command == "list_all_events":
                all_events = self._list_all_events() # Uses self.memory_store
                return self._build_response_dict(success=True, data=all_events)
            elif command == "remove_event":
                if len(args) != 3:
                    return self._build_response_dict(success=False, error="Incorrect arguments for 'remove_event'. Usage: remove_event \"<event_name>\" <yyyy-mm-dd>")
                event_name, event_date = args[1], args[2]
                if not _validate_date(event_date):
                    return self._build_response_dict(success=False, error=f"Invalid date format '{event_date}'. Use YYYY-MM-DD.")
                result = self._remove_event(event_name, event_date) # Uses self.memory_store
                return self._build_response_dict(success="failed" not in result.get("status", ""), data=result)
            else:
                return self._build_response_dict(success=False, error=f"Unknown command '{command}'. Supported: 'current_date', 'add_event', 'list_events', 'list_all_events', 'remove_event'.")
        except Exception as e:
            log.error(f"[{self.skill_name}] Error during calendar operation '{command_str_for_logging}': {e}", exc_info=True)
            return self._build_response_dict(success=False, error=f"An unexpected error occurred: {str(e)}", data={"input_command": command_str_for_logging})

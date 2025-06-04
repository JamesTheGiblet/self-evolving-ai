# c:/Users/gilbe/Desktop/self-evolving-ai/core/skill_handlers.py
import json
import re
import math
import statistics
from collections import Counter
from typing import Any, Dict, List
from utils.logger import log

# Assume your skill modules are importable like this.
# These would be the refactored skill modules that now use BaseSkillTool.
from skills import web_scraper
from skills import file_manager # Example, create this file similarly to web_scraper
from skills import api_connector # Example, create this file
from skills import maths_tool    # Example, create this file
from core.utils.data_extraction import _extract_data_recursively # Import the helper

# Import constants for stop words
from core.constants import DEFAULT_STOP_WORDS

def _call_and_parse_tool_output(tool_module, command_str: str, skill_name: str, agent_name: str) -> dict:
    """
    Calls the execute method of a given tool_module, parses its JSON string output.
    Handles potential JSONDecodeError if the output is not valid JSON.
    The tool_module.execute() is expected to return a JSON string,
    ideally structured by BaseSkillTool._create_json_response.
    """
    log_msg_prefix = f"Agent '{agent_name}' (SkillHandler for '{skill_name}')"
    raw_output_str = None  # Initialize for error logging
    tool_instance = None
    try:
        # Instantiate the tool class from the module.
        # Assumes the class name is the capitalized version of the skill_name or a known mapping.
        # For example, if skill_name is "file_manager", class name is "FileManager".
        # This part might need a more robust way to get the class name if it doesn't follow a convention.
        class_name_candidate = "".join(word.capitalize() for word in skill_name.split('_')) # e.g., file_manager -> FileManager
        # Handle specific cases for skill_name -> class_name mapping if not straightforward
        if skill_name == "web_scraper": class_name_candidate = "WebScraper"
        elif skill_name == "file_manager": class_name_candidate = "FileManager"
        elif skill_name == "api_connector": class_name_candidate = "ApiConnector"
        elif skill_name == "maths_tool": class_name_candidate = "MathsTool"
        # Add other specific mappings here as needed

        if hasattr(tool_module, class_name_candidate):
            ToolClass = getattr(tool_module, class_name_candidate)
            tool_instance = ToolClass() # Assumes constructor takes no args or uses defaults
            raw_output_str = tool_instance.execute(command_str)
        else:
            # Fallback to module-level execute if no class_name_candidate found or class method doesn't exist
            if hasattr(tool_module, 'execute') and callable(tool_module.execute):
                raw_output_str = tool_module.execute(command_str)
            else:
                raise AttributeError(f"Class {class_name_candidate} not found or module-level execute method missing in module {tool_module.__name__}")
        
        parsed_output = json.loads(raw_output_str)
        return parsed_output  # This dict will have {"success": True/False, "data": ..., "error": ...}

    except json.JSONDecodeError as e:
        log(f"{log_msg_prefix}: Failed to decode JSON output. Error: {e}. Raw: '{raw_output_str}'", level="ERROR")
        return {"success": False, "error": f"JSON decode error from {skill_name}", "details": str(e), "raw_output": raw_output_str}
    except Exception as e:
        # This catches errors from tool_module.execute() if it fails before returning a string,
        # or other unexpected issues.
        log(f"{log_msg_prefix}: Unexpected error during execution or parsing. Command: '{command_str}'. Error: {e}", level="ERROR", exc_info=True)
        return {"success": False, "error": f"Execution or parsing error in {skill_name}", "details": str(e)}

def _generic_handle_operation(agent_name: str, command_str: str, context_manager, tool_module, skill_name: str) -> dict:
    """
    Generic handler for operations, using _call_and_parse_tool_output.
    context_manager is passed but may not be used directly in this refactored version.
    """
    log(f"Agent '{agent_name}' attempting {skill_name} operation: '{command_str}'", level="INFO")
    
    tool_result = _call_and_parse_tool_output(tool_module, command_str, skill_name, agent_name)

    if tool_result.get("success"): # This 'success' key is from the tool's JSON response
        log(f"Agent '{agent_name}': {skill_name} operation successful. Full tool response: {tool_result}", level="DEBUG")
        # The skill_handler's response structure. We pass the whole tool_result as data.
        # The tool_result itself contains "data", "error", "details" keys as appropriate.
        return {"status": "success", "data": tool_result}
    else:
        log(f"Agent '{agent_name}': {skill_name} operation failed. Error: {tool_result.get('error')}, Details: {tool_result.get('details')}", level="WARN")
        return {
            "status": "error", 
            "message": tool_result.get("error", f"Unknown error from {skill_name}"), 
            "details": tool_result.get("details"),
            "raw_output": tool_result.get("raw_output") # Propagate raw_output if JSON parsing failed
        }

# --- Specific Skill Handlers ---

def handle_web_operation(agent_name: str, command_str: str, context_manager) -> dict:
    """Handles web scraping operations."""
    return _generic_handle_operation(agent_name, command_str, context_manager, web_scraper, "web_scraper")

def handle_file_operation(agent_name: str, command_str: str, context_manager) -> dict:
    """Handles file system operations."""
    return _generic_handle_operation(agent_name, command_str, context_manager, file_manager, "file_manager")

def handle_api_call(agent_name: str, command_str: str, context_manager) -> dict:
    """Handles generic API calls."""
    return _generic_handle_operation(agent_name, command_str, context_manager, api_connector, "api_connector")

def handle_maths_operation(agent_name: str, command_str: str, context_manager) -> dict:
    """Handles mathematical operations."""
    return _generic_handle_operation(agent_name, command_str, context_manager, maths_tool, "maths_tool")

def handle_basic_stats(agent_name: str, command_str: str, context_manager) -> dict:
    """Performs basic statistical analysis on provided JSON data."""
    log_msg_prefix = f"Agent '{agent_name}' (SkillHandler for 'basic_stats')"
    log(f"{log_msg_prefix} attempting operation with command_str: {command_str}", level="INFO")
    try:
        data_payload = json.loads(command_str) # Expects a JSON string of data
        data_points = data_payload.get("data_points", [])

        extracted_numbers: List[float] = []
        extracted_texts: List[str] = []
        _extract_data_recursively(data_points, extracted_numbers, extracted_texts)

        details: Dict[str, Any] = {
            "input_item_count": len(data_points),
            "extracted_numbers_count": len(extracted_numbers),
            "extracted_texts_count": len(extracted_texts),
            "analysis_type": "basic_stats"
        }
        outcome = "success_no_data_analyzed"
        immediate_reward = 0.1

        if extracted_numbers:
            num_analysis = {}
            num_analysis["sum"] = sum(extracted_numbers)
            num_analysis["mean"] = num_analysis["sum"] / len(extracted_numbers) if extracted_numbers else 0
            num_analysis["min"] = min(extracted_numbers) if extracted_numbers else None
            num_analysis["max"] = max(extracted_numbers) if extracted_numbers else None
            num_analysis["count"] = len(extracted_numbers)

            # Simple std dev (population)
            if len(extracted_numbers) > 0:
                variance = sum([(x - num_analysis["mean"]) ** 2 for x in extracted_numbers]) / len(extracted_numbers)
                num_analysis["std_dev_population"] = math.sqrt(variance)
            else:
                num_analysis["std_dev_population"] = 0

            details["numerical_analysis"] = num_analysis
            outcome = "success_numerical_analysis"
            immediate_reward += 0.3 + min(len(extracted_numbers) * 0.01, 0.2)
            log(f"{log_msg_prefix}: Numerical analysis performed. Mean: {num_analysis['mean']:.2f}")

        if extracted_texts:
            txt_analysis = {}
            full_text = " ".join(extracted_texts)
            words = re.findall(r'\b\w+\b', full_text.lower())
            filtered_words = [word for word in words if word not in DEFAULT_STOP_WORDS and len(word) > 2 and not word.isdigit()]
            word_counts = Counter(filtered_words)
            txt_analysis["top_keywords"] = word_counts.most_common(5) # Top 5 keywords

            details["textual_analysis"] = txt_analysis
            if outcome == "success_numerical_analysis":
                outcome = "success_mixed_analysis"
            else:
                outcome = "success_textual_analysis"
            immediate_reward += 0.2 + min(len(extracted_texts) * 0.001, 0.2)
            log(f"{log_msg_prefix}: Textual analysis performed. Top keywords: {txt_analysis['top_keywords']}")

        if not extracted_numbers and not extracted_texts:
            outcome = "failure_no_data_extracted"
            immediate_reward = -0.1
            log(f"{log_msg_prefix}: No numerical or textual data extracted from input.", level="WARN")

        return {"status": "success", "data": {"outcome": outcome, "details": details, "reward": immediate_reward}}
    except json.JSONDecodeError as e:
        log(f"{log_msg_prefix}: Failed to decode JSON for basic_stats. Error: {e}. Raw: '{command_str}'", level="ERROR")
        return {"status": "error", "message": "Invalid JSON data for basic_stats", "details": str(e)}
    except Exception as e:
        log(f"{log_msg_prefix}: Unexpected error during basic_stats. Error: {e}", level="ERROR", exc_info=True)
        return {"status": "error", "message": f"Execution error in basic_stats", "details": str(e)}


def handle_log_summary(agent_name: str, command_str: str, context_manager) -> dict:
    """Handles log summary operations. Expects command_str to be a JSON string of the data."""
    log_msg_prefix = f"Agent '{agent_name}' (SkillHandler for 'log_summary')"
    log(f"{log_msg_prefix} attempting operation with command_str: {command_str}", level="INFO")
    try:
        data_payload = json.loads(command_str)
        log_entries = data_payload.get("data_points", [])

        # Simple log summary: count entries, count keywords
        log_entries_count = len(log_entries)
        keyword_counts = Counter()
        
        # Define keywords to track (can be configurable)
        keywords_to_track = ["error", "failure", "success", "warning", "info", "debug", "critical", "timeout"]

        for entry in log_entries:
            if isinstance(entry, dict):
                # Concatenate string values from dict for search
                text_to_search = " ".join(str(v) for v in entry.values() if isinstance(v, str))
            elif isinstance(entry, str):
                text_to_search = entry
            else:
                continue # Skip non-string/non-dict entries

            for keyword in keywords_to_track:
                if keyword in text_to_search.lower():
                    keyword_counts[keyword] += 1

        summary_result = {
            "log_entries_count": log_entries_count,
            "keyword_counts": dict(keyword_counts)
        }

        log(f"{log_msg_prefix}: log_summary operation successful. Result: {summary_result}", level="DEBUG")
        return {"status": "success", "data": summary_result}
    except json.JSONDecodeError as e:
        log(f"{log_msg_prefix}: Failed to decode JSON for log_summary. Error: {e}. Raw: '{command_str}'", level="ERROR")
        return {"status": "error", "message": "Invalid JSON data for log_summary", "details": str(e)}
    except Exception as e:
        log(f"{log_msg_prefix}: Unexpected error during log_summary. Error: {e}", level="ERROR", exc_info=True)
        return {"status": "error", "message": f"Execution error in log_summary", "details": str(e)}

def handle_generic_complexity(agent_name: str, command_str: str, context_manager) -> dict:
    """Analyzes the complexity of provided JSON data."""
    log_msg_prefix = f"Agent '{agent_name}' (SkillHandler for 'complexity')"
    log(f"{log_msg_prefix} attempting operation with command_str: {command_str}", level="INFO")
    try:
        data_payload = json.loads(command_str)
        data_points = data_payload.get("data_points", [])

        # Simple complexity metric: sum of lengths of string representation of items
        # plus a factor for nested structures.
        complexity_score = 0
        items_processed = 0

        for item in data_points:
            items_processed += 1
            item_str = str(item)
            complexity_score += len(item_str) # Base on string length

            if isinstance(item, (list, dict)):
                complexity_score += (len(item_str) * 0.1) # Bonus for structured data

        final_complexity_score = complexity_score * 0.01 # Scale down for readability

        summary_result = {
            "items_processed": items_processed,
            "complexity_score": final_complexity_score
        }

        log(f"{log_msg_prefix}: Complexity analysis performed. Score: {final_complexity_score:.2f}", level="DEBUG")
        return {"status": "success", "data": summary_result}
    except json.JSONDecodeError as e:
        log(f"{log_msg_prefix}: Failed to decode JSON for complexity. Error: {e}. Raw: '{command_str}'", level="ERROR")
        return {"status": "error", "message": "Invalid JSON data for complexity", "details": str(e)}
    except Exception as e:
        log(f"{log_msg_prefix}: Unexpected error during complexity analysis. Error: {e}", level="ERROR", exc_info=True)
        return {"status": "error", "message": f"Execution error in complexity", "details": str(e)}
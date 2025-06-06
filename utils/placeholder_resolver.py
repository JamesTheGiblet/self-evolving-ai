# core/utils/placeholder_resolver.py

from typing import Any, Dict, List, Optional
import re
from utils.logger import log

# Assuming _extract_data_recursively is available and correctly resolves paths in nested dicts/lists
from .data_extraction import _extract_data_recursively as get_value_from_path

PLACEHOLDER_PATTERN = re.compile(r"<FROM_PREVIOUS_STEP:([^>]+)>")

def resolve_placeholders(item_to_resolve: Any, previous_step_output: Optional[Dict[str, Any]]) -> Any:
    """
    Recursively resolves placeholders like "<FROM_PREVIOUS_STEP:key.subkey>"
    within a given item (string, list, or dictionary) using data from
    the previous_step_output.

    Args:
        item_to_resolve: The item (string, list, dict) containing potential placeholders.
        previous_step_output: The output from the previous step, used as context for resolution.
                              Can be None if there's no previous step.

    Returns:
        The item with placeholders resolved. If a placeholder cannot be resolved,
        it remains as is.
    """
    if isinstance(item_to_resolve, dict):
        resolved_dict = {}
        for key, value in item_to_resolve.items():
            resolved_dict[key] = resolve_placeholders(value, previous_step_output)
        return resolved_dict
    elif isinstance(item_to_resolve, list):
        return [resolve_placeholders(element, previous_step_output) for element in item_to_resolve]
    elif isinstance(item_to_resolve, str):
        match = PLACEHOLDER_PATTERN.fullmatch(item_to_resolve) # Check if the entire string is a placeholder
        if match:
            if previous_step_output is None:
                log(f"Placeholder '{item_to_resolve}' found but no previous_step_output to resolve from. Placeholder remains.", level="DEBUG")
                return item_to_resolve # Return original placeholder

            path = match.group(1)
            resolved_value = get_value_from_path(previous_step_output, path)
            if resolved_value is not None:
                log(f"Resolved placeholder '{item_to_resolve}' to value (type: {type(resolved_value)}): {str(resolved_value)[:100]}", level="TRACE")
                return resolved_value
            else:
                log(f"Could not resolve placeholder path '{path}' from previous step output. Placeholder '{item_to_resolve}' remains.", level="DEBUG")
                return item_to_resolve # Return original placeholder if path not found or resolves to None explicitly from path
        return item_to_resolve # Not a placeholder string, or not a full-match placeholder
    else:
        return item_to_resolve # Not a string, list, or dict (e.g., int, float, bool)
# core/utils/data_extraction.py
import re
import math # For isfinite check
from typing import List, Any, Dict, Optional

def _extract_data_recursively(item: Any, numbers: List[float], texts: List[str]):
    """
    Recursively extracts numerical and textual data from various structures.
    Numbers are parsed from strings if possible.
    Ensures that only finite numbers are added.
    """
    if isinstance(item, (int, float)):
        if math.isfinite(item):
            numbers.append(float(item))
    elif isinstance(item, str):
        texts.append(item) # Add the original string to texts
        # Try to extract numbers from string
        found_numbers_in_str = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", item)
        for num_str in found_numbers_in_str:
            try:
                num = float(num_str)
                if math.isfinite(num):
                    numbers.append(num) # Add successfully parsed finite numbers
            except ValueError:
                pass  # Not a valid float, ignore
    elif isinstance(item, list):
        for sub_item in item:
            _extract_data_recursively(sub_item, numbers, texts)
    elif isinstance(item, dict):
        for key, value in item.items():
            # Optionally, process keys as text:
            # _extract_data_recursively(str(key), numbers, texts)
            _extract_data_recursively(value, numbers, texts)

def _get_value_from_path(data_dict: Optional[Dict[str, Any]], path: str) -> Any:
    """
    Helper to get a value from a nested dict using a dot-separated path.
    Supports accessing list elements by index.
    """
    if not isinstance(data_dict, dict) or not path:
        return None
    keys = path.split('.')
    current_val: Any = data_dict
    for key in keys:
        if isinstance(current_val, dict):
            current_val = current_val.get(key)
        elif isinstance(current_val, list) and key.isdigit():
            try:
                current_val = current_val[int(key)]
            except (IndexError, ValueError):
                return None
        else:
            return None
        if current_val is None: # Check after each access
            return None
    return current_val
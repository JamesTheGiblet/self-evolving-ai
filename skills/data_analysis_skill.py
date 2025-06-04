# skills/data_analysis_skill.py

import json
import statistics
from collections import Counter
import re
from typing import Any, Dict, List
from skills.base_skill import BaseSkillTool
from utils.logger import log
from core.utils.data_extraction import _extract_data_recursively # Assuming this utility is available
from core.constants import DEFAULT_STOP_WORDS # Assuming this utility is available

class DataAnalysisSkillTool(BaseSkillTool): # Inherits from BaseSkillTool
    skill_name: str = "DataAnalysis"
    skill_description: str = "Performs various data analysis tasks like summarization, statistics, and pattern matching."

    def __init__(self, *args, **kwargs):
        # Ensure the skill_name class attribute is passed to the BaseSkillTool's constructor.
        # Any other arguments passed by skill_loader during instantiation will be handled by *args, **kwargs.
        super().__init__(skill_name=self.skill_name, *args, **kwargs)


    def get_capabilities(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "description": self.skill_description,
            "commands": {
                "log_summary": {
                    "description": "Generates a summary of log data.",
                    "args_usage": "<json_string_with_data_points_and_analysis_type>",
                    "example": 'log_summary {"data_points": [{"level": "INFO", "message": "User logged in"}, {"level": "ERROR", "message": "DB connection failed"}], "analysis_type": "log_summary"}'
                },
                "complexity_analysis": {
                    "description": "Analyzes the complexity of provided data.",
                    "args_usage": "<json_string_with_data_points_and_analysis_type>",
                    "example": 'complexity_analysis {"data_points": [1, {"a": [2,3]}, "hello"], "analysis_type": "complexity_analysis"}'
                },
                "basic_stats_analysis": {
                    "description": "Calculates basic statistics for numerical data.",
                    "args_usage": "<json_string_with_data_points_and_analysis_type>",
                    "example": 'basic_stats_analysis {"data_points": [10, 20, 30, 20], "analysis_type": "basic_stats_analysis"}'
                },
                "advanced_stats": {
                    "description": "Calculates advanced statistics for numerical data.",
                    "args_usage": "<json_string_with_data_points_and_analysis_type>",
                    "example": 'advanced_stats {"data_points": [10, 20, 30, 20, 25], "analysis_type": "advanced_stats"}'
                },
                "keyword_search": {
                    "description": "Searches for keywords in textual data.",
                    "args_usage": "<json_string_with_data_points_keywords_and_analysis_type>",
                    "example": 'keyword_search {"data_points": ["log message one", "another error log"], "keywords": ["error", "one"], "analysis_type": "keyword_search"}'
                },
                "regex_match": {
                    "description": "Matches a regex pattern in textual data.",
                    "args_usage": "<json_string_with_data_points_pattern_and_analysis_type>",
                    "example": 'regex_match {"data_points": ["email: test@example.com"], "regex_pattern": "\\\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Z|a-z]{2,}\\\\b", "analysis_type": "regex_match"}'
                },
                "correlation": {
                    "description": "Calculates correlation between numerical series (expects structured input).",
                    "args_usage": "<json_string_with_named_series_and_analysis_type>",
                    "example": 'correlation {"series_a": [1,2,3], "series_b": [2,4,6], "analysis_type": "correlation"}'
                }
            }
        }

    def execute(self, command_str: str) -> Dict[str, Any]:
        log(f"[{self.skill_name}] Received command_str: {command_str[:200]}...", level="DEBUG")
        try:
            payload = json.loads(command_str)
            analysis_type = payload.get("analysis_type")
            data_points = payload.get("data_points", []) # Default for most types

            extracted_numbers: List[float] = []
            extracted_texts: List[str] = []
            # For correlation, data_points might be a dict of series
            if analysis_type == "correlation" and isinstance(payload, dict):
                 _extract_data_recursively(payload, extracted_numbers, extracted_texts) # Extract from all values if it's a dict of series
            else:
                _extract_data_recursively(data_points, extracted_numbers, extracted_texts)

            result_data = {"analysis_type_processed": analysis_type}

            if analysis_type == "log_summary":
                # Simplified summary
                result_data["summary"] = f"Processed {len(data_points)} log entries. Found {len(extracted_texts)} text segments."
                return self._build_response_dict(success=True, data=result_data, error="Log summary generated.")
            
            elif analysis_type == "complexity_analysis":
                # Simplified complexity
                result_data["complexity_score"] = sum(len(str(item)) for item in data_points) * 0.1
                return self._build_response_dict(success=True, data=result_data, error="Complexity analysis performed.")

            elif analysis_type == "basic_stats_analysis":
                if extracted_numbers:
                    result_data["mean"] = statistics.mean(extracted_numbers) if extracted_numbers else 0
                    result_data["count"] = len(extracted_numbers)
                    return self._build_response_dict(success=True, data=result_data, error="Basic stats calculated.")
                else:
                    return self._build_response_dict(success=False, data=result_data, error="No numerical data for basic_stats_analysis.")
            
            elif analysis_type == "advanced_stats":
                if extracted_numbers and len(extracted_numbers) > 1:
                    result_data["median"] = statistics.median(extracted_numbers)
                    result_data["stdev"] = statistics.stdev(extracted_numbers)
                    return self._build_response_dict(success=True, data=result_data, error="Advanced stats calculated.")
                elif extracted_numbers: # Only one number
                    result_data["median"] = extracted_numbers[0]
                    result_data["stdev"] = 0
                    return self._build_response_dict(success=True, data=result_data, error="Advanced stats (single point) calculated.")
                else:
                    return self._build_response_dict(success=False, data=result_data, error="Insufficient numerical data for advanced_stats.")

            # Add more handlers here for keyword_search, regex_match, correlation
            # For now, they will fall through to the "not implemented" case.

            else:
                log(f"[{self.skill_name}] Analysis type '{analysis_type}' not fully implemented in this skill tool.", level="WARN")
                return self._build_response_dict(success=False, data=result_data, error=f"Analysis type '{analysis_type}' recognized but not fully implemented by DataAnalysisSkillTool.")

        except json.JSONDecodeError as e:
            log(f"[{self.skill_name}] Error decoding JSON command: {e}. Command: {command_str}", level="ERROR")
            return self._build_response_dict(success=False, error=f"Invalid JSON in command: {e}")
        except Exception as e:
            log(f"[{self.skill_name}] Error executing command '{command_str[:50]}...': {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error=f"Execution error: {e}")
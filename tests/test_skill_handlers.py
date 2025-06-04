import pytest
import json
from unittest.mock import patch, MagicMock

from core import skill_handlers # Import the module we are testing

class TestBasicSkillHandlers:
    def test_handle_basic_stats(self):
        input_data = {"data_points": [1, 2, 3, 4, 5, "not_a_number"]}
        expected_output = {
            "count": 5,
            "sum": 15,
            "mean": 3.0,
            "min": 1,
            "max": 5,
        }
        assert skill_handlers.handle_basic_stats(input_data) == expected_output

    def test_handle_basic_stats_empty(self):
        input_data = {"data_points": []}
        expected_output = {
            "count": 0,
            "sum": 0,
            "mean": 0,
            "min": None,
            "max": None,
        }
        assert skill_handlers.handle_basic_stats(input_data) == expected_output

    def test_handle_basic_stats_no_data_points_key(self):
        input_data = {} # "data_points" key is missing
        expected_output = { # Should default to empty list
            "count": 0,
            "sum": 0,
            "mean": 0,
            "min": None,
            "max": None,
        }
        assert skill_handlers.handle_basic_stats(input_data) == expected_output

    def test_handle_log_summary_strings(self):
        input_data = {"data_points": ["error in system", "action success", "another error"]}
        result = skill_handlers.handle_log_summary(input_data)
        assert result["log_entries_count"] == 3
        assert result["keyword_counts"]["error"] == 2
        assert result["keyword_counts"]["success"] == 1
        assert result["keyword_counts"]["action"] == 1

    def test_handle_log_summary_dicts(self):
        input_data = {"data_points": [
            {"content": "system error detected", "outcome": "failure"},
            {"content": "user action completed", "outcome": "success"},
        ]}
        result = skill_handlers.handle_log_summary(input_data)
        assert result["log_entries_count"] == 2
        assert result["keyword_counts"]["error"] == 1
        assert result["keyword_counts"]["success"] == 1
        assert result["keyword_counts"]["action"] == 1 # "action completed"

    def test_handle_log_summary_empty(self):
        input_data = {"data_points": []}
        result = skill_handlers.handle_log_summary(input_data)
        assert result["log_entries_count"] == 0
        assert result["keyword_counts"] == {"error": 0, "success": 0, "action": 0}

    def test_handle_generic_complexity(self):
        input_data = {"data_points": [1, {"a": 2}, "test"]}
        result = skill_handlers.handle_generic_complexity(input_data)
        assert result["items_processed"] == 3
        assert result["complexity_score"] > 0 # Exact score depends on str(data)

    def test_handle_generic_complexity_empty(self):
        input_data = {"data_points": []}
        result = skill_handlers.handle_generic_complexity(input_data)
        assert result["items_processed"] == 0
        assert result["complexity_score"] == len(str([])) * 0.1


@pytest.mark.parametrize("handler_func_name, tool_module_path, tool_name", [
    ("handle_web_operation", "core.skill_handlers.web_scraper", "web_scraper"),
    ("handle_file_operation", "core.skill_handlers.file_manager", "file_manager"),
    ("handle_api_call", "core.skill_handlers.api_connector", "api_connector"),
    ("handle_maths_operation", "core.skill_handlers.maths_tool", "maths_tool"),
])
class TestToolBasedSkillHandlers:

    def test_tool_success(self, handler_func_name, tool_module_path, tool_name):
        """Test successful operation when tool returns valid JSON."""
        handler_func = getattr(skill_handlers, handler_func_name)
        mock_tool_execute = MagicMock(return_value=json.dumps({"status": "ok", "data": "some_data"}))

        with patch(tool_module_path) as mock_tool_module:
            mock_tool_module.execute = mock_tool_execute
            
            result = handler_func("test_command")
            
            assert result == {"status": "ok", "data": "some_data"}
            mock_tool_execute.assert_called_once_with("test_command", {})

    def test_tool_returns_invalid_json(self, handler_func_name, tool_module_path, tool_name):
        """Test ValueError when tool returns non-JSON string."""
        handler_func = getattr(skill_handlers, handler_func_name)
        mock_tool_execute = MagicMock(return_value="this is not json")

        with patch(tool_module_path) as mock_tool_module:
            mock_tool_module.execute = mock_tool_execute
            
            with pytest.raises(ValueError, match="non-JSON"):
                handler_func("test_command")
            mock_tool_execute.assert_called_once_with("test_command", {})

    def test_tool_execute_raises_exception(self, handler_func_name, tool_module_path, tool_name):
        """Test handler propagates exception from tool's execute method."""
        handler_func = getattr(skill_handlers, handler_func_name)
        mock_tool_execute = MagicMock(side_effect=IOError("Disk full"))

        with patch(tool_module_path) as mock_tool_module:
            mock_tool_module.execute = mock_tool_execute
            
            with pytest.raises(IOError, match="Disk full"):
                handler_func("test_command")
            mock_tool_execute.assert_called_once_with("test_command", {})

    def test_tool_module_not_loaded(self, handler_func_name, tool_module_path, tool_name):
        """Test RuntimeError when the tool module itself is None."""
        handler_func = getattr(skill_handlers, handler_func_name)
        
        # To properly test this, we need to simulate the module being None *at the time of import*
        # within skill_handlers.py, or more simply, patch the global reference within skill_handlers.
        # The `with patch(tool_module_path, None)` simulates that the import `from skills import tool_name`
        # resulted in `tool_name` being `None`.
        with patch(tool_module_path, None):
            # We need to reload skill_handlers or ensure the handler function re-evaluates
            # the tool's availability. The current implementation checks the global variable
            # (e.g., `web_scraper`) directly inside the handler.
            # So, patching it to None should work.

            # If the module was already imported and the tool variable set,
            # we need to patch the variable *inside* the skill_handlers module.
            # Example: patch('core.skill_handlers.web_scraper', None)
            # The `tool_module_path` is already 'core.skill_handlers.web_scraper', etc.
            # So this patch should correctly make the tool None within the handler's scope.

            with pytest.raises(RuntimeError, match="module not loaded or available"):
                handler_func("test_command")

    # Specific test for maths_tool to ensure its specific error message if needed,
    # though the generic one above should cover it.
    # The following test is now implemented as a standalone function at the end of the file.


# Example of how to run this test file:
# Assuming this file is tests/core/test_skill_handlers.py
# And your project root has 'core' and 'skills' directories.
#
# From the project root:
# pytest
# or
# pytest tests/core/test_skill_handlers.py

# To ensure the `patch` for tool_module_not_loaded works as intended,
# let's consider how skill_handlers.py imports and uses the tools:
#
# core/skill_handlers.py:
# try:
#     from skills import web_scraper
# except ImportError:
#     web_scraper = None
# ...
# def handle_web_operation(command_string: str):
#     if web_scraper:  <-- This is what we are testing
#         ...
#     else:
#         raise RuntimeError("Web scraper tool module not loaded...")
#
# When `patch('core.skill_handlers.web_scraper', None)` is used, it directly sets
# the `web_scraper` variable *within the `core.skill_handlers` module* to `None`.
# This correctly simulates the scenario where the import failed or the tool is unavailable.
# The `tool_module_path` in the parametrize fixture is already set up like this.

# A small adjustment to the test_maths_tool_module_not_loaded_specific
# It was inside the class, but it's better as a standalone or integrated if it's truly specific.
# For now, the parametrized test covers it. If a unique message was desired, it would be:

def test_maths_tool_specific_not_loaded_message():
    """Test specific RuntimeError for maths_tool if its message was unique."""
    # This test is redundant if the generic message "module not loaded or available" is used for all.
    # If maths_tool had a unique error message, this would be useful.
    # For now, let's assume the generic message is fine.
    with patch('core.skill_handlers.maths_tool', None):
        with pytest.raises(RuntimeError, match="Maths tool module not loaded or available for maths_operation."):
             skill_handlers.handle_maths_operation("add 1 1")
import unittest
from unittest.mock import MagicMock, patch
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Adjust path as necessary to import DataAnalysisBasicV1
from capabilities import data_analysis # Import the module itself
from capabilities.data_analysis import DataAnalysisBasicV1

class TestDataAnalysisBasicV1(unittest.TestCase):

    def setUp(self):
        self.capability = DataAnalysisBasicV1()
        self.mock_agent_memory = MagicMock()
        # Configure mock_agent_memory.log to be a list by default for most tests
        self.mock_agent_memory.log = []
        self.mock_agent_memory.add_to_log = MagicMock() # Mock the method directly
        self.agent_id = "test_agent_DA"

    def test_execute_success(self):
        data_input = {"key1": "value1", "key2": "value2"}
        expected_summary = f"Data processed: {len(data_input)} keys."
        
        result = self.capability.execute(self.agent_id, self.mock_agent_memory, data_input) # capability is DataAnalysisBasicV1 instance
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["analysis_summary"], expected_summary)
        self.mock_agent_memory.add_to_log.assert_called_once_with(
            f"'{self.capability.CAPABILITY_NAME}' primary execution successful."
        )

    def test_execute_primary_failure_triggers_fallback(self):
        data_input_triggering_failure = {"trigger_failure": True, "info": "test data"}
        
        result = self.capability.execute(self.agent_id, self.mock_agent_memory, data_input_triggering_failure)
        
        self.assertEqual(result["status"], "fallback_success")
        self.assertIn("Simulated primary analysis failure", result["reason"])
        self.assertEqual(result["message"], "Default analysis result due to error.")
        
        # Check that add_to_log was called by the fallback
        # The exact message includes the original error and data_input
        self.mock_agent_memory.add_to_log.assert_called_once_with(
            f"[{self.agent_id}] Fallback for '{self.capability.CAPABILITY_NAME}' triggered due to: Simulated primary analysis failure in data_analysis_basic_v1. Input was: {data_input_triggering_failure}"
        )

    def test_fallback_when_agent_memory_log_is_none(self):
        # Simulate agent_memory.log being None initially
        self.mock_agent_memory.log = None
        data_input = {"trigger_failure": True, "info": "data for None log test"}

        # We expect the fallback to handle this gracefully
        with patch.object(data_analysis, 'log') as mock_builtin_log: # Patch the log function in the imported data_analysis module
            result = self.capability.execute(self.agent_id, self.mock_agent_memory, data_input)

            self.assertEqual(result["status"], "fallback_success")
            self.assertIn("Simulated primary analysis failure", result["reason"])
            
            # Verify that agent_memory.log was initialized to a list by the fallback
            self.assertIsInstance(self.mock_agent_memory.log, list)
            
            # Verify that the fallback attempted to log to the (now initialized) agent_memory.log
            self.mock_agent_memory.add_to_log.assert_called_once()
            
            # Verify the specific log message about initializing agent_memory.log
            found_init_log = False
            for call_args in mock_builtin_log.call_args_list:
                if f"AgentMemory.log is missing or not a list (type: <class 'NoneType'>). Initializing" in call_args[0][0]:
                    found_init_log = True
                    break
            self.assertTrue(found_init_log, "Log message about initializing agent_memory.log not found.")

    def test_fallback_when_agent_memory_log_is_not_list(self):
        # Simulate agent_memory.log being something other than a list
        self.mock_agent_memory.log = "not_a_list"
        data_input = {"trigger_failure": True, "info": "data for non-list log test"}

        with patch.object(data_analysis, 'log') as mock_builtin_log: # Patch the log function in the imported data_analysis module
            result = self.capability.execute(self.agent_id, self.mock_agent_memory, data_input)

            self.assertEqual(result["status"], "fallback_success")
            self.assertIsInstance(self.mock_agent_memory.log, list) # Should be re-initialized
            self.mock_agent_memory.add_to_log.assert_called_once()
            
            found_init_log = False
            for call_args in mock_builtin_log.call_args_list:
                if f"AgentMemory.log is missing or not a list (type: <class 'str'>). Initializing" in call_args[0][0]:
                    found_init_log = True
                    break
            self.assertTrue(found_init_log, "Log message about initializing agent_memory.log (for non-list) not found.")

    @patch.object(data_analysis, 'log') # Patch the log function in the imported data_analysis module
    def test_fallback_critical_failure_if_add_to_log_fails_unexpectedly(self, mock_builtin_log_for_capability):
        # This test is a bit more involved as it simulates a failure *within* the fallback's try block,
        # specifically if agent_memory.add_to_log itself raises an unexpected error.
        data_input = {"trigger_failure": True, "info": "critical fallback test"}
        
        # Make agent_memory.add_to_log raise an unexpected error
        self.mock_agent_memory.add_to_log.side_effect = TypeError("Unexpected error during add_to_log")

        result = self.capability.execute(self.agent_id, self.mock_agent_memory, data_input)

        self.assertEqual(result["status"], "fallback_failed")
        self.assertIn("Unexpected error during add_to_log", result["reason"])
        self.assertEqual(result["critical_error"], "Fallback mechanism encountered an unexpected error.")
        
        # Check that the critical error was logged by the capability's own logger
        found_critical_log = False
        for call_args in mock_builtin_log_for_capability.call_args_list:
            args, kwargs = call_args
            if args and f"[ERROR] [{self.agent_id}] Cap '{self.capability.CAPABILITY_NAME}' fallback itself FAILED critically" in args[0]:
                found_critical_log = True
                break
        self.assertTrue(found_critical_log, "Critical fallback failure log message not found.")

if __name__ == '__main__':
    unittest.main()

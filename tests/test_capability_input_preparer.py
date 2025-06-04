# tests/unit/test_capability_input_preparer.py

import unittest
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import MagicMock, patch, ANY
from core.capability_input_preparer import CapabilityInputPreparer
from core.skill_definitions import SKILL_CAPABILITY_MAPPING # Actual mapping
 
class TestCapabilityInputPreparer(unittest.TestCase):

    def setUp(self):
        self.skill_map = SKILL_CAPABILITY_MAPPING
        self.preparer = CapabilityInputPreparer(skill_capability_mapping=self.skill_map)

        # Mock Agent
        self.mock_agent = MagicMock()
        self.mock_agent.name = "test_agent"
        self.mock_agent.state = {
            "lineage_id": "test_lineage",
            "last_failed_skill_details": None # Default
        }
        self.mock_agent.generation = 1
        self.mock_agent.memory = MagicMock()
        self.mock_agent.memory.get_log.return_value = [{"event": "some_log_entry"}] # Mock recent logs
        self.mock_agent.capability_params = { # Example agent-specific params
            "sequence_executor_v1": {
                "sub_sequence_param_key_to_use": "my_custom_sequence_params"
            },
            "my_custom_sequence_params": {
                 "sub_sequence": ["knowledge_storage_v1"]
            }
        }

        # Mock ContextManager
        self.mock_context = MagicMock()
        self.mock_context.get_tick.return_value = 10

        # Mock KnowledgeBase
        self.mock_knowledge = MagicMock()

        self.all_agent_names = ["test_agent", "skill_agent_1", "skill_agent_2"]
        self.agent_info_map = {
            "test_agent": {"agent_type": "task", "capabilities": ["knowledge_storage_v1"]},
            "skill_agent_1": {"agent_type": "skill", "capabilities": ["data_analysis_basic_v1"]},
            "skill_agent_2": {"agent_type": "skill", "capabilities": ["web_services_v1"]},
        }

    def _call_prepare(self, cap_name: str):
        return self.preparer.prepare_inputs(
            agent=self.mock_agent,
            cap_name_to_prep=cap_name,
            context=self.mock_context,
            knowledge=self.mock_knowledge,
            all_agent_names_in_system=self.all_agent_names,
            agent_info_map=self.agent_info_map
        )

    def test_prepare_knowledge_storage_v1(self):
        inputs = self._call_prepare("knowledge_storage_v1")
        self.assertIn("data_to_store", inputs)
        self.assertEqual(inputs["data_to_store"]["source"], "test_agent")
        self.assertEqual(inputs["data_to_store"]["tick"], 10)

    def test_prepare_communication_broadcast_v1(self):
        inputs = self._call_prepare("communication_broadcast_v1")
        self.assertIn("message_content", inputs)
        self.assertIn("info", inputs["message_content"])

    def test_prepare_knowledge_retrieval_v1(self):
        inputs = self._call_prepare("knowledge_retrieval_v1")
        self.assertEqual(inputs["query_params"], {}) # Default empty query params

    def test_prepare_data_analysis_basic_v1(self):
        inputs = self._call_prepare("data_analysis_basic_v1")
        self.assertIn("data_to_analyze", inputs)
        self.assertEqual(len(inputs["data_to_analyze"]), 1) # From mock_agent.memory.get_log()
        self.mock_agent.memory.get_log.assert_called_once()

    def test_prepare_data_analysis_v1(self):
        inputs = self._call_prepare("data_analysis_v1")
        self.assertIn("data_to_analyze", inputs)
        self.assertEqual(len(inputs["data_to_analyze"]), 1)

    @patch('core.capability_input_preparer.random.choices')
    def test_prepare_invoke_skill_agent_v1_specific_actions(self, mock_random_choices):
        skill_action_to_expected_data_key = {
            "maths_operation": "maths_command",
            "log_summary": "analysis_type", # and data_points
            "complexity": "analysis_type",  # and data_points
            "web_operation": "web_command",
            "file_operation": "file_command",
            "api_call": "api_command"
        }

        for skill_action, expected_key in skill_action_to_expected_data_key.items():
            with self.subTest(skill_action=skill_action):
                mock_random_choices.return_value = [skill_action] # Force this action
                inputs = self._call_prepare("invoke_skill_agent_v1")

                self.assertEqual(inputs["skill_action_to_request"], skill_action)
                self.assertIn("request_data", inputs)
                self.assertIn(expected_key, inputs["request_data"],
                              f"Expected key '{expected_key}' not found in request_data for {skill_action}")
                if skill_action in ["log_summary", "complexity"]:
                    self.assertIn("data_points", inputs["request_data"])
    
    @patch('core.capability_input_preparer.log') # To check the log call
    def test_prepare_invoke_skill_agent_v1_no_preferable_actions(self, mock_log):
        # Modify the instance's list for this test
        original_actions = list(self.preparer.globally_preferable_skill_actions) # Save to restore
        self.preparer.globally_preferable_skill_actions = []
        
        inputs = self._call_prepare("invoke_skill_agent_v1")

        self.assertIsNone(inputs.get("skill_action_to_request"))
        self.assertIn("request_data", inputs)
        self.assertEqual(inputs["request_data"].get("error"), "No skill actions available to choose from.")
        
        # Check that the error was logged
        # Using ANY for the first argument if the exact agent name formatting might vary slightly
        # or if other parts of the log message are dynamic.
        # For a more precise check, construct the exact expected log string.
        expected_log_message = f"[{self.mock_agent.name}] No globally preferable skill actions defined for input preparation."
        
        found_log = False
        for call_arg in mock_log.call_args_list:
            if call_arg[0][0] == expected_log_message and call_arg[1].get('level') == "ERROR":
                found_log = True
                break
        self.assertTrue(found_log, f"Expected log message '{expected_log_message}' with level ERROR not found.")

        # Restore the original list for other tests
        self.preparer.globally_preferable_skill_actions = original_actions

    @patch('core.capability_input_preparer.random.choices')
    def test_prepare_invoke_skill_agent_v1_with_recent_failure(self, mock_random_choices):
        # Configure the mock to return a predictable action, so the test doesn't depend on randomness here.
        # We are interested in the 'weights' argument passed to it.
        mock_random_choices.return_value = ["maths_operation"] # Example return

        self.mock_agent.state["last_failed_skill_details"] = {
            "tick": 9, # Recent failure
            "action_requested": "web_operation"
        }

        # Call prepare_inputs once
        self._call_prepare("invoke_skill_agent_v1")

        # Assert that random.choices was called
        mock_random_choices.assert_called_once()

        # Get the arguments passed to random.choices
        # random.choices is called as random.choices(population, weights=action_weights, k=1)
        call_args = mock_random_choices.call_args
        population_arg = call_args[0][0] # First positional argument
        weights_arg = call_args[1]['weights'] # Keyword argument 'weights'

        self.assertIsNotNone(weights_arg, "Weights argument was not passed to random.choices")

        web_op_index = population_arg.index("web_operation")
        self.assertEqual(weights_arg[web_op_index], 0.1, "Weight for recently failed 'web_operation' should be 0.1")
        for i, action in enumerate(population_arg):
            if action != "web_operation":
                self.assertEqual(weights_arg[i], 1.0, f"Weight for '{action}' should be 1.0")

    def test_prepare_sequence_executor_v1_agent_default(self):
        # Agent has "my_custom_sequence_params" defined in its capability_params
        # and sequence_executor_v1.sub_sequence_param_key_to_use points to it.
        inputs = self._call_prepare("sequence_executor_v1")
        self.assertEqual(inputs.get("sub_sequence_param_key_to_use"), "my_custom_sequence_params")
        self.assertNotIn("sub_sequence", inputs) # The key is passed, not the sequence itself

    def test_prepare_sequence_executor_v1_random_choice(self):
        # Remove the agent's default to force random choice among defined sequences
        del self.mock_agent.capability_params["sequence_executor_v1"]
        # Add another named sequence to agent's params for random choice
        self.mock_agent.capability_params["another_sequence_params"] = {"sub_sequence": ["knowledge_retrieval_v1"]}

        inputs = self._call_prepare("sequence_executor_v1")
        self.assertIn(inputs.get("sub_sequence_param_key_to_use"), ["my_custom_sequence_params", "another_sequence_params"])

    def test_prepare_sequence_executor_v1_fallback(self):
        # Remove all named sequences to trigger fallback
        self.mock_agent.capability_params = {"sequence_executor_v1": {}} # No sub_sequence_param_key_to_use
        
        inputs = self._call_prepare("sequence_executor_v1")
        # Check if it falls back to the direct "sub_sequence" if no named sequences are found
        # or if the capability_params for sequence_executor_v1 itself contains a sub_sequence.
        # Based on current logic, it will try to find a key ending in _sequence_params.
        # If none, it might result in an error or an empty sequence if not handled.
        # The current fallback is a direct ["knowledge_storage_v1"]
        self.assertEqual(inputs.get("sub_sequence"), ["knowledge_storage_v1"])

    def test_prepare_interpret_goal_with_llm_v1(self):
        inputs = self._call_prepare("interpret_goal_with_llm_v1")
        self.assertEqual(inputs["user_query"], "What is the current status and should I be concerned?")

    def test_prepare_unknown_capability(self):
        inputs = self._call_prepare("unknown_capability_xyz")
        # Should still contain default inputs
        self.assertEqual(inputs["current_tick"], 10)
        self.assertEqual(inputs["agent_name"], "test_agent")

if __name__ == '__main__':
    unittest.main()
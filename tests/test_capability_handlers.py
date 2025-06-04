# tests/test_capability_handlers.py

import json
import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import sys
import time

# Ensure the core modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.capability_handlers import (
    _extract_data_recursively,
    execute_knowledge_storage_v1, # Already present
    execute_communication_broadcast_v1,
    execute_knowledge_retrieval_v1,
    execute_data_analysis_basic_v1,
    execute_data_analysis_v1,
    execute_invoke_skill_agent_v1,
    execute_triangulated_insight_v1,
    execute_interpret_goal_with_llm_v1,
    execute_conversational_exchange_llm_v1,
    _get_value_from_path,
    _compare_values
)
from core.skill_definitions import SKILL_CAPABILITY_MAPPING # For invoke_skill_agent_v1

# Mock parts of the system these handlers might interact with
class MockAgent:
    def __init__(self, name="test_handler_agent"):
        self.name = name
        self.state = {
            "lineage_id": "test_lineage",
            "last_failed_skill_details": None,
            "pending_skill_requests": {}
        }
        self.memory = MagicMock()
        self.communication_bus = MagicMock()
        self.context_manager = MagicMock() # For execute_invoke_skill_agent_v1
        self.context_manager.get_tick.return_value = 100
        self.context_manager.tick_interval = 0.5
        self.knowledge_base = MagicMock() # For execute_invoke_skill_agent_v1
        self.capabilities = ["knowledge_storage_v1", "invoke_skill_agent_v1"] # Example
        self.capability_params = {
            "invoke_skill_agent_v1": {"timeout_duration": 5.0, "success_reward": 0.7, "failure_reward": -0.2, "timeout_reward": -0.1}
        }
        self.agent_info_map = {} # For execute_invoke_skill_agent_v1

    def _get_rl_state_representation(self): # Mock for invoke_skill_agent_v1
        return ("mock_state",)

    def _execute_capability(self, capability_name, context, knowledge, all_agent_names_in_system, **cap_inputs): # Add this mock method
        # This will be replaced by a MagicMock in tests that need it.
        raise NotImplementedError("MockAgent._execute_capability should be mocked in the test if called.")

class TestCapabilityHandlers(unittest.TestCase):

    def setUp(self):
        self.mock_agent = MockAgent()
        self.mock_knowledge = MagicMock()
        self.mock_context = MagicMock()
        self.mock_context.get_tick.return_value = 123
        self.mock_all_agent_names = ["agent_a", "agent_b"]
        self.mock_params_used = {} # Default empty, specific tests can populate
        self.mock_cap_inputs = {}  # Default empty

    # --- Test Helper Functions ---
    def test_extract_data_recursively(self):
        numbers = []
        texts = []
        data = [1, "hello 2.5", {"value": 3.0, "text": "world -4"}, [5, "item 6.0"]]
        _extract_data_recursively(data, numbers, texts)
        self.assertCountEqual(numbers, [1.0, 2.5, 3.0, -4.0, 5.0, 6.0])
        self.assertCountEqual(texts, ["hello 2.5", "world -4", "item 6.0"])

    def test_get_value_from_path(self):
        data = {"a": {"b": {"c": 10}}, "d": [0, {"e": 20}]}
        self.assertEqual(_get_value_from_path(data, "a.b.c"), 10)
        self.assertEqual(_get_value_from_path(data, "d.1.e"), 20)
        self.assertIsNone(_get_value_from_path(data, "a.x.c"))
        self.assertIsNone(_get_value_from_path(data, "d.2"))
        self.assertIsNone(_get_value_from_path(None, "a.b"))

    def test_compare_values(self):
        self.assertTrue(_compare_values(5, "==", 5))
        self.assertTrue(_compare_values(5, ">", 4))
        self.assertTrue(_compare_values("abc", "contains", "b"))
        self.assertTrue(_compare_values(None, "not_exists", None))
        self.assertTrue(_compare_values(5, "in", [1, 5, 10]))
        self.assertFalse(_compare_values(5, "<", 5))
        self.assertFalse(_compare_values(None, "==", 5)) # None comparison

    # --- Test Capability Handlers ---

    def test_execute_knowledge_storage_v1_success(self):
        self.mock_knowledge.store.return_value = 0.8 # Contribution score
        cap_inputs = {"data_to_store": {"key": "value"}}
        result = execute_knowledge_storage_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success")
        self.assertAlmostEqual(result["reward"], 0.5 + 0.8 * 0.5)
        self.mock_knowledge.store.assert_called_once()
        self.mock_agent.memory.log_knowledge_contribution.assert_called_once_with(0.8)

    def test_execute_knowledge_storage_v1_placeholder_resolution(self):
        self.mock_knowledge.store.return_value = 0.6
        cap_inputs = {
            "data_to_store": "<FROM_PREVIOUS_STEP:details.some.data>",
            "previous_step_output": {"details": {"some": {"data": "resolved_value"}}}
        }
        result = execute_knowledge_storage_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success")
        self.mock_knowledge.store.assert_called_with(
            ANY, ANY, {"original_agent": self.mock_agent.name, "tick": 123, "payload": "resolved_value"}, 123
        )

    def test_execute_data_analysis_basic_v1_numerical(self):
        cap_inputs = {"data_to_analyze": [1, 2, 3, 10, -2]} # Outlier is 10 and -2 if std_devs=2
        params_used = {"outlier_std_devs": 1.5, "top_n_keywords": 3} # Override for testing
        result = execute_data_analysis_basic_v1(
            self.mock_agent, params_used, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success_numerical_analysis")
        self.assertIn("numerical_analysis", result["details"])
        num_analysis = result["details"]["numerical_analysis"]
        self.assertAlmostEqual(num_analysis["mean"], 2.8)
        self.assertIn("outliers", num_analysis)
        # Mean = 2.8, StdDev_pop ~ 4.16. 1.5*StdDev ~ 6.24. Bounds: ~[-3.44, 9.04]. Outliers: 10
        self.assertCountEqual(num_analysis["outliers"], [10.0])

    def test_execute_data_analysis_basic_v1_textual(self):
        cap_inputs = {"data_to_analyze": ["hello world", "test world example", "hello test"]}
        params_used = {"outlier_std_devs": 2.0, "top_n_keywords": 2}
        result = execute_data_analysis_basic_v1(
            self.mock_agent, params_used, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success_textual_analysis")
        self.assertIn("textual_analysis", result["details"])
        txt_analysis = result["details"]["textual_analysis"]
        # words: hello, world, test, world, example, hello, test
        # filtered (len>2, no_stop): hello, world, test, world, example, hello, test
        # counts: hello:2, world:2, test:2, example:1
        self.assertCountEqual(txt_analysis["top_keywords"], [("hello", 2), ("world", 2)]) # or test

    @patch('core.capability_handlers.call_openai_api')
    def test_execute_interpret_goal_with_llm_v1_success(self, mock_call_openai):
        mock_response_content = {
            "parsed_action": {
                "type": "invoke_skill",
                "target_skill_action": "api_call",
                "skill_parameters": {"service_name": "get_time"},
                "summary_for_user": "I will get the current time."
            }
        }
        mock_call_openai.return_value = json.dumps(mock_response_content)
        cap_inputs = {"user_query": "What time is it?"}
        params_used = {"llm_model": "test_model"}

        result = execute_interpret_goal_with_llm_v1(
            self.mock_agent, params_used, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success_goal_interpreted")
        self.assertEqual(result["details"]["type"], "invoke_skill")
        self.assertEqual(result["details"]["target_skill_action"], "api_call")
        mock_call_openai.assert_called_once()
        # Check if GUI display was attempted (if context has the method)
        if hasattr(self.mock_context, 'display_insight_in_gui'):
            self.mock_context.display_insight_in_gui.assert_called_once()

    @patch('core.capability_handlers.call_openai_api')
    def test_execute_interpret_goal_with_llm_v1_parsing_error(self, mock_call_openai):
        mock_call_openai.return_value = "this is not json"
        cap_inputs = {"user_query": "What time is it?"}
        result = execute_interpret_goal_with_llm_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_llm_response_parsing")

    # --- Tests for execute_communication_broadcast_v1 ---
    def test_execute_communication_broadcast_v1_success(self):
        """Test successful message broadcast."""
        cap_inputs = {"message_content": {"text": "hello all"}}
        
        result = execute_communication_broadcast_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(result["reward"], 0.35)
        self.mock_agent.communication_bus.broadcast_message.assert_called_once_with(
            self.mock_agent.name, {"text": "hello all"}, self.mock_all_agent_names
        )
        self.mock_agent.memory.log_message_sent.assert_called_once()
        self.assertEqual(result["details"]["message_length"], len(str({"text": "hello all"})))

    def test_execute_communication_broadcast_v1_default_message(self):
        """Test broadcast with default message content."""
        # cap_inputs is empty, so "message_content" will be missing
        result = execute_communication_broadcast_v1(
            self.mock_agent, {}, {}, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(result["reward"], 0.35)
        default_message = {"info": "default broadcast"}
        self.mock_agent.communication_bus.broadcast_message.assert_called_once_with(
            self.mock_agent.name, default_message, self.mock_all_agent_names
        )
        self.mock_agent.memory.log_message_sent.assert_called_once()
        self.assertEqual(result["details"]["message_length"], len(str(default_message)))

    def test_execute_communication_broadcast_v1_no_bus(self):
        """Test broadcast failure if agent has no communication bus."""
        self.mock_agent.communication_bus = None # Simulate no bus
        result = execute_communication_broadcast_v1(
            self.mock_agent, {}, {}, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_no_bus")
        self.assertEqual(result["reward"], -0.1)

    def test_execute_communication_broadcast_v1_no_recipients(self):
        """Test broadcast outcome when there are no other agents."""
        result = execute_communication_broadcast_v1(
            self.mock_agent, {}, {}, self.mock_knowledge, self.mock_context, [] # No other agents
        )
        self.assertEqual(result["outcome"], "success_no_recipients")
        self.assertEqual(result["reward"], 0.05)
        self.mock_agent.communication_bus.broadcast_message.assert_not_called()

    def test_execute_invoke_skill_agent_v1_request_sent(self):
        # Setup for this specific test
        self.mock_agent.agent_info_map = {
            "skill_math_0": {"agent_type": "skill", "capabilities": ["math_services_v1"]}
        }
        # SKILL_CAPABILITY_MAPPING is used by execute_invoke_skill_agent_v1
        # We need to ensure it's available or mock its access if it were a class member
        # For now, assuming SKILL_CAPABILITY_MAPPING is globally available as imported.

        cap_inputs = {
            "skill_action_to_request": "maths_operation",
            "request_data": {"maths_command": "add 1 1"}
        }
        params_used = self.mock_agent.capability_params["invoke_skill_agent_v1"]

        result = execute_invoke_skill_agent_v1(
            self.mock_agent, params_used, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )

        self.assertEqual(result["outcome"], "request_sent")
        self.assertIn("request_id", result["details"])
        self.assertEqual(result["details"]["target_skill_agent_id"], "skill_math_0")
        self.mock_agent.communication_bus.send_direct_message.assert_called_once()
        self.mock_agent.memory.log_skill_request_sent.assert_called_once()
        self.assertIn(result["details"]["request_id"], self.mock_agent.state["pending_skill_requests"])

    def test_execute_invoke_skill_agent_v1_no_suitable_agent(self):
        self.mock_agent.agent_info_map = { # No agent can do 'web_operation'
            "skill_math_0": {"agent_type": "skill", "capabilities": ["math_services_v1"]}
        }
        cap_inputs = {"skill_action_to_request": "web_operation"}
        params_used = self.mock_agent.capability_params["invoke_skill_agent_v1"]

        result = execute_invoke_skill_agent_v1(
            self.mock_agent, params_used, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_no_suitable_target_agent")

    # --- Tests for execute_sequence_executor_v1 ---

    # --- Tests for execute_triangulated_insight_v1 ---
    def test_execute_triangulated_insight_v1_rule_trigger(self):
        # Symptom from agent state
        self.mock_agent.state["last_failed_skill_details"] = {
            "symptom_id": "symptom123", "tick": 120, "reason": "failure_skill_invoke",
            "details": {"target_skill_agent_id": "skill_A"}
        }
        # Contextual data that will satisfy a rule
        def mock_retrieve_side_effect(lineage_id, query_params):
            # This mock is specific to the call made for "skill_agent_performance_history"
            # in this test case.
            expected_event_type = "skill_agent_execution_summary"
            # The key used in final_query_params is derived from symptom_kb_key_names or symptom_keys_for_query
            expected_symptom_key_in_query = "details.target_skill_agent_id" 
            expected_symptom_value = "skill_A"

            if query_params.get("event_type") == expected_event_type and \
               query_params.get(expected_symptom_key_in_query) == expected_symptom_value:
                return [{"data": {"failure_rate": 0.6, "execution_count": 5, "agent_id": "skill_A"}}]
            return [] 
        
        
        # Also mock the knowledge object passed to the handler, as it's used directly
        # if the data_source type is 'knowledge_base'
        self.mock_knowledge.retrieve_full_entries.side_effect = mock_retrieve_side_effect




        params_used_for_insight = {
            "symptom_source": "agent_state",
            "symptom_key_in_state": "last_failed_skill_details",
            "contextual_data_sources": [
                {"name": "skill_agent_performance_history", "type": "knowledge_base", "query_details": {"event_type": "skill_agent_execution_summary"}, "symptom_keys_for_query": ["details.target_skill_agent_id"]}
            ],
            "insight_rules": [{
                "name": "test_skill_agent_unreliable",
                "conditions": [
                    {"source": "symptom", "key_path": "reason", "operator": "in", "value": ["failure_skill_invoke"]},
                    {"source": "context", "data_source_name": "skill_agent_performance_history", "key_path": "failure_rate", "operator": ">", "value": 0.5},
                    {"source": "context", "data_source_name": "skill_agent_performance_history", "key_path": "execution_count", "operator": ">=", "value": 3}
                ],
                "insight_text": "Skill agent {symptom.details.target_skill_agent_id} is unreliable.",
                "confidence": 0.8,
                "suggested_action_flags": ["investigate_skill_A"]
            }]
        }

        result = execute_triangulated_insight_v1(
            self.mock_agent, params_used_for_insight, {}, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )

        self.assertEqual(result["outcome"], "success_insight_generated_by_test_skill_agent_unreliable")
        self.assertIsNotNone(result["diagnosis"])
        self.assertEqual(result["diagnosis"]["rule_applied"], "test_skill_agent_unreliable")
        self.assertEqual(result["diagnosis"]["root_cause_hypothesis"], "Skill agent skill_A is unreliable.")
        self.mock_knowledge.store.assert_called_once() # Storing the diagnosis
        self.mock_agent.context_manager.post_insight_to_gui.assert_called_once_with(result["diagnosis"])

if __name__ == '__main__':
    unittest.main()
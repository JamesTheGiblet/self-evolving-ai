# tests/test_capability_executor.py

import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import sys

# Ensure the core modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.capability_executor import (
    execute_capability_by_name,
    execute_knowledge_storage_v1,
    execute_knowledge_retrieval_v1,
    _extract_data_recursively,
    CAPABILITY_EXECUTION_MAP # Import for checking existence
)
# Assuming BaseAgent, ContextManager, KnowledgeBase are importable for type hints or mocks
# from core.agent_base import BaseAgent # Not strictly needed if we mock everything

class TestCapabilityExecutor(unittest.TestCase):

    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_agent.name = "test_executor_agent"
        self.mock_agent.state = {"lineage_id": "test_lineage"}
        self.mock_agent.memory = MagicMock()
        self.mock_agent.communication_bus = MagicMock()

        self.mock_params_used = {"param_key": "param_value"}
        self.mock_cap_inputs = {"input_key": "input_value"}
        self.mock_knowledge = MagicMock()
        self.mock_context = MagicMock()
        self.mock_context.get_tick.return_value = 123
        self.mock_all_agent_names = ["agent1", "agent2"]

    @patch('core.capability_executor.log') # Patch log where it's used
    def test_execute_unknown_capability(self, mock_log):
        """Test that executing an unknown capability returns a failure and logs an error."""
        result = execute_capability_by_name(
            "unknown_capability_name",
            self.mock_agent,
            self.mock_params_used,
            self.mock_cap_inputs,
            self.mock_knowledge,
            self.mock_context,
            self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_unknown_capability")
        self.assertEqual(result["reward"], -1.0)
        self.assertIn("error", result["details"])
        mock_log.assert_called_with(ANY, level="ERROR")

    def test_execute_known_capability_dispatches_correctly(self):
        """Test that a known capability is dispatched to its handler by patching the map."""
        capability_to_test = "knowledge_storage_v1"
        mock_specific_handler = MagicMock(return_value={"outcome": "mock_success", "reward": 0.9})

        # Patch the CAPABILITY_EXECUTION_MAP for the duration of this test
        # to ensure our mock_specific_handler is what's retrieved.
        with patch.dict('core.capability_executor.CAPABILITY_EXECUTION_MAP',
                        {capability_to_test: mock_specific_handler},
                        clear=False) as mock_map_context: # clear=False preserves other mappings
            # The 'clear=False' argument is important if other parts of the code
            # might be incidentally called and rely on other map entries.
            # If this test is perfectly isolated, clear=True or omitting it might also work.
           
            result = execute_capability_by_name(
                "knowledge_storage_v1",
                self.mock_agent,
                self.mock_params_used,
                self.mock_cap_inputs,
                self.mock_knowledge,
                self.mock_context,
                self.mock_all_agent_names
            )

            # Assert that our mock_specific_handler (which was put into the map) was called
            mock_specific_handler.assert_called_once_with(
                agent=self.mock_agent,
                params_used=self.mock_params_used,
                cap_inputs=self.mock_cap_inputs,
                knowledge=self.mock_knowledge,
                context=self.mock_context,
                all_agent_names_in_system=self.mock_all_agent_names
            )
            self.assertEqual(result["outcome"], "mock_success")
            self.assertEqual(result["reward"], 0.9)

    # --- Tests for handlers defined directly in capability_executor.py ---

    def test_execute_knowledge_storage_v1_success(self):
        """Test successful knowledge storage."""
        self.mock_knowledge.store.return_value = 0.7 # Mock contribution score
        cap_inputs = {"data_to_store": {"some_key": "some_value"}}
        
        result = execute_knowledge_storage_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )

        self.assertEqual(result["outcome"], "success")
        self.assertAlmostEqual(result["reward"], 0.5 + 0.7 * 0.5)
        self.assertEqual(result["details"]["contribution_score"], 0.7)
        self.mock_knowledge.store.assert_called_once()
        self.mock_agent.memory.log_knowledge_contribution.assert_called_once_with(0.7)

    def test_execute_knowledge_storage_v1_no_data(self):
        """Test knowledge storage failure when no data is provided."""
        cap_inputs = {"data_to_store": None} # Or missing key
        
        result = execute_knowledge_storage_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_missing_input_data")
        self.assertEqual(result["reward"], -0.2)
        self.mock_knowledge.store.assert_not_called()

    def test_execute_knowledge_retrieval_v1_success(self):
        """Test successful knowledge retrieval."""
        self.mock_knowledge.retrieve.return_value = [{"data": "item1"}, {"data": "item2"}]
        cap_inputs = {"query_params": {"type": "fact"}}

        result = execute_knowledge_retrieval_v1(
            self.mock_agent, {}, cap_inputs, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(result["details"]["items_retrieved"], 2)
        self.assertAlmostEqual(result["reward"], 0.2 + (2 * 0.05)) # 0.2 + 0.1 = 0.3
        self.mock_knowledge.retrieve.assert_called_once_with("test_lineage", query_params={"type": "fact"})

    def test_execute_knowledge_retrieval_v1_no_data(self):
        """Test knowledge retrieval when no data is found."""
        self.mock_knowledge.retrieve.return_value = []
        result = execute_knowledge_retrieval_v1(
            self.mock_agent, {}, {}, self.mock_knowledge, self.mock_context, self.mock_all_agent_names
        )
        self.assertEqual(result["outcome"], "failure_no_data_found")
        self.assertEqual(result["reward"], -0.1)

    def test_extract_data_recursively(self):
        """Test the _extract_data_recursively helper function."""
        numbers = []
        texts = []
        data = [
            1, "hello 2.5", {"value": 3.0, "text": "world -4"},
            [5, "item 6.0"]
        ]
        _extract_data_recursively(data, numbers, texts)
        
        self.assertCountEqual(numbers, [1.0, 2.5, 3.0, -4.0, 5.0, 6.0])
        self.assertCountEqual(texts, ["hello 2.5", "world -4", "item 6.0"])


if __name__ == '__main__':
    unittest.main()
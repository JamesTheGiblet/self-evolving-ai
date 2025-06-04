# tests/test_llm_planner.py
import unittest
from unittest.mock import patch, MagicMock
import json
import os

import sys
# Adjust the path to import from your project's root
# This ensures that 'core' and 'config' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.llm_planner import LLMPlanner
import config # To access default model name

class TestLLMPlanner(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.agent_capabilities = [
            "knowledge_storage_v1",
            "communication_broadcast_v1",
            "invoke_skill_agent_v1", # Important for prompt construction
            "triangulated_insight_v1",
            "knowledge_retrieval_v1" # Added for test_get_simulated_plan
        ]
        # Store original env var if exists
        self.original_openai_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = self.api_key # Set for tests

    def tearDown(self):
        # Restore original env var
        if self.original_openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_openai_api_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

    def test_construct_prompt(self):
        planner = LLMPlanner(api_key=self.api_key, model_name="simulated_test_model")
        user_query = "What is the weather?"
        prompt = planner._construct_prompt(user_query, self.agent_capabilities)

        self.assertIn(user_query, prompt)
        self.assertIn("knowledge_storage_v1", prompt)
        self.assertIn("triangulated_insight_v1", prompt)
        self.assertNotIn("invoke_skill_agent_v1", prompt.split("Available direct capabilities:")[1].split("Available skill invocations")[0]) # Check it's not in direct list
        self.assertIn("JSON list of steps", prompt)
        self.assertIn("file_operation", prompt) # Example skill

    def test_parse_llm_response_valid_json_list(self):
        planner = LLMPlanner(api_key=self.api_key)
        response_content = '[{"name": "knowledge_retrieval_v1"}, "communication_broadcast_v1"]'
        plan = planner._parse_llm_response(response_content)
        self.assertIsInstance(plan, list)
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["name"], "knowledge_retrieval_v1")

    def test_parse_llm_response_valid_json_list_with_markdown(self):
        planner = LLMPlanner(api_key=self.api_key)
        response_content = '```json\n[{"name": "knowledge_retrieval_v1"}]\n```'
        plan = planner._parse_llm_response(response_content)
        self.assertIsInstance(plan, list)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["name"], "knowledge_retrieval_v1")

    def test_parse_llm_response_invalid_json(self):
        planner = LLMPlanner(api_key=self.api_key)
        response_content = 'this is not json'
        plan = planner._parse_llm_response(response_content)
        self.assertIsNone(plan)

    def test_parse_llm_response_valid_json_not_a_list(self):
        planner = LLMPlanner(api_key=self.api_key)
        response_content = '{"name": "knowledge_retrieval_v1"}' # A dict, not a list
        plan = planner._parse_llm_response(response_content)
        self.assertIsNone(plan)

    def test_get_simulated_plan(self):
        planner = LLMPlanner(model_name="simulated_test_model") # No API key needed for simulated
        query_status = "what is the current status?" # Ensure query matches the condition in _get_simulated_plan
        # Explicitly pass the capabilities to ensure the method receives them
        plan_status = planner._get_simulated_plan(user_query=query_status, agent_capabilities=self.agent_capabilities)
        
        # Add a debug print if it still fails
        # print(f"DEBUG test_get_simulated_plan - plan_status: {plan_status}, capabilities used: {self.agent_capabilities}") 
        self.assertIsNotNone(plan_status)
        self.assertGreater(len(plan_status), 0)

        query_unknown = "tell me a joke"
        plan_unknown = planner._get_simulated_plan(query_unknown, self.agent_capabilities)
        self.assertIsNone(plan_unknown)

    @patch('core.llm_planner.OpenAI')
    def test_generate_plan_with_mocked_openai(self, MockOpenAI):
        # Setup mock response
        mock_client_instance = MockOpenAI.return_value
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps([
            {"name": "knowledge_retrieval_v1", "inputs": {"query": "latest status"}}
        ])
        mock_client_instance.chat.completions.create.return_value = mock_completion

        planner = LLMPlanner(api_key=self.api_key, model_name="gpt-3.5-turbo") # Use a real model name
        user_query = "Get the latest status report."
        
        plan = planner.generate_plan(user_query, self.agent_capabilities)

        MockOpenAI.assert_called_once_with(api_key=self.api_key)
        mock_client_instance.chat.completions.create.assert_called_once()
        args, kwargs = mock_client_instance.chat.completions.create.call_args
        self.assertEqual(kwargs['model'], "gpt-3.5-turbo")
        self.assertIn(user_query, kwargs['messages'][1]['content']) # User message is the second one

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]['name'], "knowledge_retrieval_v1")

    @patch('core.llm_planner.OpenAI')
    def test_generate_plan_openai_api_error(self, MockOpenAI):
        mock_client_instance = MockOpenAI.return_value
        # Import APIError from openai if not already imported at the top
        from openai import APIError as OpenAI_APIError # Use an alias to avoid conflict if defined elsewhere

        # Simulate an APIError from OpenAI
        # The constructor for APIError might vary slightly between versions.
        # A common way is to provide a message and potentially a request object if needed.
        mock_client_instance.chat.completions.create.side_effect = OpenAI_APIError("Test API Error", request=MagicMock(), body=None)
        
        planner = LLMPlanner(api_key=self.api_key, model_name="gpt-3.5-turbo")
        user_query = "This query will cause an API error."
        
        plan = planner.generate_plan(user_query, self.agent_capabilities)
        
        self.assertIsNone(plan)
        MockOpenAI.assert_called_once_with(api_key=self.api_key)
        mock_client_instance.chat.completions.create.assert_called_once()

    def test_planner_initialization_no_api_key_real_model(self):
        # Test initialization logging when API key is missing for a real model
        # Temporarily remove API key from environment for this specific test
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        # Patch utils.logger.log directly for more reliable capture
        # Patch 'log' where it's used by LLMPlanner
        with patch('core.llm_planner.log') as mock_log:
            planner = LLMPlanner(api_key=None, model_name="gpt-3.5-turbo")
            # The client might still initialize, but generate_plan would fail or log further.
            # The primary check here is the warning during init.

            # --- Debugging Print ---
            print(f"DEBUG: mock_log.call_args_list: {mock_log.call_args_list}")

            # Check that log was called with a message indicating API key issue or client init error
            found_expected_log_call = False
            for call_args in mock_log.call_args_list:
                args, kwargs = call_args
                message = args[0] if args else ""
                level = kwargs.get('level', 'INFO').upper() # Assuming your log function takes a level kwarg
                
                is_warning_or_error = level in ["WARNING", "ERROR"]
                contains_api_key_message = "API key not provided" in message
                contains_client_init_error = "Error initializing OpenAI client" in message

                if is_warning_or_error and (contains_api_key_message or contains_client_init_error):
                    found_expected_log_call = True
                    break
            
            self.assertTrue(found_expected_log_call, 
                            msg="Expected log call (WARNING or ERROR) about API key/client initialization was not made.")

        # Attempting a plan generation should also fail or log appropriately
        plan = planner.generate_plan("test query", self.agent_capabilities)
        self.assertIsNone(plan) # Expect None because API key is missing


if __name__ == '__main__':
    unittest.main()

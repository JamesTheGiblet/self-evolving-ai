# c:\Users\gilbe\Desktop\self-evolving-ai\core\llm_planner.py

import json
from typing import List, Dict, Any, Optional, Callable # Added Callable
from utils.logger import log
import config
from utils import local_llm_connector

class LLMPlanner:
    """
    LLMPlanner uses a Language Model to interpret user queries and generate
    a sequence of executable steps (a plan). It now uses a local LLM connector.
    """
    def __init__(self, model_name: str = config.DEFAULT_LLM_MODEL):
        self.model_name = model_name

        if self.model_name.startswith("simulated_"):
            log(f"[LLMPlanner] Initialized with SIMULATED LLM model: {self.model_name}")
        else:
            log(f"[LLMPlanner] Initialized to use LOCAL LLM model: {self.model_name} via local_llm_connector.")

    def _construct_prompt_messages(self, user_query: str, agent_capabilities: List[str]) -> List[Dict[str, str]]:
        """
        Constructs a list of prompt messages for the LLM to generate a plan.
        """
        system_content = (
            "You are an AI assistant that generates a plan to fulfill the user's request. "
            "The plan should be a JSON list of steps. Each step can be:\n"
            "1. A string representing a direct capability name.\n"
            "2. A dictionary for complex capabilities like 'invoke_skill_agent_v1' or 'sequence_executor_v1'.\n"
            "   - For 'invoke_skill_agent_v1', include 'name', 'inputs' (with 'skill_action_to_request' and 'request_data'), and optionally 'params_override'.\n\n"
            "Available direct capabilities:\n"
        )
        direct_caps_for_prompt = [cap for cap in agent_capabilities if cap not in ["invoke_skill_agent_v1", "sequence_executor_v1"]]
        for cap in direct_caps_for_prompt:
            system_content += f"- \"{cap}\"\n"
        system_content += "\n"
        system_content += "Available skill invocations (use with 'invoke_skill_agent_v1', providing 'skill_action_to_request' and 'request_data'):\n"
        system_content += '- For action \'web_operation\', \'request_data\' should be structured like: {"web_command": "get_text <URL_placeholder>"}\n'
        system_content += '- For action \'file_operation\', \'request_data\' should be structured like: {"file_command": "write <filepath_placeholder> \\"<content_placeholder>\\""}\n'
        system_content += '- For action \'api_call\', \'request_data\' should be structured like: {"api_command": "get_joke"}\n'
        system_content += '- For action \'log_summary\', \'request_data\' should be structured like: {"analysis_type": "log_summary", "data_points_hint": "<data_placeholder_from_memory_or_retrieval>"}\n'
        system_content += '- For action \'maths_operation\', \'request_data\' should be structured like: {"maths_command": "add 1 2"}\n'
        system_content += "\n"
        system_content += "Important Considerations:\n"
        system_content += "- Data from one step (especially asynchronous skill calls like 'web_operation' or 'api_call') is NOT automatically passed to the next unless the sequence executor is configured to do so. If data is needed later, a common pattern is to use a 'knowledge_storage_v1' step after the data-producing step, and a 'knowledge_retrieval_v1' step before the data-consuming step.\n"
        system_content += "- For 'knowledge_storage_v1', the 'data_to_store' in 'inputs' can be an object (e.g., {\"source\": \"web\", \"content_hint\": \"<output_of_previous_web_fetch>\"}) or a simple string placeholder (e.g., \"<generated_summary>\"). The agent is responsible for resolving/filling these placeholders using data from its memory or prior steps.\n"
        system_content += "- For 'file_operation' with 'write', the content to write should also be a placeholder if it comes from a previous step, e.g., \"<placeholder_for_summary_content>\".\n"
        system_content += "\nGenerate the JSON plan now."

        user_content = f'User Request: "{user_query}"\n\nGenerate the JSON plan.'

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    def _parse_llm_response(self, llm_response_content: Optional[str]) -> Optional[List[Any]]:
        """Parses the LLM's JSON (or JSON-like) response into a list of plan steps."""
        if not llm_response_content:
            log("[LLMPlanner] LLM response content is None or empty. Cannot parse.", level="WARNING")
            return None
        try:
            cleaned_response = llm_response_content.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:].strip()
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3].strip()
            elif cleaned_response.startswith("```"): # More generic markdown code block
                 cleaned_response = cleaned_response[3:-3].strip()
            
            plan = json.loads(cleaned_response)
            if isinstance(plan, list):
                return plan
            elif isinstance(plan, dict) and ("name" in plan or "skill_action_to_request" in plan):
                log(f"[LLMPlanner] LLM response was a single JSON object, wrapping it in a list: {str(plan)[:200]}", level="DEBUG")
                return [plan]
            
            log(f"[LLMPlanner] LLM response was valid JSON but not a list or a single step object: {str(plan)[:200]}", level="WARNING")
            return None
        except json.JSONDecodeError as e:
            log(f"[LLMPlanner] Failed to parse LLM JSON response: {e}\nRaw response: {llm_response_content}", level="ERROR")
            return None
        except Exception as e:
            log(f"[LLMPlanner] Unexpected error parsing LLM response: {e}\nRaw response: {llm_response_content}", level="ERROR")
            return None

    def _get_simulated_plan(self, user_query: str, agent_capabilities: List[str]) -> Optional[List[Any]]:
        """Generates a simulated plan for testing purposes. Distinct from local LLM calls."""
        log(f"[LLMPlanner] SIMULATING plan for query: '{user_query}' using model '{self.model_name}'")
        if "status" in user_query.lower() and "knowledge_retrieval_v1" in agent_capabilities:
            return [
                {"name": "knowledge_retrieval_v1", "inputs": {"query_params": {"event_type": "status_report", "limit": 1}}},
                {"name": "communication_broadcast_v1", "inputs": {"message_content": {"info": "Status retrieved and broadcasted (simulated)."}}}
            ]
        elif "create a file" in user_query.lower() and "invoke_skill_agent_v1" in agent_capabilities:
            return [
                {"name": "invoke_skill_agent_v1", 
                 "inputs": {
                     "skill_action_to_request": "file_operation", 
                     "request_data": {"file_command": "write ./agent_data/test_llm_sim_plan.txt \"Hello from Simulated LLM Plan!\""}
                    }
                }
            ]
        elif self.model_name == "simulated_llm_planner_model": # General fallback for this specific simulated model
            return [
                {"name": "knowledge_retrieval_v1", "inputs": {"query_params": {"data_matches": {"type": "generic_info"}, "limit": 1}}},
                {"name": "communication_broadcast_v1", "inputs": {"message_content": {"info": f"Simulated response to: {user_query[:50]}"}}}
            ]
        log(f"[LLMPlanner] SIMULATING: No specific pre-defined plan for query: '{user_query}' with model '{self.model_name}'. Returning None.")
        return None

    def _get_simulated_text(self, prompt: str, agent_capabilities: Optional[List[str]] = None) -> Optional[str]: # Added agent_capabilities to match signature, though not used
        """Generates simulated text. Matches signature for simulated_content_generator."""
        log(f"[LLMPlanner] SIMULATING text generation for prompt: '{prompt[:100]}...'")
        if "Suggest a new, concise, and meaningful name" in prompt:
            return "New Suggested Name: SimulatedEvoMind\nNew Suggested Purpose: To simulate evolution and learning."
        else:
            return f"Simulated text response to: {prompt[:100]}"

    def _dispatch_llm_call(
        self,
        prompt_messages_generator: Callable[[str, Optional[List[str]]], List[Dict[str, str]]],
        simulated_content_generator: Callable[[str, Optional[List[str]]], Optional[Any]],
        is_plan_generation: bool,
        user_query_or_prompt: str,
        agent_capabilities: Optional[List[str]] = None,
        **llm_kwargs: Any
    ) -> Optional[str]:
        """
        Dispatches the call to either a simulated content generator (staged via local_llm_connector)
        or the real async LLM connector.

        Args:
            prompt_messages_generator: Callable that returns the list of prompt messages for the real LLM.
            simulated_content_generator: Callable that generates the simulated plan or text.
            is_plan_generation: True if generating a plan, False for general text.
            user_query_or_prompt: The original user query (for plans) or prompt (for text).
            agent_capabilities: Agent capabilities, used by prompt_messages_generator and plan simulation.
            **llm_kwargs: Keyword arguments for the real LLM call (e.g., max_tokens, temperature).

        Returns:
            The request_id string from local_llm_connector, or None on error.
        """
        if self.model_name.startswith("simulated_"):
            log(f"[LLMPlanner] Using SIMULATED LLM call for model '{self.model_name}'", level="DEBUG")
            simulated_content = simulated_content_generator(user_query_or_prompt, agent_capabilities)
            error_msg = "Simulated plan generation failed" if is_plan_generation else "Simulated text generation failed"
            return local_llm_connector.stage_simulated_llm_response(simulated_content, is_plan=is_plan_generation, error=error_msg if simulated_content is None else None)
        else:
            log(f"[LLMPlanner] Using REAL ASYNC LLM call for model '{self.model_name}' for '{user_query_or_prompt[:50]}'", level="DEBUG")
            prompt_messages = prompt_messages_generator(user_query_or_prompt, agent_capabilities)
            return local_llm_connector.call_local_llm_api_async(
                prompt_messages=prompt_messages, model_name=self.model_name, **llm_kwargs
            )

    def generate_plan(self, user_query: str, agent_capabilities: List[str], agent_state: Optional[Dict] = None) -> Optional[Any]:
        """
        Generates a plan based on the user query and agent capabilities using the local LLM.
        Returns a request_id (str) if using local LLM, or a plan (List[Any]) if simulated.
        MODIFIED: Now always returns a request_id. For simulated plans, it stores the plan
        internally in local_llm_connector for async-style retrieval.
        """
        llm_kwargs = {"temperature": 0.2}
        try:
            return self._dispatch_llm_call(
                prompt_messages_generator=self._construct_prompt_messages,
                simulated_content_generator=self._get_simulated_plan,
                is_plan_generation=True,
                user_query_or_prompt=user_query,
                agent_capabilities=agent_capabilities,
                **llm_kwargs
            )
        except Exception as e:
            log(f"[LLMPlanner] Error during local LLM plan generation: {e}", level="ERROR", exc_info=True)
            return None

    def generate_text(self, prompt: str, max_tokens: int = 150, temperature: float = 0.7) -> Optional[Any]:
        """
        Generates general text based on a prompt using the local LLM.
        MODIFIED: Now always returns a request_id. For simulated text, it stores the text
        internally in local_llm_connector for async-style retrieval.
        """
        llm_kwargs = {"max_tokens": max_tokens, "temperature": temperature}

        def _text_prompt_messages_generator(text_prompt: str, _agent_capabilities: Optional[List[str]]) -> List[Dict[str, str]]:
            # _agent_capabilities is ignored for general text generation
            return [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": text_prompt}
            ]
        try:
            return self._dispatch_llm_call(
                prompt_messages_generator=_text_prompt_messages_generator,
                simulated_content_generator=self._get_simulated_text,
                is_plan_generation=False,
                user_query_or_prompt=prompt,
                # agent_capabilities not needed for general text generation by _get_simulated_text or _text_prompt_messages_generator
                **llm_kwargs
            )
        except Exception as e:
            log(f"[LLMPlanner] Error during local LLM text generation: {e}", level="ERROR", exc_info=True)
            return None
# core/capability_input_preparer.py

import random
from typing import Dict, List, Any, TYPE_CHECKING, Optional
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from core.context_manager import ContextManager
    from memory.knowledge_base import KnowledgeBase
    # from core.skill_definitions import SKILL_CAPABILITY_MAPPING # No longer needed here

class CapabilityInputPreparer:
    def __init__(self, skill_capability_mapping: Optional[Dict[str, List[str]]] = None): # Made optional
        # self.SKILL_CAPABILITY_MAPPING = skill_capability_mapping # No longer directly used for input prep logic
        self.globally_preferable_skill_actions = [
            "maths_operation", "log_summary", "complexity_analysis", # Changed "complexity"
            "web_operation", "file_operation", "api_call" # to "complexity_analysis"
        ]
        log("[CapabilityInputPreparer] Initialized.")

    def _prepare_maths_operation_skill_data(self, agent: 'BaseAgent', context: 'ContextManager') -> Dict[str, Any]:
        return {
            "maths_command": random.choice([
                "add 5 10", "subtract 20 7", "multiply 4 6", "divide 100 4",
                "add 1 2", "subtract 10 3", "multiply 7 8", "divide 50 5",
                "power 2 3", "log 100 10", "sin 90", "cos 0"
            ]),
        }

    def _prepare_log_summary_complexity_skill_data(self, agent: 'BaseAgent', chosen_skill_action: str) -> Dict[str, Any]:
        return {
            "data_points": list(agent.memory.get_log()),
            "analysis_type": chosen_skill_action
        }

    def _prepare_web_operation_skill_data(self, agent: 'BaseAgent', context: 'ContextManager') -> Dict[str, Any]:
        # Based on TaskRouter log, WebScraper skill only supports "get"
        web_action = "get" 
        example_urls = ["https://example.com", "https://www.python.org"]
        target_url = random.choice(example_urls)
        return {"web_command": f"{web_action} {target_url}"}

    def _prepare_file_operation_skill_data(self, agent: 'BaseAgent', context: 'ContextManager') -> Dict[str, Any]:
        file_action = random.choice(["list", "read", "write"])
        example_paths = ["./agent_data/notes.txt", "./logs/", f"./agent_outputs/random_write_{context.get_tick()}.txt"]
        target_path = random.choice(example_paths)
        if target_path.endswith('/') and file_action == "read":
            log(f"[{agent.name}] invoke_skill_agent_v1: Changing file_action from 'read' to 'list' for directory-like path: {target_path}")
            file_action = "list"
        command_to_send = f"{file_action} {target_path}"
        if file_action == "write":
            content_for_write = f"Random content written by {agent.name} at tick {context.get_tick()}."
            escaped_content = content_for_write.replace('"', '\\"')
            command_to_send = f"{file_action} {target_path} \"{escaped_content}\""
        return {"file_command": command_to_send}

    def _prepare_api_call_skill_data(self, agent: 'BaseAgent', context: 'ContextManager') -> Dict[str, Any]:
        return {"api_command": random.choice(["get_joke", "get_weather 34.05 -118.24"])}

    def prepare_inputs(self,
                       agent: 'BaseAgent',
                       cap_name_to_prep: str,
                       context: 'ContextManager',
                       knowledge: 'KnowledgeBase',
                       all_agent_names_in_system: List[str],
                       agent_info_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Prepares a generic set of inputs for a capability based on its name."""
        inputs: Dict[str, Any] = {}
        inputs["current_tick"] = context.get_tick()
        inputs["agent_info_map_at_prep"] = agent_info_map
        inputs["agent_name"] = agent.name
        inputs["agent_state"] = agent.state.copy()
        inputs["agent_generation"] = agent.generation

        if cap_name_to_prep == "knowledge_storage_v1":
            inputs["data_to_store"] = {"source": agent.name, "tick": context.get_tick(), "content": f"Generic log from {agent.name} at tick {context.get_tick()}"}
        elif cap_name_to_prep == "communication_broadcast_v1":
            inputs["message_content"] = {"info": f"Generic broadcast from {agent.name} at tick {context.get_tick()}"}
        elif cap_name_to_prep == "knowledge_retrieval_v1":
            inputs["query_params"] = {}
        elif cap_name_to_prep == "data_analysis_basic_v1":
            recent_logs = agent.memory.get_log()
            inputs["data_to_analyze"] = recent_logs[-20:] if recent_logs else []
            log(f"[{agent.name}] Preparing data_analysis_basic_v1 with {len(inputs['data_to_analyze'])} recent log entries.")
        elif cap_name_to_prep == "data_analysis_v1":
            recent_logs = agent.memory.get_log()
            inputs["data_to_analyze"] = recent_logs[-50:] if recent_logs else []
            log(f"[{agent.name}] Preparing data_analysis_v1 with {len(inputs['data_to_analyze'])} recent log entries.")
        elif cap_name_to_prep == "invoke_skill_agent_v1":
            # Determine a skill action to request first.
            
            # Use the instance variable
            if not self.globally_preferable_skill_actions:
                log(f"[{agent.name}] No globally preferable skill actions defined for input preparation.", level="ERROR")
                inputs["skill_action_to_request"] = None # Will cause failure in execute_invoke_skill_agent_v1
                inputs["request_data"] = {"error": "No skill actions available to choose from."}
                return inputs

            action_weights = [1.0] * len(self.globally_preferable_skill_actions)
            last_failure = agent.state.get('last_failed_skill_details')
            current_tick_for_prep = context.get_tick()

            # Apply weights based on last failure, if any
            if last_failure and (current_tick_for_prep - last_failure.get("tick", -1000)) < 3: # Short window for recency
                failed_action_type = last_failure.get("action_requested")
                if failed_action_type in self.globally_preferable_skill_actions:
                    try:
                        idx = self.globally_preferable_skill_actions.index(failed_action_type)
                        action_weights[idx] = 0.1
                        log(f"[{agent.name}] InputPreparer: Recently failed skill action '{failed_action_type}'. Reducing its selection weight.")
                    except ValueError:
                        pass

            chosen_skill_action = random.choices(self.globally_preferable_skill_actions, weights=action_weights, k=1)[0]
            inputs["skill_action_to_request"] = chosen_skill_action

            # Set a general target_skill_agent_id (lineage) or leave None.
            # The actual instance will be resolved by TaskAgent.find_best_skill_agent_for_action.
            # For simplicity, we can set a preferred lineage based on the action.
            if chosen_skill_action in ["log_summary", "complexity_analysis", "basic_stats_analysis", "advanced_stats", "keyword_search", "regex_match", "correlation"]: # Match actions from skill_definitions
                inputs["target_skill_agent_id"] = "skill_data_analysis_skill_ops" # Preferred lineage ID
            elif chosen_skill_action == "web_operation":
                inputs["target_skill_agent_id"] = "skill_web_scraper_ops" # Use lineage ID
            elif chosen_skill_action == "file_operation":
                inputs["target_skill_agent_id"] = "skill_file_manager_ops" # Use lineage ID
            else: # For "maths_operation", "api_call", or any other not explicitly listed
                # Let find_best_skill_agent_for_action pick any suitable agent if no preferred lineage.
                inputs["target_skill_agent_id"] = None 
            
            request_data_log_detail = ""
            if chosen_skill_action == "maths_operation":
                inputs["request_data"] = self._prepare_maths_operation_skill_data(agent, context)
                request_data_log_detail = f"with maths command: {inputs['request_data']['maths_command']}"
            elif chosen_skill_action in ["log_summary", "complexity_analysis"]: # Changed "complexity"
                inputs["request_data"] = self._prepare_log_summary_complexity_skill_data(agent, chosen_skill_action)
                request_data_log_detail = "with data analysis request."
            elif chosen_skill_action == "web_operation":
                inputs["request_data"] = self._prepare_web_operation_skill_data(agent, context)
                request_data_log_detail = f"with web command: {inputs['request_data']['web_command']}"
            elif chosen_skill_action == "file_operation":
                inputs["request_data"] = self._prepare_file_operation_skill_data(agent, context)
                request_data_log_detail = f"with file command: {inputs['request_data']['file_command']}"
            elif chosen_skill_action == "api_call":
                inputs["request_data"] = self._prepare_api_call_skill_data(agent, context)
                request_data_log_detail = f"with API call: {inputs['request_data']['api_command']}"
            else:
                inputs["request_data"] = {"error": f"Unknown skill action '{chosen_skill_action}' selected."}
                log(f"[{agent.name}] invoke_skill_agent_v1: Unknown skill action '{chosen_skill_action}' selected.", level="ERROR")
                request_data_log_detail = f"Error: Unknown skill action '{chosen_skill_action}'"

            log_message_suffix = f"(Action: {chosen_skill_action}, Preferred Target Lineage: {inputs.get('target_skill_agent_id', 'Any')})"
            log(f"[{agent.name}] Preparing invoke_skill_agent_v1 {log_message_suffix} {request_data_log_detail}")

            if "request_data" not in inputs:
                inputs["request_data"] = {}
                log(f"[{agent.name}] invoke_skill_agent_v1: 'request_data' was not populated for action '{inputs.get('skill_action_to_request', 'UNKNOWN')}'. Setting to empty dict.", level="WARNING")

        elif cap_name_to_prep == "sequence_executor_v1":
            # Find available named sequences in agent.capability_params
            available_sequence_keys = [
                key for key, value in agent.capability_params.items()
                if isinstance(value, dict) and "sub_sequence" in value and key.endswith("_sequence_params") # Convention
            ]
            default_seq_key_from_cap_params = agent.capability_params.get("sequence_executor_v1", {}).get("sub_sequence_param_key_to_use")
            if default_seq_key_from_cap_params and default_seq_key_from_cap_params in available_sequence_keys: # Prioritize the agent's default
                 inputs["sub_sequence_param_key_to_use"] = default_seq_key_from_cap_params
                 log(f"[{agent.name}] Preparing sequence_executor_v1 to use agent's default sequence: '{default_seq_key_from_cap_params}'.")
            elif available_sequence_keys: # Otherwise, pick one randomly from those ending with _sequence_params
                chosen_sequence_key = random.choice(available_sequence_keys)
                inputs["sub_sequence_param_key_to_use"] = chosen_sequence_key
                log(f"[{agent.name}] Preparing sequence_executor_v1 to use randomly chosen sequence: '{chosen_sequence_key}'.")
            else: # Fallback if no named sequences are found, or if sub_sequence is directly in its own params
                if not agent.capability_params.get("sequence_executor_v1", {}).get("sub_sequence"): # Check direct sub_sequence
                    inputs["sub_sequence"] = ["knowledge_storage_v1"] # Absolute fallback
                    log(f"[{agent.name}] Preparing sequence_executor_v1 with a direct fallback sequence (no named sequences found).")
        elif cap_name_to_prep == "request_llm_plan_v1": # Kept for completeness, though likely deprecated
            # This capability is likely superseded by interpret_goal_with_llm_v1
            # If used, it should also get its goal_description from the current_goal if appropriate.
            default_goal_desc = "Analyze recent system performance and suggest improvements."
            if hasattr(agent, 'current_goal') and agent.current_goal.get("type") == "user_defined_goal":
                default_goal_desc = agent.current_goal.get("details", {}).get("description", default_goal_desc)
            inputs["goal_description"] = default_goal_desc
            log(f"[{agent.name}] Preparing request_llm_plan_v1 with goal: {inputs['goal_description']}")
        elif cap_name_to_prep == "interpret_goal_with_llm_v1":
            default_user_query = "What is the current status and should I be concerned?"
            if hasattr(agent, 'current_goal') and agent.current_goal.get("type") == "interpret_user_goal":
                default_user_query = agent.current_goal.get("details", {}).get("user_query", default_user_query)
            elif hasattr(agent, 'current_goal') and agent.current_goal.get("type") == "user_defined_goal": # Fallback if somehow called with user_defined_goal
                default_user_query = agent.current_goal.get("details", {}).get("description", default_user_query)
            inputs["user_query"] = default_user_query
            log(f"[{agent.name}] Preparing interpret_goal_with_llm_v1 with user_query: '{inputs['user_query']}'")
        elif cap_name_to_prep == "conversational_exchange_llm_v1":
            default_user_input = "Hello, what can you do?"
            if hasattr(agent, 'current_goal') and agent.current_goal.get("type") == "user_defined_goal":
                default_user_input = agent.current_goal.get("details", {}).get("description", default_user_input)
            inputs["user_input_text"] = default_user_input
            # Use agent's actual conversation history
            inputs["conversation_history"] = agent.conversation_history if hasattr(agent, 'conversation_history') else []
            inputs["system_prompt"] = "You are a helpful AI assistant within a self-evolving multi-agent system."
            log(f"[{agent.name}] Preparing conversational_exchange_llm_v1 with user_input: '{inputs['user_input_text']}'")
        else:
            log(f"[{agent.name}] No specific input preparation logic for capability: {cap_name_to_prep}", level="DEBUG")

        return inputs

# c:/Users/gilbe/Desktop/self-evolving-ai/capability_handlers/interaction_handlers.py
"""
Capability Handlers for Agent Interactions, including invoking other agents.
"""
import random
import time
from typing import Dict, List, Any, TYPE_CHECKING, Optional

from utils.logger import log
import config
from core.skill_definitions import SKILL_CAPABILITY_MAPPING # For dynamic target resolution

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from memory.agent_memory import AgentMemory # For agent.memory logging


def execute_invoke_skill_agent_v1(agent: 'BaseAgent', params_used: dict, cap_inputs: dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: list):

    # 1. Determine the final skill_action_to_request
    final_skill_action_to_request = cap_inputs.get("skill_action_to_request")
    log_suffix_decision = "(from cap_inputs)" if final_skill_action_to_request else ""

    if not final_skill_action_to_request:
        final_skill_action_to_request = params_used.get("default_skill_action_to_attempt")
        log_suffix_decision = "(from agent_params)" if final_skill_action_to_request else ""
        if not final_skill_action_to_request:
            globally_preferable_skill_actions = [
                "maths_operation", "log_summary", "complexity_analysis", # Align with CapabilityInputPreparer
                "web_operation", "file_operation", "api_call"
            ]
            action_weights = [1.0] * len(globally_preferable_skill_actions)
            last_failure = agent.state.get('last_failed_skill_details')
            current_tick_for_prep = context.get_tick()

            if last_failure and (current_tick_for_prep - last_failure.get("tick", -1000)) < 3:
                failed_action_type = last_failure.get("action_requested")
                if failed_action_type in globally_preferable_skill_actions:
                    try:
                        idx = globally_preferable_skill_actions.index(failed_action_type)
                        action_weights[idx] = 0.1
                    except ValueError: pass
            
            if not globally_preferable_skill_actions:
                log(f"[{agent.name}] InvokeSkill: No globally preferable skill actions defined.", level="ERROR")
                return {"outcome": "failure_preparation_no_skill_type", "reward": -0.4, "details": {"error": "No skill types to choose from."}}
            final_skill_action_to_request = random.choices(globally_preferable_skill_actions, weights=action_weights, k=1)[0]
            log_suffix_decision = "(agent_decided_probabilistic)"

    if not final_skill_action_to_request:
        log(f"[{agent.name}] InvokeSkill: Could not determine a skill action to request.", level="ERROR")
        return {"outcome": "failure_preparation_no_skill_action", "reward": -0.4, "details": {"error": "Skill action could not be determined."}}

    log(f"[{agent.name}] InvokeSkill: Determined skill action '{final_skill_action_to_request}' {log_suffix_decision}.")

    # --- Extract the specific command for agent lookup ---
    # final_skill_action_to_request is the CATEGORY (e.g., "file_operation")
    # final_request_data (populated later) will contain the specific command (e.g., {"file_command": "list ./path"})
    # We need the specific command to match against SKILL_CAPABILITY_MAPPING values.
    
    # Temporarily populate final_request_data to extract the specific command for lookup
    # This logic mirrors the later population of final_request_data.
    temp_request_data_for_lookup = cap_inputs.get("request_data", {}).copy()
    if final_skill_action_to_request == "maths_operation" and "maths_command" not in temp_request_data_for_lookup:
        temp_request_data_for_lookup["maths_command"] = "add 0 0" # Placeholder for lookup
    elif final_skill_action_to_request == "web_operation" and "web_command" not in temp_request_data_for_lookup:
        temp_request_data_for_lookup["web_command"] = "fetch example.com" # Placeholder
    elif final_skill_action_to_request == "file_operation" and "file_command" not in temp_request_data_for_lookup:
        temp_request_data_for_lookup["file_command"] = "list ." # Placeholder
    elif final_skill_action_to_request == "api_call" and "api_command" not in temp_request_data_for_lookup:
        temp_request_data_for_lookup["api_command"] = "get_joke" # Placeholder
    elif final_skill_action_to_request in ["log_summary", "complexity", "basic_stats"]: # These are specific enough
        if "analysis_type" not in temp_request_data_for_lookup: temp_request_data_for_lookup["analysis_type"] = final_skill_action_to_request

    specific_command_for_lookup = None
    if final_skill_action_to_request == "file_operation":
        specific_command_for_lookup = temp_request_data_for_lookup.get("file_command", "").split(' ')[0]
    elif final_skill_action_to_request == "maths_operation":
        specific_command_for_lookup = temp_request_data_for_lookup.get("maths_command", "").split(' ')[0]
    elif final_skill_action_to_request == "web_operation":
        specific_command_for_lookup = temp_request_data_for_lookup.get("web_command", "").split(' ')[0]
    elif final_skill_action_to_request == "api_call":
        specific_command_for_lookup = temp_request_data_for_lookup.get("api_command", "").split(' ')[0]
    elif final_skill_action_to_request in ["log_summary", "complexity_analysis", "basic_stats_analysis"]: # Match skill tool commands
        specific_command_for_lookup = final_skill_action_to_request # The category name is the command


    if not specific_command_for_lookup:
        log(f"[{agent.name}] InvokeSkill: Could not determine specific command for lookup from category '{final_skill_action_to_request}' and data {temp_request_data_for_lookup}.", level="ERROR")
        return {"outcome": "failure_preparation_no_specific_command", "reward": -0.4, "details": {"error": "Specific command for lookup could not be determined."}}

    log(f"[{agent.name}] InvokeSkill: Specific command for agent lookup: '{specific_command_for_lookup}' (derived from category '{final_skill_action_to_request}').")

    preferred_target_id = cap_inputs.get("target_skill_agent_id", params_used.get("target_skill_agent_id"))
    available_skill_agents_info = {
        name: agent_data for name, agent_data in agent.agent_info_map.items()
        if agent_data.get("agent_type") == "skill" and agent_data.get("is_active", True) 
    }
    
    suitable_agents_for_action = []
    for sa_name, sa_info in available_skill_agents_info.items():
        sa_configured_service_caps = sa_info.get("capabilities", []) # e.g., ["file_manager_ops_v1"]
        agent_can_perform_specific_command = False
        for service_cap_name in sa_configured_service_caps:
            # SKILL_CAPABILITY_MAPPING should map service_cap_name to a list of specific commands
            specific_commands_of_this_service = SKILL_CAPABILITY_MAPPING.get(service_cap_name, [])
            if specific_command_for_lookup in specific_commands_of_this_service:
                agent_can_perform_specific_command = True
                break
        if agent_can_perform_specific_command:
            suitable_agents_for_action.append(sa_name)

    chosen_target_skill_agent_id = None
    if preferred_target_id:
        if preferred_target_id in suitable_agents_for_action:
            chosen_target_skill_agent_id = preferred_target_id
            log(f"[{agent.name}] InvokeSkill: Using preferred target '{chosen_target_skill_agent_id}' for specific command '{specific_command_for_lookup}'.")
        elif preferred_target_id in available_skill_agents_info:
            log(f"[{agent.name}] InvokeSkill: Preferred target '{preferred_target_id}' cannot perform specific command '{specific_command_for_lookup}'. Looking for alternatives.", level="WARNING")
        else:
            log(f"[{agent.name}] InvokeSkill: Preferred target '{preferred_target_id}' not found. Looking for alternatives.", level="WARNING")

    if not chosen_target_skill_agent_id and suitable_agents_for_action:
        chosen_target_skill_agent_id = random.choice(suitable_agents_for_action)
        log(f"[{agent.name}] InvokeSkill: Selected suitable agent '{chosen_target_skill_agent_id}' for specific command '{specific_command_for_lookup}'. Suitable: {suitable_agents_for_action}")

    if not chosen_target_skill_agent_id:
        log(f"[{agent.name}] InvokeSkill: No suitable target agent found for specific command '{specific_command_for_lookup}' (derived from category '{final_skill_action_to_request}'). Suitable: {suitable_agents_for_action}, All Skill Agents: {list(available_skill_agents_info.keys())}", level="WARNING")
        return {"outcome": "failure_no_suitable_target_agent", "reward": -0.3, "details": {"error": f"No suitable agent for specific command '{specific_command_for_lookup}' (category: '{final_skill_action_to_request}')."}}

    final_request_data = cap_inputs.get("request_data", {}).copy() 
    if final_skill_action_to_request == "maths_operation" and "maths_command" not in final_request_data:
        final_request_data["maths_command"] = random.choice(["add 1 2", "subtract 5 3", "multiply 2 3", "divide 10 2"])
    elif final_skill_action_to_request == "web_operation" and "web_command" not in final_request_data:
        final_request_data["web_command"] = random.choice(["fetch https://example.com", "get_text https://www.python.org"])
    elif final_skill_action_to_request == "file_operation" and "file_command" not in final_request_data:
        file_action = random.choice(["list", "read", "write"])
        example_paths = ["./agent_data/notes.txt", "./logs/", f"./agent_outputs/random_write_{context.get_tick()}.txt"]
        target_path = random.choice(example_paths)
        command_to_send = f"{file_action} {target_path}"
        if file_action == "write":
            content_for_write = f"Random content written by {agent.name} at tick {context.get_tick()}."
            escaped_content = content_for_write.replace('"', '\\"') # Basic escaping
            command_to_send = f"{file_action} {target_path} \"{escaped_content}\""
        final_request_data["file_command"] = command_to_send
    elif final_skill_action_to_request == "api_call" and "api_command" not in final_request_data:
        final_request_data["api_command"] = random.choice(["get_joke", "get_weather 34.05 -118.24"])
    elif final_skill_action_to_request in ["log_summary", "complexity_analysis", "basic_stats_analysis"] :
        if "data_points" not in final_request_data: final_request_data["data_points"] = [] 
        # Ensure analysis_type in request_data matches the skill_action_to_request for these specific actions
        final_request_data["analysis_type"] = final_skill_action_to_request

    timeout_duration = cap_inputs.get("timeout_duration", params_used.get("timeout_duration", 5.0))
    success_reward = cap_inputs.get("success_reward", params_used.get("success_reward", 0.75))
    failure_reward = cap_inputs.get("failure_reward", params_used.get("failure_reward", -0.25))
    timeout_reward = cap_inputs.get("timeout_reward", params_used.get("timeout_reward", -0.1))

    wait_for_response_flag = cap_inputs.get("wait_for_response", False)
    
    request_id = f"{agent.name}_req_{context.get_tick()}_{int(time.time()*1000)}"
    
    tick_interval = 0.5 
    if agent.context_manager and hasattr(agent.context_manager, 'tick_interval'):
        tick_interval = agent.context_manager.tick_interval
    skill_timeout_in_ticks = 10 
    if tick_interval > 0.001: 
        skill_timeout_in_ticks = max(1, int(timeout_duration / tick_interval) + 2) 
    else: 
        skill_timeout_in_ticks = max(1, 5, int(timeout_duration * 2)) 

    if not agent.communication_bus:
        log(f"[{agent.name}] Cap 'invoke_skill_agent_v1' failed: Agent has no communication bus.", level="ERROR")
        return {"outcome": "failure_no_bus", "reward": -0.2, "details": {"error": "Agent communication bus not available."}}
    
    message_content = {
        "action": final_skill_action_to_request,
        "request_id": request_id,
        "data": final_request_data
    }
    agent.communication_bus.send_direct_message(agent.name, chosen_target_skill_agent_id, message_content)
    log(f"[{agent.name}] Cap 'invoke_skill_agent_v1' sent request '{request_id}' to '{chosen_target_skill_agent_id}'. Mode: {'SYNC' if wait_for_response_flag else 'ASYNC'}.", level="INFO")
    agent.memory.log_message_sent() 
     
    is_sync_path_expected = bool(wait_for_response_flag)

    if is_sync_path_expected:
        log(f"[{agent.name}] InvokeSkill (SYNC): Dispatching request '{request_id}' to '{chosen_target_skill_agent_id}'. Will pend for response.", level="INFO")
        return {
            "outcome": "sync_request_sent_pending_response", 
            "reward": 0.01, 
            "details": {
                "request_id": request_id,
                "target_skill_agent_id": chosen_target_skill_agent_id,
                "skill_action_requested": final_skill_action_to_request,
                "timeout_at_tick": context.get_tick() + skill_timeout_in_ticks,
                "original_rl_state_for_q_update": agent._get_rl_state_representation(),
                "rewards_for_resolution": { 
                    "success": success_reward,
                    "failure": failure_reward,
                    "timeout": timeout_reward
                }
            }
        }
    else:
        agent.memory.log_skill_request_sent(
            tick=context.get_tick(), request_id=request_id,
            target_skill_agent_id=chosen_target_skill_agent_id,
            capability_name="invoke_skill_agent_v1", request_data=final_request_data
        )
        current_sim_tick = context.get_tick()
        agent.state.setdefault('pending_skill_requests', {})
        agent.state['pending_skill_requests'][request_id] = {
            "original_rl_state": agent._get_rl_state_representation(),
            "tick_sent": current_sim_tick,
            "target_skill_agent_id": chosen_target_skill_agent_id,
            "success_reward": success_reward, "failure_reward": failure_reward,
            "timeout_reward": timeout_reward, "timeout_at_tick": current_sim_tick + skill_timeout_in_ticks,
            "capability_name": "invoke_skill_agent_v1", "request_data": final_request_data
        }
        immediate_dispatch_reward = 0.05
        log(f"[{agent.name}] Cap 'invoke_skill_agent_v1' request '{request_id}' dispatched ASYNC. Pending response. Timeout in {skill_timeout_in_ticks} ticks (at tick {agent.state['pending_skill_requests'][request_id]['timeout_at_tick']}).")
        return {"outcome": "request_sent", "reward": immediate_dispatch_reward, "details": {"request_id": request_id, "target_skill_agent_id": chosen_target_skill_agent_id, "timeout_at_tick": agent.state['pending_skill_requests'][request_id]["timeout_at_tick"], "wait_for_response": is_sync_path_expected}}
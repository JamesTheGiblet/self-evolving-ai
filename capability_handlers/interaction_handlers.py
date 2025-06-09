# capability_handlers/interaction_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
import uuid # For generating request_ids

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus

# --- Handler function definitions ---
def execute_invoke_skill_agent_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles invoking a skill agent to perform a task.
    Sends a TASK_REQUEST message via the CommunicationBus.
    `cap_inputs` should contain:
        - "skill_agent_name": str, name of the target skill agent.
        - "task_description": str, natural language description of the task.
        - "task_parameters" (optional): dict, specific parameters for the task.
        - "expected_response_format" (optional): str, hint for response format.
    """
    skill_agent_name = cap_inputs.get("skill_agent_name")
    task_description = cap_inputs.get("task_description")
    task_parameters = cap_inputs.get("task_parameters", {})
    expected_response_format = cap_inputs.get("expected_response_format")

    if not skill_agent_name or not task_description:
        log(f"[{agent.name}] Failed invoke_skill_agent_v1: Missing skill_agent_name or task_description.", level="WARN")
        return {"outcome": "failure_missing_parameters", "reward": -0.2, "details": {"error": "skill_agent_name and task_description are required."}}

    if skill_agent_name not in all_agent_names_in_system:
        log(f"[{agent.name}] Failed invoke_skill_agent_v1: Skill agent '{skill_agent_name}' not found in system.", level="WARN")
        return {"outcome": "failure_skill_agent_not_found", "reward": -0.1, "details": {"error": f"Skill agent '{skill_agent_name}' not found."}}

    request_id = str(uuid.uuid4())
    task_request_message = {
        "type": "TASK_REQUEST", # Message type for the bus/recipient
        "request_id": request_id,
        "requester_agent_name": agent.name,
        "task_description": task_description,
        "task_parameters": task_parameters,
        "expected_response_format": expected_response_format,
        "timestamp": context.get_tick() # Or use time.time()
    }

    log(f"[{agent.name}] Executing invoke_skill_agent_v1. Target: {skill_agent_name}. Task: '{task_description}'. Request ID: {request_id}", level="INFO")

    communication_bus: 'CommunicationBus' = getattr(agent, 'communication_bus', None)
    if not communication_bus:
        return {"outcome": "failure_communication_bus_unavailable", "reward": -0.3, "details": {"error": "CommunicationBus not accessible to agent."}}

    success = communication_bus.send_direct_message(
        sender_name=agent.name,
        recipient_name=skill_agent_name,
        content=task_request_message
    )

    if success:
        # The invoking agent should store this request_id to correlate responses.
        # agent.memory.add_pending_request(request_id, skill_agent_name, "TASK_REQUEST", context.get_tick())
        return {"outcome": "success_skill_invocation_sent", "reward": 0.4, "details": {"skill_agent_invoked": skill_agent_name, "task_description": task_description, "request_id": request_id, "status": "task_request_sent_via_bus"}}
    else:
        return {"outcome": "failure_dispatch_to_skill_agent_failed", "reward": -0.25, "details": {"error": f"Failed to send TASK_REQUEST to '{skill_agent_name}' via CommunicationBus."}}

def execute_request_information_from_agent_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles requesting specific information from another agent.
    Sends an INFO_REQUEST message via the CommunicationBus.
    `cap_inputs` should contain:
        - "target_agent_name": str, name of the agent to query.
        - "information_query": dict, describing the info needed (e.g., {"query_type": "get_status"}).
        - "response_timeout_ticks" (optional): int, suggestion for timeout.
    """
    target_agent_name = cap_inputs.get("target_agent_name")
    information_query = cap_inputs.get("information_query")
    # response_timeout_ticks = cap_inputs.get("response_timeout_ticks") # For future use by requester

    if not target_agent_name or not information_query:
        return {"outcome": "failure_missing_info_request_params", "reward": -0.2, "details": {"error": "'target_agent_name' and 'information_query' are required."}}
    if target_agent_name not in all_agent_names_in_system and target_agent_name != agent.name: # Allow self-query if bus supports
        return {"outcome": "failure_target_agent_not_found", "reward": -0.1, "details": {"error": f"Target agent '{target_agent_name}' not found."}}

    request_id = str(uuid.uuid4())
    info_request_message = {"type": "INFO_REQUEST", "request_id": request_id, "requester_agent_name": agent.name, "query": information_query}

    log(f"[{agent.name}] Executing request_information_from_agent_v1. Target: {target_agent_name}. Query: {information_query}. Request ID: {request_id}", level="INFO")

    communication_bus: 'CommunicationBus' = getattr(agent, 'communication_bus', None)
    if not communication_bus:
        return {"outcome": "failure_communication_bus_unavailable", "reward": -0.3, "details": {"error": "CommunicationBus not accessible."}}

    success = communication_bus.send_direct_message(sender_name=agent.name, recipient_name=target_agent_name, content=info_request_message)

    if success:
        # agent.memory.add_pending_request(request_id, target_agent_name, "INFO_REQUEST", context.get_tick())
        return {"outcome": "success_info_request_sent", "reward": 0.3, "details": {"target_agent": target_agent_name, "query_sent": information_query, "request_id": request_id}}
    else:
        return {"outcome": "failure_dispatch_info_request_failed", "reward": -0.25, "details": {"error": f"Failed to send INFO_REQUEST to '{target_agent_name}' via CommunicationBus."}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("invoke_skill_agent_v1", execute_invoke_skill_agent_v1)
    register_capability("request_information_from_agent_v1", execute_request_information_from_agent_v1)
    log("[InteractionHandlers] Successfully registered interaction handlers.", level="DEBUG")
except ImportError:
    log("[InteractionHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[InteractionHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
# capability_handlers/interaction_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_invoke_skill_agent_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles invoking a skill agent to perform a task.
    Placeholder implementation.
    """
    skill_agent_name = cap_inputs.get("skill_agent_name")
    task_description = cap_inputs.get("task_description")

    if not skill_agent_name or not task_description:
        log(f"[{agent.name}] Failed invoke_skill_agent_v1: Missing skill_agent_name or task_description.", level="WARN")
        return {"outcome": "failure_missing_parameters", "reward": -0.2, "details": {"error": "skill_agent_name and task_description are required."}}

    log(f"[{agent.name}] Executing invoke_skill_agent_v1. Target Skill Agent: {skill_agent_name}. Task: {task_description}", level="INFO")
    # Logic to find and dispatch task to skill_agent_name via CommunicationBus or direct call if applicable
    # This would likely involve creating a task, sending it, and then waiting for a response or a task ID.
    # For now, simulate successful dispatch.
    return {"outcome": "success_skill_invocation_initiated", "reward": 0.4, "details": {"skill_agent_invoked": skill_agent_name, "task_assigned": task_description, "status": "simulated_dispatch_ok"}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("invoke_skill_agent_v1", execute_invoke_skill_agent_v1)
    log("[InteractionHandlers] Successfully registered interaction handlers.", level="DEBUG")
except ImportError:
    log("[InteractionHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[InteractionHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
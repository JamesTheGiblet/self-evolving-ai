# capability_handlers/planning_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
from utils import local_llm_connector # Assuming direct use for now
import config # For default model

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_interpret_goal_with_llm_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles interpreting a high-level goal into a plan using an LLM.
    This is a synchronous call for simplicity. An async version would be preferable.
    """
    goal_description = cap_inputs.get("goal_description")
    model_name = params_used.get("llm_model", config.DEFAULT_LLM_MODEL)
    # Example prompt, would need to be more sophisticated
    prompt_messages = [{"role": "system", "content": "You are a planning assistant. Convert the user's goal into a JSON list of actionable steps."},
                       {"role": "user", "content": f"Goal: {goal_description}"}]

    if not goal_description:
        return {"outcome": "failure_missing_goal", "reward": -0.2, "details": {"error": "goal_description is required."}}

    log(f"[{agent.name}] Executing interpret_goal_with_llm_v1. Model: {model_name}. Goal: {goal_description}", level="INFO")
    llm_plan_str = local_llm_connector.call_local_llm_api(prompt_messages=prompt_messages, model_name=model_name)

    if llm_plan_str:
        # Further parsing of llm_plan_str into a structured plan would happen here
        return {"outcome": "success_plan_generated", "reward": 0.7, "details": {"raw_plan_from_llm": llm_plan_str}}
    else:
        return {"outcome": "failure_llm_planning_failed", "reward": -0.4, "details": {"error": "LLM failed to generate a plan."}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("interpret_goal_with_llm_v1", execute_interpret_goal_with_llm_v1)
    log("[PlanningHandlers] Successfully registered planning handlers.", level="DEBUG")
except ImportError:
    log("[PlanningHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[PlanningHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
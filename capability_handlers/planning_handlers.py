# capability_handlers/planning_handlers.py

from typing import Dict, Any, List
from capability_handlers.sequence_handlers import execute_sequence_executor_v1
from utils.logger import log
from core.context_manager import ContextManager
from core.llm_planner import LLMPlanner
 
def execute_interpret_goal_with_llm_v1(agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list):
    """
    Uses the LLMPlanner to generate a sequence of actions for a high-level user query
    and then executes that sequence using sequence_executor_v1.
    """
    user_query = cap_inputs.get("user_query", params_used.get("default_query", "Perform a standard task."))
    llm_model_name = params_used.get("llm_model", "simulated_llm") # Could be configured

    log(f"[{agent.name}] Cap 'interpret_goal_with_llm_v1' received query: '{user_query}'")

    # LLMPlanner now uses local_llm_connector which doesn't take an api_key directly here.
    # API keys for external services would be handled by the connector if needed, typically via env vars.
    planner_instance = LLMPlanner(model_name=llm_model_name)

    # In a real scenario, you'd pass available capabilities and skills to the planner
    # For now, the simulated planner has a hardcoded response for a specific goal.
    # You would also need to describe the skill agent actions.
    # For simplicity in this example, we'll pass the direct capabilities.
    # The LLMPlanner's _construct_prompt has hardcoded skill examples for now.
    # generate_plan now returns a request_id for an async operation
    request_id = planner_instance.generate_plan(user_query, agent.capabilities)

    if request_id:
        log(f"[{agent.name}] LLM plan generation dispatched. Request ID: {request_id}")
        # Return a pending outcome, TaskAgent will handle the async response
        return {
            "outcome": "pending_llm_interpretation", # New outcome type
            "reward": 0.05, # Small reward for dispatching
            "details": {
                "request_id": request_id,
                "llm_model_used": llm_model_name,
                "original_user_query": user_query, # Store original query for context
                "capability_initiated": "interpret_goal_with_llm_v1"
            }
        }
    else:
        log(f"[{agent.name}] LLMPlanner failed to generate a plan for query: '{user_query}'", level="WARNING")
        return {"outcome": "failure_llm_planning_failed", "reward": -0.5, "details": {"user_query": user_query, "error": "LLM planner returned no plan."}}
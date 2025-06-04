# self-evolving-ai/core/capability_executor.py

"""
Capability Executor Dispatcher

This module is responsible for dispatching capability execution requests
to the appropriate handler functions defined in core.capability_handlers.
"""
from typing import Dict, Any, List, TYPE_CHECKING
from core.skill_definitions import SKILL_CAPABILITY_MAPPING
from utils.logger import log
from core.context_manager import ContextManager 
import random
import time
import math # For sqrt in basic_v1 std_dev
import re # For parsing numbers from strings
from collections import Counter # For keyword frequency
import statistics # For data_analysis_v1 
import inspect # To check if handler is a coroutine
from capability_handlers.knowledge_handlers import execute_knowledge_storage_v1
# --- Import handlers from their specific files in capability_handlers subdirectory ---
from capability_handlers.interaction_handlers import execute_invoke_skill_agent_v1
from capability_handlers.insight_handlers import execute_triangulated_insight_v1
from capability_handlers.llm_handlers import execute_conversational_exchange_llm_v1
# Import the canonical version of execute_knowledge_retrieval_v1
from capability_handlers.knowledge_handlers import execute_knowledge_retrieval_v1
# Import the canonical version of execute_communication_broadcast_v1
from capability_handlers.communication_handlers import execute_communication_broadcast_v1
# Import the canonical version of execute_data_analysis_basic_v1
from capability_handlers.data_analysis_handlers import execute_data_analysis_basic_v1
# Import the canonical version of execute_data_analysis_v1
from capability_handlers.data_analysis_handlers import execute_data_analysis_v1
# Import the canonical version of execute_sequence_executor_v1
from capability_handlers.export_handlers import execute_export_agent_evolution_v1 # New import
from capability_handlers.sequence_handlers import execute_sequence_executor_v1
from capability_handlers.planning_handlers import execute_interpret_goal_with_llm_v1 # Import canonical version
from core.utils.data_extraction import _extract_data_recursively # Import the canonical version

if TYPE_CHECKING:
    from core.agent_base import BaseAgent # For type hinting
    from memory.knowledge_base import KnowledgeBase # For type hinting

# Import the specific handler function
try:
    from memory.fact_memory import FactMemory
except ImportError:
    FactMemory = None # Placeholder if not available
# --- IMPORTANT: ALL CAPABILITY EXECUTION FUNCTIONS MUST ACCEPT 'all_agent_names_in_system' ---
# This ensures a consistent signature even if a specific capability doesn't use it.



CAPABILITY_EXECUTION_MAP = {
    "knowledge_storage_v1": execute_knowledge_storage_v1, # This mapping is crucial
    "communication_broadcast_v1": execute_communication_broadcast_v1,
    "sequence_executor_v1": execute_sequence_executor_v1,
    # Parameters for these capabilities are defined in core.capability_definitions.CAPABILITY_REGISTRY
    "knowledge_retrieval_v1": execute_knowledge_retrieval_v1, # Now uses imported canonical version
    "data_analysis_basic_v1": execute_data_analysis_basic_v1,
    "data_analysis_v1": execute_data_analysis_v1, # Added new capability
    "invoke_skill_agent_v1": execute_invoke_skill_agent_v1, 
#    "request_llm_plan_v1": execute_request_llm_plan_v1, # Register the new planning capability
    "interpret_goal_with_llm_v1": execute_interpret_goal_with_llm_v1, # New LLM planning capability
    "triangulated_insight_v1": execute_triangulated_insight_v1,
    "conversational_exchange_llm_v1": execute_conversational_exchange_llm_v1,
    "export_agent_evolution_v1": execute_export_agent_evolution_v1 # New mapping
}

print("[DEBUG] CAPABILITY_EXECUTION_MAP keys at load time:", list(CAPABILITY_EXECUTION_MAP.keys()))

# This function is called by BaseAgent._execute_capability
def execute_capability_by_name(capability_name: str, agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list) -> dict:
    """
    Dynamically executes a capability based on its name using the CAPABILITY_EXECUTION_MAP.
    """
    log(f"[DEBUG] Requested execution of capability: {capability_name}", level="DEBUG")
    log(f"[DEBUG] Agent: {getattr(agent, 'name', str(agent))}", level="DEBUG")
    log(f"[DEBUG] Params used: {params_used}", level="DEBUG")
    log(f"[DEBUG] Capability inputs: {cap_inputs}", level="DEBUG")
    log(f"[DEBUG] All agent names in system: {all_agent_names_in_system}", level="DEBUG")
    if capability_name in CAPABILITY_EXECUTION_MAP:
        execution_function = CAPABILITY_EXECUTION_MAP[capability_name]
        log(f"[DEBUG] Found execution function: {execution_function.__name__}", level="DEBUG")
        # Pass cap_inputs as a single dictionary argument, rather than unpacking it.
        # The handler functions are defined to accept 'cap_inputs' as a dictionary.
        try:
            result = execution_function(
                agent=agent,
                params_used=params_used,
                cap_inputs=cap_inputs, # Pass the dictionary directly
                knowledge=knowledge,
                context=context,
                all_agent_names_in_system=all_agent_names_in_system
            )
            log(f"[DEBUG] Execution result: {result}", level="DEBUG")
            return result
        except Exception as e:
            log(f"[ERROR] Exception during capability execution: {e}", level="ERROR")
            return {"outcome": "failure_exception", "reward": -1.0, "details": {"error": str(e)}}
    else:
        log(f"[{agent.name}] Attempted to execute unknown capability '{capability_name}'.", level="ERROR")
        return {"outcome": "failure_unknown_capability", "reward": -1.0, "details": {"error": f"Capability '{capability_name}' not found in execution map."}}
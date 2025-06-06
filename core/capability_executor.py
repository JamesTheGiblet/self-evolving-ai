# self-evolving-ai/core/capability_executor.py

"""
Capability Executor Dispatcher

This module is responsible for dispatching capability execution requests
to the appropriate handler functions defined in core.capability_handlers.
"""
from typing import TYPE_CHECKING
import os
import importlib.util
import sys
from utils.logger import log
from core.context_manager import ContextManager

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase

# CAPABILITY_EXECUTION_MAP will be populated dynamically by handler modules
CAPABILITY_EXECUTION_MAP = {}

def register_capability(capability_name: str, handler_function: callable):
    """
    Registers a capability handler function.
    Called by handler modules during their import.
    """
    if capability_name in CAPABILITY_EXECUTION_MAP:
        log(f"[CapabilityExecutor] Warning: Capability '{capability_name}' is being re-registered. Overwriting existing handler.", level="WARN")
    CAPABILITY_EXECUTION_MAP[capability_name] = handler_function
    log(f"[CapabilityExecutor] Registered handler for capability: {capability_name} -> {handler_function.__name__}", level="DEBUG")

def execute_capability_by_name(
    capability_name: str,
    agent,
    params_used: dict,
    cap_inputs: dict,
    knowledge,
    context: ContextManager,
    all_agent_names_in_system: list,
) -> dict:
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
        try:
            result = execution_function(
                agent=agent,
                params_used=params_used,
                cap_inputs=cap_inputs,
                knowledge=knowledge,
                context=context,
                all_agent_names_in_system=all_agent_names_in_system,
            )
            log(f"[DEBUG] Execution result: {result}", level="DEBUG")
            return result
        except Exception as e:
            log(f"[ERROR] Exception during capability execution: {e}", level="ERROR")
            return {"outcome": "failure_exception", "reward": -1.0, "details": {"error": str(e)}}
    else:
        log(f"[{agent.name}] Attempted to execute unknown capability '{capability_name}'.", level="ERROR")
        return {
            "outcome": "failure_unknown_capability",
            "reward": -1.0,
            "details": {"error": f"Capability '{capability_name}' not found in execution map."},
        }

def _load_and_register_handlers_dynamically():
    """
    Scans the 'capability_handlers' directory and imports Python modules
    to trigger their self-registration process.
    """
    # Determine the absolute path to the 'capability_handlers' directory
    # Assumes 'capability_executor.py' is in 'core/' and 'capability_handlers/' is a sibling to 'core/'
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_file_dir) # Goes up one level from 'core' to project root
    handlers_dir = os.path.join(project_root, "capability_handlers")

    log(f"[CapabilityExecutor] Dynamically loading handlers from: {handlers_dir}", level="INFO")

    for filename in os.listdir(handlers_dir):
        if filename.endswith(".py") and not filename.startswith("__init__"):
            module_name_simple = filename[:-3] # e.g., knowledge_handlers
            module_path = os.path.join(handlers_dir, filename)
            
            # Construct a unique module name for importlib, e.g., capability_handlers.knowledge_handlers
            qualified_module_name = f"capability_handlers.{module_name_simple}"

            try:
                spec = importlib.util.spec_from_file_location(qualified_module_name, module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[qualified_module_name] = module # Important for relative imports within the loaded module if any
                    spec.loader.exec_module(module) # This executes the module, triggering self-registration calls
                    log(f"[CapabilityExecutor] Loaded and processed handler module: {qualified_module_name}", level="DEBUG")
            except Exception as e:
                log(f"[CapabilityExecutor] Error loading handler module {qualified_module_name} from {module_path}: {e}", level="ERROR", exc_info=True)
    
    log(f"[CapabilityExecutor] All handler modules processed. Final CAPABILITY_EXECUTION_MAP keys: {list(CAPABILITY_EXECUTION_MAP.keys())}", level="INFO")

_load_and_register_handlers_dynamically()

# capability_handlers/llm_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
from utils import local_llm_connector # Assuming direct use for now
import config # For default model

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_conversational_exchange_llm_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles a conversational exchange with an LLM.
    This is a synchronous call for simplicity in this example.
    An async version would return a request_id and outcome "pending_llm_response".
    """
    prompt_messages = cap_inputs.get("prompt_messages")
    model_name = params_used.get("llm_model", config.DEFAULT_LLM_MODEL)

    if not prompt_messages:
        log(f"[{agent.name}] Failed conversational_exchange_llm_v1: Missing prompt_messages.", level="WARN")
        return {"outcome": "failure_missing_prompt", "reward": -0.2, "details": {"error": "prompt_messages are required."}}

    log(f"[{agent.name}] Executing conversational_exchange_llm_v1. Model: {model_name}. Prompt: {str(prompt_messages)[:100]}", level="INFO")
    
    llm_response = local_llm_connector.call_local_llm_api(prompt_messages=prompt_messages, model_name=model_name)

    if llm_response:
        return {"outcome": "success_llm_response_received", "reward": 0.5, "details": {"llm_response": llm_response}}
    else:
        return {"outcome": "failure_llm_call_failed", "reward": -0.3, "details": {"error": "LLM call did not return a response."}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("conversational_exchange_llm_v1", execute_conversational_exchange_llm_v1)
    log("[LLMHandlers] Successfully registered LLM handlers.", level="DEBUG")
except ImportError:
    log("[LLMHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[LLMHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
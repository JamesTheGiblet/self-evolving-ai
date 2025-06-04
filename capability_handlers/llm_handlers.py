# c:/Users/gilbe/Desktop/self-evolving-ai/capability_handlers/llm_handlers.py
"""
Capability Handlers for LLM-based interactions.
"""
from typing import Dict, List, Any, TYPE_CHECKING, Optional

from utils.logger import log
from utils import local_llm_connector
import config

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager


def execute_conversational_exchange_llm_v1(agent: 'BaseAgent', 
                                       params_used: dict,    
                                       cap_inputs: dict,     
                                       knowledge: 'KnowledgeBase', 
                                       context: 'ContextManager',  
                                       all_agent_names_in_system: list 
                                       ) -> Dict[str, Any]:
    """
    Handles a conversational turn using the configured local LLM.
    """
    messages: List[Dict[str, str]] = []
    conversation_history = cap_inputs.get("conversation_history", [])
    user_input = cap_inputs.get("user_input_text")
    system_prompt = cap_inputs.get("system_prompt", "You are a helpful AI assistant.")
    llm_model_to_use = params_used.get("llm_model", config.DEFAULT_LLM_MODEL)

    if system_prompt: 
        messages.append({"role": "system", "content": system_prompt})
    for entry in conversation_history:
        if isinstance(entry, dict) and "role" in entry and "content" in entry:
            messages.append(entry)
        else:
            log(f"Agent {getattr(agent, 'name', 'Unknown')}: Invalid entry in conversation history: {entry}", level="WARN")

    messages.append({"role": "user", "content": user_input})

    try:
        agent_name = getattr(agent, 'name', 'UnknownAgent')
        log(f"Agent {agent_name}: Dispatching conversational exchange to local LLM. Model: {llm_model_to_use}", level="INFO")

        request_id = local_llm_connector.call_local_llm_api_async(
            prompt_messages=messages,
            model_name=llm_model_to_use,
            temperature=params_used.get("temperature", 0.7),
        )

        if not request_id:
            log(f"Agent {agent_name}: Failed to dispatch LLM conversational exchange.", level="ERROR")
            return {"outcome": "failure_llm_dispatch", "reward": -0.5, "details": "Failed to dispatch LLM conversation."}

        return {
            "outcome": "pending_llm_conversation", 
            "reward": 0.05, 
            "details": {
                "request_id": request_id, 
                "llm_model_used": llm_model_to_use, 
                "user_input_text": user_input, 
                "capability_initiated": "conversational_exchange_llm_v1"
            }
        }
    except Exception as e:
        agent_name = getattr(agent, 'name', 'UnknownAgent')
        log(f"Agent {agent_name}: Error during local LLM conversational exchange: {e}", level="ERROR", exc_info=True)
        return {"outcome": "failure_llm_exception", "reward": -0.5, "details": f"LLM call exception: {e}"}
# c:/Users/gilbe/Desktop/self-evolving-ai/capability_handlers/communication_handlers.py

from typing import Dict, List, Any, TYPE_CHECKING
from utils.logger import log
from core.context_manager import ContextManager

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase # Not directly used in body, but part of signature
else:
    BaseAgent = Any
    KnowledgeBase = Any

def execute_communication_broadcast_v1(agent: BaseAgent, params_used: dict, cap_inputs: dict, knowledge: KnowledgeBase, context: ContextManager, all_agent_names_in_system: list):
    """Executes the communication_broadcast_v1 capability."""
    outcome = "pending"
    details = {}
    immediate_reward = 0.0

    message_content_dict = cap_inputs.get("message_content", {"info": "default broadcast"})
    
    if agent.communication_bus and all_agent_names_in_system: 
        agent.communication_bus.broadcast_message(agent.name, message_content_dict, all_agent_names_in_system)
        agent.memory.log_message_sent()
        outcome = "success"
        details["message_length"] = len(str(message_content_dict)) 
        immediate_reward = 0.35
        log(f"[{agent.name}] Cap 'communication_broadcast_v1' broadcasted: '{message_content_dict}'")
    elif not agent.communication_bus:
        outcome = "failure_no_bus"
        immediate_reward = -0.1
        log(f"[{agent.name}] Cap 'communication_broadcast_v1' failed: No communication bus.")
    else: 
        outcome = "success_no_recipients"
        immediate_reward = 0.05
        log(f"[{agent.name}] Cap 'communication_broadcast_v1' attempted broadcast, but no other agents in system.")
    return {"outcome": outcome, "details": details, "reward": immediate_reward}
# capability_handlers/communication_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_communication_broadcast_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles broadcasting a message to other agents or the system.
    Placeholder implementation.
    """
    message_content = cap_inputs.get("message_content", "Default broadcast message.")
    target_agents = cap_inputs.get("target_agents") # Can be None (all), "system", or a list of agent names

    log(f"[{agent.name}] Executing communication_broadcast_v1. Message: '{message_content}'. Target: {target_agents}", level="INFO")
    # Actual broadcast logic would go here, possibly interacting with CommunicationBus
    # For now, just a log and a successful outcome.
    return {"outcome": "success_message_broadcasted", "reward": 0.3, "details": {"message_sent": message_content, "recipients_targeted": target_agents or "all_active"}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("communication_broadcast_v1", execute_communication_broadcast_v1)
    log("[CommunicationHandlers] Successfully registered communication handlers.", level="DEBUG")
except ImportError:
    log("[CommunicationHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[CommunicationHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
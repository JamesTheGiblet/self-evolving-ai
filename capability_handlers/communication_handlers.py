# capability_handlers/communication_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_communication_broadcast_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles broadcasting a message to other agents or the system.
    """
    message_content = cap_inputs.get("message_content", "Default broadcast message.")
    target_agents = cap_inputs.get("target_agents") # Can be None (all), "system", or a list of agent names
    # The `params_used` could define a default broadcast scope if not in cap_inputs.
    # e.g., broadcast_scope = params_used.get("default_scope", "all_active")

    log(f"[{agent.name}] Executing communication_broadcast_v1. Message: '{message_content}'. Target: {target_agents}", level="INFO")

    if not message_content:
        log(f"[{agent.name}] Cap 'communication_broadcast_v1' failed: message_content is empty.", level="WARN")
        return {"outcome": "failure_empty_message", "reward": -0.1, "details": {"error": "Message content cannot be empty."}}

    # Actual broadcast logic would interact with CommunicationBus
    # Example:
    # success = agent.communication_bus.broadcast_message(
    #     sender_name=agent.name,
    #     message_content=message_content, # This should be the full message dict
    #     target_specification=target_agents # The bus interprets this
    # )
    # For now, simulate success
    success = True

    if success:
        return {"outcome": "success_message_broadcasted", "reward": 0.3, "details": {"message_sent_preview": str(message_content)[:100], "recipients_targeted": target_agents or "all_active"}}
    else:
        # This path would be taken if the communication_bus.broadcast_message call returned False
        log(f"[{agent.name}] Cap 'communication_broadcast_v1' failed: CommunicationBus reported failure.", level="ERROR")
        return {"outcome": "failure_broadcast_failed_on_bus", "reward": -0.2, "details": {"error": "CommunicationBus could not broadcast message."}}

def execute_communication_direct_message_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles sending a direct message to a specific agent.
    """
    recipient_agent_name = cap_inputs.get("recipient_agent_name")
    message_payload = cap_inputs.get("message_content") # The actual data/payload of the message
    message_type = cap_inputs.get("message_type", "direct_message") # Optional message type

    if not recipient_agent_name:
        return {"outcome": "failure_missing_recipient", "reward": -0.2, "details": {"error": "Recipient agent name is required."}}
    if not message_payload:
        return {"outcome": "failure_missing_content", "reward": -0.2, "details": {"error": "Message content is required."}}
    if recipient_agent_name not in all_agent_names_in_system and recipient_agent_name != agent.name: # Allow self-messaging if bus supports
        return {"outcome": "failure_recipient_not_found", "reward": -0.1, "details": {"error": f"Recipient '{recipient_agent_name}' not found in system."}}

    # Construct the full message to be sent, including the type
    full_message_content = {
        "type": message_type,
        "payload": message_payload,
        # Potentially add sender_id, timestamp etc. if not handled by CommunicationBus
    }

    log(f"[{agent.name}] Executing communication_direct_message_v1. To: '{recipient_agent_name}', Type: '{message_type}', Payload: '{str(message_payload)[:100]}'", level="INFO")

    # Actual direct message sending logic via CommunicationBus
    # success = agent.communication_bus.send_direct_message(sender_name=agent.name, recipient_name=recipient_agent_name, content=full_message_content)
    # For now, simulate success
    success = True

    if success:
        return {"outcome": "success_direct_message_sent", "reward": 0.4, "details": {"recipient_sent_to": recipient_agent_name, "message_type_used": message_type, "payload_preview": str(message_payload)[:100]}}
    else:
        log(f"[{agent.name}] Cap 'communication_direct_message_v1' failed to send to '{recipient_agent_name}': CommunicationBus reported failure.", level="ERROR")
        return {"outcome": "failure_direct_message_failed_on_bus", "reward": -0.3, "details": {"error": "CommunicationBus could not send direct message."}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("communication_broadcast_v1", execute_communication_broadcast_v1)
    register_capability("communication_direct_message_v1", execute_communication_direct_message_v1)
    log("[CommunicationHandlers] Successfully registered communication handlers.", level="DEBUG")
except ImportError:
    log("[CommunicationHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[CommunicationHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
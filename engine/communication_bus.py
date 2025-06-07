# engine/communication_bus.py

from utils.logger import log
from collections import defaultdict
from typing import List, Dict, Any, DefaultDict, Optional
import uuid # For generating unique message IDs
import copy
import time
 
class CommunicationBus:
    META_AGENT_NAME = "MetaAgent"  # Default name for the MetaAgent

    def __init__(self, enable_logging: bool = False):
        """Initializes the communication bus with message queues for agents."""
        # Stores message envelopes: { 'id': str, 'sender': str, 'type': str, 'content': dict, 'timestamp': float, 'processed': bool }
        self.message_queues: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.broadcast_log: List[Dict[str, Any]] = []  # Log of all broadcast messages
        self.enable_logging = enable_logging
        self.registered_agents: set[str] = set()
        if self.enable_logging:
            log("[CommunicationBus] Initialized.")

    def register_agent(self, agent_name: str) -> None:
        """Registers an agent explicitly to ensure presence in message queues."""
        if agent_name not in self.registered_agents:
            self.registered_agents.add(agent_name)
            # Initialize empty queue if not present
            _ = self.message_queues[agent_name]
            if self.enable_logging:
                log(f"[CommunicationBus] Registered agent '{agent_name}'.")

    def broadcast_message(self, sender_name: str, content: dict, all_agent_names: List[str]) -> None:
        """
        Sends a message to all other agents.
        The message content should be a dictionary.
        """
        msg_id = str(uuid.uuid4())
        timestamp = time.time()
        message = {
            "id": msg_id,
            "sender": sender_name,
            "type": "broadcast",
            "content": content,
            "timestamp": timestamp,
            "processed": False
        }
        self.broadcast_log.append(message)

        if self.enable_logging:
            log(f"[CommunicationBus] Agent '{sender_name}' broadcasting: {content}")

        unique_agents = set(all_agent_names)
        for agent_name in unique_agents:
            if agent_name != sender_name:
                self.register_agent(agent_name)
                self.message_queues[agent_name].append(copy.deepcopy(message))

    def send_direct_message(self, sender_name: str, recipient_name: str, content: dict) -> None:
        """Sends a message directly to a specific agent."""
        if sender_name == recipient_name:
            if self.enable_logging:
                log(f"[CommunicationBus] Agent '{sender_name}' attempted to send a direct message to itself. Use internal state.")
            return

        self.register_agent(recipient_name)
        msg_id = str(uuid.uuid4())
        message = {
            "id": msg_id,
            "sender": sender_name,
            "type": "direct",
            "content": content,
            "timestamp": time.time(),
            "processed": False
        }
        self.message_queues[recipient_name].append(message)

        if self.enable_logging:
            log(f"[CommunicationBus] Agent '{sender_name}' sent direct message to '{recipient_name}': {content}")

    def get_messages_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all *unprocessed* messages for an agent.
        Messages are not cleared here; they are marked processed via mark_message_processed.
        """
        self.register_agent(agent_name)
        unprocessed_messages = [
            msg for msg in self.message_queues.get(agent_name, []) if not msg.get("processed")
        ]
        return unprocessed_messages

    def mark_message_processed(self, message_id: str) -> None:
        """Marks a specific message as processed across all agent queues it might be in (for broadcasts)."""
        found_and_marked = False
        for agent_queue in self.message_queues.values():
            for msg in agent_queue:
                if msg.get("id") == message_id:
                    msg["processed"] = True
                    found_and_marked = True
                    # For direct messages, we can break early after finding it in one queue.
                    # For broadcast, it might be in multiple, but this loop structure handles it.
        if found_and_marked and self.enable_logging:
            log(f"[CommunicationBus] Marked message ID '{message_id}' as processed.")
        elif not found_and_marked and self.enable_logging:
            log(f"[CommunicationBus] Attempted to mark message ID '{message_id}' as processed, but not found.", level="WARNING")

    def get_message_by_request_id(self, recipient_agent_id: str, request_id_to_find: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific unprocessed message for an agent by looking for 'request_id'
        within the message's 'content' dictionary.
        Marks the message as processed if found.
        """
        self.register_agent(recipient_agent_id)
        agent_queue = self.message_queues.get(recipient_agent_id, [])
        for msg_envelope in agent_queue:
            if not msg_envelope.get("processed"):
                # The request_id is expected inside the 'content' part of the message envelope
                if isinstance(msg_envelope.get("content"), dict) and \
                   msg_envelope["content"].get("request_id") == request_id_to_find:
                    # Mark as processed before returning
                    # self.mark_message_processed(msg_envelope["id"]) # TaskAgent handles this via _handle_pending_skill_responses
                    if self.enable_logging:
                        log(f"[CommunicationBus] Found message for request_id '{request_id_to_find}' for agent '{recipient_agent_id}'.")
                    return msg_envelope
        return None

    def has_messages(self, agent_name: str) -> bool:
        self.register_agent(agent_name)
        return bool(self.message_queues.get(agent_name))

    def get_all_agents(self) -> List[str]:
        """Returns list of all registered agents."""
        return list(self.registered_agents)

    def publish_message(self, publisher_name: str, advertisement_content: Dict[str, Any]) -> None:
        """
        Publishes a message, typically a service advertisement, to a designated listener.
        Currently, this directs the advertisement to the MetaAgent.

        Args:
            publisher_name (str): The name of the agent publishing the advertisement (e.g., a SkillAgent).
            advertisement_content (Dict[str, Any]): The advertisement message, which should include
                                                   a 'type' (e.g., "SERVICE_ADVERTISEMENT") and 'payload'.
        """
        # Ensure MetaAgent is registered to receive messages.
        # MetaAgent should register itself upon its initialization.
        self.register_agent(self.META_AGENT_NAME)

        # The message being sent to MetaAgent is the advertisement_content itself.
        # The sender for the direct message is the original publisher (e.g., a SkillAgent).
        self.send_direct_message(
            sender_name=publisher_name,
            recipient_name=self.META_AGENT_NAME,
            content=advertisement_content
        )

        if self.enable_logging:
            log(f"[CommunicationBus] Agent '{publisher_name}' published service advertisement to '{self.META_AGENT_NAME}'. Services: {advertisement_content.get('payload', {}).get('services_offered', 'N/A')}", level="INFO")

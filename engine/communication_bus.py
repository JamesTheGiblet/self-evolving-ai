# engine/communication_bus.py

from utils.logger import log
from collections import defaultdict
from typing import List, Dict, Any, DefaultDict, Optional, Union # Added Union
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
            _ = self.message_queues[agent_name] # Ensures the key exists in the defaultdict
            if self.enable_logging:
                log(f"[CommunicationBus] Registered agent '{agent_name}'.")

    def broadcast_message(self,
                          sender_name: str,
                          message_content: Dict[str, Any], # This is the full message dict from the sender
                          all_agent_names_in_system: List[str],
                          target_specification: Optional[Union[str, List[str]]] = None
                          ) -> bool:
        """
        Sends a message to specified target agents or all other agents.
        The message_content should be the complete dictionary payload the sender intends to send.
        The bus wraps this content in an envelope with metadata.

        Args:
            sender_name: Name of the agent sending the message.
            message_content: The dictionary payload of the message.
            all_agent_names_in_system: A list of all currently active agent names in the system.
            target_specification:
                - None (default): Broadcast to all other agents in all_agent_names_in_system.
                - "system": Broadcast to all agents in all_agent_names_in_system (including sender if they are part of it, though typically filtered).
                - List[str]: A list of specific agent names to target.

        Returns:
            True if the message was queued for at least one recipient, False otherwise.
        """
        msg_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # The bus creates an envelope. The 'content' of this envelope is the message_content provided by the sender.
        # The 'type' in the envelope indicates it's a broadcast, distinct from the type within message_content.
        envelope = {
            "id": msg_id,
            "sender": sender_name,
            "type": "broadcast", # Bus-level type
            "content": message_content, # Sender's full message
            "timestamp": timestamp,
            "processed": False
        }
        self.broadcast_log.append(envelope)

        if self.enable_logging:
            log(f"[CommunicationBus] Agent '{sender_name}' broadcasting (ID: {msg_id}). Target: {target_specification or 'all_others'}. Content: {str(message_content)[:150]}")

        recipients: List[str] = []
        if target_specification is None: # Broadcast to all *other* agents
            recipients = [name for name in all_agent_names_in_system if name != sender_name]
        elif target_specification == "system": # Broadcast to all agents in the provided list
            recipients = [name for name in all_agent_names_in_system] # Could include sender if they are in the list
        elif isinstance(target_specification, list):
            recipients = [name for name in target_specification if name in all_agent_names_in_system]
            if sender_name in recipients: # Typically, an agent doesn't broadcast to itself this way
                log(f"[CommunicationBus] Warning: Sender '{sender_name}' is in explicit broadcast recipient list. This is unusual.", level="WARN")
        else:
            log(f"[CommunicationBus] Invalid target_specification for broadcast: {target_specification}. No message sent.", level="ERROR")
            return False

        if not recipients:
            log(f"[CommunicationBus] No valid recipients found for broadcast from '{sender_name}' with target '{target_specification}'.", level="WARN")
            return False

        for agent_name in recipients:
            # Ensure recipient is registered and has a queue
            self.register_agent(agent_name)
            # Add a deep copy to prevent modifications in one queue affecting others
            self.message_queues[agent_name].append(copy.deepcopy(envelope))
        
        log(f"[CommunicationBus] Broadcast message ID '{msg_id}' queued for {len(recipients)} recipients: {recipients}", level="DEBUG")
        return True

    def send_direct_message(self, sender_name: str, recipient_name: str, content: dict) -> bool:
        """
        Sends a message directly to a specific agent.
        Returns True if successfully queued, False otherwise.
        """
        if not recipient_name:
            log(f"[CommunicationBus] Agent '{sender_name}' attempted to send direct message with no recipient specified.", level="ERROR")
            return False
        if sender_name == recipient_name: # Allow self-messaging if needed for specific patterns, but log it.
            if self.enable_logging:
                log(f"[CommunicationBus] Agent '{sender_name}' sending a direct message to itself. Content: {str(content)[:100]}", level="DEBUG")
            # return False # Original behavior: disallow self-messaging.
                           # New behavior: allow, as some agent designs might use this.

        self.register_agent(recipient_name) # Ensure recipient is registered
        msg_id = str(uuid.uuid4())
        message = {
            "id": msg_id,
            "sender": sender_name,
            "type": "direct", # Bus-level type
            "content": content, # Sender's full message
            "timestamp": time.time(),
            "processed": False
        }
        self.message_queues[recipient_name].append(message)

        if self.enable_logging:
            log(f"[CommunicationBus] Agent '{sender_name}' sent direct message (ID: {msg_id}) to '{recipient_name}'. Content: {str(content)[:150]}")
        return True

    def get_messages_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all *unprocessed* messages for an agent.
        Messages are not cleared here; they are marked processed via mark_message_processed.
        """
        self.register_agent(agent_name) # Ensure agent is registered and queue exists
        unprocessed_messages = [
            msg for msg in self.message_queues.get(agent_name, []) if not msg.get("processed")
        ]
        return unprocessed_messages

    def mark_message_processed(self, message_id: str) -> None:
        """Marks a specific message as processed across all agent queues it might be in (for broadcasts)."""
        found_and_marked = False
        for agent_queue in self.message_queues.values():
            for msg in agent_queue:
                if msg.get("id") == message_id and not msg.get("processed"): # Only mark if not already processed
                    msg["processed"] = True
                    found_and_marked = True
                    # For direct messages, we can break early after finding it in one queue.
                    # For broadcast, it might be in multiple, but this loop structure handles it.
                    # If it's a direct message, it will only be in one queue.
                    if msg.get("type") == "direct":
                        break 
            if found_and_marked and msg.get("type") == "direct": # Optimization for direct messages
                break


        if found_and_marked and self.enable_logging:
            log(f"[CommunicationBus] Marked message ID '{message_id}' as processed.", level="TRACE")
        elif not found_and_marked and self.enable_logging: # This can happen if a message was already marked processed by another logic path, or if ID is wrong.
            log(f"[CommunicationBus] Attempted to mark message ID '{message_id}' as processed, but not found or already marked.", level="DEBUG")

    def get_message_by_request_id(self, recipient_agent_id: str, request_id_to_find: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific unprocessed message for an agent by looking for 'request_id'
        within the message's 'content.payload' or 'content' dictionary.
        Does NOT mark the message as processed here; the caller should do that.
        """
        self.register_agent(recipient_agent_id) # Ensure agent is registered
        agent_queue = self.message_queues.get(recipient_agent_id, [])
        for msg_envelope in agent_queue:
            if not msg_envelope.get("processed"):
                content_data = msg_envelope.get("content")
                if isinstance(content_data, dict):
                    # Check direct content for request_id (e.g., skill execution requests)
                    if content_data.get("request_id") == request_id_to_find:
                        if self.enable_logging:
                            log(f"[CommunicationBus] Found message for request_id '{request_id_to_find}' (in content) for agent '{recipient_agent_id}'.", level="TRACE")
                        return msg_envelope
                    
                    # Check content.payload for request_id (e.g., TASK_OFFER_RESPONSE)
                    payload_data = content_data.get("payload")
                    if isinstance(payload_data, dict) and payload_data.get("negotiation_id") == request_id_to_find: # TASK_OFFER_RESPONSE uses negotiation_id
                        if self.enable_logging:
                            log(f"[CommunicationBus] Found message for negotiation_id '{request_id_to_find}' (in content.payload) for agent '{recipient_agent_id}'.", level="TRACE")
                        return msg_envelope
                    if isinstance(payload_data, dict) and payload_data.get("contract_id") == request_id_to_find: # CONTRACT_ACKNOWLEDGED uses contract_id
                        if self.enable_logging:
                            log(f"[CommunicationBus] Found message for contract_id '{request_id_to_find}' (in content.payload) for agent '{recipient_agent_id}'.", level="TRACE")
                        return msg_envelope
        return None

    def has_messages(self, agent_name: str) -> bool:
        """Checks if an agent has any unprocessed messages."""
        self.register_agent(agent_name) # Ensure agent is registered
        return any(not msg.get("processed") for msg in self.message_queues.get(agent_name, []))

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
        
        success = self.send_direct_message(
            sender_name=publisher_name,
            recipient_name=self.META_AGENT_NAME,
            content=advertisement_content # The content is the full advertisement message
        )

        if success and self.enable_logging:
            log(f"[CommunicationBus] Agent '{publisher_name}' published service advertisement to '{self.META_AGENT_NAME}'. Services: {advertisement_content.get('payload', {}).get('services_offered', 'N/A')}", level="INFO")
        elif not success and self.enable_logging:
            log(f"[CommunicationBus] Failed to publish service advertisement from '{publisher_name}' to '{self.META_AGENT_NAME}'.", level="ERROR")

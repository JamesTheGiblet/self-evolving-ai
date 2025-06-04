# memory/agent_memory.py

from typing import List, Dict, Any
from utils.logger import log
from typing import List, Dict, Any, Optional

class AgentMemory:
    """
    Stores logs, metrics, and other memory items for a single agent.
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.tick_history: List[Dict[str, Any]] = [] # Renamed from log_entries
        self.messages_sent_count: int = 0
        self.messages_received_count: int = 0
        self.skill_requests_sent: List[Dict[str, Any]] = []
        self.skill_responses_received: List[Dict[str, Any]] = []
        self.skill_timeouts: List[Dict[str, Any]] = []
        self.knowledge_contributions: List[float] = [] # To store knowledge contribution scores
        
        # Attributes to align with MemoryProtocol and FitnessEngine expectations
        self.peer_interactions: List[Dict[str, Any]] = [] # Track interactions with other agents
        self.last_knowledge_contribution_score: float = 0.0 # Store the most recent score
        log(f"[AgentMemory] Initialized for agent {self.agent_id}")

    def log_tick(self, entry: Dict[str, Any]):
        """Logs an entry for the current tick's activities."""
        if "agent_id" not in entry:
            entry["agent_id"] = self.agent_id
        self.tick_history.append(entry)
        # log(f"[{self.agent_id}] Memory: Logged tick entry: {entry.get('action', 'N/A')}", level="TRACE")

    def log_message_sent(self):
        """Logs that a message was sent."""
        self.messages_sent_count += 1
        self.log_tick({
            "action": "message_sent",
            "outcome": "success",
            "current_messages_sent_count": self.messages_sent_count
        })

    def log_message_received(self):
        """Logs that a message was received."""
        self.messages_received_count += 1
        self.log_tick({
            "action": "message_received",
            "outcome": "success",
            "current_messages_received_count": self.messages_received_count
        })

    def log_skill_request_sent(self, tick: int, request_id: str, target_skill_agent_id: str, capability_name: str, request_data: dict):
        """Logs a skill request being sent."""
        log_detail = {
            "tick": tick,
            "request_id": request_id,
            "target_skill_agent_id": target_skill_agent_id,
            "capability_name": capability_name,
            "request_data": request_data
        }
        self.skill_requests_sent.append(log_detail)
        self.log_tick({"action": "skill_request_sent", "details": log_detail})

    def log_skill_response_received(self, tick: int, request_id: str, from_skill_agent_id: str, response_status: str, response_data: dict):
        """Logs a skill response being received."""
        log_detail = {
            "tick": tick,
            "request_id": request_id,
            "from_skill_agent_id": from_skill_agent_id,
            "response_status": response_status,
            "response_data": response_data
        }
        self.skill_responses_received.append(log_detail)
        self.log_tick({"action": "skill_response_received", "details": log_detail})

    def log_skill_timeout(self, tick: int, request_id: str, target_skill_agent_id: str):
        """Logs a skill request timeout."""
        log_detail = {
            "tick": tick,
            "request_id": request_id,
            "target_skill_agent_id": target_skill_agent_id
        }
        self.skill_timeouts.append(log_detail)
        self.log_tick({"action": "skill_timeout", "details": log_detail})

    def log_knowledge_contribution(self, score: float):
        """Logs a knowledge contribution score."""
        self.knowledge_contributions.append(score)
        self.last_knowledge_contribution_score = score # Update the last score
        self.log_tick({
            "action": "knowledge_contribution",
            "outcome": "logged",
            "score": score,
            "cumulative_score": sum(self.knowledge_contributions)
        })
        # log(f"[{self.agent_id}] Memory: Logged knowledge contribution: {score:.2f}", level="DEBUG")

    def log_peer_interaction(self, interaction_type: str, target_agent_id: str, details: Optional[Dict[str, Any]] = None):
        """Logs an interaction with another agent."""
        interaction_log = {
            "type": interaction_type, # e.g., "skill_request_to", "message_to", "received_from"
            "target_agent_id": target_agent_id,
            "details": details or {}
        }
        self.peer_interactions.append(interaction_log)
        self.log_tick({
            "action": "peer_interaction",
            "details": interaction_log
        })

    def get_log(self) -> List[Dict[str, Any]]:
        """Returns all log entries."""
        return self.tick_history
    
    # Methods to comply with MemoryProtocol
    def get_recent_logs(self, count: int = 0) -> List[Dict[str, Any]]:
        """Retrieves recent log entries. If count is 0 or less, returns all."""
        if count <= 0 or count >= len(self.tick_history):
            return list(self.tick_history)  # Return a copy
        return list(self.tick_history[-count:]) # Return a copy of the last 'count' items

    def get_cumulative_knowledge_contribution(self) -> float:
        """
        Calculates and returns the sum of all knowledge contribution scores.
        """
        return sum(self.knowledge_contributions) if self.knowledge_contributions else 0.0

    def get_messages_sent_count(self) -> int:
        return self.messages_sent_count

    def get_messages_received_count(self) -> int:
        return self.messages_received_count

    def get(self, key: str, default: Any = None) -> Any:
        """Generic getter for attributes like 'last_knowledge_contribution_score' or 'peer_interactions'."""
        if key == "last_knowledge_contribution_score": # Explicitly handle for clarity
            return self.last_knowledge_contribution_score
        elif key == "peer_interactions": # Return the list itself
            return self.peer_interactions
        return getattr(self, key, default)
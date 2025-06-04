# engine / fitness_engine.py

from typing import Optional, Protocol, List, Dict, Any
import numpy as np # For averaging

class MemoryProtocol(Protocol):
    tick_history: List[Dict[str, Any]]
    messages_sent: int
    peer_interactions: List[Any]
    knowledge_contribution_score: float

    def get_recent_logs(self, count: int = 0) -> List[Dict[str, Any]]: ...
    def get_messages_sent_count(self) -> int: ...
    # Add get_agent_name if not implicitly available and needed for feedback aggregation
    def get_messages_received_count(self) -> int: ...
    def get(self, key: str, default: Any = None) -> Any: ...

class FitnessEngine: # TODO: Ensure AgentMemory fully implements MemoryProtocol or adjust protocol
    """
    FitnessEngine calculates an agent's fitness score based on
    activity metrics, communications, interactions, knowledge contributions,
    capability performance, and optional user feedback.
    """

    KNOWLEDGE_CONTRIBUTION_NORMALIZATION_FACTOR = 10.0
    CAPABILITY_PERFORMANCE_NORMALIZATION_FACTOR = 20.0

    def __init__(self, context_manager: Optional[object] = None) -> None:
        self.context = context_manager

    def evaluate(self, memory: MemoryProtocol, agent_name: str) -> float:
        # Corrected to use 'tick_logs' as defined in AgentMemory
        recent_logs = memory.get_recent_logs() # get_recent_logs can handle returning all if count is 0 or not provided

        messages_received = memory.get_messages_received_count()
        peer_interactions_len = len(getattr(memory, "peer_interactions", []))
        knowledge_score_raw = memory.get("last_knowledge_contribution_score", 0.0)

        tick_history_len = len(getattr(memory, "tick_history", []))
        messages_sent = memory.get_messages_sent_count()

        tick_factor_raw = min(tick_history_len / 100.0, 1.0)
        comms_factor_raw = min((messages_sent + messages_received) / 20.0, 1.0)
        interaction_factor_raw = min(peer_interactions_len / 10.0, 1.0)
        knowledge_factor_raw = min(knowledge_score_raw / self.KNOWLEDGE_CONTRIBUTION_NORMALIZATION_FACTOR, 1.0)

        capability_net_score = 0.0
        capability_actions_count = 0

        total_reward = 0.0
        num_actions = 0

        # Iterate over recent_logs, which correctly fetches from memory.tick_logs
        for log_entry in recent_logs:
            if isinstance(log_entry, dict) and log_entry.get("action", "").startswith("execute_"):
                capability_actions_count += 1
                outcome = log_entry.get("outcome", "unknown")
                details = log_entry.get("details", {})

                if outcome == "success":
                    capability_net_score += 1.0
                    if "contribution_score" in details:
                        capability_net_score += details["contribution_score"] * 0.5
                    if details.get("items_retrieved", 0) > 0:
                        capability_net_score += 0.2
                    total_reward += 1.0
                elif outcome.startswith("failure_"):
                    capability_net_score -= 0.5
                    total_reward -= 0.5
                num_actions += 1

        # Add base_fitness calculation as requested
        base_fitness = (total_reward / num_actions) if num_actions > 0 else 0.0 # Avoid division by zero

        capability_performance_raw = 0.0
        if capability_actions_count > 0:
            avg_net_score = capability_net_score / capability_actions_count
            capability_performance_raw = (avg_net_score + 0.5) / 2.0
            capability_performance_raw = max(0.0, min(capability_performance_raw, 1.0))

        # Normalize weights to sum to 1.0 (user feedback included)
        default_weights = {
            "tick_factor_weight": 0.05 / 1.2,
            "comms_factor_weight": 0.15 / 1.2,
            "interaction_factor_weight": 0.10 / 1.2,
            "knowledge_factor_weight": 0.30 / 1.2,
            "capability_performance_factor_weight": 0.40 / 1.2,
            "user_feedback_weight": 0.20 / 1.2
        }

        current_weights = default_weights
        if self.context and hasattr(self.context, "get_fitness_weights"):
            ctx_weights = self.context.get_fitness_weights()
            # Normalize ctx_weights if you expect them to be arbitrary
            total = sum(ctx_weights.get(k, v) for k, v in default_weights.items())
            if total > 0:
                current_weights = {k: ctx_weights.get(k, v)/total for k, v in default_weights.items()}

        fitness_score = (
            tick_factor_raw * current_weights["tick_factor_weight"]
            + comms_factor_raw * current_weights["comms_factor_weight"]
            + interaction_factor_raw * current_weights["interaction_factor_weight"]
            + knowledge_factor_raw * current_weights["knowledge_factor_weight"]
            + capability_performance_raw * current_weights["capability_performance_factor_weight"]
        )

        user_feedback_score_raw = 0.0
        if self.context and hasattr(self.context, "get_user_feedback_score"):
            user_feedback_score_raw = self.context.get_user_feedback_score(agent_name)
            user_feedback_score_raw = max(0.0, min(user_feedback_score_raw, 1.0))

        fitness_score += user_feedback_score_raw * current_weights["user_feedback_weight"]

        return max(0.0, min(fitness_score, 1.0))

    def calculate_current_performance_profile(self, agent_memories: List[MemoryProtocol]) -> Dict[str, Any]:
        """
        Calculates a system-wide performance profile by aggregating metrics from all agent memories.
        """
        if not agent_memories:
            return {
                "num_agents": 0,
                "avg_tick_factor": 0,
                "avg_comms_factor": 0,
                "avg_interaction_factor": 0,
                "avg_knowledge_factor": 0,
                "avg_capability_performance": 0,
                "system_success_rate": 0,
                "total_actions_executed": 0
            }

        num_agents = len(agent_memories)
        all_tick_factors = []
        all_comms_factors = []
        all_interaction_factors = []
        all_knowledge_factors = []
        all_capability_performance = []
        
        total_actions = 0
        successful_actions = 0

        for memory in agent_memories:
            # Simplified extraction of factors, similar to evaluate()
            tick_history_len = len(getattr(memory, "tick_history", []))
            messages_sent = memory.get_messages_sent_count()
            messages_received = memory.get_messages_received_count()
            peer_interactions_len = len(getattr(memory, "peer_interactions", []))
            knowledge_score_raw = memory.get("last_knowledge_contribution_score", 0.0)

            all_tick_factors.append(min(tick_history_len / 100.0, 1.0))
            all_comms_factors.append(min((messages_sent + messages_received) / 20.0, 1.0))
            all_interaction_factors.append(min(peer_interactions_len / 10.0, 1.0))
            all_knowledge_factors.append(min(knowledge_score_raw / self.KNOWLEDGE_CONTRIBUTION_NORMALIZATION_FACTOR, 1.0))

            # Capability performance (simplified from evaluate)
            cap_net_score = 0.0
            cap_actions_count = 0
            recent_logs = memory.get_recent_logs()
            for log_entry in recent_logs:
                if isinstance(log_entry, dict) and log_entry.get("action", "").startswith("execute_"):
                    cap_actions_count += 1
                    total_actions +=1
                    outcome = log_entry.get("outcome", "unknown")
                    if outcome == "success":
                        cap_net_score += 1.0
                        successful_actions +=1
                    elif outcome.startswith("failure_"):
                        cap_net_score -= 0.5
            
            if cap_actions_count > 0:
                avg_net_score = cap_net_score / cap_actions_count
                cap_perf_raw = max(0.0, min((avg_net_score + 0.5) / 2.0, 1.0))
                all_capability_performance.append(cap_perf_raw)

        return {
            "num_agents": num_agents,
            "avg_tick_factor": float(np.mean(all_tick_factors)) if all_tick_factors else 0,
            "avg_comms_factor": float(np.mean(all_comms_factors)) if all_comms_factors else 0,
            "avg_interaction_factor": float(np.mean(all_interaction_factors)) if all_interaction_factors else 0,
            "avg_knowledge_factor": float(np.mean(all_knowledge_factors)) if all_knowledge_factors else 0,
            "avg_capability_performance": float(np.mean(all_capability_performance)) if all_capability_performance else 0,
            "system_success_rate": (successful_actions / total_actions) if total_actions > 0 else 0,
            "total_actions_executed": total_actions
        }

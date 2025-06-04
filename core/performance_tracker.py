# core/performance_tracker.py
from typing import Dict, List, Any, Optional
from utils.logger import log

class CapabilityPerformanceTracker:
    def __init__(self, initial_capabilities: Optional[List[str]] = None):
        self.performance: Dict[str, Dict[str, Any]] = {}
        self.usage_frequency: Dict[str, int] = {}
        if initial_capabilities:
            for cap_name in initial_capabilities:
                self.performance[cap_name] = {"attempts": 0, "successes": 0, "total_reward": 0.0}
                self.usage_frequency[cap_name] = 0
        log("[CapabilityPerformanceTracker] Initialized.")

    def add_capability(self, cap_name: str):
        """Adds a new capability to track if not already present."""
        if cap_name not in self.performance:
            self.performance[cap_name] = {"attempts": 0, "successes": 0, "total_reward": 0.0}
            log(f"[CapabilityPerformanceTracker] Added tracking for new capability: {cap_name}")
        if cap_name not in self.usage_frequency:
            self.usage_frequency[cap_name] = 0
            
    def record_capability_chosen(self, cap_name: str):
        """Records that a capability was chosen for execution."""
        self.add_capability(cap_name) # Ensure it's tracked
        self.usage_frequency[cap_name] = self.usage_frequency.get(cap_name, 0) + 1

    def record_capability_execution(self, cap_name: str, outcome_is_success: bool, reward: float):
        """Records the outcome of a capability execution."""
        self.add_capability(cap_name) # Ensure it's tracked
        
        self.performance[cap_name]["attempts"] += 1
        if outcome_is_success:
            self.performance[cap_name]["successes"] += 1
        self.performance[cap_name]["total_reward"] += reward

    def get_stats_for_capability(self, cap_name: str) -> Optional[Dict[str, Any]]:
        """Returns performance statistics for a specific capability."""
        return self.performance.get(cap_name)

    def get_all_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """Returns all performance statistics."""
        return self.performance.copy()

    def get_usage_frequency(self, cap_name: str) -> int:
        """Returns the usage frequency of a specific capability."""
        return self.usage_frequency.get(cap_name, 0)
        
    def get_all_usage_frequencies(self) -> Dict[str, int]:
        """Returns all usage frequencies."""
        return self.usage_frequency.copy()

    def get_overall_average_reward(self) -> float:
        """Calculates the average reward across all capability executions."""
        total_reward = 0.0
        total_attempts = 0
        for cap_stats in self.performance.values():
            total_reward += cap_stats.get("total_reward", 0.0)
            total_attempts += cap_stats.get("attempts", 0)
        
        return (total_reward / total_attempts) if total_attempts > 0 else 0.0

    def get_config_data(self) -> Dict[str, Any]:
        """Returns data suitable for agent configuration (e.g., for saving state)."""
        return {
            "performance": self.performance.copy(),
            "usage_frequency": self.usage_frequency.copy()
        }

    def load_config_data(self, data: Dict[str, Any]):
        """Loads data from a configuration (e.g., when recreating an agent)."""
        self.performance = data.get("performance", {})
        self.usage_frequency = data.get("usage_frequency", {})
        log("[CapabilityPerformanceTracker] Loaded data from config.")


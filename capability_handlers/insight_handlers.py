# capability_handlers/insight_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_triangulated_insight_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles generating insights by triangulating data from multiple sources.
    `cap_inputs` should contain:
        - "focus_topic": str, e.g., "system_efficiency_degradation"
        - "data_sources": List[str], e.g., ["knowledge_base:recent_facts", "meta_agent:agent_fitness_scores"]
        - "analysis_depth" (optional): int, e.g., 3
    """
    focus_topic = cap_inputs.get("focus_topic")
    data_sources = cap_inputs.get("data_sources")
    analysis_depth = cap_inputs.get("analysis_depth", 1) # Default depth

    if not focus_topic or not data_sources:
        return {"outcome": "failure_missing_inputs", "reward": -0.2, "details": {"error": "Missing 'focus_topic' or 'data_sources' in cap_inputs."}}

    log(f"[{agent.name}] Executing triangulated_insight_v1. Topic: '{focus_topic}'. Sources: {data_sources}. Depth: {analysis_depth}", level="INFO")

    # Placeholder for actual insight generation logic.
    # This would involve:
    # 1. Parsing data_sources and fetching data from KnowledgeBase, MetaAgent, CommunicationBus logs, etc.
    # 2. Analyzing the collected data in relation to the focus_topic.
    # 3. Synthesizing an insight.

    simulated_insight_summary = f"Simulated insight for '{focus_topic}': Analysis of {len(data_sources)} sources at depth {analysis_depth} suggests a potential correlation related to recent system events."
    details = {
        "focus_topic": focus_topic,
        "data_sources_queried": data_sources,
        "analysis_depth_used": analysis_depth,
        "insight_summary": simulated_insight_summary,
        "confidence_score": 0.75 # Simulated confidence
    }

    # The agent's internal logic (e.g., within its FSM or behavior tree)
    # might use this insight to update its beliefs, goals, or trigger other actions.
    # For example, it could store this insight in its working memory or the knowledge base.
    if hasattr(agent, 'memory') and hasattr(agent.memory, 'add_working_memory_item'):
        agent.memory.add_working_memory_item(
            item_type="generated_insight",
            content=details,
            source_capability="triangulated_insight_v1"
        )

    return {"outcome": "success_insight_generated", "reward": 0.6, "details": details}

def execute_anomaly_detection_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Detects anomalies in specified system metrics.
    `cap_inputs` should contain:
        - "metric_to_monitor": str, e.g., "average_agent_energy"
        - "monitoring_window_ticks": int, e.g., 50
        - "detection_parameters": dict, e.g., {"method": "std_dev_threshold", "std_dev_multiplier": 3.0}
                                      or {"method": "absolute_change_threshold", "change_threshold_percent": 50}
    """
    metric_to_monitor = cap_inputs.get("metric_to_monitor")
    monitoring_window_ticks = cap_inputs.get("monitoring_window_ticks", 20)
    detection_params = cap_inputs.get("detection_parameters")

    if not metric_to_monitor or not detection_params or "method" not in detection_params:
        return {"outcome": "failure_missing_anomaly_inputs", "reward": -0.2, "details": {"error": "Missing 'metric_to_monitor' or valid 'detection_parameters' in cap_inputs."}}

    log(f"[{agent.name}] Executing anomaly_detection_v1. Metric: '{metric_to_monitor}'. Window: {monitoring_window_ticks} ticks. Params: {detection_params}", level="INFO")

    # Placeholder for actual anomaly detection:
    # 1. Fetch historical data for 'metric_to_monitor' over 'monitoring_window_ticks' (e.g., from ContextManager or MetaAgent).
    # 2. Apply the specified 'detection_parameters.method'.
    # For simulation, we'll randomly decide if an anomaly is found.
    import random
    anomaly_detected = random.choice([True, False, False]) # Skew towards no anomaly for realism
    simulated_current_value = random.uniform(50, 150)
    simulated_threshold = 100 if detection_params["method"] == "absolute_change_threshold" else (simulated_current_value * 0.3 if anomaly_detected else simulated_current_value * 1.5)

    details = {
        "metric_monitored": metric_to_monitor,
        "anomaly_detected": anomaly_detected,
        "current_value_simulated": f"{simulated_current_value:.2f}",
        "threshold_details_simulated": f"Method: {detection_params['method']}, Threshold Value (simulated): {simulated_threshold:.2f}"
    }
    reward = 0.7 if anomaly_detected else 0.1 # Higher reward for "finding" an anomaly

    return {"outcome": "success_anomaly_check_complete", "reward": reward, "details": details}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("triangulated_insight_v1", execute_triangulated_insight_v1)
    register_capability("anomaly_detection_v1", execute_anomaly_detection_v1)
    log("[InsightHandlers] Successfully registered insight handlers.", level="DEBUG")
except ImportError:
    log("[InsightHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[InsightHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
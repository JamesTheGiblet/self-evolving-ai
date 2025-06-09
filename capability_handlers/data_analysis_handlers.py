# capability_handlers/data_analysis_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
from collections import Counter # For advanced analysis

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_data_analysis_basic_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles basic data analysis tasks.
    Supported analysis_types (from params_used): "summary", "type_check", "length".
    """
    data_to_analyze = cap_inputs.get("data")
    analysis_type = params_used.get("analysis_type", "summary") # Default analysis type

    log(f"[{agent.name}] Executing data_analysis_basic_v1. Type: '{analysis_type}'. Data preview: {str(data_to_analyze)[:100]}", level="INFO")

    if data_to_analyze is None: # Explicitly check for None, as empty list/string can be valid
        return {"outcome": "failure_no_data_provided", "reward": -0.1, "details": {"error": "No 'data' provided in cap_inputs."}}

    details = {"analysis_type_performed": analysis_type}
    reward = 0.2 # Base reward for successful basic analysis

    if analysis_type == "summary":
        details["data_type"] = str(type(data_to_analyze).__name__)
        try:
            details["data_length"] = len(data_to_analyze)
        except TypeError:
            details["data_length"] = "N/A (type does not have length)"
        details["summary"] = f"Data is of type '{details['data_type']}' with length {details['data_length']}."
        outcome = "success_summary_generated"
    elif analysis_type == "type_check":
        details["data_type"] = str(type(data_to_analyze).__name__)
        outcome = "success_type_checked"
    elif analysis_type == "length":
        try:
            details["data_length"] = len(data_to_analyze)
            outcome = "success_length_calculated"
        except TypeError:
            outcome = "failure_cannot_get_length"
            details["error"] = f"Data of type '{type(data_to_analyze).__name__}' does not have a length."
            reward = -0.05
    else:
        outcome = "failure_unknown_analysis_type"
        details["error"] = f"Unsupported analysis_type: {analysis_type}"
        reward = -0.05

    return {"outcome": outcome, "reward": reward, "details": details}

def execute_data_analysis_advanced_v1(
    agent: 'BaseAgent',
    params_used: Dict, # Not typically used here, analysis type comes from cap_inputs
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles more advanced data analysis tasks.
    `cap_inputs` should contain:
        - "data_to_analyze": The data.
        - "analysis_type": e.g., "descriptive_statistics", "text_keyword_frequency", "value_counts".
        - "parameters" (optional): Dict for analysis_type specific params.
            - For "text_keyword_frequency": {"top_n": 5}
    """
    data_to_analyze = cap_inputs.get("data_to_analyze")
    analysis_type = cap_inputs.get("analysis_type")
    parameters = cap_inputs.get("parameters", {})

    log(f"[{agent.name}] Executing data_analysis_advanced_v1. Type: '{analysis_type}'. Params: {parameters}. Data preview: {str(data_to_analyze)[:100]}", level="INFO")

    if data_to_analyze is None:
        return {"outcome": "failure_no_data_provided", "reward": -0.2, "details": {"error": "Missing 'data_to_analyze' in cap_inputs."}}
    if not analysis_type:
        return {"outcome": "failure_no_analysis_type", "reward": -0.2, "details": {"error": "Missing 'analysis_type' in cap_inputs."}}

    details = {"analysis_type_performed": analysis_type, "parameters_used": parameters}
    reward = 0.0
    outcome = "pending"

    if analysis_type == "descriptive_statistics":
        if isinstance(data_to_analyze, list) and all(isinstance(n, (int, float)) for n in data_to_analyze):
            if not data_to_analyze:
                details["statistics"] = {"count": 0, "sum": 0, "mean": "N/A", "min": "N/A", "max": "N/A"}
            else:
                count = len(data_to_analyze)
                data_sum = sum(data_to_analyze)
                mean = data_sum / count
                data_min = min(data_to_analyze)
                data_max = max(data_to_analyze)
                details["statistics"] = {"count": count, "sum": data_sum, "mean": mean, "min": data_min, "max": data_max}
            outcome = "success_descriptive_stats_calculated"
            reward = 0.5
        else:
            outcome = "failure_invalid_data_for_descriptive_stats"
            details["error"] = "Data must be a list of numbers for descriptive_statistics."
            reward = -0.1

    elif analysis_type == "text_keyword_frequency":
        if isinstance(data_to_analyze, str):
            top_n = parameters.get("top_n", 5)
            if not isinstance(top_n, int) or top_n <= 0: top_n = 5
            
            words = ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in data_to_analyze).split()
            if not words:
                details["keyword_frequency"] = {}
            else:
                word_counts = Counter(words)
                details["keyword_frequency"] = dict(word_counts.most_common(top_n))
            outcome = "success_keyword_frequency_calculated"
            reward = 0.4
        else:
            outcome = "failure_invalid_data_for_text_analysis"
            details["error"] = "Data must be a string for text_keyword_frequency."
            reward = -0.1

    elif analysis_type == "value_counts":
        if isinstance(data_to_analyze, list):
            details["value_counts"] = dict(Counter(data_to_analyze))
            outcome = "success_value_counts_calculated"
            reward = 0.3
        else:
            outcome = "failure_invalid_data_for_value_counts"
            details["error"] = "Data must be a list for value_counts."
            reward = -0.1
    else:
        outcome = "failure_unsupported_advanced_analysis_type"
        details["error"] = f"Unsupported analysis_type: {analysis_type}"
        reward = -0.15

    return {"outcome": outcome, "reward": reward, "details": details}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("data_analysis_basic_v1", execute_data_analysis_basic_v1)
    register_capability("data_analysis_advanced_v1", execute_data_analysis_advanced_v1)
    log("[DataAnalysisHandlers] Successfully registered data analysis handlers.", level="DEBUG")
except ImportError:
    log("[DataAnalysisHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[DataAnalysisHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
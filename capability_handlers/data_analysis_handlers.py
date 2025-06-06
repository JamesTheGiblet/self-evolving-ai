# capability_handlers/data_analysis_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_data_analysis_basic_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles basic data analysis tasks.
    Placeholder implementation.
    """
    data_to_analyze = cap_inputs.get("data")
    analysis_type = params_used.get("analysis_type", "summary")
    log(f"[{agent.name}] Executing data_analysis_basic_v1. Type: {analysis_type}. Data: {str(data_to_analyze)[:100]}", level="INFO")
    # Basic analysis logic here
    if data_to_analyze:
        return {"outcome": "success_analysis_complete", "reward": 0.4, "details": {"analysis_type": analysis_type, "result_summary": f"Analyzed data of type {type(data_to_analyze).__name__}"}}
    else:
        return {"outcome": "failure_no_data", "reward": -0.1, "details": {"error": "No data provided for analysis."}}

def execute_data_analysis_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles more advanced data analysis tasks.
    Placeholder implementation.
    """
    # This would be a more complex version of the basic analysis
    log(f"[{agent.name}] Executing data_analysis_v1 (advanced).", level="INFO")
    return execute_data_analysis_basic_v1(agent, params_used, cap_inputs, knowledge, context, all_agent_names_in_system) # Delegate for now

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("data_analysis_basic_v1", execute_data_analysis_basic_v1)
    register_capability("data_analysis_v1", execute_data_analysis_v1)
    log("[DataAnalysisHandlers] Successfully registered data analysis handlers.", level="DEBUG")
except ImportError:
    log("[DataAnalysisHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[DataAnalysisHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
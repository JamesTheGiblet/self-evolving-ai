# capability_handlers/sequence_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager

# --- Handler function definitions ---
def execute_sequence_executor_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: List[str]) -> Dict[str, Any]:
    """
    Handles executing a predefined sequence of actions or capabilities.
    Placeholder implementation. The actual execution of a sequence is complex
    and would likely involve the agent's internal logic or a dedicated sequence engine.
    This handler might initiate such a sequence.
    """
    sequence_name = cap_inputs.get("sequence_name", params_used.get("default_sequence_name", "default_behavior_loop"))
    sequence_params = cap_inputs.get("sequence_params", {})

    log(f"[{agent.name}] Executing sequence_executor_v1. Sequence: {sequence_name}. Params: {sequence_params}", level="INFO")
    
    # Here, the agent would typically trigger its internal FSM or behavior tree
    # to start executing the named sequence.
    # For simulation, we just acknowledge the request.
    # The "reward" might depend on the successful initiation, not completion.
    return {"outcome": "success_sequence_initiated", "reward": 0.1, "details": {"sequence_name": sequence_name, "status": "Sequence execution initiated by agent."}}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("sequence_executor_v1", execute_sequence_executor_v1)
    log("[SequenceHandlers] Successfully registered sequence handlers.", level="DEBUG")
except ImportError:
    log("[SequenceHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[SequenceHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
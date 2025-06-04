# agents/capabilities/data_analysis.py

import os
import sys
# Corrected sys.path.append to be BEFORE the import and point to project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.logger import log

class DataAnalysisBasicV1:
    """
    Hypothetical capability class for 'data_analysis_basic_v1'.
    """
    CAPABILITY_NAME = "data_analysis_basic_v1"

    def __init__(self):
        pass

    def execute(self, agent_id: str, agent_memory, data_input: dict):
        """
        Executes the primary logic of the data analysis capability.
        """
        try:
            log(f"[{agent_id}] Attempting primary execution of '{self.CAPABILITY_NAME}' with input: {data_input}")
            # Simulate a condition that causes primary failure for demonstration
            if data_input.get("trigger_failure", False):
                raise ValueError("Simulated primary analysis failure in data_analysis_basic_v1")
            
            # Example primary logic:
            result = {"analysis_summary": f"Data processed: {len(data_input)} keys.", "status": "success"}
            agent_memory.add_to_log(f"'{self.CAPABILITY_NAME}' primary execution successful.")
            return result
        except Exception as e:
            log(f"[{agent_id}] Primary execution of '{self.CAPABILITY_NAME}' failed: {e}. Attempting fallback.")
            return self._fallback(agent_id, agent_memory, e, data_input)

    def _fallback(self, agent_id: str, agent_memory, original_error: Exception, data_input: dict):
        """
        Fallback logic for the data analysis capability.
        """
        fallback_message_prefix = f"[{agent_id}] Fallback for '{self.CAPABILITY_NAME}'"
        try:
            # Robust check for agent_memory.log (though AgentMemory fix should prevent issues)
            if not hasattr(agent_memory, 'log') or not isinstance(agent_memory.log, list):
                log(f"{fallback_message_prefix}: AgentMemory.log is missing or not a list (type: {type(getattr(agent_memory, 'log', None))}). Initializing to allow logging.")
                agent_memory.log = [] # Ensure it's a list so the fallback can at least log its attempt
            
            agent_memory.add_to_log(f"{fallback_message_prefix} triggered due to: {original_error}. Input was: {data_input}")
            log(f"{fallback_message_prefix} completed. Returning default/safe response.")
            return {"status": "fallback_success", "reason": str(original_error), "message": "Default analysis result due to error."}
        except Exception as fallback_e:
            # This is where the original error message you saw would be logged if agent_memory.log.append (or add_to_log) failed.
            log(f"[ERROR] [{agent_id}] Cap '{self.CAPABILITY_NAME}' fallback itself FAILED critically: {fallback_e}. Original error: {original_error}")
            # The error message from your logs indicates this path was taken because agent_memory.log was not usable.
            # With the AgentMemory fix and the robust check above, this critical failure path for *this specific reason* should be avoided.
            return {"status": "fallback_failed", "reason": str(fallback_e), "critical_error": "Fallback mechanism encountered an unexpected error."}
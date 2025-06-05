# core/skill_agent.py
from typing import Dict, Any, Optional, TYPE_CHECKING, List
from core.agent_base import BaseAgent
from utils.logger import log
import config
from memory.agent_memory import AgentMemory 
import json # For parsing if skill_tool still returns string by mistake
import copy # For deepcopying details
from engine.identity_engine import IdentityEngine # For type hinting

if TYPE_CHECKING:
    from core.context_manager import ContextManager
    from memory.knowledge_base import KnowledgeBase
    from engine.communication_bus import CommunicationBus
    from skills.base_skill import BaseSkillTool

class SkillAgent(BaseAgent):
    AGENT_TYPE = "skill"

    def __init__(self, 
                 skill_tool: 'BaseSkillTool', 
                 context_manager: 'ContextManager',
                 knowledge_base: 'KnowledgeBase',
                 communication_bus: 'CommunicationBus', # Added comma
                 agent_name: Optional[str] = None, # Keep for flexibility, though BaseAgent.name is primary
                 capabilities: Optional[List[str]] = None, 
                 capability_params: Optional[Dict[str, Any]] = None,
                 lineage_id: Optional[str] = None,
                 generation: int = 0,
                 behavior_mode: Optional[str] = None, # Added
                 agent_id: Optional[str] = None,
                 identity_engine: Optional['IdentityEngine'] = None): # Added identity_engine

        name_for_base = agent_id or agent_name or \
                        (skill_tool.skill_name if hasattr(skill_tool, 'skill_name') else "UnnamedSkillAgent")
        
        # Ensure capabilities list is correctly formed for BaseAgent
        provided_capabilities = capabilities
        if not provided_capabilities and hasattr(skill_tool, 'skill_name'):
            # If no capabilities are explicitly passed, use the skill_tool's name as its capability.
            # This aligns with how TaskRouter might identify it.
            # We might want a more structured capability name like "skill_tool_name_v1"
            # Local import to avoid circular dependency at module level if skill_loader imports SkillAgent
            from core.skill_loader import generate_lineage_id_from_skill_name # Local import
            temp_lineage = generate_lineage_id_from_skill_name(skill_tool.skill_name)
            provided_capabilities = [temp_lineage.replace("skill_", "", 1) + "_v1"] # Example: "calendar_ops_v1"

        elif not provided_capabilities:
            provided_capabilities = ["unknown_skill_capability_v1"]

        # Determine lineage_id more robustly
        derived_lineage_id = lineage_id
        if not derived_lineage_id and hasattr(skill_tool, 'skill_name'):
            from core.skill_loader import generate_lineage_id_from_skill_name # Local import
            derived_lineage_id = generate_lineage_id_from_skill_name(skill_tool.skill_name)
        elif not derived_lineage_id: # Fallback if skill_tool has no name or lineage_id not provided
            derived_lineage_id = name_for_base.split('-gen')[0]

        super().__init__(
            name=name_for_base, # This will be the unique ID like "skill_calendar_ops-gen0"
            agent_id=agent_id or name_for_base, # Ensure agent_id is also set
            context_manager=context_manager,
            knowledge_base=knowledge_base,
            communication_bus=communication_bus,
            agent_type=SkillAgent.AGENT_TYPE,
            capabilities=provided_capabilities, 
            capability_params=capability_params,
            initial_energy=config.DEFAULT_INITIAL_ENERGY * 0.5, 
            max_age=config.DEFAULT_MAX_AGENT_AGE, 
            lineage_id=derived_lineage_id,
            generation=generation,
            behavior_mode=behavior_mode or "reactive", # Skill agents are typically reactive
            identity_engine=identity_engine # Pass to BaseAgent
        )
        self.skill_tool = skill_tool
        
        # Ensure self.memory is initialized for SkillAgent as well
        if not hasattr(self, 'memory') or self.memory is None:
             self.memory = AgentMemory(agent_id=self.id)

        log(f"SkillAgent '{self.name}' (ID: {self.id}) initialized. Skill: '{self.skill_tool.skill_name if hasattr(self.skill_tool, 'skill_name') else 'UnknownSkill'}', Lineage: {self.lineage_id}, Gen: {self.generation}.", level="INFO")

    def execute_skill_action(self, skill_command_str: str, params: Dict[str, Any], invoking_agent_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a specific command using its skill_tool.
        This method is called by TaskAgents (via invoke_skill_agent_v1 capability)
        or internally by the SkillAgent's message handler.
        """
        log(f"[{self.name}] Executing skill command: '{skill_command_str}' requested by Agent '{invoking_agent_id}'. Params: {params}, TaskID: {task_id}", level="INFO")

        current_tick = self.context_manager.get_tick()

        action_name_for_log_parts = ["skill_action"]
        if hasattr(self.skill_tool, 'skill_name') and self.skill_tool.skill_name:
            action_name_for_log_parts.append(self.skill_tool.skill_name.lower())

        # Extract the first word of the command string for logging, if available
        command_first_word = skill_command_str.split(' ')[0] if skill_command_str else "unknown_cmd"
        action_name_for_log_parts.append(command_first_word)
        action_name_for_log = "_".join(action_name_for_log_parts)


        action_result: Dict[str, Any] = {}
        final_response_to_task_agent: Dict[str, Any] = {
            "status": "failure_internal_error",
            "message": "Skill execution did not complete as expected.",
            "data": None,
            "request_id": task_id # Include task_id in the payload
        }

        try:
            # The skill_tool.execute method should now return a dictionary
            raw_execution_result = self.skill_tool.execute(skill_command_str)

            if isinstance(raw_execution_result, dict):
                action_result = raw_execution_result
            elif isinstance(raw_execution_result, str):
                log(f"[{self.name}] Skill '{self.skill_tool.skill_name}' returned a string, attempting JSON parse. Consider updating skill to return a dict.", level="WARN")
                try:
                    action_result = json.loads(raw_execution_result)
                    if not isinstance(action_result, dict):
                        raise ValueError("Parsed result is not a dictionary.")
                except (json.JSONDecodeError, ValueError) as e:
                    log(f"[{self.name}] Failed to parse skill execution result string: '{raw_execution_result}'. Error: {e}", level="ERROR")
                    action_result = {"success": False, "message": f"Skill execution produced unparsable string result: {e}", "data": None, "error": f"JSON parse error: {e}"}
            else:
                log(f"[{self.name}] Skill '{self.skill_tool.skill_name}' returned an unexpected type: {type(raw_execution_result)}. Expected dict.", level="ERROR")
                action_result = {"success": False, "message": f"Skill execution returned unexpected type: {type(raw_execution_result)}", "data": None, "error": f"Unexpected return type: {type(raw_execution_result)}"}

            is_success = action_result.get("success", False)
            reward = 1.0 if is_success else -0.5

            log_entry_details = {
                "invoked_by": invoking_agent_id,
                "task_id": task_id,
                "command_executed": skill_command_str,
                "params_received": copy.deepcopy(params),
                "skill_tool_response": copy.deepcopy(action_result)
            }

            self.memory.log_tick({
                "tick": current_tick,
                "action": action_name_for_log,
                "invoked_by": invoking_agent_id,
                "task_id": task_id,
                "command": skill_command_str,
                "params": copy.deepcopy(params),
                "outcome": "success" if is_success else "failure",
                "reward": reward,
                "details": log_entry_details
            })

            if is_success:
                log(f"[{self.name}] Skill command '{skill_command_str}' executed successfully by '{self.skill_tool.skill_name}'. Data: {action_result.get('data')}", level="INFO")
                final_response_to_task_agent = {
                    "status": "success",
                    "data": action_result.get("data"),
                    "message": action_result.get("message", "Skill executed successfully."),
                    "request_id": task_id # Include task_id in the payload
                }
            else:
                error_msg = action_result.get('error', action_result.get('message', 'No specific error message from skill.'))
                log(f"[{self.name}] Skill command '{skill_command_str}' execution failed by '{self.skill_tool.skill_name}'. Error: {error_msg}", level="WARN")
                final_response_to_task_agent = {
                    "status": "failure_skill_reported",
                    "data": action_result.get("data"), "message": error_msg, "error": error_msg,
                    "request_id": task_id # Include task_id in the payload
                }

        except Exception as e:
            log(f"[{self.name}] Critical error during execution of skill command '{skill_command_str}': {e}", level="ERROR", exc_info=True)
            reward = -1.0
            self.memory.log_tick({
                "tick": current_tick,
                "action": action_name_for_log,
                "invoked_by": invoking_agent_id,
                "task_id": task_id,
                "command": skill_command_str,
                "params": copy.deepcopy(params),
                "outcome": "exception",
                "reward": reward,
                "details": {"error": str(e), "traceback": True}
            })
            final_response_to_task_agent = {
                "status": "failure_exception_in_skill_agent",
                "message": f"Exception in SkillAgent: {str(e)}",
                "data": None,
                "error": str(e),
                "request_id": task_id # Include task_id in the payload
            }

        # Send the response back to the invoking agent
        if invoking_agent_id and task_id:
             self.communication_bus.send_direct_message(self.name, invoking_agent_id, final_response_to_task_agent)
             log(f"[{self.name}] Sent response for ReqID {task_id} to {invoking_agent_id}. Status: {final_response_to_task_agent['status']}", level="DEBUG")
        else:
             log(f"[{self.name}] Cannot send response: invoking_agent_id ({invoking_agent_id}) or task_id ({task_id}) missing.", level="WARN")

        return final_response_to_task_agent

    def _handle_message(self, sender_id: str, message_content: Dict[str, Any]) -> bool:
        """
        Handles a received message. Overrides BaseAgent to process skill requests.
        Returns True if the message was handled by this method, False otherwise.
        """
        intended_skill_action_category = message_content.get('action')
        request_id = message_content.get('request_id')
        params_from_message = message_content.get('data', {})

        # Check if this message is a skill execution request (sent by invoke_skill_agent_v1)
        if intended_skill_action_category and request_id:
            log(f"[{self.name}] Identified skill execution request from {sender_id} (ReqID: {request_id}): Intended Action Category '{intended_skill_action_category}'", level="INFO")

            actual_command_for_tool = None
            # Determine the actual command string for the skill_tool.execute() method
            # This logic is copied from SkillAgent.run's previous message loop
            if intended_skill_action_category == "maths_operation" and "maths_command" in params_from_message:
                actual_command_for_tool = params_from_message["maths_command"]
            elif intended_skill_action_category == "file_operation" and "file_command" in params_from_message:
                actual_command_for_tool = params_from_message["file_command"]
            elif intended_skill_action_category == "web_operation" and "web_command" in params_from_message:
                actual_command_for_tool = params_from_message["web_command"]
            elif intended_skill_action_category == "api_call" and "api_command" in params_from_message: # For ApiConnector
                actual_command_for_tool = params_from_message["api_command"]
            elif intended_skill_action_category == "calendar_operation" and "calendar_command" in params_from_message: # For Calendar
                actual_command_for_tool = params_from_message["calendar_command"]
            elif intended_skill_action_category == "echo_operation" and "echo_command" in params_from_message: # For EchoSkill
                actual_command_for_tool = params_from_message["echo_command"]
            elif intended_skill_action_category == "weather_query" and "weather_command" in params_from_message: # For Weather
                 actual_command_for_tool = params_from_message["weather_command"]
            # Add more specific handlers if 'action' is a category and 'data' contains the true command
            elif intended_skill_action_category in ["log_summary", "complexity_analysis", "basic_stats_analysis"] and "data_points" in params_from_message:
                # For these, the command_str for the tool might be the JSON payload itself, or a specific command
                # This depends on how the DataAnalysisSkill is designed to be called.
                # If DataAnalysisSkill expects a command like "summarize_logs" and then the data:
                # actual_command_for_tool = f"{intended_skill_action_category} {json.dumps(params_from_message)}"
                # Or if it just takes the JSON string directly for its _execute_skill:
                actual_command_for_tool = json.dumps(params_from_message)
            else:
                # Fallback: if 'action' is not a known category that nests the command,
                # assume 'action' itself is the command string for the tool.
                # This might be the case if TaskAgent sends the direct skill command in 'action'.
                log(f"[{self.name}] Using 'action' field ('{intended_skill_action_category}') from message content directly as command for skill tool. Params from message data: {params_from_message}", level="DEBUG")
                actual_command_for_tool = intended_skill_action_category
                # If params_from_message are arguments, they need to be appended to actual_command_for_tool
                # This part needs careful consideration based on how TaskAgent formats messages.
                # For now, assuming if 'action' is the command, 'data' might be ignored by some simple skills
                # or used by more complex ones that parse their own data.

            if actual_command_for_tool is None:
                log(f"[{self.name}] Could not determine actual command for skill tool from message: {message_content}", level="WARN")
                # Send a failure response back
                error_response = {
                    "status": "failure_bad_request",
                    "message": "SkillAgent could not determine the command to execute.",
                    "data": None,
                    "error": "Malformed skill request.",
                    "request_id": request_id # Include request_id in the payload
                }
                self.communication_bus.send_direct_message(self.name, sender_id, error_response)
                # Note: We don't mark the message processed here; _process_communication does that after _handle_message returns.
                return True # Indicate message was handled (as a bad request)

            log(f"[{self.name}] Final command string for skill tool '{self.skill_tool.skill_name}': '{actual_command_for_tool}'", level="DEBUG")

            # Execute the skill action. execute_skill_action now sends the response.
            self.execute_skill_action(
                skill_command_str=actual_command_for_tool,
                params=params_from_message, # Pass the original 'data' payload for context/logging
                invoking_agent_id=sender_id,
                task_id=request_id
            )
            # Note: We don't mark the message processed here; _process_communication does that after _handle_message returns.
            return True # Indicate message was handled (as a skill request)

        # If it's not a skill request message, let the base class handle it.
        # This is where generic broadcasts or other message types would be handled by BaseAgent.
        return super()._handle_message(sender_id, message_content)

    def get_config(self) -> dict:
        base_config = super().get_config()
        base_config.update({
            "skill_tool_name": self.skill_tool.skill_name if hasattr(self.skill_tool, 'skill_name') else "UnknownSkillTool"
        })
        return base_config

    def get_fitness(self) -> Dict[str, float]:
        # current_tick = self.context_manager.get_tick() # Not directly used in this method's logic
        log_entries = self.memory.get_log()
        
        num_executions = 0
        total_reward = 0.0
        successful_executions = 0

        for entry in log_entries:
            action = entry.get("action", "")
            if action.startswith("skill_action_"): 
                num_executions += 1
                total_reward += entry.get("reward", 0.0)
                if entry.get("outcome") == "success":
                    successful_executions += 1
        
        avg_reward = (total_reward / num_executions) if num_executions > 0 else 0.0
        
        if num_executions > 0:
            normalized_reward_component = (avg_reward + 1) / 2 # Map avg_reward from [-1, 1] to [0, 1]
            normalized_reward_component = max(0, min(1, normalized_reward_component))
        else:
            normalized_reward_component = 0.0 # No executions, so no reward evidence, low utility
 
        success_rate_component = (successful_executions / num_executions) if num_executions > 0 else 0.0

        survival_bonus = min(self.age * 0.0001, 0.1) 

        energy_factor = (self.energy / (config.DEFAULT_INITIAL_ENERGY * 0.5)) if (config.DEFAULT_INITIAL_ENERGY * 0.5) > 0 else 0 
        energy_bonus = (energy_factor - 0.5) * 0.1 

        fitness = (normalized_reward_component * 0.5) + \
                  (success_rate_component * 0.3) + \
                  (survival_bonus * 0.1) + \
                  (energy_bonus * 0.1)
        fitness = max(0.0, min(1.0, fitness))

        log(f"[{self.name}] Fitness Calc: Fit={fitness:.3f} (Execs:{num_executions}, SuccessRate:{success_rate_component:.2f}, AvgRw:{avg_reward:.2f}, NormRw:{normalized_reward_component:.2f}, Surv:{survival_bonus:.2f}, En:{energy_bonus:.3f})", level="DEBUG")
        return {"fitness": fitness, "executions": float(num_executions), "average_reward": avg_reward}

    def run(self, context: 'ContextManager', knowledge: 'KnowledgeBase', all_agent_names_in_system: List[str], agent_info_map: Dict[str, Dict[str, Any]]):
        if not super().run_cycle(): 
            return
        
        # Message processing is now handled by BaseAgent.run_cycle() -> _process_communication()
        # which calls our overridden _handle_message for each message.
        # The logic for identifying and executing skill requests is now in _handle_message.

        # The rest of the run method can remain, primarily for logging the start/end of the tick.
        memory_size_at_run_start = len(self.memory.get_log()) if self.memory else 0
        log_data_run_start = {
            "tick": context.get_tick(), # Use context.get_tick() for current tick
            "action": "skill_agent_run_start", 
            "age": self.age, 
            "energy": self.energy,
            "memory_size": memory_size_at_run_start
        }
        if not hasattr(self, 'memory') or self.memory is None:
            self.memory = AgentMemory(agent_id=self.id)
        self.memory.log_tick(log_data_run_start) # Log the start of the run cycle

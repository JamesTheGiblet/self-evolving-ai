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
        This method is called by TaskAgents (via invoke_skill_agent_v1 capability).
        """
        log(f"[{self.name}] Received request from Agent '{invoking_agent_id}' to execute skill command: '{skill_command_str}'. Params: {params}, TaskID: {task_id}", level="INFO")

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
            "data": None
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
                final_response_to_task_agent = {"status": "success", "data": action_result.get("data"), "message": action_result.get("message", "Skill executed successfully.")}
            else:
                error_msg = action_result.get('error', action_result.get('message', 'No specific error message from skill.'))
                log(f"[{self.name}] Skill command '{skill_command_str}' execution failed by '{self.skill_tool.skill_name}'. Error: {error_msg}", level="WARN")
                final_response_to_task_agent = {"status": "failure_skill_reported", "data": action_result.get("data"), "message": error_msg, "error": error_msg}

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
            final_response_to_task_agent = {"status": "failure_exception_in_skill_agent", "message": f"Exception in SkillAgent: {str(e)}", "data": None, "error": str(e)}
        
        return final_response_to_task_agent


    def get_config(self) -> dict:
        base_config = super().get_config()
        base_config.update({
            "skill_tool_name": self.skill_tool.skill_name if hasattr(self.skill_tool, 'skill_name') else "UnknownSkillTool"
        })
        return base_config

    def get_fitness(self) -> Dict[str, float]:
        current_tick = self.context_manager.get_tick()
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
        
        normalized_reward_component = (avg_reward + 1) / 2 
        normalized_reward_component = max(0, min(1, normalized_reward_component))

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
        
        current_tick = context.get_tick()
        memory_size_at_run_start = len(self.memory.get_log()) if self.memory else 0
        log_data_run_start = {
            "tick": current_tick, 
            "action": "skill_agent_run_start", 
            "age": self.age, 
            "energy": self.energy,
            "memory_size": memory_size_at_run_start
        }
        if not hasattr(self, 'memory') or self.memory is None:
            self.memory = AgentMemory(agent_id=self.id)
        self.memory.log_tick(log_data_run_start)

        log(f"[{self.name}] SkillAgent run cycle. Status: {self.state['status']}. Memory size: {memory_size_at_run_start + 1}", level="TRACE")
        
        messages = self.communication_bus.get_messages_for_agent(self.name)
        processed_a_skill_request_this_tick = False

        for msg in messages:
            log(f"[{self.name}] Received message ID {msg['id']} from {msg['sender']}: {str(msg['content'])[:100]}", level="TRACE")
            
            message_content = msg['content']
            # 'action' from the message is the *intended skill action category* (e.g., "maths_operation")
            # The actual command for the tool might be nested in 'data'.
            intended_skill_action_category = message_content.get('action') 
            request_id = message_content.get('request_id')
            params_from_message = message_content.get('data', {}) 

            # --- Added Detailed Debug Logging ---
            log(f"[{self.name}] DEBUG RUN MSG_CONTENT: {message_content}", level="DEBUG")
            log(f"[{self.name}] DEBUG RUN: intended_skill_action_category='{intended_skill_action_category}' (type: {type(intended_skill_action_category)}), req_id='{request_id}' (type: {type(request_id)}), processed_flag={processed_a_skill_request_this_tick}", level="DEBUG")
            log(f"[{self.name}] DEBUG RUN: Condition check: intended_skill_action_category is truthy? {bool(intended_skill_action_category)}, req_id is truthy? {bool(request_id)}, not processed_flag? {not processed_a_skill_request_this_tick}", level="DEBUG")
            # --- End Detailed Debug Logging ---

            if intended_skill_action_category and request_id and not processed_a_skill_request_this_tick:
                log(f"[{self.name}] Identified skill execution request from {msg['sender']} (ReqID: {request_id}): Intended Action Category '{intended_skill_action_category}'", level="INFO")
                
                actual_command_for_tool = None
                # Determine the actual command string for the skill_tool.execute() method
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
                # Example for data analysis skills if they are invoked this way:
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
                    actual_command_for_tool = intended_skill_action_category # The 'action' field from the message
                    # If params_from_message are arguments, they need to be appended to actual_command_for_tool
                    # This part needs careful consideration based on how TaskAgent formats messages.
                    # For now, assuming if 'action' is the command, 'data' might be ignored by some simple skills
                    # or used by more complex ones that parse their own data.

                if actual_command_for_tool is None:
                    log(f"[{self.name}] Could not determine actual command for skill tool from message: {message_content}", level="WARN")
                    # Send a failure response back
                    error_response = {"status": "failure_bad_request", "message": "SkillAgent could not determine the command to execute.", "data": None, "error": "Malformed skill request."}
                    self.communication_bus.send_direct_message(self.name, msg['sender'], error_response, request_id=request_id)
                    self.communication_bus.mark_message_processed(msg['id']) # Mark as processed to avoid loop
                    continue # Move to the next message

                log(f"[{self.name}] Final command string for skill tool '{self.skill_tool.skill_name}': '{actual_command_for_tool}'", level="DEBUG")

                response_content = self.execute_skill_action(
                    skill_command_str=actual_command_for_tool, 
                    params=params_from_message, # Pass the original 'data' payload for context/logging
                    invoking_agent_id=msg['sender'],
                    task_id=request_id 
                )
                self.communication_bus.send_direct_message(self.name, msg['sender'], response_content, request_id=request_id)
                processed_a_skill_request_this_tick = True 
            elif msg['content'].get("type") == "broadcast_info": # Example of handling other message types
                log(f"[{self.name}] Noted broadcast: {msg['content'].get('data')}", level="DEBUG")
            else: # If not a skill request and not handled by other specific logic
                if not self._handle_message(msg['sender'], message_content): # Call BaseAgent's handler
                    log(f"[{self.name}] Message from {msg['sender']} not specifically handled by SkillAgent or BaseAgent: {str(message_content)[:100]}", level="DEBUG")

            self.communication_bus.mark_message_processed(msg['id'])

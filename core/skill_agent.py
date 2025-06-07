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
                 communication_bus: 'CommunicationBus',
                 name: Optional[str] = None, # Added explicit name parameter
                 agent_id: Optional[str] = None,
                 identity_engine: Optional['IdentityEngine'] = None,
                 **config_kwargs): # Catch all other config values

        # Determine name for BaseAgent: prioritize explicit name, then agent_id, then from skill_tool
        # config_kwargs.get('name') is no longer needed here as name is passed explicitly from MetaAgent
        name_for_base = name or \
                        agent_id or \
                        (skill_tool.skill_name if hasattr(skill_tool, 'skill_name') else "UnnamedSkillAgent")
        
        # 'name' should have been passed explicitly and popped from config_kwargs by MetaAgent.
        # Popping here again is a safeguard / no-op if MetaAgent handled it.
        config_kwargs.pop('name', None)

        # Remove 'skill_tool_name' from config_kwargs as it's not a BaseAgent parameter
        config_kwargs.pop('skill_tool_name', None)
        
        # Determine capabilities for BaseAgent: prioritize from config_kwargs, then derive, then default
        provided_capabilities = config_kwargs.pop('capabilities', None)
        if not provided_capabilities and hasattr(skill_tool, 'skill_name'):
            from core.skill_loader import generate_lineage_id_from_skill_name # Local import
            temp_lineage = generate_lineage_id_from_skill_name(skill_tool.skill_name)
            provided_capabilities = [temp_lineage.replace("skill_", "", 1) + "_v1"] # Example: "calendar_ops_v1"
        elif not provided_capabilities:
            provided_capabilities = ["unknown_skill_capability_v1"]

        # Determine lineage_id for BaseAgent: prioritize from config_kwargs, then derive, then default
        derived_lineage_id = config_kwargs.pop('lineage_id', None)
        if not derived_lineage_id and hasattr(skill_tool, 'skill_name'):
            from core.skill_loader import generate_lineage_id_from_skill_name # Local import
            derived_lineage_id = generate_lineage_id_from_skill_name(skill_tool.skill_name)
        elif not derived_lineage_id:
            derived_lineage_id = name_for_base.split('-gen')[0]

        # Resolve initial_energy: prioritize from config_kwargs, then default for SkillAgent
        resolved_initial_energy = config_kwargs.pop('initial_energy', config.DEFAULT_INITIAL_ENERGY * 0.5)
        
        # Resolve max_age: prioritize from config_kwargs, then default system max_age
        resolved_max_age = config_kwargs.pop('max_age', config.DEFAULT_MAX_AGENT_AGE)

        # Resolve generation: prioritize from config_kwargs, then default
        resolved_generation = config_kwargs.pop('generation', 0)

        # Resolve behavior_mode: prioritize from config_kwargs, then default for SkillAgent
        resolved_behavior_mode = config_kwargs.pop('behavior_mode', "reactive")
        
        # Resolve capability_params: prioritize from config_kwargs, then default (None means BaseAgent uses its own default)
        resolved_capability_params = config_kwargs.pop('capability_params', None)

        super().__init__(
            name=name_for_base, # This will be the unique ID like "skill_calendar_ops-gen0"
            agent_id=agent_id or name_for_base, # Ensure agent_id is also set
            context_manager=context_manager,
            knowledge_base=knowledge_base,
            communication_bus=communication_bus,
            agent_type=SkillAgent.AGENT_TYPE,
            capabilities=provided_capabilities, 
            capability_params=resolved_capability_params,
            initial_energy=resolved_initial_energy, 
            max_age=resolved_max_age, 
            lineage_id=derived_lineage_id,
            generation=resolved_generation,
            behavior_mode=resolved_behavior_mode,
            identity_engine=identity_engine,
            **config_kwargs # Pass any remaining unhandled kwargs from the config
        )
        self.skill_tool = skill_tool
        
        # Initialize self.state if it doesn't exist (should be handled by BaseAgent, but good for safety)
        if not hasattr(self, 'state') or self.state is None:
            self.state = {}
        self.state.setdefault('active_contracts', {})

        # Ensure self.memory is initialized for SkillAgent as well
        if not hasattr(self, 'memory') or self.memory is None:
             self.memory = AgentMemory(agent_id=self.id)
        log(f"SkillAgent '{self.name}' (ID: {self.id}) initialized. Skill: '{self.skill_tool.skill_name if hasattr(self.skill_tool, 'skill_name') else 'UnknownSkill'}', Lineage: {self.lineage_id}, Gen: {self.generation}, InitialEnergy: {self.energy:.2f}, MaxAge: {self.max_age}.", level="INFO")

        # Advertise services upon initialization
        if self.communication_bus:
            self.advertise_services()

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
    
    def _evaluate_task_offer(self, proposed_terms: Dict[str, Any], capability_requested: str, tool_command_str: str) -> Dict[str, Any]:
        """
        Evaluates a task offer from a TaskAgent.
        Returns a dictionary with "response_type" ("accept", "reject") and "reason"/"actual_terms".
        """
        # Simple evaluation logic for now:
        # - Check if agent has enough energy for the potential cost.
        # - Check if the reward is positive.
        # - Check if the capability is something this agent can do.
        # - If not acceptable, consider a counter-offer.

        # Cost to SkillAgent for executing the skill (internal estimate)
        estimated_internal_cost = self.get_estimated_cost() # This is cost per invocation, not per specific command yet
        
        # Max cost the TaskAgent is willing for the SkillAgent to charge it (this is different from internal cost)
        max_chargeable_cost_by_task_agent = proposed_terms.get("max_energy_cost_to_task_agent", 0.0)
        proposed_reward_by_task_agent = proposed_terms.get("reward_for_success", 0.0)
        
        # Profitability check (simplified)
        # If reward > internal_cost AND chargeable_cost >= internal_cost
        # This is a very basic model. A real model would consider opportunity cost, risk, etc.
        is_profitable = (proposed_reward_by_task_agent > estimated_internal_cost) and \
                        (max_chargeable_cost_by_task_agent >= estimated_internal_cost)
        
        can_perform_capability = capability_requested in self.capabilities # Check if the conceptual capability is offered
        # A more detailed check might involve validating the tool_command_str against the skill_tool

        if self.energy > estimated_internal_cost and is_profitable and can_perform_capability:
            log(f"[{self.name}] Evaluating TASK_OFFER for '{capability_requested}': ACCEPTING. Proposed reward: {proposed_reward_by_task_agent}, Max cost to task_agent: {max_chargeable_cost_by_task_agent}, My estimated internal cost: {estimated_internal_cost}", level="INFO")
            return {
                "response_type": "accept",
                "actual_terms": { # SkillAgent confirms the terms it accepts
                    "reward_for_success": proposed_reward_by_task_agent,
                    "energy_cost_charged_to_task_agent": min(max_chargeable_cost_by_task_agent, estimated_internal_cost + (proposed_reward_by_task_agent - estimated_internal_cost) * 0.1), # Charge a bit more than cost if profitable
                    "deadline_ticks": proposed_terms.get("deadline_ticks")
                }
            }
        else:
            # --- Attempt Counter-Offer Logic ---
            # If capable and has energy, but offer wasn't profitable enough
            if self.energy > estimated_internal_cost and can_perform_capability and not is_profitable:
                # Try to make a counter-offer: ask for a bit more reward
                # and propose to charge its internal cost if that's acceptable to the TaskAgent.
                counter_reward = estimated_internal_cost + (self.base_tick_energy_cost * 2) # e.g., cost + 2 ticks profit
                counter_cost_charged = estimated_internal_cost # Propose to charge its internal cost

                # Only make counter-offer if it's better than original and within TaskAgent's max cost
                if counter_reward > proposed_reward_by_task_agent and counter_cost_charged <= max_chargeable_cost_by_task_agent:
                    log(f"[{self.name}] Evaluating TASK_OFFER for '{capability_requested}': COUNTER-OFFERING. Original Reward: {proposed_reward_by_task_agent}, Counter Reward: {counter_reward}. Original Max Cost: {max_chargeable_cost_by_task_agent}, Counter Cost Charged: {counter_cost_charged}", level="INFO")
                    return {
                        "response_type": "counter_offer",
                        "counter_proposed_terms": {
                            "reward_for_success": counter_reward,
                            "energy_cost_charged_to_task_agent": counter_cost_charged,
                            "deadline_ticks": proposed_terms.get("deadline_ticks") # Keep original deadline for now
                        },
                        "reason": "Original offer not sufficiently profitable."
                    }

            # --- Rejection Logic (if no acceptance or counter-offer) ---
            reason = ""
            if self.energy <= estimated_internal_cost: reason += "Insufficient energy. "
            if not is_profitable and not (self.energy > estimated_internal_cost and can_perform_capability): # Avoid double-logging if counter was possible
                reason += "Offer not profitable. "
            if not can_perform_capability: reason += f"Cannot perform '{capability_requested}'. "
            if not reason: reason = "Offer terms not acceptable." # Generic fallback

            log(f"[{self.name}] Evaluating TASK_OFFER for '{capability_requested}': REJECTING. Reason: {reason.strip()}", level="INFO")
            return {
                "response_type": "reject",
                "reason": reason.strip()
            }

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
            "memory_size": memory_size_at_run_start,
        }
        if not hasattr(self, 'memory') or self.memory is None:
            self.memory = AgentMemory(agent_id=self.id)
        self.memory.log_tick(log_data_run_start) # Log the start of the run cycle

    def _handle_message(self, sender_id: str, message_content: Dict[str, Any]) -> bool:
        """Handles a received message. Overrides BaseAgent to process skill requests and task offers."""
        message_type = message_content.get('type')
        payload = message_content.get('payload', {})

        # Initialize self.state if it doesn't exist (should be handled by BaseAgent, but good for safety)
        if not hasattr(self, 'state') or self.state is None:
            self.state = {}
        self.state.setdefault('active_contracts', {})

        if message_type == "TASK_OFFER":
            negotiation_id = payload.get('negotiation_id')
            requester_agent_id = payload.get('requester_agent_id')
            capability_requested = payload.get('capability_requested')
            tool_command_str = payload.get('tool_command_str')
            proposed_terms = payload.get('proposed_terms')

            log(f"[{self.name}] Received TASK_OFFER (NegID: {negotiation_id}) from '{requester_agent_id}' for '{capability_requested}'. Command: '{tool_command_str}'", level="INFO")

            if not all([negotiation_id, requester_agent_id, capability_requested, tool_command_str, proposed_terms]):
                log(f"[{self.name}] Invalid TASK_OFFER received, missing fields. Payload: {payload}", level="WARN")
                # Optionally send a reject message with "bad_request"
                return True # Handled (as a bad offer)

            evaluation_result = self._evaluate_task_offer(proposed_terms, capability_requested, tool_command_str)

            response_message = {
                "type": "TASK_OFFER_RESPONSE",
                "payload": {
                    "negotiation_id": negotiation_id, # Echo back the ID
                    "responder_agent_id": self.id,
                    "response_type": evaluation_result["response_type"],
                    "actual_terms": evaluation_result.get("actual_terms"), # For 'accept'
                    "counter_proposed_terms": evaluation_result.get("counter_proposed_terms"), # For 'counter_offer'
                    "reason": evaluation_result.get("reason")
                },
                "recipient_agent_id": requester_agent_id # Send back to original requester
            }
            self.communication_bus.send_direct_message(self.name, requester_agent_id, response_message)
            log(f"[{self.name}] Sent TASK_OFFER_RESPONSE (NegID: {negotiation_id}) to '{requester_agent_id}'. Type: {evaluation_result['response_type']}", level="DEBUG")
            return True # Message handled
        
        elif message_type == "CONTRACT_AGREEMENT":
            contract_id = payload.get('contract_id')
            task_agent_id = payload.get('task_agent_id')
            log(f"[{self.name}] Received CONTRACT_AGREEMENT (ID: {contract_id}) from TaskAgent '{task_agent_id}'.", level="INFO")

            if not all([contract_id, task_agent_id, payload.get('agreed_terms')]):
                log(f"[{self.name}] Invalid CONTRACT_AGREEMENT received, missing fields. Payload: {payload}", level="WARN")
                # Optionally send a reject/error message
                return True

            # Store the contract details
            self.state['active_contracts'][contract_id] = {
                "task_agent_id": task_agent_id,
                "capability_requested": payload.get('capability_requested'),
                "tool_command_str": payload.get('tool_command_str'),
                "agreed_terms": payload.get('agreed_terms'),
                "status": "acknowledged", # Mark as acknowledged by SkillAgent
                "received_at_tick": self.context_manager.get_tick()
            }
            
            # Send CONTRACT_ACKNOWLEDGED back to TaskAgent
            ack_message = {"type": "CONTRACT_ACKNOWLEDGED", "payload": {"contract_id": contract_id, "skill_agent_id": self.id, "status": "acknowledged"}}
            self.communication_bus.send_direct_message(self.name, task_agent_id, ack_message)
            log(f"[{self.name}] Sent CONTRACT_ACKNOWLEDGED for ContractID '{contract_id}' to '{task_agent_id}'.", level="INFO")
            return True

        # Existing skill execution request handling
        intended_skill_action_category = message_content.get('action') # Used by older direct invocation
        request_id = payload.get('request_id', message_content.get('request_id')) # Check payload first for consistency
        params_from_message = payload.get('data', message_content.get('data', {}))

        # Check if this message is a skill execution request (sent by invoke_skill_agent_v1 or after negotiation)
        # The 'action' key might be used by direct invocations, while negotiated ones might use a different structure.
        # For now, we assume 'tool_command_str' in params_from_message is the primary way to get the command.
        if request_id and params_from_message.get("tool_command_str"): # More specific check for execution
            log(f"[{self.name}] Identified skill execution request from {sender_id} (ReqID: {request_id}): Action Category '{intended_skill_action_category or 'N/A'}'", level="INFO")

            actual_command_for_tool = params_from_message.get("tool_command_str")

            if not actual_command_for_tool and intended_skill_action_category: # Fallback
                log(f"[{self.name}] 'tool_command_str' not found. Using 'action' field ('{intended_skill_action_category}') as command. Data: {params_from_message}", level="DEBUG")
                actual_command_for_tool = intended_skill_action_category

            if actual_command_for_tool is None:
                log(f"[{self.name}] Could not determine actual command for skill tool from message: {message_content}", level="WARN")
                error_response = {
                    "status": "failure_bad_request", "message": "SkillAgent could not determine command.",
                    "data": None, "error": "Malformed skill request.", "request_id": request_id
                }
                if self.communication_bus: self.communication_bus.send_direct_message(self.name, sender_id, error_response)
                return True

            log(f"[{self.name}] Final command for tool '{self.skill_tool.skill_name}': '{actual_command_for_tool}'", level="DEBUG")
            self.execute_skill_action(
                skill_command_str=actual_command_for_tool,
                params=params_from_message,
                invoking_agent_id=sender_id,
                task_id=request_id
            )
            return True

        return super()._handle_message(sender_id, message_content)

    # --- Dynamic Service Discovery Methods ---

    def get_estimated_cost(self) -> float:
        """
        Placeholder for calculating the estimated energy cost for this agent's services.
        Could be dynamic based on skill complexity or internal state.
        """
        # For now, a simple base cost, perhaps related to its base tick energy cost or a fixed value.
        return self.base_tick_energy_cost * 5 + 0.1 # Example: 5 ticks worth of base cost + a small fixed fee

    def get_current_load(self) -> float:
        """
        Placeholder for reporting current load. 0.0 (idle) to 1.0 (max capacity).
        """
        # This would require tracking active tasks or message queue length.
        return 0.1 # Default to mostly idle for now

    def get_reputation(self) -> float:
        """
        Placeholder for fetching/calculating the agent's reputation.
        This could be based on successful task completions, user feedback, etc.
        """
        return 0.75 # Default to a decent reputation

    def advertise_services(self):
        """Broadcasts the agent's capabilities and service offerings."""
        service_details = {
            "estimated_cost_per_invocation": self.get_estimated_cost(),
            "current_load_factor": self.get_current_load(),
            "reputation_score": self.get_reputation(),
            "skill_tool_name": self.skill_tool.skill_name if hasattr(self.skill_tool, 'skill_name') else "UnknownSkillTool"
        }
        advertisement_message = {
            "type": "SERVICE_ADVERTISEMENT", # New message type for CommunicationBus
            "payload": {
                "agent_id": self.id, # Use self.id which is the unique agent_id
                "agent_name": self.name,
                "agent_type": self.agent_type,
                "services_offered": list(self.capabilities), # self.capabilities lists the services it provides
                "service_details": service_details,
                "timestamp": self.context_manager.get_tick() # For freshness
            }
        }
        if hasattr(self.communication_bus, 'publish_message'):
            self.communication_bus.publish_message(self.name, advertisement_message) # MetaAgent or ServiceRegistry would listen
            log(f"Agent {self.name} (ID: {self.id}) advertised services: {list(self.capabilities)}. Details: {service_details}", level="INFO")
        else:
            log(f"Agent {self.name} (ID: {self.id}) could not advertise services: 'publish_message' method not found on CommunicationBus. Advertisement: {advertisement_message}", level="WARN")

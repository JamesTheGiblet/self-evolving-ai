# self-evolving-ai/core/task_agent.py

import copy
import random
import time
from typing import Dict, Any, TYPE_CHECKING, Optional, List
import uuid
from core.agent_base import BaseAgent
# from core.llm_planner import LLMPlanner # LLMPlanner is used by interpret_goal_with_llm_v1 capability
from utils.logger import log
from core.skill_definitions import SKILL_CAPABILITY_MAPPING
from core.performance_tracker import CapabilityPerformanceTracker
from core.agent_rl import AgentRLSystem
import config
from utils import local_llm_connector
from engine.identity_engine import IdentityEngine # For type hinting

if TYPE_CHECKING:
    from core.context_manager import ContextManager
    from memory.knowledge_base import KnowledgeBase
    from engine.communication_bus import CommunicationBus
    from core.capability_input_preparer import CapabilityInputPreparer
    from memory.agent_memory import AgentMemory
    from agents.code_gen_agent import LLMInterface # Added for LLM capabilities

CapabilityParamsType = Optional[Dict[str, Dict]]
CapabilitiesType = Optional[List[str]]

class TaskAgent(BaseAgent):
    AGENT_TYPE = "task"

    def __init__(self,
                 agent_id: str,
                 name: str,
                 context_manager: 'ContextManager',
                 knowledge_base: 'KnowledgeBase',
                 communication_bus: 'CommunicationBus',
                 capabilities: CapabilitiesType = None,
                 capability_params: CapabilityParamsType = None,
                 behavior_mode: str = "explore",
                 generation: int = 0,
                 lineage_id: Optional[str] = None,
                 initial_focus: Optional[str] = None,
                 initial_goal: Optional[Dict] = None,
                 max_age: Optional[int] = None,
                 insight_confidence_threshold: float = 0.5,
                 insight_fitness_time_window: Optional[int] = None,
                 initial_state_override: Optional[Dict[str, Any]] = None,
                 role: Optional[str] = None,
                 alpha: float = 0.1,
                 gamma: float = 0.9,
                 epsilon: float = 0.1,
                 max_pending_skill_requests: int = 5,
                 symptom_investigation_priority: float = 0.5,
                 generic_task_failure_rate: float = 0.1,
                 llm_model_name: str = config.DEFAULT_LLM_MODEL
                 , agent_type: Optional[str] = None, # Added to accept from config unpacking
                 identity_engine: Optional['IdentityEngine'] = None, # Added
                 llm_interface: Optional['LLMInterface'] = None, # Added for LLM capabilities
                ):

        resolved_initial_energy = config.DEFAULT_INITIAL_ENERGY
        if initial_state_override and "energy_level" in initial_state_override:
            resolved_initial_energy = float(initial_state_override["energy_level"])
        elif initial_state_override and "energy" in initial_state_override:
            resolved_initial_energy = float(initial_state_override["energy"])

        super().__init__(name=name,
                         context_manager=context_manager,
                         knowledge_base=knowledge_base,
                         communication_bus=communication_bus,
                         agent_type=TaskAgent.AGENT_TYPE,
                         capabilities=capabilities,
                         capability_params=capability_params,
                         initial_energy=resolved_initial_energy,
                         max_age=max_age,
                         lineage_id=lineage_id,
                         generation=generation,
                         identity_engine=identity_engine) # Pass to BaseAgent

        # State initialization should happen AFTER the super().__init__ call
        # which sets up the base self.state.
        if initial_state_override:
            # Merge relevant parts of initial_state_override into self.state
            # self.state is initialized in BaseAgent's __init__
            for key, value in initial_state_override.items():
                # Only override if the key is one we want to carry over, or if it's not already set by BaseAgent
                if key in ['pending_llm_operations', 'pending_skill_requests', 'last_failed_skill_details', 'current_goal', 'goal_history', 'conversation_history'] or key not in self.state:
                    self.state[key] = copy.deepcopy(value)
            log(f"[{self.name}] TaskAgent state merged with overrides: {list(initial_state_override.keys())}", level="DEBUG")

        self.id = agent_id
        self.role = role
        self.behavior_mode = behavior_mode
        self.initial_focus = initial_focus
        self.initial_energy = resolved_initial_energy
        self.initial_goal = copy.deepcopy(initial_goal) if initial_goal else {"type": "idle", "details": "Default initial idle state."}
        self.current_goal: Dict[str, Any] = copy.deepcopy(self.initial_goal)
        self.goal_history: List[Dict[str, Any]] = []
        self.rl_system = AgentRLSystem(alpha=alpha, gamma=gamma, epsilon=epsilon)
        self.problem_observation_chance = 0.05

        self.insight_confidence_threshold = insight_confidence_threshold
        self.insight_fitness_time_window = insight_fitness_time_window
        
        self.max_pending_skill_requests = max_pending_skill_requests
        self.symptom_investigation_priority = symptom_investigation_priority
        self.generic_task_failure_rate = generic_task_failure_rate
        self.llm_model_name = llm_model_name
        self.llm_interface = llm_interface # Store the LLM interface
        self.complex_goal_completion_reward = 2.0
        self.energy_efficiency_bonus_factor = 0.5
        self.pending_delayed_rewards: List[Dict[str, Any]] = []
        
        # Initialize state keys if not present from override
        self.state.setdefault('pending_llm_operations', {})
        self.state.setdefault('pending_skill_requests', {})
        self.last_diagnosis: Optional[Dict[str, Any]] = None
        self.state.setdefault('pending_contract_acknowledgements', {}) # For tracking contract agreements
        self.state.setdefault('pending_negotiations', {}) # For tracking skill offers
        self.conversation_history: List[Dict[str, str]] = []

        self.capability_performance_tracker = CapabilityPerformanceTracker(initial_capabilities=self.capabilities)
        
        from memory.agent_memory import AgentMemory
        self.memory: 'AgentMemory' = AgentMemory(agent_id=self.id)

        from core.capability_input_preparer import CapabilityInputPreparer
        from core.skill_definitions import SKILL_CAPABILITY_MAPPING as SCM
        self.input_preparer: 'CapabilityInputPreparer' = CapabilityInputPreparer(skill_capability_mapping=SCM)

        self.all_agent_names_in_system_cache: List[str] = []
        self.current_skill_action_registry: Dict[str, List[str]] = {} # To be populated by MetaAgent
        
        log(f"[{self.name} ID:{self.id}] TaskAgent initialized. Role: {self.role}, Behavior: {self.behavior_mode}, Initial Energy: {self.initial_energy:.2f}")

    def _send_contract_agreement(self, negotiation_id: str, skill_agent_id: str, capability_requested: str, tool_command_str: str, agreed_terms: Dict[str, Any]):
        """Sends a CONTRACT_AGREEMENT message to the SkillAgent."""
        contract_id = negotiation_id # Use negotiation_id as contract_id

        contract_agreement_message = {
            "type": "CONTRACT_AGREEMENT",
            "payload": {
                "contract_id": contract_id,
                "task_agent_id": self.id,
                "skill_agent_id": skill_agent_id,
                "capability_requested": capability_requested,
                "tool_command_str": tool_command_str,
                "agreed_terms": agreed_terms,
                "success_conditions": "SkillAgent reports success_skill_execution.", # Placeholder
                "failure_conditions": "SkillAgent reports failure or timeout."     # Placeholder
            }
            # Removed recipient_agent_id from here, send_direct_message takes it as a param
        }

        # Corrected call to send_direct_message
        self.communication_bus.send_direct_message(
            sender_name=self.name, # Use sender_name
            recipient_name=skill_agent_id, # Use recipient_name
            content=contract_agreement_message # Use content
        )

        # Assuming success for now, as send_direct_message doesn't return status in current stub
        self.state['pending_contract_acknowledgements'][contract_id] = {
            "skill_agent_id": skill_agent_id,
            "capability_requested": capability_requested,
            "tool_command_str": tool_command_str,
            "agreed_terms": agreed_terms,
            "status": "agreement_sent",
            "sent_at_tick": self.context_manager.get_tick(),
            "original_invoking_capability_request_id": self.state['pending_negotiations'][negotiation_id].get("original_invoking_capability_request_id")
        }
        log(f"[{self.name}] Sent CONTRACT_AGREEMENT (ID: {contract_id}) to '{skill_agent_id}'. Terms: {agreed_terms}", level="INFO")


        # --- Query KnowledgeBase for service listings ---
        # skill_action_to_request is the conceptual capability, e.g., "maths_operation"
        # However, SkillAgents advertise their primary service capability, e.g., "maths_ops_v1"
        # We need a mapping from the requested action to the service capability name.
        # For now, let's assume skill_action_to_request IS the service capability name
        # or that the capability invoking this method provides the correct service capability name.
        # This part might need refinement based on how `invoke_skill_agent_v1` determines what to ask for.
        # Let's assume `skill_action_to_request` is the *service capability name* (e.g. "maths_ops_v1")
        
    def find_best_skill_agent_for_action(self, skill_action_to_request: str, preferred_target_id: Optional[str] = None) -> Optional[str]:
        if not skill_action_to_request:
            log(f"[{self.name}] find_best_skill_agent_for_action: No skill_action_to_request provided.", level="WARNING")
            return None
                
        service_capability_to_query = skill_action_to_request # TODO: Refine this mapping if needed
        
        log(f"[{self.name}] Querying KnowledgeBase for service listings offering '{service_capability_to_query}'. Preferred target (lineage): {preferred_target_id}", level="DEBUG")
        
        # Query the KnowledgeBase
        # The capability_needed here should be the service name like "calendar_ops_v1"
        # The SKILL_CAPABILITY_MAPPING maps "calendar_ops_v1" to ["current_date", "add_event", ...]
        # SkillAgent.advertise_services() uses self.capabilities which is like ["calendar_ops_v1"]
        
        # If skill_action_to_request is a specific command (e.g., "add"), we need to find which service offers it.
        # For now, let's assume skill_action_to_request is the *service name* itself (e.g., "maths_ops_v1")
        # This means the calling capability (like invoke_skill_agent_v1) needs to know the service name.
        
        matching_service_advertisements = self.knowledge_base.query_service_listings(
            capability_needed=service_capability_to_query, # This should be the service like "maths_ops_v1"
            current_tick=self.context_manager.get_tick()
            # We can add min_reputation later
        )

        if not matching_service_advertisements:
            log(f"[{self.name}] find_best_skill_agent_for_action: No service listings found in KnowledgeBase for service '{service_capability_to_query}'.", level="WARNING")
            return None

        active_and_capable_agents = [listing.get("agent_id") for listing in matching_service_advertisements if listing.get("agent_id")]
        log(f"[{self.name}] find_best_skill_agent_for_action: Agents from KB for '{service_capability_to_query}': {active_and_capable_agents}", level="DEBUG")

        chosen_target_skill_agent_id = None
        if preferred_target_id:
            # Check if the preferred_target_id is a lineage prefix for any suitable agents
            agents_in_preferred_lineage = [
                sa_name for sa_name in active_and_capable_agents
                if sa_name.startswith(preferred_target_id) # Lineage match
            ]
            if agents_in_preferred_lineage:
                # Choose one from the preferred lineage (e.g., highest generation or random)
                # For now, let's pick randomly from the preferred lineage
                chosen_target_skill_agent_id = random.choice(agents_in_preferred_lineage)
                log(f"[{self.name}] find_best_skill_agent_for_action: Using agent '{chosen_target_skill_agent_id}' from preferred lineage '{preferred_target_id}' for action '{skill_action_to_request}'.")
            else:
                log(f"[{self.name}] find_best_skill_agent_for_action: No agent from preferred lineage '{preferred_target_id}' found for service '{service_capability_to_query}'. Looking for any suitable alternative. Agents from KB: {active_and_capable_agents}", level="WARNING")
        
        # Fallback if no preferred target was given, or if preferred lineage had no suitable agent
        if not chosen_target_skill_agent_id and active_and_capable_agents: # Check active_and_capable_agents again
            chosen_target_skill_agent_id = random.choice(active_and_capable_agents)
            log(f"[{self.name}] find_best_skill_agent_for_action: Selected agent '{chosen_target_skill_agent_id}' for service '{service_capability_to_query}'. Agents from KB: {active_and_capable_agents}")
        
        if not chosen_target_skill_agent_id:
            log(f"[{self.name}] find_best_skill_agent_for_action: No suitable target agent found for service '{service_capability_to_query}'. Agents from KB: {active_and_capable_agents}", level="WARNING")
            return None
            
        return chosen_target_skill_agent_id

    def _initiate_skill_negotiation(self,
                                    target_skill_agent_id: str,
                                    capability_name_requested: str, # e.g., "maths_operation"
                                    tool_command_str_for_skill: str, # e.g., "add 1 2"
                                    original_invoking_capability_request_id: str, # The request_id of the capability that initiated this negotiation
                                    proposed_reward: float = 5.0,
                                    max_acceptable_cost: float = 1.0,
                                    deadline_ticks_from_now: int = 50
                                    ) -> Optional[str]:
        """
        Sends a TASK_OFFER to a SkillAgent and tracks it.
        Returns the negotiation_id (task_id for the offer) if successful, else None.
        """
        if not self.communication_bus:
            log(f"[{self.name}] Cannot initiate negotiation: CommunicationBus not available.", level="ERROR")
            return None

        current_tick = self.context_manager.get_tick()
        negotiation_id = f"neg_{self.id}_{current_tick}_{uuid.uuid4().hex[:6]}"

        proposed_terms = {
            "reward_for_success": proposed_reward,
            "max_energy_cost_to_task_agent": max_acceptable_cost, # Max cost SkillAgent can charge TaskAgent
            "deadline_ticks": current_tick + deadline_ticks_from_now
        }

        task_offer_message = {
            "type": "TASK_OFFER", # New message type
            "payload": {
                "negotiation_id": negotiation_id, # Unique ID for this negotiation
                "requester_agent_id": self.id,
                "requester_agent_name": self.name,
                "capability_requested": capability_name_requested, # The conceptual capability
                "tool_command_str": tool_command_str_for_skill,   # The specific command for the tool
                "proposed_terms": proposed_terms
            }
            # Removed recipient_agent_id from here
        }

        # Corrected call to send_direct_message
        self.communication_bus.send_direct_message(
            sender_name=self.name, # Use sender_name
            recipient_name=target_skill_agent_id, # Use recipient_name
            content=task_offer_message # Use content
        )
        # Assuming success for now
        self.state['pending_negotiations'][negotiation_id] = {
            "target_skill_agent_id": target_skill_agent_id,
            "capability_requested": capability_name_requested,
            "tool_command_str": tool_command_str_for_skill,
            "proposed_terms": proposed_terms,
            "status": "offer_sent",
            "sent_at_tick": current_tick,
            "original_invoking_capability_request_id": original_invoking_capability_request_id, # To link back
            "timeout_at_tick": current_tick + deadline_ticks_from_now + 10 # Offer response timeout
        }
        log(f"[{self.name}] Sent TASK_OFFER (NegID: {negotiation_id}) for '{capability_name_requested}' to '{target_skill_agent_id}'. Proposed terms: {proposed_terms}", level="INFO")
        return negotiation_id


    def _report_symptom(self, symptom_type: str, details_dict: Dict[str, Any], severity: str = "warning", symptom_id_prefix: str = "symptom"):
        current_tick = self.context_manager.get_tick()
        symptom_id = f"{symptom_id_prefix}_{current_tick}_{uuid.uuid4().hex[:6]}"

        symptom_data = {
            "symptom_id": symptom_id,
            "timestamp": time.time(),
            "tick": current_tick,
            "type": symptom_type,
            "severity": severity,
            "source_agent_id": self.id,
            "source_agent_name": self.name,
            "details": details_dict,
            "related_data_refs": [],
            "event_type": "symptom_report", # Ensure this is set for KB queries
            "lineage_id": self.lineage_id
        }
        # Use store_system_event for symptoms as they are system-relevant events
        self.knowledge_base.store_system_event(
            event_type="symptom_report", # Consistent event_type
            event_details=symptom_data, # Pass the whole symptom_data as details
            source_agent_id=self.id,
            related_agent_ids=[self.id] # Or other relevant agents if applicable
        )
        self.memory.log_tick({
            "action": "reported_symptom",
            "symptom_data": symptom_data,
            "kb_contribution": 0.0, # store_system_event doesn't return contribution score directly
            "tick": current_tick
        })
        log(f"[{self.name}] Reported symptom '{symptom_id}' (Type: {symptom_type}, Severity: {severity})", level="INFO")


    def _investigate_symptoms(self, goal_details: Dict):
        current_tick = self.context_manager.get_tick()
        log(f"[{self.name}] Starting symptom investigation based on goal: {goal_details}", level="INFO")
        self.memory.log_tick({"action": "start_symptom_investigation", "goal_details": goal_details, "tick": current_tick})

        query_criteria = goal_details.get("criteria", {"data_matches": {"event_type": "symptom_report"}})
        
        # Querying for system events of type "symptom_report"
        symptoms_found_events = self.knowledge_base.query_system_events(
            event_type_filter="symptom_report",
            # Add other filters if needed, e.g., source_agent_id_filter=self.id for self-reported
            limit=10 # Limit the number of symptoms to investigate per cycle
        )

        if not symptoms_found_events:
            log(f"[{self.name}] No symptoms found matching criteria: {query_criteria}", level="INFO")
            self.memory.log_tick({"action": "symptom_investigation_complete", "status": "no_symptoms_found", "tick": current_tick})
            return

        log(f"[{self.name}] Found {len(symptoms_found_events)} symptoms to investigate.", level="INFO")

        for event_entry in symptoms_found_events:
            # The actual symptom_data is within event_entry['details']
            symptom_data = event_entry.get("details", {}) 
            if not symptom_data or symptom_data.get("type") is None: # Check for 'type' within symptom_data
                log(f"[{self.name}] Skipping event entry due to missing symptom data or type: {event_entry}", level="DEBUG")
                continue

            log(f"[{self.name}] Investigating symptom: {symptom_data.get('details', {}).get('description','N/A')} from {symptom_data.get('source_agent_name')}", level="DEBUG")
            self.memory.log_tick({
                "action": "investigating_specific_symptom",
                "symptom_id": symptom_data.get("symptom_id", "unknown_symptom"),
                "symptom_details": symptom_data,
                "tick": current_tick
            })

            if self.has_capability("triangulated_insight_v1"):
                log(f"[{self.name}] Attempting to use 'triangulated_insight_v1' for symptom: {symptom_data.get('symptom_id')}", level="INFO")
                
                insight_cap_inputs = {
                    "symptom_data": symptom_data, # Pass the extracted symptom_data
                }

                # all_agents_list is now self.all_agent_names_in_system_cache
                insight_result = self._execute_capability(
                    "triangulated_insight_v1",
                    self.context_manager,
                    self.knowledge_base,
                    self.all_agent_names_in_system_cache,
                    **insight_cap_inputs
                )
                log(f"[{self.name}] 'triangulated_insight_v1' result: {insight_result.get('outcome')}. Details: {insight_result.get('best_insight')}", level="INFO")
                
                # The insight handler now stores the best insight in KB and GUI.
                # We can check if an insight was generated.
                if insight_result.get("best_insight"):
                    self.last_diagnosis = insight_result["best_insight"] # Store the best insight as last_diagnosis
                    log(f"[{self.name}] Stored diagnosis: {self.last_diagnosis.get('root_cause_hypothesis')}")
        self.memory.log_tick({"action": "symptom_investigation_complete", "status": "processed_symptoms", "symptoms_count": len(symptoms_found_events), "tick": current_tick})
        log(f"[{self.name}] Finished symptom investigation cycle.", level="INFO")


    def execute_goal(self):
        current_tick = self.context_manager.get_tick()
        original_goal_type = self.current_goal.get("type")

        if random.random() < self.problem_observation_chance: 
            observed_service = f"Service_{chr(random.randint(65, 67))}"
            problem_details = {
                "service_id": observed_service,
                "description": f"Simulated intermittent failure in {observed_service}",
                "observed_metric_deviation": random.uniform(-0.5, 0.5)
            }
            self._report_symptom(symptom_type="simulated_service_failure", details_dict=problem_details, severity="warning")

        goal_type = self.current_goal.get("type")
        goal_completed_successfully = False

        if goal_type == "investigate_symptoms":
            self._investigate_symptoms(self.current_goal.get("details", {}))
        elif goal_type == "generic_task":
            # ... (existing generic_task logic) ...
            self.memory.log_tick({"action": "execute_generic_task", "details": self.current_goal.get("details"), "tick": current_tick})
            log(f"[{self.name}] Goal: Performing generic task: {self.current_goal.get('details')}", level="DEBUG")
            if random.random() < self.generic_task_failure_rate: # Use configured rate 
                 failure_details = {
                     "task_processor_id": "generic_task_processor",
                     "description": "Failed to complete generic task",
                     "error_code": random.randint(1000, 1005)
                 }
                 self._report_symptom(symptom_type="generic_task_failure", details_dict=failure_details, severity="error")
                 self.current_goal = {"type": "idle", "reason": "generic_task_failed"}
            else:
                goal_completed_successfully = True
                self.current_goal = {"type": "idle", "reason": "generic_task_complete"}
        elif goal_type == "execute_llm_generated_plan":
            plan_details = self.current_goal.get("details", {})
            plan_to_execute = plan_details.get("plan_to_execute")
            original_query = plan_details.get("original_user_query")

            if plan_to_execute and isinstance(plan_to_execute, list):
                log(f"[{self.name}] Goal: Execute LLM generated plan for query '{original_query}'. Plan: {plan_to_execute}")
                # The actual execution will be picked up by the capability selection logic in run()
                # This goal type primarily signals intent and provides the plan.
                # The run() method will prioritize sequence_executor_v1 if this goal is active.
                # No direct action here, but the goal remains until sequence_executor is chosen.
                pass
            # Removed duplicate "generic_task" handling from here, it's handled above.
        elif goal_type == "user_defined_goal":
            goal_description = self.current_goal.get('details', {}).get('description', '')
            if goal_description:
                log(f"[{self.name}] Goal: Processing user_defined_goal: '{goal_description}'", level="INFO")
                ack_insight = {
                    "diagnosing_agent_id": self.name,
                    "root_cause_hypothesis": f"Received user goal: '{goal_description}'. Attempting to interpret...",
                    "confidence": 0.95,
                    "suggested_actions": ["LLM Interpretation"]
                }
                # Corrected method name for displaying insight
                if self.context_manager and hasattr(self.context_manager, 'post_insight_to_gui'):
                    self.context_manager.post_insight_to_gui(ack_insight)

                if self.has_capability("interpret_goal_with_llm_v1"):
                    initial_rl_state_for_interpret = self._get_rl_state_representation() # Get state before execution
                    cap_inputs = {
                        "user_query": goal_description,
                        "current_system_context": {
                            "tick": self.context_manager.get_tick(),
                            "available_capabilities": self.capabilities,
                            "agent_name": self.name
                        },
                        "llm_provider": "local_ollama", # Example, can be configured
                        "llm_model": self.llm_model_name
                    }
                    interpretation_result = self._execute_capability(
                        "interpret_goal_with_llm_v1",
                        self.context_manager,
                        self.knowledge_base,
                        self.all_agent_names_in_system_cache, 
                        **cap_inputs
                    ) 
                    
                    if interpretation_result.get("outcome") == "success_goal_interpreted":
                        parsed_action_details = interpretation_result.get("details", {})
                        log(f"[{self.name}] LLM interpreted user goal into: {parsed_action_details}", level="INFO")
                        # This part assumes interpret_goal_with_llm_v1 returns a dict that can be used to set a new goal
                        if parsed_action_details.get("type") == "invoke_skill":
                            self.set_goal({
                                "type": "execute_parsed_skill_invocation",
                                "details": parsed_action_details,
                                "original_user_query": goal_description
                            })
                        else:
                            # If the LLM returns a plan (list of steps), set goal to execute it
                            if isinstance(parsed_action_details, list): # Assuming the plan is directly in details
                                self.set_goal({
                                    "type": "execute_llm_generated_plan",
                                    "details": {"plan_to_execute": parsed_action_details, "original_user_query": goal_description}
                                })
                            else: # If it's a dict but not 'invoke_skill', or other unhandled structure
                                log(f"[{self.name}] LLM interpretation result type '{parsed_action_details.get('type')}' or structure not directly actionable for new goal. Setting to idle. Details: {parsed_action_details}", level="WARN")
                                self.current_goal = {"type": "idle", "reason": "llm_interpretation_unhandled_type"}
                    elif interpretation_result.get("outcome") == "pending_llm_interpretation":
                        log(f"[{self.name}] LLM interpretation for user goal is pending. Request ID: {interpretation_result.get('details', {}).get('request_id')}")
                        # Goal remains 'user_defined_goal' or 'interpret_user_goal', pending LLM response.
                    else:
                        log(f"[{self.name}] Failed to interpret user goal with LLM. Result: {interpretation_result}. Setting to idle.", level="WARNING")
                        self.current_goal = {"type": "idle", "reason": "llm_interpretation_failed"}
                    self._update_state_after_action(initial_rl_state_for_interpret, "interpret_goal_with_llm_v1", interpretation_result)

                elif self.has_capability("conversational_exchange_llm_v1"): 
                    log(f"[{self.name}] No 'interpret_goal_with_llm_v1'. Using 'conversational_exchange_llm_v1' for user goal: '{goal_description}'", level="INFO")
                    cap_inputs_for_convo = {
                        "user_input_text": goal_description,
                        "conversation_history": self.conversation_history, 
                        "system_prompt": f"You are an AI assistant named {self.name}. The current simulation tick is {self.context_manager.get_tick()}."
                    }
                    initial_rl_state_for_convo = self._get_rl_state_representation()
                    convo_result = self._execute_capability(
                        "conversational_exchange_llm_v1",
                        self.context_manager,
                        self.knowledge_base,
                        self.all_agent_names_in_system_cache,
                        **cap_inputs_for_convo
                    )
                    self._update_state_after_action(initial_rl_state_for_convo, "conversational_exchange_llm_v1", convo_result)
                else:
                    log(f"[{self.name}] Does not have 'interpret_goal_with_llm_v1' or 'conversational_exchange_llm_v1' capability to process user goal. Idling.", level="WARN")
                    self.current_goal = {"type": "idle", "reason": "missing_llm_capabilities_for_user_goal"}
            else: 
                log(f"[{self.name}] User goal has no description.", level="WARNING")
                self.current_goal = {"type": "idle", "reason": "failed_no_user_goal_description"}
                self.memory.log_tick({"action": "no_user_goal_description", "tick": current_tick})

        elif goal_type == "idle":
            pass
        elif goal_type == "execute_parsed_skill_invocation":
            self.log_event(f"Executing parsed skill invocation goal: {self.current_goal.get('details')}")
            invocation_details = self.current_goal.get("details", {})

            action_name = invocation_details.get("action") or invocation_details.get("target_skill_action")
            parameters = invocation_details.get("params") or invocation_details.get("skill_parameters")
            preferred_target = invocation_details.get("preferred_target_agent_id")

            if action_name:
                pending_update = {
                    "action": action_name,
                    "params": parameters if parameters is not None else {},
                }
                if preferred_target:
                    pending_update["preferred_target_agent_id"] = preferred_target
                
                self.state["pending_skill_invocation"] = pending_update

                self.memory.log_tick({
                    "action": "parsed_skill_invocation_set_pending",
                    "skill_action": action_name,
                    "params": self.state["pending_skill_invocation"]["params"],
                    "tick": self.context_manager.get_tick()
                })
                self.current_goal = {"type": "idle", "reason": "pending_skill_invocation_set_for_rl"}
            else:
                self.log_event("Cannot execute parsed skill: 'action' or 'target_skill_action' missing in goal details.", level="ERROR")
                self._report_symptom(
                    symptom_type="parsed_skill_invocation_error",
                    details_dict={"error": "Missing action in parsed skill details", "goal_details": invocation_details},
                    severity="error"
                )
                self.current_goal = {"type": "idle", "reason": "parsed_skill_invocation_missing_action"}
        else:
            log(f"[{self.name}] Unknown goal type: {goal_type}", level="WARNING")
            self.memory.log_tick({"action": "unknown_goal_type", "goal_type": goal_type, "tick": current_tick})
            self.current_goal = {"type": "idle", "reason": "unknown_goal_type_processed"}

        if goal_completed_successfully and original_goal_type not in ["idle", "investigate_symptoms"]:
            completion_reward = self.complex_goal_completion_reward 
            energy_ratio = self.energy / self.initial_energy if self.initial_energy > 0 else 0 
            energy_bonus = energy_ratio * self.energy_efficiency_bonus_factor
            total_goal_reward = completion_reward + energy_bonus
            self.memory.log_tick({"action": "complex_goal_completed", "original_goal_type": original_goal_type, "reward": total_goal_reward, "energy_bonus_applied": energy_bonus, "tick": current_tick})
            log(f"[{self.name}] Achieved complex goal '{original_goal_type}'. Reward: {completion_reward:.2f}, Energy Bonus: {energy_bonus:.2f}", level="INFO")

    def get_config(self) -> dict:
        agent_config = super().get_config() 
        agent_config.update({
            "agent_id": self.id,
            "initial_goal": copy.deepcopy(self.initial_goal),
            "behavior_mode": self.behavior_mode,
            "initial_focus": self.initial_focus,
            "role": self.role,
            "insight_confidence_threshold": self.insight_confidence_threshold,
            "insight_fitness_time_window": self.insight_fitness_time_window,
            "max_pending_skill_requests": self.max_pending_skill_requests,
            "symptom_investigation_priority": self.symptom_investigation_priority,
            "generic_task_failure_rate": self.generic_task_failure_rate,
            "llm_model_name": self.llm_model_name,
            "alpha": self.rl_system.alpha,
            "gamma": self.rl_system.gamma,
            "epsilon": self.rl_system.epsilon,
            "initial_energy_config": self.initial_energy # This might be redundant if initial_energy in base_config is current
        })
        return agent_config

    def set_goal(self, goal: Dict):
        self.current_goal = goal
        current_tick = self.context_manager.get_tick()
        log(f"[{self.name}] New goal assigned: {goal.get('type')}", level="INFO")
        self.memory.log_tick({"action": "new_goal_assigned", "goal_type": goal.get('type'), "goal_details": goal.get("details"), "tick": current_tick})

    def _handle_pending_skill_responses(self):
        current_tick = self.context_manager.get_tick()
        if not self.state.get('pending_skill_requests'):
            return

        completed_request_ids = []
        for req_id, req_details in list(self.state['pending_skill_requests'].items()):
            if current_tick >= req_details.get("timeout_at_tick", float('inf')): 
                log(f"[{self.name}] Skill request '{req_id}' to '{req_details['target_skill_agent_id']}' timed out.", level="WARNING")
                self._update_q_value( 
                    state_tuple=req_details["original_rl_state"],
                    action=req_details["capability_name"], 
                    reward=req_details["timeout_reward"],
                    next_state_tuple=self._get_rl_state_representation() 
                )
                self.capability_performance_tracker.record_capability_execution(req_details["capability_name"], False, req_details["timeout_reward"])
                self.state["last_failed_skill_details"] = {
                    "tick": current_tick,
                    "target_skill_agent_id": req_details['target_skill_agent_id'],
                    "action_requested": req_details['request_data'].get('action', req_details.get('skill_action_to_request', 'unknown_skill_action')),
                    "reason": "failure_skill_timeout"
                }
                completed_request_ids.append(req_id)
                continue

            response_message = self.communication_bus.get_message_by_request_id(self.name, req_id)
            if response_message:
                log(f"[{self.name}] Received response for skill request '{req_id}': {str(response_message['content'])[:100]}", level="INFO")
                
                response_content = response_message['content']
                status = response_content.get("status", "failure_unknown_response_format")
                skill_operation_data = response_content.get("data", {}) 
                
                reward_to_apply = req_details["failure_reward"]
                is_success = False

                # Check the 'status' from the SkillAgent's response payload, not just the outer message status
                skill_reported_status = response_content.get("status", "failure_unknown_response_format")

                if "success" in skill_reported_status.lower(): # Check the skill's own reported status
                    reward_to_apply = req_details["success_reward"]
                    is_success = True

                    # --- Add Inter-Agent Payment Logic ---
                    agreed_terms = req_details.get("agreed_terms", {})
                    agreed_payment_amount = agreed_terms.get("energy_cost_charged_to_task_agent", 0.0) # Use agreed cost
                    skill_agent_name_for_payment = req_details['target_skill_agent_id']
                    task_id_for_payment = req_id

                    if agreed_payment_amount > 0:
                        log(f"[{self.name}] Attempting to pay SkillAgent '{skill_agent_name_for_payment}' {agreed_payment_amount:.2f} energy for successful task '{task_id_for_payment}'.", level="INFO")
                        payment_successful = self.context_manager.process_inter_agent_energy_transfer(
                            payer_agent_name=self.name,
                            payee_agent_name=skill_agent_name_for_payment,
                            amount=agreed_payment_amount,
                            reason=f"Payment for successful completion of task {task_id_for_payment}"
                        )
                        if payment_successful:
                            log(f"[{self.name}] Successfully paid {skill_agent_name_for_payment} {agreed_payment_amount:.2f} energy for task {task_id_for_payment}.")
                        else:
                            log(f"[{self.name}] Failed to pay {skill_agent_name_for_payment} for task {task_id_for_payment}. Check ContextManager logs.", level="WARN")
                    else:
                        log(f"[{self.name}] No payment processed for task {task_id_for_payment} as agreed cost was {agreed_payment_amount:.2f}.", level="DEBUG")
                    # --- End Inter-Agent Payment Logic --- 
                else:
                    failure_reason_detail = response_content.get("message", response_content.get("error", skill_reported_status))
                    log(f"[{self.name}] Skill request '{req_id}' to '{req_details['target_skill_agent_id']}' reported operational failure: {failure_reason_detail}", level="WARNING")

                self._update_q_value( 
                    state_tuple=req_details["original_rl_state"],
                    action=req_details["capability_name"],
                    reward=reward_to_apply,
                    next_state_tuple=self._get_rl_state_representation() 
                )
                self.capability_performance_tracker.record_capability_execution(req_details["capability_name"], is_success, reward_to_apply)
                if not is_success:
                     self.state["last_failed_skill_details"] = {
                        "tick": current_tick,
                        "target_skill_agent_id": req_details['target_skill_agent_id'],
                        "action_requested": req_details['request_data'].get('action', req_details.get('skill_action_to_request', 'unknown_skill_action')),
                        "reason": f"failure_skill_response_{skill_reported_status}"
                    }
                completed_request_ids.append(req_id)
                self.communication_bus.mark_message_processed(response_message['id']) # Mark as processed

        for req_id in completed_request_ids:
            if req_id in self.state['pending_skill_requests']: 
                del self.state['pending_skill_requests'][req_id]

    def _handle_negotiation_responses(self):
        """Handles responses to TASK_OFFERs."""
        current_tick = self.context_manager.get_tick()
        if not self.state.get('pending_negotiations'):
            return

        resolved_negotiation_ids = []
        for neg_id, neg_details in list(self.state['pending_negotiations'].items()):
            if neg_details["status"] != "offer_sent": # Already processed or timed out
                if current_tick >= neg_details.get("timeout_at_tick", float('inf')) and neg_details["status"] == "offer_sent":
                    log(f"[{self.name}] Negotiation '{neg_id}' with '{neg_details['target_skill_agent_id']}' for '{neg_details['capability_requested']}' timed out waiting for response.", level="WARNING")
                    # TODO: Update RL/performance for the invoking capability that initiated this negotiation
                    resolved_negotiation_ids.append(neg_id)
                continue

            # Check for response message from SkillAgent
            response_message = self.communication_bus.get_message_by_request_id(
                recipient_agent_id=self.name, # Corrected parameter name
                request_id_to_find=neg_id,      # Match by negotiation_id
                # message_type_filter="TASK_OFFER_RESPONSE" # This filter is not in get_message_by_request_id
            )
            # Filter by type after getting the message
            if response_message and response_message.get('content', {}).get('type') != "TASK_OFFER_RESPONSE":
                response_message = None # Ignore if not the right type

            if response_message:
                response_payload = response_message['content'].get('payload', {})
                response_type = response_payload.get('response_type')
                log(f"[{self.name}] Received TASK_OFFER_RESPONSE for NegID '{neg_id}' from '{response_payload.get('responder_agent_id')}'. Type: {response_type}", level="INFO")

                if response_type == "accept":
                    neg_details["status"] = "accepted"
                    actual_terms = response_payload.get("actual_terms", neg_details["proposed_terms"])
                    log(f"[{self.name}] Offer NegID '{neg_id}' ACCEPTED by '{neg_details['target_skill_agent_id']}' for '{neg_details['capability_requested']}'. Agreed terms: {actual_terms}", level="INFO")
 
                    # Send CONTRACT_AGREEMENT instead of direct skill execution
                    self._send_contract_agreement(
                        negotiation_id=neg_id,
                        skill_agent_id=neg_details["target_skill_agent_id"],
                        capability_requested=neg_details["capability_requested"],
                        tool_command_str=neg_details["tool_command_str"],
                        agreed_terms=actual_terms
                    )
                    # Negotiation is resolved, but contract acknowledgement is pending.
                    # Skill execution will happen after CONTRACT_ACKNOWLEDGED.

                elif response_type == "reject":
                    neg_details["status"] = "rejected"
                    log(f"[{self.name}] Offer NegID '{neg_id}' REJECTED by '{neg_details['target_skill_agent_id']}'. Reason: {response_payload.get('reason')}", level="INFO")
                elif response_type == "counter_offer":
                    counter_terms = response_payload.get("counter_proposed_terms")
                    log(f"[{self.name}] Offer NegID '{neg_id}' received COUNTER-OFFER from '{neg_details['target_skill_agent_id']}'. Counter Terms: {counter_terms}", level="INFO")

                    if not counter_terms:
                        log(f"[{self.name}] Counter-offer for NegID '{neg_id}' is missing terms. Rejecting.", level="WARN")
                        neg_details["status"] = "counter_rejected_invalid"
                        # Optionally send a message back indicating invalid counter-offer
                    else:
                        # Simple evaluation of counter-offer:
                        # Accept if new reward is not more than 1.5x original proposed reward
                        # AND new cost is not more than 1.2x original max_acceptable_cost.
                        original_proposed_reward = neg_details["proposed_terms"]["reward_for_success"]
                        original_max_cost = neg_details["proposed_terms"]["max_energy_cost_to_task_agent"]
                        
                        counter_reward = counter_terms.get("reward_for_success", float('inf'))
                        counter_cost_charged = counter_terms.get("energy_cost_charged_to_task_agent", float('inf'))

                        if counter_reward <= original_proposed_reward * 1.5 and \
                           counter_cost_charged <= original_max_cost * 1.2 and \
                           counter_cost_charged <= self.energy: # Check if TaskAgent can afford this cost
                            
                            neg_details["status"] = "counter_accepted"
                            neg_details["agreed_terms"] = counter_terms # Store the NEWLY agreed terms
                            log(f"[{self.name}] Counter-offer NegID '{neg_id}' ACCEPTED. Agreed terms: {counter_terms}", level="INFO")

                            # Send CONTRACT_AGREEMENT based on accepted counter-offer
                            self._send_contract_agreement(
                                negotiation_id=neg_id,
                                skill_agent_id=neg_details["target_skill_agent_id"],
                                capability_requested=neg_details["capability_requested"],
                                tool_command_str=neg_details["tool_command_str"],
                                agreed_terms=counter_terms # Use the counter_terms
                            )
                            # Negotiation is resolved, contract acknowledgement pending.
                        else:
                            neg_details["status"] = "counter_rejected"
                            log(f"[{self.name}] Counter-offer NegID '{neg_id}' REJECTED. Original proposed reward: {original_proposed_reward}, counter: {counter_reward}. Original max cost: {original_max_cost}, counter: {counter_cost_charged}", level="INFO")
                            # Optionally, send a "COUNTER_OFFER_REJECTED" message back to SkillAgent
                self.communication_bus.mark_message_processed(response_message['id'])
                resolved_negotiation_ids.append(neg_id)
            
            elif current_tick >= neg_details.get("timeout_at_tick", float('inf')):
                 log(f"[{self.name}] Negotiation '{neg_id}' with '{neg_details['target_skill_agent_id']}' for '{neg_details['capability_requested']}' timed out waiting for response (checked after get_message_by_request_id).", level="WARNING")
                 resolved_negotiation_ids.append(neg_id)

        for neg_id in resolved_negotiation_ids:
            self.state['pending_negotiations'].pop(neg_id, None)

    def _handle_contract_acknowledgements(self):
        """Handles CONTRACT_ACKNOWLEDGED messages from SkillAgents."""
        current_tick = self.context_manager.get_tick()
        if not self.state.get('pending_contract_acknowledgements'):
            return

        resolved_contract_ids = []
        for contract_id, contract_details in list(self.state['pending_contract_acknowledgements'].items()):
            if contract_details["status"] != "agreement_sent":
                # TODO: Handle timeout for acknowledgement
                continue

            ack_message = self.communication_bus.get_message_by_request_id(
                recipient_agent_id=self.name, # Corrected parameter name
                request_id_to_find=contract_id, # Match by contract_id
                # message_type_filter="CONTRACT_ACKNOWLEDGED" # This filter is not in get_message_by_request_id
            )
            # Filter by type after getting the message
            if ack_message and ack_message.get('content', {}).get('type') != "CONTRACT_ACKNOWLEDGED":
                ack_message = None # Ignore if not the right type


            if ack_message:
                ack_payload = ack_message['content'].get('payload', {})
                log(f"[{self.name}] Received CONTRACT_ACKNOWLEDGED for ContractID '{contract_id}' from '{ack_payload.get('skill_agent_id')}'.", level="INFO")

                if ack_payload.get("status") == "acknowledged":
                    contract_details["status"] = "acknowledged"
                    # Now initiate the actual skill execution
                    skill_execution_request_id = contract_details.get("original_invoking_capability_request_id", f"skill_req_{contract_id}")
                    
                    skill_execution_message_content = {
                        # "action": contract_details["capability_requested"], # 'action' is not used by SkillAgent's _handle_message for execution
                        "type": "SKILL_EXECUTION_REQUEST", # New, more explicit type
                        "request_id": skill_execution_request_id, 
                        "data": {"tool_command_str": contract_details["tool_command_str"]}
                    }
                    self.state['pending_skill_requests'][skill_execution_request_id] = {
                        "target_skill_agent_id": contract_details["skill_agent_id"],
                        "capability_name": contract_details["capability_requested"], # The conceptual capability
                        "request_data": skill_execution_message_content['data'],
                        "original_rl_state": self.state.get("last_rl_state_before_action", self._get_rl_state_representation()),
                        "success_reward": contract_details["agreed_terms"]["reward_for_success"],
                        "failure_reward": -1.0, # Standard failure penalty
                        "timeout_reward": -0.5, # Standard timeout penalty
                        "timeout_at_tick": current_tick + (contract_details["agreed_terms"].get("deadline_ticks", current_tick + 50) - current_tick + 10), # Use agreed deadline
                        "agreed_terms": contract_details["agreed_terms"] # Store the final agreed terms
                    }
                    self.communication_bus.send_direct_message(self.name, contract_details["skill_agent_id"], skill_execution_message_content)
                    log(f"[{self.name}] Contract '{contract_id}' acknowledged. Sent skill execution request (ReqID: {skill_execution_request_id}) to '{contract_details['skill_agent_id']}'.", level="INFO")
                
                self.communication_bus.mark_message_processed(ack_message['id'])
                resolved_contract_ids.append(contract_id)
            # TODO: Add timeout logic for acknowledgements

        for contract_id in resolved_contract_ids:
            self.state['pending_contract_acknowledgements'].pop(contract_id, None)

    def _handle_pending_llm_operations(self):
        current_tick = self.context_manager.get_tick()
        if not self.state.get('pending_llm_operations'):
            return

        completed_request_ids = []
        for req_id, req_details in list(self.state['pending_llm_operations'].items()):
            if current_tick >= req_details.get("timeout_at_tick", float('inf')): 
                log(f"[{self.name}] LLM operation '{req_id}' (Cap: {req_details['capability_initiated']}) timed out.", level="WARNING")
                self._update_q_value(
                    state_tuple=req_details["original_rl_state"],
                    action=req_details["capability_initiated"],
                    reward=req_details["timeout_reward"],
                    next_state_tuple=self._get_rl_state_representation()
                )
                self.capability_performance_tracker.record_capability_execution(req_details["capability_initiated"], False, req_details["timeout_reward"])
                completed_request_ids.append(req_id)
                self.current_goal = {"type": "idle", "reason": f"llm_op_timeout_{req_details['capability_initiated']}"}
                continue

            llm_response_data = None
            if self.context_manager: 
                llm_response_data = self.context_manager.get_llm_response_if_ready(req_id)

            if llm_response_data and llm_response_data.get("status") != "pending":
                log(f"[{self.name}] Handling LLM Response for ReqID '{req_id}'. Capability: {req_details['capability_initiated']}. Raw Response: {str(llm_response_data)[:300]}", level="INFO")
                
                reward_to_apply = req_details["failure_reward"]
                is_success = False
                processed_details = {}

                if llm_response_data.get("status") == "completed":
                    llm_content = llm_response_data.get("response")
                    if llm_content:
                        is_success = True
                        reward_to_apply = req_details["success_reward"]
                        from core.llm_planner import LLMPlanner # Local import for parsing
                        
                        if req_details["capability_initiated"] == "interpret_goal_with_llm_v1":
                            try:
                                planner = LLMPlanner() 
                                parsed_plan = planner._parse_llm_response(llm_content)
                                if parsed_plan:
                                    processed_details = {"parsed_plan": parsed_plan, "summary_for_user": "Goal interpreted into plan."}
                                    self.set_goal({
                                        "type": "execute_llm_generated_plan",
                                        "details": {"plan_to_execute": parsed_plan, "original_user_query": req_details.get("original_cap_inputs", {}).get("user_query")}
                                    })
                                    log(f"[{self.name}] LLM successfully interpreted user goal into plan. New goal set: 'execute_llm_generated_plan'. Plan: {str(parsed_plan)[:200]}", level="INFO")
                                else:
                                    is_success = False
                                    reward_to_apply = req_details["failure_reward"]
                                    processed_details = {"error": "Failed to parse LLM plan from content."}
                                    log(f"[{self.name}] Failed to parse LLM plan from content: {str(llm_content)[:100]}...", level="ERROR")
                            except Exception as e:
                                is_success = False
                                reward_to_apply = req_details["failure_reward"]
                                processed_details = {"error": f"Exception parsing LLM plan: {e}"}
                                log(f"[{self.name}] Exception while parsing LLM plan: {e}", level="ERROR", exc_info=True)

                        elif req_details["capability_initiated"] == "conversational_exchange_llm_v1":
                            processed_details = {"llm_response_text": llm_content}
                            self.conversation_history.append({"role": "assistant", "content": llm_content})
                            log(f"[{self.name}] LLM generated conversational response: {llm_content[:100]}", level="INFO")
                            if self.context_manager and hasattr(self.context_manager, 'post_insight_to_gui'):
                                original_prompt = req_details.get("original_cap_inputs", {}).get("user_input_text", "User query N/A")
                                self.context_manager.post_insight_to_gui({ # Use post_insight_to_gui
                                     "diagnosing_agent_id": self.name,
                                    "root_cause_hypothesis": f"LLM Response to: '{original_prompt}'", 
                                    "confidence": 0.95, 
                                    "response_text": llm_content 
                                })
                    else: 
                        is_success = False 
                        reward_to_apply = req_details["failure_reward"]
                        processed_details = {"error": "LLM returned no content despite completed status."}
                        log(f"[{self.name}] LLM operation '{req_id}' completed but returned no content.", level="WARNING")
                        
                else: 
                    processed_details = {"error": llm_response_data.get("error_details", "Unknown LLM error occurred.")} # Use error_details
                    log(f"[{self.name}] LLM call error status: {processed_details['error']}", level="ERROR")

                self._update_q_value(req_details["original_rl_state"], req_details["capability_initiated"], reward_to_apply, self._get_rl_state_representation())
                self.capability_performance_tracker.record_capability_execution(req_details["capability_initiated"], is_success, reward_to_apply)
                completed_request_ids.append(req_id)

        for req_id in completed_request_ids:
            if req_id in self.state['pending_llm_operations']:
                del self.state['pending_llm_operations'][req_id]

    def log_event(self, message: str, level: str = "INFO"):
        log_message = f"[{self.name}] EVENT: {message}"
        log(log_message, level=level.upper())
        current_tick = self.context_manager.get_tick() if self.context_manager else -1
        self.memory.log_tick({"event_log": message, "level": level, "tick": current_tick})

    def get_fitness(self) -> Dict[str, float]:
        total_reward = 0
        num_actions = 0
        insight_bonus = 0.0
        successful_insights_count = 0
        total_insight_confidence = 0.0

        current_tick = self.context_manager.get_tick() 
        log_entries_to_consider = self.memory.get_log()
        log(f"[{self.name}] get_fitness: Processing {len(log_entries_to_consider)} log entries from agent memory. Logs: {str(log_entries_to_consider)[:200]}", level="DEBUG") 

        if self.insight_fitness_time_window is not None:
            start_tick_for_window = max(0, current_tick - self.insight_fitness_time_window)
            log_entries_to_consider = [
                log_entry for log_entry in self.memory.get_log()
                if log_entry.get("tick", 0) >= start_tick_for_window 
            ]

        for tick_log in log_entries_to_consider:
            if "reward" in tick_log and tick_log.get("action") not in [
                "age_increment", "new_goal_assigned", "reported_symptom", 
                "start_symptom_investigation", "investigating_specific_symptom", 
                "symptom_investigation_complete", "unknown_goal_type", 
                "no_action_chosen_final", "max_age_reached"
            ]:
                log(f"[{self.name}] get_fitness: Counting action '{tick_log.get('action')}' with reward {tick_log['reward']}", level="DEBUG") 
                total_reward += tick_log["reward"]
                num_actions += 1
            else:
                log(f"[{self.name}] get_fitness: Skipping action '{tick_log.get('action')}' from num_actions due to exclusion or no reward. Tick log: {str(tick_log)[:100]}", level="DEBUG") 

            if tick_log.get("action") == "triangulated_insight_v1" and "success" in tick_log.get("outcome", ""):
                # The insight details are now in the 'best_insight' field of the result's 'details'
                insight_details_from_log = tick_log.get("details", {}).get("best_insight", {})
                if insight_details_from_log and isinstance(insight_details_from_log, dict) and insight_details_from_log.get("confidence", 0.0) > self.insight_confidence_threshold: 
                     successful_insights_count += 1
                     total_insight_confidence += insight_details_from_log.get("confidence", 0.0)
        
        average_reward = (total_reward / num_actions) if num_actions > 0 else 0.0 
        normalized_reward_component = (average_reward + 1) / 2 # Standard normalization for [-1, 1] to [0, 1]
        normalized_reward_component = max(0, min(1, normalized_reward_component))
        survival_bonus = min(self.age * 0.0001, 0.1)

        if successful_insights_count > 0:
            avg_insight_confidence = total_insight_confidence / successful_insights_count
            insight_bonus = min(successful_insights_count * 0.05 + avg_insight_confidence * 0.1, 0.2)
        
        energy_factor = (self.energy / self.initial_energy) if self.initial_energy > 0 else 0
        energy_bonus = (energy_factor - 0.5) * 0.1 

        fitness = (normalized_reward_component * 0.6) + \
                  (survival_bonus * 0.1) + \
                  (insight_bonus * 0.2) + \
                  (energy_bonus * 0.1)
        fitness = max(0.0, min(1.0, fitness))
        
        # Log level changed to DEBUG to reduce verbosity, INFO can be used if this specific log is frequently monitored.
        log(f"[{self.name}] Fitness Calc: Fit={fitness:.3f} (NumActions/Execs:{num_actions}, AvgRw:{average_reward:.2f}, NormRw:{normalized_reward_component:.2f}, Surv:{survival_bonus:.2f}, Ins:{insight_bonus:.2f}, En:{energy_bonus:.3f} ({self.energy:.1f}/{self.initial_energy:.1f}))", level="DEBUG")
        return {"fitness": fitness, "executions": float(num_actions), "average_reward": average_reward}

    def run(self,
            context: 'ContextManager',
            knowledge: 'KnowledgeBase',
            all_agent_names_in_system: list,
            agent_info_map: Dict[str, Dict[str, Any]],
            skill_action_registry: Dict[str, List[str]]): # Added skill_action_registry
        current_sim_tick = context.get_tick()
        self.agent_info_map = agent_info_map
        self.all_agent_names_in_system_cache = all_agent_names_in_system

        if not super().run_cycle():
            log(f"[{self.name} Tick:{current_sim_tick}] Base run_cycle returned False. Status: {self.state['status']}. Skipping TaskAgent actions.", level="DEBUG")
            return
        self.current_skill_action_registry = skill_action_registry # Store the dynamic registry

        if 'pending_sequence_state' in self.state and self.state['pending_sequence_state']:
            pending_seq_info = self.state['pending_sequence_state']
            sync_step_details_from_invoke = pending_seq_info['sync_step_details'] 
            request_id_to_check = sync_step_details_from_invoke['request_id']
            
            response_message = self.communication_bus.get_message_by_request_id(self.name, request_id_to_check)
            resolved_sync_step_result = None

            if response_message:
                response_content = response_message['content']
                status_from_skill_agent = response_content.get("status", "failure_unknown_response_format")
                skill_op_data = response_content.get("data", {})
                # SkillAgent's response payload for success is {"status": "success", "data": ..., "message": ...}
                # We need to check the 'status' within this payload.
                skill_reported_status = response_content.get("status", "failure_unknown_response_format")
                is_overall_success = "success" in skill_reported_status.lower()
                
                reward_for_sync_step = sync_step_details_from_invoke["rewards_for_resolution"]["success"] if is_overall_success else sync_step_details_from_invoke["rewards_for_resolution"]["failure"]
                outcome_for_sync_step = "success_response_received_sync" if is_overall_success else "failure_skill_response_sync"
                
                resolved_sync_step_result = {"outcome": outcome_for_sync_step, "reward": reward_for_sync_step, "details": skill_op_data}
                
                self._update_q_value(
                    sync_step_details_from_invoke["original_rl_state_for_q_update"], "invoke_skill_agent_v1",
                    reward_for_sync_step, self._get_rl_state_representation()
                )
                self.capability_performance_tracker.record_capability_execution("invoke_skill_agent_v1", is_overall_success, reward_for_sync_step)
                if not is_overall_success:
                    self.state["last_failed_skill_details"] = {"tick": current_sim_tick, "target_skill_agent_id": sync_step_details_from_invoke['target_skill_agent_id'], "action_requested": sync_step_details_from_invoke['skill_action_requested'], "reason": f"sync_response_{status_from_skill_agent}"}
                self.communication_bus.mark_message_processed(response_message['id']) 

            elif current_sim_tick >= sync_step_details_from_invoke["timeout_at_tick"]:
                log(f"[{self.name}] Sync step '{sync_step_details_from_invoke['skill_action_requested']}' (ReqID: {request_id_to_check}) for sequence timed out.", level="WARNING")
                reward_for_sync_step = sync_step_details_from_invoke["rewards_for_resolution"]["timeout"]
                resolved_sync_step_result = {"outcome": "failure_response_timeout_sync", "reward": reward_for_sync_step, "details": {"error": "Timeout waiting for skill response synchronously."}}
                
                self._update_q_value(
                    sync_step_details_from_invoke["original_rl_state_for_q_update"], "invoke_skill_agent_v1",
                    reward_for_sync_step, self._get_rl_state_representation()
                )
                self.capability_performance_tracker.record_capability_execution("invoke_skill_agent_v1", False, reward_for_sync_step)
                self.state["last_failed_skill_details"] = {"tick": current_sim_tick, "target_skill_agent_id": sync_step_details_from_invoke['target_skill_agent_id'], "action_requested": sync_step_details_from_invoke['skill_action_requested'], "reason": "failure_sync_wait_timeout"}
            
            if resolved_sync_step_result: # If the synchronous step was resolved (either by response or timeout)
                log(f"[{self.name}] Resuming sequence. Sync step '{sync_step_details_from_invoke['skill_action_requested']}' resolved. Outcome: {resolved_sync_step_result['outcome']}.")
                cap_inputs_for_resume = {
                    "resuming_sequence_after_sync_step": True,
                    "sequence_state_for_resume": pending_seq_info, 
                    "resolved_sync_step_result": resolved_sync_step_result
                }
                # Clear the pending state *before* executing the capability that might set it again if it also pauses.
                del self.state['pending_sequence_state']
                 
                initial_rl_state_for_seq_resume = self._get_rl_state_representation()
                resumed_sequence_result = self._execute_capability("sequence_executor_v1", context, knowledge, all_agent_names_in_system, **cap_inputs_for_resume)
                self._update_state_after_action(initial_rl_state_for_seq_resume, "sequence_executor_v1", resumed_sequence_result)
            # If resolved_sync_step_result is None, it means we are still waiting for the sync step, so return to avoid further actions this tick.
            else:
                log(f"[{self.name}] Still waiting for synchronous step in sequence (ReqID: {request_id_to_check}). Skipping further actions this tick.", level="DEBUG")
                return

        # --- Behavior Mode Switching Logic ---
        if self.behavior_mode == "explore":
            overall_avg_reward = self.capability_performance_tracker.get_overall_average_reward()
            total_attempts = sum(stats.get("attempts", 0) for stats in self.capability_performance_tracker.get_all_performance_stats().values())

            if total_attempts >= config.TASK_AGENT_MIN_EXECS_FOR_EXPLOIT and overall_avg_reward >= config.TASK_AGENT_MIN_AVG_REWARD_FOR_EXPLOIT:
                log(f"[{self.name} Tick:{current_sim_tick}] Switching behavior mode from 'explore' to 'exploit'. Executions: {total_attempts}, Avg Reward: {overall_avg_reward:.2f}", level="INFO")
                self.behavior_mode = "exploit"
                self.memory.log_tick({"tick": current_sim_tick, "action": "behavior_mode_switch", "old_mode": "explore", "new_mode": "exploit", "trigger_metrics": {"executions": total_attempts, "average_reward": overall_avg_reward}})
        
        log(f"[{self.name} ID:{self.id} Tick:{current_sim_tick} Gen:{self.generation} Mode:{self.behavior_mode} Caps:{len(self.capabilities)}] TaskAgent run. Energy: {self.energy:.2f}", level="DEBUG")
        
        self.memory.log_tick({"action": "task_agent_run_start", "age": self.age, "energy": self.energy, "tick": current_sim_tick})
        
        self._handle_pending_skill_responses()
        self._handle_pending_llm_operations()
        self._handle_negotiation_responses() # Handle negotiation responses
        self._handle_contract_acknowledgements() # Handle contract acknowledgements
        
        chosen_capability_name: Optional[str] = None
        cap_inputs_for_execution: Dict[str, Any] = {}
        action_selection_reason = "rl_system"
        log(f"[{self.name} Tick:{current_sim_tick}] Current Goal: {self.current_goal.get('type')}. Details: {str(self.current_goal.get('details', {}))[:100]}", level="DEBUG")

        # --- Goal-Driven Action Selection (Prioritized) ---
        # Handle the 'user_defined_goal' goal type (Entry Point)
        if self.current_goal.get("type") == "execute_llm_generated_plan":
            plan_details = self.current_goal.get("details", {})
            plan_to_execute = plan_details.get("plan_to_execute")
            original_query = plan_details.get("original_user_query")

            if plan_to_execute and isinstance(plan_to_execute, list) and self.has_capability("sequence_executor_v1"):
                log(f"[{self.name}] Goal-driven choice: 'sequence_executor_v1' for 'execute_llm_generated_plan'. Query: '{original_query}'. Plan: {str(plan_to_execute)[:100]}", level="INFO")
                chosen_capability_name = "sequence_executor_v1"
                cap_inputs_for_execution = {
                    "sub_sequence": plan_to_execute,
                    "pass_outputs_between_steps": False, # Default, can be overridden by plan
                    "stop_on_failure": True # Default, can be overridden by plan
                }
                action_selection_reason = "executing_llm_generated_plan"
                # The goal is consumed by selecting this capability.
                # If sequence_executor_v1 pauses, it will set its own pending state.
                # Otherwise, the goal is done.
                self.current_goal = {"type": "idle", "reason": "llm_plan_execution_initiated"}
            elif not self.has_capability("sequence_executor_v1"):
                log(f"[{self.name}] Cannot execute LLM plan: 'sequence_executor_v1' capability missing.", level="ERROR")
                self.current_goal = {"type": "idle", "reason": "llm_plan_execution_failed_no_sequence_executor"}
            else:
                log(f"[{self.name}] LLM plan execution failed: No plan or invalid plan in goal details for 'execute_llm_generated_plan'.", level="ERROR")
                self.current_goal = {"type": "idle", "reason": "llm_plan_execution_failed_invalid_plan"}
        
        # This goal type primarily sets up the *next* state/goal, not the current tick's action,
        # unless it's a conversational turn which is executed immediately.
        elif not chosen_capability_name and self.current_goal.get("type") == "user_defined_goal":
            goal_description = self.current_goal.get('details', {}).get('description', '')
            if goal_description:
                log(f"[{self.name}] Goal-driven choice: Processing 'user_defined_goal': '{goal_description}' by selecting LLM capability.", level="INFO")
                # Acknowledge the goal in the GUI
                ack_insight = {"diagnosing_agent_id": self.name, "root_cause_hypothesis": f"Received user goal: '{goal_description}'. Attempting to interpret...", "confidence": 0.95, "suggested_actions": ["LLM Interpretation"]}
                if self.context_manager and hasattr(self.context_manager, 'post_insight_to_gui'): # Use the correct method name
                    self.context_manager.post_insight_to_gui(ack_insight)

                if self.has_capability("interpret_goal_with_llm_v1"):
                    # Set the goal to indicate interpretation is pending/needed
                    self.set_goal({"type": "interpret_user_goal", "details": {"user_query": goal_description}})
                    log(f"[{self.name}] Set goal to 'interpret_user_goal' for '{goal_description}'. RL will choose 'interpret_goal_with_llm_v1' next.", level="INFO")
                    # Do NOT set chosen_capability_name here. The logic below for "interpret_user_goal" or RL will pick it up.

                elif self.has_capability("conversational_exchange_llm_v1"):
                    # Ensure conversational_exchange_llm_v1 is not chosen if the goal is already to self-diagnose
                    if self.current_goal.get("type") == "self_diagnose_failures":
                        log(f"[{self.name}] Goal is 'self_diagnose_failures', skipping conversational exchange for user_defined_goal '{goal_description}'.", level="DEBUG")
                        # Let the self_diagnose_failures logic below handle it.
                        # We might need to ensure that if self_diagnose_failures was set by _update_state_after_action,
                        # it takes precedence in this same tick if possible, or the next tick.
                        # For now, if self_diagnose_failures is set, the next block will catch it.
                        pass
                    else:
                        log(f"[{self.name}] No 'interpret_goal_with_llm_v1'. Using 'conversational_exchange_llm_v1' for user goal: '{goal_description}'", level="INFO")
                        self._execute_conversational_goal(goal_description, context, knowledge, all_agent_names_in_system)
                        chosen_capability_name = "conversational_exchange_llm_v1" # Mark as handled this tick
                        action_selection_reason = "user_goal_llm_conversation"
                    # _execute_conversational_goal will set goal to idle.
                else:
                    log(f"[{self.name}] Goal-driven choice: Has 'user_defined_goal' but no LLM capability (interpret or conversational). Will fall to RL/idle.", level="WARN")
                    self.current_goal = {"type": "idle", "reason": "missing_llm_capabilities_for_user_goal"}
            else:
                log(f"[{self.name}] User goal has no description. Idling.", level="WARNING")
                self.current_goal = {"type": "idle", "reason": "failed_no_user_goal_description"}
      
        # Handle the 'interpret_user_goal' goal type
        # This goal type exists specifically to trigger the 'interpret_goal_with_llm_v1' capability.
        elif not chosen_capability_name and self.current_goal.get("type") == "interpret_user_goal":
            if self.has_capability("interpret_goal_with_llm_v1"):
                log(f"[{self.name}] Goal-driven choice: Goal is 'interpret_user_goal'. Selecting 'interpret_goal_with_llm_v1'.", level="INFO")
                chosen_capability_name = "interpret_goal_with_llm_v1"
                action_selection_reason = "goal_driven_interpret_user_goal"
                # Inputs will be prepared by input_preparer below.
                # The goal remains 'interpret_user_goal' until the LLM response is processed by _update_state_after_action.
            else:
                log(f"[{self.name}] Goal 'interpret_user_goal' requires 'interpret_goal_with_llm_v1' capability, which is missing. Cannot execute.", level="ERROR")
                self.current_goal = {"type": "idle", "reason": "missing_interpret_capability_for_goal"}

        elif not chosen_capability_name and self.current_goal.get("type") == "self_diagnose_failures":
            if self.has_capability("triangulated_insight_v1"):
                log(f"[{self.name}] Goal-driven choice: Goal is 'self_diagnose_failures'. Selecting 'triangulated_insight_v1'. Details: {self.current_goal.get('details')}", level="INFO")
                chosen_capability_name = "triangulated_insight_v1"
                action_selection_reason = "goal_driven_self_diagnose_failures"
                # cap_inputs_for_execution will be prepared by input_preparer
            else:
                log(f"[{self.name}] Goal 'self_diagnose_failures' requires 'triangulated_insight_v1' capability, which is missing. Cannot execute.", level="ERROR")
                self.current_goal = {"type": "idle", "reason": "missing_insight_capability_for_self_diagnosis"}

        elif not chosen_capability_name and "pending_skill_invocation" in self.state and self.state["pending_skill_invocation"]:
            pending_skill_details = self.state.pop("pending_skill_invocation")
            
            if self.has_capability("invoke_skill_agent_v1"):
                chosen_capability_name = "invoke_skill_agent_v1"
                cap_inputs_for_execution = {
                    "skill_action_to_request": pending_skill_details.get("action"),
                    "request_data": pending_skill_details.get("params", {}),
                    "target_skill_agent_id": pending_skill_details.get("preferred_target_agent_id"),
                    "wait_for_response": pending_skill_details.get("wait_for_response", False)
                }
                action_selection_reason = "llm_parsed_skill_invocation"
                log(f"[{self.name}] State-driven choice: Acting on 'pending_skill_invocation'. Chose '{chosen_capability_name}' for action '{pending_skill_details.get('action')}'.")
                # Goal remains idle as this was driven by internal state, not a top-level goal.
                # If invoke_skill_agent_v1 is async, it will set its own pending state.
            else:
                log(f"[{self.name}] Had pending_skill_invocation but missing 'invoke_skill_agent_v1' capability. Cannot execute.", level="ERROR")
                self._report_symptom(
                    symptom_type="capability_missing_for_pending_skill",
                    details_dict={"error": "invoke_skill_agent_v1 missing", "pending_details": pending_skill_details},
                    severity="error"
                )
        # Handle 'investigate_symptoms' goal type
        elif not chosen_capability_name and self.current_goal.get("type") == "investigate_symptoms" and not self.last_diagnosis: # Only if no diagnosis is pending action
            log(f"[{self.name}] Goal-driven choice: Goal is 'investigate_symptoms'. Letting RL choose next action (e.g., knowledge_retrieval or triangulated_insight).", level="DEBUG")
        elif self.current_goal.get("type") == "investigate_symptoms" and self.last_diagnosis:
            log(f"[{self.name}] Goal is 'investigate_symptoms' and has a last_diagnosis: {self.last_diagnosis.get('root_cause_hypothesis')}") # Use root_cause_hypothesis
            suggested_actions = self.last_diagnosis.get("suggested_actions", []) # Use suggested_actions
            
            if "run_diagnostic_sequence_A" in suggested_actions and self.has_capability("sequence_executor_v1"): # Example action
                chosen_capability_name = "sequence_executor_v1"
                cap_inputs_for_execution = {"sub_sequence_param_key_to_use": "diagnostic_sequence_A_params"} # Ensure this param key exists
                action_selection_reason = "diagnosis_suggestion_sequence_A"
                log(f"[{self.name}] Goal-driven choice (from diagnosis): Chose '{chosen_capability_name}' for sequence 'diagnostic_sequence_A_params'.")
            
            if chosen_capability_name:
                self.last_diagnosis = None 
                log(f"[{self.name}] Cleared last_diagnosis after acting on it.")
                self.current_goal = {"type": "idle", "reason": "acted_on_diagnosis_suggestion"}
        # Handle 'generic_task' goal type (internal execution)
        elif not chosen_capability_name and self.current_goal.get("type") == "generic_task": 
            log(f"[{self.name}] Goal-driven choice: Performing 'generic_task': {self.current_goal.get('details')}", level="DEBUG")
            if random.random() < self.generic_task_failure_rate: 
                 failure_details = {
                     "task_processor_id": "generic_task_processor",
                     "description": "Failed to complete generic task",
                     "error_code": random.randint(1000, 1005)
                 }
                 self._report_symptom(symptom_type="generic_task_failure", details_dict=failure_details, severity="error")
                 self.set_goal({"type": "idle", "reason": "generic_task_failed"})
            else:
                log(f"[{self.name}] Achieved complex goal 'generic_task'. Reward: {self.complex_goal_completion_reward:.2f}, Energy Bonus: {self.energy_efficiency_bonus_factor * (self.energy / self.initial_energy if self.initial_energy > 0 else 0):.2f}", level="INFO") 
                self.set_goal({"type": "idle", "reason": "generic_task_complete"})
            chosen_capability_name = "internal_generic_task_execution" 

        # --- RL-Driven Action Selection (Fallback) ---
        if not chosen_capability_name: # If no goal-driven action was selected
            current_rl_state = self._get_rl_state_representation()
            available_caps = self.available_capabilities()
            
            chosen_capability_name, exploration_method = self.rl_system.choose_action(
                current_rl_state_tuple=current_rl_state,
                available_actions=available_caps,
                agent_name=self.name,
                explore_mode_active=(self.behavior_mode == "explore")
            )
            action_selection_reason = f"rl_system_{exploration_method}"
            log(f"[{self.name}] RL-driven choice: Chosen capability '{chosen_capability_name}' via {exploration_method}. Available: {available_caps}", level="DEBUG")

        # --- Input Preparation (if a capability was chosen and inputs weren't set by goal logic) ---        
        if chosen_capability_name and chosen_capability_name != "internal_generic_task_execution":
            # Only prepare inputs if they weren't already set by specific goal-driven logic
            if not cap_inputs_for_execution: # Check if cap_inputs_for_execution is still empty
                cap_inputs_for_execution = self.input_preparer.prepare_inputs(
                    agent=self, 
                    cap_name_to_prep=chosen_capability_name,
                    context=context,
                    knowledge=knowledge,
                    all_agent_names_in_system=all_agent_names_in_system,
                    agent_info_map=agent_info_map
                )
                log(f"[{self.name}] Input preparation called for '{chosen_capability_name}'. Prepared inputs: {str(cap_inputs_for_execution)[:100]}", level="DEBUG")


        if chosen_capability_name:
            if chosen_capability_name == "internal_generic_task_execution":
                log(f"[{self.name}] Final Action: '{chosen_capability_name}'. Reason: internal_task_logic. No capability dispatch.", level="INFO")
            else:
                log(f"[{self.name}] Final Action Choice: '{chosen_capability_name}'. Reason: {action_selection_reason}. Inputs: {str(cap_inputs_for_execution)[:100]}", level="INFO")
                initial_rl_state_for_update = self._get_rl_state_representation()
                self.capability_performance_tracker.record_capability_chosen(chosen_capability_name)
                
                log(f"[{self.name}] Memory size before _execute_capability's potential logging: {len(self.memory.get_log())}", level="DEBUG")

                execution_result = self._execute_capability(
                    chosen_capability_name,
                    context,
                    knowledge,
                    all_agent_names_in_system,
                    **cap_inputs_for_execution
                )
                self._update_state_after_action(initial_rl_state_for_update, chosen_capability_name, execution_result)
        else:
            no_action_log_detail = f"Reason for no action: {action_selection_reason}."
            if action_selection_reason.startswith("rl_system") and not chosen_capability_name:
                no_action_log_detail += f" RL system did not select an action (available_caps: {self.available_capabilities()})."
            
            log(f"[{self.name}] No capability chosen for execution this tick. {no_action_log_detail}", level="DEBUG")
            
            log(f"[{self.name}] Memory size before 'no_action_chosen_final' log_tick: {len(self.memory.get_log())}", level="DEBUG")
            
            log_data_no_action = {"tick": current_sim_tick, "action": "no_action_chosen_final", "reason": action_selection_reason, "outcome": "neutral", "reward": 0.0}
            self.memory.log_tick(log_data_no_action)
            
            log(f"[{self.name}] Memory size after 'no_action_chosen_final' log_tick: {len(self.memory.get_log())}. Data: {log_data_no_action}", level="DEBUG")

        log(f"[{self.name} Tick:{current_sim_tick}] TaskAgent run() end. Energy: {self.energy:.2f}", level="DEBUG")

    def _update_state_after_action(self, initial_rl_state: tuple, executed_capability: str, result: Dict[str, Any]):
        current_tick = self.context_manager.get_tick()
        reward = result.get("reward", 0.0)
        outcome = result.get("outcome", "unknown_outcome")
        details = result.get("details", {})

        # Standard logging for all capability executions
        log_data_action = {"tick": current_tick, "action": executed_capability, "outcome": outcome, "reward": reward, "details": copy.deepcopy(details)}
        self.memory.log_tick(log_data_action)
        log(f"[{self.name}] _update_state_after_action: Logged action '{executed_capability}', Outcome: '{outcome}', Reward: {reward}. Memory size: {len(self.memory.get_log())}", level="DEBUG")

        if executed_capability == "sequence_executor_v1" and outcome == "sequence_paused_waiting_for_sync_step":
            self.state['pending_sequence_state'] = details 
            log(f"[{self.name}] Action '{executed_capability}' outcome: {outcome}. Sequence paused, state stored.", level="INFO")
            
            log_data_pause_initiate = {
                "tick": current_tick, "action": executed_capability, "outcome": outcome,
                "reward": 0.0, 
                "details": {"message": "Sequence paused, awaiting sync step resolution."}
            }
            # This specific log for pause initiation is already covered by the general log_data_action above.
            # If more specific details are needed for pause, they can be added here or to log_data_action.
            # log(f"[{self.name}] _update_state_after_action: Memory size before log_tick for PAUSED '{executed_capability}': {len(self.memory.get_log())}", level="DEBUG")
            # self.memory.log_tick(log_data_pause_initiate)
            # log(f"[{self.name}] _update_state_after_action: Called self.memory.log_tick for PAUSED Action: '{executed_capability}', Outcome: '{outcome}'. Memory size now: {len(self.memory.get_log())}", level="DEBUG")
            return # Return early as Q-value update is handled by sequence executor for sync steps

        # Handle LLM operation pending state
        if outcome == "pending_llm_interpretation" or outcome == "pending_llm_conversation":
            request_id = details.get("request_id")
            if request_id:
                self.state['pending_llm_operations'][request_id] = {
                    "capability_initiated": executed_capability,
                    "original_rl_state": initial_rl_state,
                    "original_cap_inputs": details.get("original_cap_inputs", {}), # Store original inputs if provided by cap
                    "success_reward": details.get("rewards_for_resolution", {}).get("success", 1.0),
                    "failure_reward": details.get("rewards_for_resolution", {}).get("failure", -1.0),
                    "timeout_reward": details.get("rewards_for_resolution", {}).get("timeout", -0.5),
                    "timeout_at_tick": current_tick + details.get("timeout_in_ticks", 20)
                }
                log(f"[{self.name}] LLM operation for '{executed_capability}' is PENDING. Request ID: {request_id}. State stored.", level="INFO")
            return # Return early, Q-value update will happen when LLM response is processed

        # Default Q-value update for completed (non-pending) actions
        self._update_q_value(initial_rl_state, executed_capability, reward, self._get_rl_state_representation())
        self.capability_performance_tracker.record_capability_execution(executed_capability, "success" in outcome.lower(), reward)

        # Specific goal updates based on LLM interpretation results (if not pending)
        if executed_capability == "interpret_goal_with_llm_v1" and outcome == "success_goal_interpreted":
            parsed_action_details = details.get("parsed_plan", details) # Prefer "parsed_plan" if present
            original_user_query = details.get("original_user_query", "Unknown query") # Capability should pass this back
            if isinstance(parsed_action_details, list): # If it's a plan
                self.set_goal({
                    "type": "execute_llm_generated_plan",
                    "details": {"plan_to_execute": parsed_action_details, "original_user_query": original_user_query}
                })
            elif isinstance(parsed_action_details, dict) and parsed_action_details.get("type") == "invoke_skill":
                self.set_goal({
                    "type": "execute_parsed_skill_invocation",
                    "details": parsed_action_details,
                    "original_user_query": original_user_query
                })
            else:
                log(f"[{self.name}] LLM interpretation successful but result type '{type(parsed_action_details)}' or content not directly actionable for new goal. Setting to idle. Details: {str(parsed_action_details)[:200]}", level="WARN")
                self.current_goal = {"type": "idle", "reason": "llm_interpretation_unhandled_type_after_success"}

        elif executed_capability == "conversational_exchange_llm_v1" and outcome == "success_conversation_response":
            # If the capability directly handles conversation history update, nothing more needed here.
            # Goal is typically set to idle after a conversational turn.
            self.current_goal = {"type": "idle", "reason": "conversational_exchange_llm_v1_completed"}

        # If a sequence completed, set goal to idle
        elif executed_capability == "sequence_executor_v1" and "success" in outcome:
            log(f"[{self.name}] Sequence '{details.get('sequence_name', 'unnamed')}' completed with outcome: {outcome}. Setting goal to idle.", level="INFO")
            self.current_goal = {"type": "idle", "reason": f"sequence_{details.get('sequence_name', 'unnamed')}_completed"}
        elif executed_capability == "sequence_executor_v1" and "failure" in outcome:
            log(f"[{self.name}] Sequence '{details.get('sequence_name', 'unnamed')}' failed with outcome: {outcome}. Setting goal to idle.", level="WARN")
            self.current_goal = {"type": "idle", "reason": f"sequence_{details.get('sequence_name', 'unnamed')}_failed"}

        # If the current goal was 'interpret_user_goal' and it led to a failure or non-pending outcome, reset goal.
        if self.current_goal.get("type") == "interpret_user_goal" and executed_capability == "interpret_goal_with_llm_v1" and outcome != "pending_llm_interpretation":
            if "success" not in outcome: # If interpretation failed
                self.current_goal = {"type": "idle", "reason": "interpret_user_goal_failed_or_unactionable"}
            # If successful, the goal would have been changed by the logic above.

        # If the current goal was 'user_defined_goal' and it led to a conversational exchange, it's handled by _execute_conversational_goal.
        # If it led to 'interpret_goal_with_llm_v1', the goal would have been changed to 'interpret_user_goal' or directly to execute a plan.
        # If the goal is still 'user_defined_goal' after an action that wasn't 'interpret_goal_with_llm_v1' or 'conversational_exchange_llm_v1',
        # and the action completed (not pending), it implies the goal might need to be reset or re-evaluated.
        # This case should be rare if goal-driven logic correctly transitions goals.

        # --- Automated Root Cause Analysis Trigger ---
        # Check if this feature is enabled for the agent and if the executed capability is not the insight itself
        if executed_capability != "triangulated_insight_v1":
            insight_cap_params = self.capability_params.get("triangulated_insight_v1", {})
            enable_auto_diagnosis = insight_cap_params.get("auto_trigger_on_high_failure", config.DEFAULT_AUTO_DIAGNOSIS_ENABLED)
            min_attempts_for_check = insight_cap_params.get("min_attempts_for_failure_check", config.DEFAULT_MIN_ATTEMPTS_FOR_FAILURE_CHECK)
            failure_threshold = insight_cap_params.get("failure_rate_threshold_for_insight", config.DEFAULT_FAILURE_RATE_THRESHOLD_FOR_INSIGHT)

            if self.has_capability("triangulated_insight_v1") and enable_auto_diagnosis:
                cap_stats = self.capability_performance_tracker.get_stats_for_capability(executed_capability)
                if cap_stats and cap_stats["attempts"] >= min_attempts_for_check:
                    current_failure_rate = 1.0 - (cap_stats["successes"] / cap_stats["attempts"]) if cap_stats["attempts"] > 0 else 0.0
                    
                    is_already_diagnosing_this = (
                        self.current_goal.get("type") == "self_diagnose_failures" and
                        self.current_goal.get("details", {}).get("failing_capability") == executed_capability
                    )

                    if current_failure_rate >= failure_threshold and not is_already_diagnosing_this:
                        log(f"[{self.name}] High failure rate ({current_failure_rate:.2f}) for capability '{executed_capability}' after {cap_stats['attempts']} attempts. Triggering self-diagnosis.", level="WARNING")
                        self.set_goal({
                            "type": "self_diagnose_failures",
                            "details": {
                                "failing_capability": executed_capability,
                                "current_failure_rate": current_failure_rate,
                                "attempts": cap_stats["attempts"],
                                "successes": cap_stats["successes"]
                            }
                        })

        if self.current_goal.get("type") == "user_defined_goal" and \
           executed_capability not in ["interpret_goal_with_llm_v1", "conversational_exchange_llm_v1"] and \
           "pending" not in outcome:
            log(f"[{self.name}] Action '{executed_capability}' completed for 'user_defined_goal', but goal was not transitioned. Setting to idle.", level="DEBUG")
            self.current_goal = {"type": "idle", "reason": "user_defined_goal_action_completed_no_transition"}
            # chosen_capability_name = "conversational_exchange_llm_v1" # This line was problematic and removed


    def _update_q_value(self, state_tuple: tuple, action: str, reward: float, next_state_tuple: tuple):
        """Helper to call RL system's Q-value update."""
        if self.rl_system:
            available_next_actions = self.available_capabilities()
            self.rl_system.update_q_value(state_tuple, action, reward, next_state_tuple, available_next_actions, self.name)
        else:
            log(f"[{self.name}] Attempted to update Q-value, but no RL system found.", level="TRACE")

    def _execute_conversational_goal(self, goal_description: str, context: 'ContextManager', knowledge: 'KnowledgeBase', all_agent_names_in_system: List[str]):
        """Helper method to execute the conversational exchange capability directly."""
        current_tick = self.context_manager.get_tick()
        log(f"[{self.name}] Executing conversational exchange for user goal: '{goal_description}'", level="INFO")

        cap_inputs_for_convo = {
            "user_input_text": goal_description,
            "conversation_history": self.conversation_history,
            "system_prompt": f"You are an AI assistant named {self.name}. The current simulation tick is {self.context_manager.get_tick()}."
        }
        initial_rl_state_for_convo = self._get_rl_state_representation()

        # Execute the capability directly
        convo_result = self._execute_capability(
            "conversational_exchange_llm_v1",
            context,
            knowledge,
            all_agent_names_in_system,
            **cap_inputs_for_convo
        )

        # Update state and RL based on the result
        self._update_state_after_action(initial_rl_state_for_convo, "conversational_exchange_llm_v1", convo_result)

        # After conversational turn, set goal back to idle
        self.current_goal = {"type": "idle", "reason": "conversational_exchange_complete"}
        log(f"[{self.name}] Conversational exchange complete. Goal set to idle.", level="INFO")

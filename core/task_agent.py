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
                 identity_engine: Optional['IdentityEngine'] = None # Added
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
        self.complex_goal_completion_reward = 2.0
        self.energy_efficiency_bonus_factor = 0.5
        self.pending_delayed_rewards: List[Dict[str, Any]] = []
        
        # Initialize state keys if not present from override
        self.state.setdefault('pending_llm_operations', {})
        self.state.setdefault('pending_skill_requests', {})
        self.last_diagnosis: Optional[Dict[str, Any]] = None
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


    def find_best_skill_agent_for_action(self, skill_action_to_request: str, preferred_target_id: Optional[str] = None) -> Optional[str]:
        if not skill_action_to_request:
            log(f"[{self.name}] find_best_skill_agent_for_action: No skill_action_to_request provided.", level="WARNING")
            return None

        # Get potential agent names from the dynamic registry provided by MetaAgent
        potential_agent_names = self.current_skill_action_registry.get(skill_action_to_request, [])

        if not potential_agent_names:
            log(f"[{self.name}] find_best_skill_agent_for_action: No SkillAgents registered for action '{skill_action_to_request}' in current_skill_action_registry.", level="WARNING")
            return None

        # Filter these potential agents by their active status using self.agent_info_map
        active_and_capable_agents = [
            name for name in potential_agent_names
            if self.agent_info_map.get(name, {}).get("agent_type") == "skill" and \
               self.agent_info_map.get(name, {}).get("is_active", False)
        ]

        if not active_and_capable_agents:
            log(f"[{self.name}] find_best_skill_agent_for_action: Found {len(potential_agent_names)} agents for action '{skill_action_to_request}', but none are currently active or in agent_info_map.", level="WARNING")
            return None

        log(f"[{self.name}] find_best_skill_agent_for_action: Active agents for '{skill_action_to_request}': {active_and_capable_agents}", level="DEBUG")

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
                # Preferred lineage ID was given, but no suitable (or active) agent from that lineage can perform the action.
                log(f"[{self.name}] find_best_skill_agent_for_action: No suitable agent from preferred lineage '{preferred_target_id}' can perform '{skill_action_to_request}'. Looking for any suitable alternative. Active & capable: {active_and_capable_agents}", level="WARNING")
        
        # Fallback if no preferred target was given, or if preferred lineage had no suitable agent
        if not chosen_target_skill_agent_id and active_and_capable_agents: # Check active_and_capable_agents again
            chosen_target_skill_agent_id = random.choice(active_and_capable_agents)
            log(f"[{self.name}] find_best_skill_agent_for_action: Selected suitable agent '{chosen_target_skill_agent_id}' for action '{skill_action_to_request}'. Active & capable: {active_and_capable_agents}")
        
        if not chosen_target_skill_agent_id:
            log(f"[{self.name}] find_best_skill_agent_for_action: No suitable target agent found for skill action '{skill_action_to_request}'. Active & capable: {active_and_capable_agents}, All registered for action: {potential_agent_names}", level="WARNING")
            return None
            
        return chosen_target_skill_agent_id

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
            "event_type": "symptom_report",
            "lineage_id": self.lineage_id
        }
        contribution_score = self.knowledge_base.store(
            lineage_id=self.lineage_id,
            storing_agent_name=self.name,
            item=symptom_data,
            tick=current_tick
        )
        self.memory.log_knowledge_contribution(contribution_score)
        self.memory.log_tick({
            "action": "reported_symptom",
            "symptom_data": symptom_data,
            "kb_contribution": contribution_score,
            "tick": current_tick
        })
        log(f"[{self.name}] Reported symptom '{symptom_id}' (Type: {symptom_type}, Severity: {severity})", level="INFO")


    def _investigate_symptoms(self, goal_details: Dict):
        current_tick = self.context_manager.get_tick()
        log(f"[{self.name}] Starting symptom investigation based on goal: {goal_details}", level="INFO")
        self.memory.log_tick({"action": "start_symptom_investigation", "goal_details": goal_details, "tick": current_tick})

        query_criteria = goal_details.get("criteria", {"data_matches": {"event_type": "symptom_report"}})
        
        symptoms_found = self.knowledge_base.retrieve_full_entries(
            lineage_id=self.lineage_id,
            query_params=query_criteria,
            current_tick=current_tick
        )

        if not symptoms_found:
            log(f"[{self.name}] No symptoms found matching criteria: {query_criteria}", level="INFO")
            self.memory.log_tick({"action": "symptom_investigation_complete", "status": "no_symptoms_found", "tick": current_tick})
            return

        log(f"[{self.name}] Found {len(symptoms_found)} symptoms to investigate.", level="INFO")

        for symptom_entry in symptoms_found:
            symptom_data = symptom_entry.get("data", {})
            if not symptom_data or symptom_data.get("event_type") != "symptom_report":
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
                    "symptom_data": symptom_data,
                }

                # all_agents_list is now self.all_agent_names_in_system_cache
                insight_result = self._execute_capability(
                    "triangulated_insight_v1",
                    self.context_manager,
                    self.knowledge_base,
                    self.all_agent_names_in_system_cache,
                    **insight_cap_inputs
                )
                log(f"[{self.name}] 'triangulated_insight_v1' result: {insight_result.get('outcome')}. Details: {insight_result.get('details')}", level="INFO")
                
                if "diagnosis" in insight_result and insight_result["diagnosis"]:
                    self.last_diagnosis = insight_result["diagnosis"]
                    log(f"[{self.name}] Stored diagnosis: {self.last_diagnosis.get('diagnosis_id')}")
        self.memory.log_tick({"action": "symptom_investigation_complete", "status": "processed_symptoms", "symptoms_count": len(symptoms_found), "tick": current_tick})
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
                if self.context_manager and hasattr(self.context_manager, 'display_insight_in_gui'):
                    self.context_manager.display_insight_in_gui(ack_insight)

                if self.has_capability("interpret_goal_with_llm_v1"):
                    initial_rl_state_for_interpret = self._get_rl_state_representation() # Get state before execution
                    cap_inputs = {
                        "user_query": goal_description,
                        "current_system_context": {
                            "tick": self.context_manager.get_tick(),
                            "available_capabilities": self.capabilities,
                            "agent_name": self.name
                        },
                        "llm_provider": "openai", 
                        "llm_model": "gpt-3.5-turbo" if self.llm_model_name == config.DEFAULT_LLM_MODEL else self.llm_model_name
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
                            else:
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
            "initial_energy_config": self.initial_energy
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

                operational_status = skill_operation_data.get("status", "success") 

                if "success" in status.lower() and "success" in operational_status.lower():
                    reward_to_apply = req_details["success_reward"]
                    is_success = True
                else:
                    failure_reason_detail = skill_operation_data.get("message", skill_operation_data.get("error", status))
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
                        "reason": f"failure_skill_response_{status}"
                    }
                completed_request_ids.append(req_id)

        for req_id in completed_request_ids:
            if req_id in self.state['pending_skill_requests']: 
                del self.state['pending_skill_requests'][req_id]

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
                                        "details": {"plan_to_execute": parsed_plan, "original_user_query": req_details.get("original_cap_inputs")}
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
                            if self.context_manager and hasattr(self.context_manager, 'display_system_insight'):
                                original_prompt = req_details.get("original_cap_inputs", "User query N/A")
                                self.context_manager.display_system_insight({
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
                    processed_details = {"error": llm_response_data.get("error", "Unknown LLM error occurred.")}
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
                diagnosis_data = tick_log.get("diagnosis")
                if not diagnosis_data and "details" in tick_log:
                    diagnosis_data = tick_log.get("details", {}).get("diagnosis")

                if diagnosis_data and isinstance(diagnosis_data, dict) and diagnosis_data.get("confidence", 0.0) > self.insight_confidence_threshold: 
                     successful_insights_count += 1
                     total_insight_confidence += diagnosis_data.get("confidence", 0.0)
        
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
                op_status_tool = skill_op_data.get("status", "success") 
                is_overall_success = "success" in status_from_skill_agent.lower() and "success" in op_status_tool.lower()
                
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
                    "pass_outputs_between_steps": False,
                    "stop_on_failure": True
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
                if self.context_manager and hasattr(self.context_manager, 'display_system_insight'): # Use the correct method name
                    self.context_manager.display_system_insight(ack_insight)

                if self.has_capability("interpret_goal_with_llm_v1"):
                    # Set the goal to indicate interpretation is pending/needed
                    self.set_goal({"type": "interpret_user_goal", "details": {"user_query": goal_description}})
                    log(f"[{self.name}] Set goal to 'interpret_user_goal' for '{goal_description}'. RL will choose 'interpret_goal_with_llm_v1' next.", level="INFO")
                    # Do NOT set chosen_capability_name here. The logic below for "interpret_user_goal" or RL will pick it up.

                elif self.has_capability("conversational_exchange_llm_v1"):
                    log(f"[{self.name}] No 'interpret_goal_with_llm_v1'. Using 'conversational_exchange_llm_v1' for user goal: '{goal_description}'", level="INFO")
                    # Execute conversational exchange immediately as it's a single turn
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
            log(f"[{self.name}] Goal is 'investigate_symptoms' and has a last_diagnosis: {self.last_diagnosis.get('diagnosis_id')}")
            suggested_actions = self.last_diagnosis.get("suggested_action_flags", [])
            
            if "run_diagnostic_sequence_A" in suggested_actions and self.has_capability("sequence_executor_v1"):
                chosen_capability_name = "sequence_executor_v1"
                cap_inputs_for_execution = {"sub_sequence_param_key_to_use": "diagnostic_sequence_A_params"}
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
            parsed_action_details = details # Assuming 'details' contains the parsed plan/action
            original_user_query = details.get("original_user_query", "Unknown query") # Capability should pass this back
            if isinstance(parsed_action_details, list): # If it's a plan
                self.set_goal({
                    "type": "execute_llm_generated_plan",
                    "details": {"plan_to_execute": parsed_action_details, "original_user_query": original_user_query}
                })
            elif parsed_action_details.get("type") == "invoke_skill":
                self.set_goal({
                    "type": "execute_parsed_skill_invocation",
                    "details": parsed_action_details,
                    "original_user_query": original_user_query
                })
            else:
                log(f"[{self.name}] LLM interpretation successful but result type '{parsed_action_details.get('type')}' not directly actionable for new goal. Setting to idle. Details: {parsed_action_details}", level="WARN")
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
        if self.current_goal.get("type") == "user_defined_goal" and \
           executed_capability not in ["interpret_goal_with_llm_v1", "conversational_exchange_llm_v1"] and \
           "pending" not in outcome:
            log(f"[{self.name}] Action '{executed_capability}' completed for 'user_defined_goal', but goal was not transitioned. Setting to idle.", level="DEBUG")
            self.current_goal = {"type": "idle", "reason": "user_defined_goal_action_completed_no_transition"}


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

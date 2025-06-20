# core / mutation_engine.py

import random
import copy
from typing import Dict, List, Any, Callable, TYPE_CHECKING, Optional
import ast # For parsing code to find stubs
import sys # For ast.unparse check

from core.agent_base import BaseAgent
from engine.fitness_engine import FitnessEngine
from utils.logger import log
from core.capability_registry import CAPABILITY_REGISTRY # Ensure this is used or remove if not
import config as global_config # Import the main config file
from agents.code_gen_agent import CodeGenAgent # For type hinting
if TYPE_CHECKING:
    from core.meta_agent import MetaAgent
    from core.task_agent import TaskAgent
    from core.skill_agent import SkillAgent

MUTATABLE_SKILL_AGENT_CAPABILITIES = [
    # These are "meta-capabilities" that SkillAgents use to declare skill sets.
    "data_analysis_basic_v1",
    "math_services_v1",
    "web_services_v1",
    "file_services_v1",
    "api_services_v1",
    "weather_services_v1", # Added
    "calendar_services_v1" # Added
]

# Capabilities that TaskAgents can actually execute (should have a handler in TaskAgent or BaseAgent)
EXECUTABLE_TASK_AGENT_CAPABILITIES = [
    cap_name for cap_name, cap_details in CAPABILITY_REGISTRY.items()
    if cap_details.get("handler") is not None and cap_name not in MUTATABLE_SKILL_AGENT_CAPABILITIES
]

class MutationEngine:
    """
    Handles the mutation of agent configurations to drive evolution.
    """
    # Define capabilities that are considered essential for Task Agents and should be protected from removal.
    ESSENTIAL_TASK_CAPABILITIES = {
        "sequence_executor_v1",
        "invoke_skill_agent_v1",
        "knowledge_storage_v1" # Add knowledge_storage_v1 as essential
    }
    # Define default skill lineages and minimums for rescue logic
    DEFAULT_SKILL_LINEAGE_BASES: List[str] = [] # To be populated in __init__
    MIN_SURVIVORS_PER_DEFAULT_LINEAGE = 1
    # Configurable survival rate for initial selection, if not defined elsewhere
    AGENT_SURVIVAL_RATE = 0.5 

    def __init__(self, meta_agent_instance: 'MetaAgent', knowledge_base_instance: Any, context_manager_instance: Any):
        self.meta_agent: 'MetaAgent' = meta_agent_instance
        self.knowledge = knowledge_base_instance
        self.context = context_manager_instance
        self.fitness_engine = FitnessEngine(self.context)
        self.behavior_mode_performance: Dict[str, Dict[str, float]] = {
            mode: {"total_fitness": 0.0, "count": 0.0} for mode in BaseAgent.BEHAVIOR_MODES
        }
        self.last_agent_fitness_scores: Dict[str, float] = {} # Store name -> fitness

        # Populate DEFAULT_SKILL_LINEAGE_BASES from MetaAgent's default skill configs
        self.DEFAULT_SKILL_LINEAGE_BASES = list(set(
            cfg.get('lineage_id', 'unknown_lineage') # Default to 'unknown_lineage' if somehow missing
            for cfg in self.meta_agent.default_skill_configs_by_lineage.values() if cfg and cfg.get('lineage_id')))
        
        # For asynchronous code generation
        self.pending_code_generation_requests: Dict[str, Dict[str, Any]] = {}
        self.code_gen_request_timeout_ticks = int(global_config.LOCAL_LLM_REQUEST_TIMEOUT / (global_config.TICK_INTERVAL if global_config.TICK_INTERVAL > 0 else 1.0)) + 10 # Add buffer
        self.code_gen_agent: Optional[CodeGenAgent] = None
        log("[MutationEngine] Initialized.")

    def set_code_gen_agent(self, code_gen_agent_instance: CodeGenAgent):
        """Sets the CodeGenAgent instance for the MutationEngine."""
        self.code_gen_agent = code_gen_agent_instance
        if self.code_gen_agent:
            log("[MutationEngine] CodeGenAgent instance has been set.", level="INFO")
        else:
            log("[MutationEngine] CodeGenAgent instance set to None.", level="WARN")

    def should_mutate(self, fitness: float) -> bool:
        return random.random() < (1.0 - fitness)

    def mutate_config(self, config: Dict[str, Any], agent_type: str, all_active_agent_names: Optional[List[str]] = None) -> Dict[str, Any]: # Added all_active_agent_names
        if all_active_agent_names is None:
            all_active_agent_names = []
        
        mutated_config = copy.deepcopy(config)
        mutated_config["agent_type"] = config.get("agent_type", "task")

        # Robust lineage_id determination:
        # Priority: 1. Existing 'lineage_id' from config (should already be base if from instance)
        #           2. Derived base from 'name' in config
        original_name_for_lineage = config.get("name", "unknown_agent")
        base_lineage_from_name = original_name_for_lineage.split('-gen')[0].split('_0')[0]
        
        # Use existing lineage_id if present and valid, otherwise derive from name.
        # Then, ensure it's stripped to the base form.
        current_lineage_id = config.get("lineage_id", base_lineage_from_name)
        if current_lineage_id: 
            mutated_config["lineage_id"] = current_lineage_id.split('-gen')[0].split('_0')[0]
        else: 
            mutated_config["lineage_id"] = base_lineage_from_name # This is already the base if derived

        # Generation update - ensure it increments from the parent's generation
        mutated_config["generation"] = config.get("generation", 0) + 1
        # Name update using the correctly determined base lineage_id and new generation
        mutated_config["name"] = f"{mutated_config['lineage_id']}-gen{mutated_config['generation']}"
        # Ensure agent_id is also unique, using the new name.
        mutated_config["agent_id"] = mutated_config["name"]

        if agent_type == "task":
            # Ensure 'initial_state_override' exists and is a dictionary for energy setting for TaskAgents
            if "initial_state_override" not in mutated_config or not isinstance(mutated_config.get("initial_state_override"), dict):
                mutated_config["initial_state_override"] = {}
            mutated_config["initial_state_override"]["energy"] = global_config.DEFAULT_INITIAL_ENERGY
            log(f"[{mutated_config['name']}] MUTATION: Initial energy for new TaskAgent set to default: {global_config.DEFAULT_INITIAL_ENERGY}")
        elif agent_type == "skill":
            # SkillAgents do not use 'initial_state_override' for energy; they use 'initial_energy' directly.
            # Remove 'initial_state_override' if it exists in the config for a skill agent.
            if "initial_state_override" in mutated_config:
                del mutated_config["initial_state_override"]
                log(f"[{mutated_config['name']}] MUTATION: Removed 'initial_state_override' from SkillAgent config.", level="DEBUG")

        # Force behavior_mode for task agents, maintain for skill agents
        if agent_type == "task":
            mutated_config["behavior_mode"] = "explore"
            log(f"[{mutated_config['name']}] MUTATION: Behavior mode forced to 'explore' for task agent.")
        elif agent_type == "skill":
            # For skill agents, keep their configured mode (usually "observer") or default to it.
            mutated_config["behavior_mode"] = config.get("behavior_mode", "observer")
            # log(f"[{mutated_config['name']}] MUTATION: Behavior mode for skill agent set to '{mutated_config['behavior_mode']}'.") # Optional: log if needed
        else:
            # Fallback for any other unknown agent type, though ideally this branch isn't hit.
            mutated_config["behavior_mode"] = "explore"

        current_caps = list(mutated_config.get("capabilities", []))
        current_params = mutated_config.get("capability_params", {}).copy()
        agent_role = mutated_config.get("role", "generalist") # Get the agent's role

        # --- Placeholder for Role-Specific Mutation Logic ---
        # Here, you could define preferred capabilities or parameter ranges for specific roles.
        # For example:
        # if agent_role == "data_collector":
        #     # Prioritize adding knowledge_retrieval_v1, web_services_v1, etc.
        #     # Bias parameter mutations towards efficiency for these capabilities.
        # elif agent_role == "diagnoser":
        #     # Prioritize triangulated_insight_v1, data_analysis_v1.
        # agent_type = mutated_config.get("agent_type") # agent_type is now passed as an argument

        if agent_type == "skill":
            # Ensure skill agent has at least one skill-providing capability
            possessed_skill_providing_caps = [c for c in current_caps if c in MUTATABLE_SKILL_AGENT_CAPABILITIES]
            
            if not possessed_skill_providing_caps: # If it has no valid skill-providing capabilities
                available_to_force_add = [c for c in MUTATABLE_SKILL_AGENT_CAPABILITIES if c not in current_caps]
                if available_to_force_add:
                    cap_to_add = random.choice(available_to_force_add)
                    current_caps.append(cap_to_add)
                    current_caps = list(set(current_caps)) # Ensure uniqueness
                    log(f"[{mutated_config['name']}] MUTATION: Forced adding skill-providing capability '{cap_to_add}' to skill agent.")
                elif MUTATABLE_SKILL_AGENT_CAPABILITIES:
                    log(f"[{mutated_config['name']}] MUTATION: Skill agent has capabilities, but none are from MUTATABLE_SKILL_AGENT_CAPABILITIES. Check config. Caps: {current_caps}", level="WARNING")

        mutation_type_roll = random.random()
        mutation_rate_add_capability = 0.2 # Example rate
        mutation_rate_remove_capability = 0.15 # Example rate
        min_capabilities = 1 # Example min capabilities

        # --- Role-influenced capability addition ---
        if mutation_type_roll < mutation_rate_add_capability:
            # Example: Define role_preferred_capabilities
            # role_preferred_capabilities = {"data_collector": ["knowledge_retrieval_v1", "web_services_v1"], ...}
            # preferred_for_role = role_preferred_capabilities.get(agent_role, [])

            if agent_type == "skill":
                available_to_add = [c_name for c_name in MUTATABLE_SKILL_AGENT_CAPABILITIES if c_name not in current_caps]
            else: # For TaskAgent - only allow adding executable capabilities
                # if preferred_for_role: # Prioritize adding role-specific caps
                #    available_to_add = [c for c in preferred_for_role if c not in current_caps] + [c for c in CAPABILITY_REGISTRY.keys() if c not in current_caps and c not in preferred_for_role]
                available_to_add = [c_name for c_name in EXECUTABLE_TASK_AGENT_CAPABILITIES if c_name not in current_caps]
            
            if available_to_add:
                cap_to_add = random.choice(available_to_add)
                current_caps.append(cap_to_add)
                current_caps = list(set(current_caps)) # Ensure uniqueness
                if cap_to_add in CAPABILITY_REGISTRY:
                    current_params.setdefault(cap_to_add, CAPABILITY_REGISTRY[cap_to_add]["params"].copy())
                log(f"[{mutated_config['name']}] MUTATION: Added capability '{cap_to_add}'")
        # --- Role-influenced capability removal (less likely to remove core role capabilities) ---
        elif mutation_type_roll < mutation_rate_add_capability + mutation_rate_remove_capability:
            if len(current_caps) > min_capabilities: # Only remove if above min
                protected_caps = set()
                for cap_name_iter in current_caps: # Iterate over a copy for safety if modifying
                    if cap_name_iter in CAPABILITY_REGISTRY and CAPABILITY_REGISTRY[cap_name_iter].get("critical", False):
                        protected_caps.add(cap_name_iter)
                
                if agent_type == "task":
                    protected_caps.update(self.ESSENTIAL_TASK_CAPABILITIES.intersection(current_caps))
                elif agent_type == "skill":
                    # Protect the defining capability of the skill agent's lineage
                    agent_lineage_id = mutated_config.get("lineage_id")
                    if agent_lineage_id and agent_lineage_id in self.meta_agent.default_skill_configs_by_lineage:
                        default_config_for_lineage = self.meta_agent.default_skill_configs_by_lineage[agent_lineage_id]
                        defining_capabilities = default_config_for_lineage.get("capabilities", [])
                        for def_cap in defining_capabilities:
                            if def_cap in current_caps: # Only protect if currently possessed
                                protected_caps.add(def_cap)
                                log(f"[{mutated_config['name']}] MUTATION: Protecting defining capability '{def_cap}' for lineage '{agent_lineage_id}'.")
                    
                    # Original logic to prevent removing the last skill-providing capability (from MUTATABLE list)
                    # This acts as a fallback or secondary protection.
                    possessed_skill_providing_caps = [c for c in current_caps if c in MUTATABLE_SKILL_AGENT_CAPABILITIES]
                    if len(possessed_skill_providing_caps) == 1 and possessed_skill_providing_caps[0] in current_caps:
                        if possessed_skill_providing_caps[0] not in protected_caps: # Avoid double-logging if already protected
                           protected_caps.add(possessed_skill_providing_caps[0])
                           log(f"[{mutated_config['name']}] MUTATION: Protecting last mutable skill capability '{possessed_skill_providing_caps[0]}'.")
                # Example: Add role-core capabilities to protected_caps (if using roles for skills)
                # role_core_capabilities = {"data_collector": {"knowledge_retrieval_v1"}, ...}
                # protected_caps.update(role_core_capabilities.get(agent_role, set()))
                
                eligible_for_removal = [cap for cap in current_caps if cap not in protected_caps]

                if eligible_for_removal:
                    cap_to_remove = random.choice(eligible_for_removal)
                    current_caps.remove(cap_to_remove)
                    current_params.pop(cap_to_remove, None)
                    log(f"[{mutated_config['name']}] MUTATION: Removed capability '{cap_to_remove}'")
                else:
                    log(f"[{mutated_config['name']}] MUTATION: Skipped removing capability; only protected or min capabilities remain. Protected: {protected_caps}, Current: {current_caps}")
            else:
                log(f"[{mutated_config['name']}] MUTATION: Skipped removing capability; at or below min_capabilities ({min_capabilities}).")

        # --- Role-influenced parameter mutation ---
        elif current_caps: # Default to mutating parameters if not adding/removing
            cap_to_modify_params = random.choice(current_caps)
            if cap_to_modify_params in current_params:
                params_for_cap = current_params[cap_to_modify_params]
                if params_for_cap:
                    param_key = random.choice(list(params_for_cap.keys()))
                    original_value = params_for_cap[param_key]
                    
                    if isinstance(original_value, bool): # Check for bool first
                        new_bool_value = not original_value
                        params_for_cap[param_key] = new_bool_value
                        log(f"[{mutated_config['name']}] MUTATION: Toggled boolean param '{cap_to_modify_params}.{param_key}' from {original_value} to {new_bool_value}.")
                    elif isinstance(original_value, (int, float)): # Then check for int/float
                        # Ensure change_factor is not too close to 1 to guarantee a change for integers
                        change_factor = random.choice([random.uniform(0.5, 0.95), random.uniform(1.05, 1.5)])
                        new_value = original_value * change_factor
                        if isinstance(original_value, int):
                            new_value = round(new_value)
                            if new_value == original_value:
                                if original_value == 0:
                                    new_value += random.choice([-1, 1]) # Ensure 0 always changes
                                else:
                                    new_value += random.choice([-1, 1])
                        params_for_cap[param_key] = new_value
                        original_value_display = f"{original_value:.2f}" if isinstance(original_value, float) else original_value
                        new_value_display = f"{new_value:.2f}" if isinstance(new_value, float) else new_value
                        log(f"[{mutated_config['name']}] MUTATION: Cap '{cap_to_modify_params}', param '{param_key}' from {original_value_display} to {new_value_display}")
                    elif cap_to_modify_params == "invoke_skill_agent_v1" and param_key == "target_skill_agent_id":
                        other_skill_agents = [name for name in all_active_agent_names if name.startswith("skill_") and name != original_value]
                        if other_skill_agents:
                            new_target = random.choice(other_skill_agents)
                            params_for_cap[param_key] = new_target
                            log(f"[{mutated_config['name']}] MUTATION: Cap '{cap_to_modify_params}', param '{param_key}' (target_skill_agent_id) from '{original_value}' to '{new_target}'")
                        else:
                            log(f"[{mutated_config['name']}] MUTATION: Cap '{cap_to_modify_params}', param '{param_key}', no other skill agents to switch to (current: '{original_value}').")
                    
                    elif cap_to_modify_params == "sequence_executor_v1" and param_key == "sub_sequence":
                        current_sequence = list(original_value)
                        available_primitive_caps = [
                            c_name for c_name in CAPABILITY_REGISTRY.keys()
                            if c_name != "sequence_executor_v1" and c_name in current_caps
                        ]
                        seq_mutation_type = random.choice(["add", "remove", "swap", "replace_element"])
                        MAX_SEQUENCE_LENGTH = 5

                        if seq_mutation_type == "add" and available_primitive_caps and len(current_sequence) < MAX_SEQUENCE_LENGTH:
                            cap_to_add_name = random.choice(available_primitive_caps)
                            insert_pos = random.randint(0, len(current_sequence))
                            
                            step_definition = cap_to_add_name
                            if cap_to_add_name == "invoke_skill_agent_v1":
                                target_skill_id = random.choice([n for n in all_active_agent_names if n.startswith("skill_")]) if [n for n in all_active_agent_names if n.startswith("skill_")] else "skill_data_analysis_0" # Fallback
                                sub_request_type = random.choice(["math", "data_analysis", "web", "file", "api_call"])
                                request_data_payload = {}
                                skill_action_for_sub_step = ""

                                if sub_request_type == "math":
                                    request_data_payload = {"maths_command": random.choice(["add 1 1", "subtract 10 5"])}
                                    skill_action_for_sub_step = "maths_operation"
                                elif sub_request_type == "data_analysis":
                                    request_data_payload = {"data_points": [], "analysis_type": random.choice(["log_summary", "complexity"])}
                                    skill_action_for_sub_step = random.choice(["log_summary", "complexity"])
                                elif sub_request_type == "web":
                                    request_data_payload = {"web_command": random.choice(["get_text https://example.com", "fetch https://www.python.org/doc/"])}
                                    skill_action_for_sub_step = "web_operation"
                                elif sub_request_type == "file":
                                    request_data_payload = {"file_command": random.choice(["list ./", "read ./data.txt"])}
                                    skill_action_for_sub_step = "file_operation"
                                elif sub_request_type == "api_call":
                                    request_data_payload = {"api_command": random.choice(["get_joke Any", "get_weather 0 0"])}
                                    skill_action_for_sub_step = "api_call"
                                
                                step_definition = {
                                    "name": "invoke_skill_agent_v1",
                                    "inputs": {
                                        "skill_action_to_request": skill_action_for_sub_step,
                                        "request_data": request_data_payload
                                    },
                                    "params_override": {"target_skill_agent_id": target_skill_id}
                                }
                            current_sequence.insert(insert_pos, step_definition)
                            log(f"[{mutated_config['name']}] MUTATION: SeqExec: Added element to sequence. New: {current_sequence}")

                        elif seq_mutation_type == "remove" and current_sequence and len(current_sequence) > 1:
                            removed_cap = current_sequence.pop(random.randrange(len(current_sequence)))
                            log(f"[{mutated_config['name']}] MUTATION: SeqExec: Removed '{str(removed_cap)[:50]}' from sequence. New: {current_sequence}")
                        elif seq_mutation_type == "swap" and len(current_sequence) >= 2:
                            idx1, idx2 = random.sample(range(len(current_sequence)), 2)
                            current_sequence[idx1], current_sequence[idx2] = current_sequence[idx2], current_sequence[idx1]
                            log(f"[{mutated_config['name']}] MUTATION: SeqExec: Swapped elements in sequence. New: {current_sequence}")
                        elif seq_mutation_type == "replace_element" and current_sequence and available_primitive_caps:
                            idx_to_replace = random.randrange(len(current_sequence))
                            new_cap_for_seq_name = random.choice(available_primitive_caps)
                            old_cap_in_seq = current_sequence[idx_to_replace]
                            
                            new_step_definition = new_cap_for_seq_name
                            if new_cap_for_seq_name == "invoke_skill_agent_v1":
                                target_skill_id = random.choice([n for n in all_active_agent_names if n.startswith("skill_")]) if [n for n in all_active_agent_names if n.startswith("skill_")] else "skill_data_analysis_0" # Fallback
                                sub_request_type = random.choice(["math", "data_analysis", "web", "file", "api_call"])
                                request_data_payload = {}
                                skill_action_for_sub_step = ""
                                if sub_request_type == "math":
                                    request_data_payload = {"maths_command": random.choice(["add 1 1", "subtract 10 5"])}
                                    skill_action_for_sub_step = "maths_operation"
                                elif sub_request_type == "data_analysis":
                                    request_data_payload = {"data_points": [], "analysis_type": random.choice(["log_summary", "complexity"])}
                                    skill_action_for_sub_step = random.choice(["log_summary", "complexity"])
                                elif sub_request_type == "web":
                                    request_data_payload = {"web_command": random.choice(["get_text https://example.com", "fetch https://www.python.org/doc/"])}
                                    skill_action_for_sub_step = "web_operation"
                                elif sub_request_type == "file":
                                    request_data_payload = {"file_command": random.choice(["list ./", "read ./data.txt"])}
                                    skill_action_for_sub_step = "file_operation"
                                elif sub_request_type == "api_call":
                                    request_data_payload = {"api_command": random.choice(["get_joke Any", "get_weather 0 0"])}
                                    skill_action_for_sub_step = "api_call"

                                new_step_definition = {
                                    "name": "invoke_skill_agent_v1",
                                    "inputs": {
                                        "skill_action_to_request": skill_action_for_sub_step,
                                        "request_data": request_data_payload
                                    },
                                    "params_override": {"target_skill_agent_id": target_skill_id}
                                }
                            current_sequence[idx_to_replace] = new_step_definition
                            log(f"[{mutated_config['name']}] MUTATION: SeqExec: Replaced '{str(old_cap_in_seq)[:50]}' with '{str(new_step_definition)[:50]}' in sequence. New: {current_sequence}")

                        params_for_cap[param_key] = current_sequence


        mutated_config["capabilities"] = current_caps
        mutated_config["capability_params"] = current_params

        return mutated_config

    def _determine_survivors(self, all_agents_current_gen_with_metrics):
        # all_agents_current_gen_with_metrics: list of (agent, {'fitness': float, 'executions': int, ...})

        # Sort agents by fitness, highest first
        sorted_agents_with_metrics = sorted(
            all_agents_current_gen_with_metrics,
            key=lambda x: x[1]['fitness'],
            reverse=True
        )

        # Determine the number of agents to survive based on survival rate
        num_to_survive_initially = int(len(sorted_agents_with_metrics) * self.config.get('survival_rate', 0.5))

        # Initial selection of survivors based purely on fitness
        current_survivors = [
            agent_metric_tuple[0] for agent_metric_tuple in sorted_agents_with_metrics[:num_to_survive_initially]
        ]
        survivor_metrics_map = {
            agent_metric_tuple[0]: agent_metric_tuple[1] for agent_metric_tuple in sorted_agents_with_metrics[:num_to_survive_initially]
        }

        # --- Intervention to preserve default skill lineages ---
        for lineage_base_name in self.DEFAULT_SKILL_LINEAGE_BASES:
            # Check if this lineage is already represented among the current survivors
            is_lineage_represented = any(
                agent.agent_type == 'skill' and agent.lineage_name.startswith(lineage_base_name)
                for agent in current_survivors
            )

            if is_lineage_represented:
                continue # This lineage is fine, move to the next

            # Lineage is not represented. Try to rescue one.
            # Find candidates from the *entire current population* of this lineage.
            candidates_for_rescue_with_metrics = [
                (agent, metrics) for agent, metrics in all_agents_current_gen_with_metrics
                if agent.agent_type == 'skill' and agent.lineage_name.startswith(lineage_base_name)
            ]

            if not candidates_for_rescue_with_metrics:
                log.warning(f"MutationEngine: No candidates found for rescue in lineage '{lineage_base_name}'. It might be extinct or was never populated this generation.")
                continue

            # Prioritize candidates for rescue:
            # 1. Prefer those with 0 executions (culled for inactivity).
            # 2. Among those with 0 executions, prefer younger ones (higher generation number).
            # 3. Then, those with >0 executions but low success (already likely culled).
            # 4. Fallback: highest fitness among them.
            def rescue_priority_key(agent_metric_tuple):
                agent, metrics = agent_metric_tuple
                executions = metrics.get('executions', -1)
                fitness = metrics.get('fitness', 0.0)
                generation = agent.generation

                if executions == 0:
                    # Primary rescue targets: 0 executions.
                    # Higher generation (younger) is better.
                    return (0, -generation, -fitness)
                elif executions > 0:
                    # Secondary: already executed but culled (likely low success).
                    return (1, -fitness, -generation)
                else: # executions == -1 (unknown, should not happen if metrics are good)
                    return (2, -fitness, -generation)

    def _update_behavior_mode_performance(self, agent_config: dict, fitness: float):
        mode = agent_config.get("behavior_mode")
        if mode and mode in self.behavior_mode_performance:
            self.behavior_mode_performance[mode]["total_fitness"] += fitness
            self.behavior_mode_performance[mode]["count"] += 1
        elif mode:
            log(f"[MutationEngine] Behavior mode '{mode}' from agent '{agent_config.get('name')}' not in tracker. Initializing.", level="WARNING")
            self.behavior_mode_performance[mode] = {"total_fitness": fitness, "count": 1.0}
        else:
            log(f"[MutationEngine] Agent '{agent_config.get('name')}' has no behavior_mode in config. Cannot update performance.", level="WARNING")

    def run_assessment_and_mutation(self):
        # First, handle any pending asynchronous code generation responses
        self._handle_pending_code_generation_responses()

        current_tick = self.context.get_tick()
        log(f"MutationEngine: Starting assessment and mutation cycle (Tick {current_tick})...")

        if current_tick > 0 and current_tick % 100 == 0: # TODO: Make this configurable
            self.last_agent_fitness_scores.clear() # Clear old scores on decay/reset
            log("[MutationEngine] Decaying behavior mode performance statistics...")
            decay_factor = 0.9
            for mode in self.behavior_mode_performance:
                self.behavior_mode_performance[mode]["total_fitness"] *= decay_factor
                self.behavior_mode_performance[mode]["count"] *= decay_factor
                if self.behavior_mode_performance[mode]["count"] < 0.001:
                    self.behavior_mode_performance[mode]["count"] = 0.0

        assessable_agent_data = []
        current_cycle_fitness_scores: Dict[str, float] = {}
        for agent in self.meta_agent.agents:
            try:
                # Check for aging out before fitness calculation
                if agent.age > agent.max_age:
                    log(f"  - Agent '{agent.name}' (Age: {agent.age}/{agent.max_age}) removed due to old age.")
                    # This agent will be removed later when the population is cleared.
                    # It won't be added to assessable_agent_data, so it won't be a candidate for mutation.
                    continue # Skip to the next agent
                
                fitness_metrics = agent.get_fitness() # Now returns a dict
                assessable_agent_data.append({
                    "config": agent.get_config(),
                    "fitness_metrics": fitness_metrics, # Store the whole dict
                    "instance": agent
                })
                current_cycle_fitness_scores[agent.name] = fitness_metrics["fitness"] # Store fitness score by agent name
                # Log assessment for agents that are not aged out
                self._update_behavior_mode_performance(agent.get_config(), fitness_metrics["fitness"])
                log(f"  - Assessing Agent '{agent.name}': Calculated Fitness = {fitness_metrics['fitness']:.2f}, Executions: {fitness_metrics.get('executions', 'N/A')}")
            except Exception as e:
                log(f"MutationEngine: Error assessing fitness for {agent.name} (Type: {agent.agent_type}): {e}", level="ERROR")
                continue

        self.last_agent_fitness_scores = current_cycle_fitness_scores # Update with the latest scores

        if not assessable_agent_data:
            log("MutationEngine: No agents successfully assessed for fitness. Skipping mutation.", level="WARNING")
            return

        assessed_task_agents = [d for d in assessable_agent_data if d["config"].get("agent_type") == "task"]
        assessed_skill_agents = [d for d in assessable_agent_data if d["config"].get("agent_type") == "skill"]

        new_task_agent_configs = []
        new_skill_agent_configs = []
        
        all_current_agent_names = self.meta_agent.get_all_agent_names() # Get all names for mutate_config

        if assessed_task_agents:
            assessed_task_agents.sort(key=lambda x: x["fitness_metrics"]["fitness"], reverse=True)
            task_pop_configs = [d["config"] for d in assessed_task_agents]
            task_weights = [max(0.001, d["fitness_metrics"]["fitness"]) for d in assessed_task_agents]

            if sum(task_weights) == 0:
                log("MutationEngine: All Task Agent fitnesses are zero. Reverting to uniform selection for mutation.", level="WARNING")
                task_weights = [1.0] * len(task_pop_configs)

            num_to_mutate_task = max(1, int(len(task_pop_configs) * 0.5))
            num_to_mutate_task = min(num_to_mutate_task, len(task_pop_configs))

            try:
                selected_task_configs_for_mutation = random.choices(task_pop_configs, weights=task_weights, k=num_to_mutate_task)
            except ValueError as e:
                log(f"MutationEngine: ValueError in random.choices for Task Agents. Pop: {len(task_pop_configs)}, Weights: {len(task_weights)}. Err: {e}", level="ERROR")
                selected_task_configs_for_mutation = random.sample(task_pop_configs, k=min(num_to_mutate_task, len(task_pop_configs))) if task_pop_configs else []
            
            for selected_config in selected_task_configs_for_mutation:
                mutated_config = self.mutate_config(selected_config, "task", all_current_agent_names) # Pass agent_type
                new_task_agent_configs.append(mutated_config)
                # Attempt radical code generation based on the mutated config
                # This is now asynchronous, so it won't block the mutation cycle.
                if random.random() < 0.05: # Reduced chance for demo, adjust as needed
                    self._attempt_code_generation_for_evolution(mutated_config, current_tick)
                log(f"  - Agent '{selected_config['name']}' selected and mutated for next generation.")
        else:
            log("MutationEngine: No Task Agents to mutate.", level="INFO")

        if assessed_skill_agents:
            assessed_skill_agents.sort(key=lambda x: x["fitness_metrics"]["fitness"], reverse=True)
            skill_pop_configs = [d["config"] for d in assessed_skill_agents]
            skill_weights = [max(0.001, d["fitness_metrics"]["fitness"]) for d in assessed_skill_agents]

            if sum(skill_weights) == 0:
                log("MutationEngine: All Skill Agent fitnesses are zero. Reverting to uniform selection for mutation.", level="WARNING")
                skill_weights = [1.0] * len(skill_pop_configs)

            num_to_mutate_skill = max(1, int(len(skill_pop_configs) * 0.5))
            num_to_mutate_skill = min(num_to_mutate_skill, len(skill_pop_configs))

            try:
                selected_skill_configs_for_mutation = random.choices(skill_pop_configs, weights=skill_weights, k=num_to_mutate_skill)
            except ValueError as e:
                log(f"MutationEngine: ValueError in random.choices for Skill Agents. Pop: {len(skill_pop_configs)}, Weights: {len(skill_weights)}. Err: {e}", level="ERROR")
                selected_skill_configs_for_mutation = random.sample(skill_pop_configs, k=min(num_to_mutate_skill, len(skill_pop_configs))) if skill_pop_configs else []
            
            # Ensure we mutate each selected config only once, even if selected multiple times by random.choices
            # This can happen if k is large or weights are skewed.
            unique_selected_skill_configs = []
            seen_configs_str = set()
            for cfg in selected_skill_configs_for_mutation:
                cfg_str = str(cfg) # Simple way to check for dict equality for uniqueness
                if cfg_str not in seen_configs_str:
                    unique_selected_skill_configs.append(cfg)
                    seen_configs_str.add(cfg_str)

            for selected_config in unique_selected_skill_configs:
                mutated_config = self.mutate_config(selected_config, "skill", all_current_agent_names) # Pass agent_type
                new_skill_agent_configs.append(mutated_config)
                # Attempt radical code generation based on the mutated config
                # This is now asynchronous.
                if random.random() < 0.05: # Reduced chance for demo
                    self._attempt_code_generation_for_evolution(mutated_config, current_tick)
                log(f"  - Skill Agent '{selected_config['name']}' selected and mutated for next generation.")
        else:
            log("MutationEngine: No Skill Agents assessed or selected for mutation based on fitness.", level="INFO")

        # --- START Rescue default skill lineages (before re-seeding) ---
        # This logic tries to keep an existing (but mutated) agent from a default lineage
        # if it wasn't selected by the fitness-weighted mutation process, especially if it had 0 executions.

        # `new_skill_agent_configs` contains configs of agents already chosen for mutation.
        # `assessed_skill_agents` contains all skill agents from the current generation with their metrics.

        for lineage_base_name in self.DEFAULT_SKILL_LINEAGE_BASES:
            is_lineage_represented_in_new_configs = any(
                config.get('lineage_id', '').startswith(lineage_base_name)
                for config in new_skill_agent_configs
            )

            if is_lineage_represented_in_new_configs:
                continue # This lineage is already covered by a mutated agent.

            # Lineage not represented. Try to rescue one from the current generation.
            candidates_for_rescue = [
                data for data in assessed_skill_agents # Use the full list of assessed skill agents
                if data['config'].get('lineage_id', '').startswith(lineage_base_name)
            ]

            if not candidates_for_rescue:
                log(f"MutationEngine: No candidates from current generation found for rescue in lineage '{lineage_base_name}'. Will rely on re-seeding if necessary.", level="WARNING")
                continue

            def rescue_priority_key(agent_data_dict):
                metrics = agent_data_dict['fitness_metrics'] # This is now a dict
                config = agent_data_dict['config']
                executions = metrics.get('executions', -1.0) # Default to -1 if not found
                fitness = metrics.get('fitness', 0.0)
                generation = config.get('generation', 0)

                if executions == 0:
                    return (0, -generation, -fitness) # Priority: 0 executions, younger, higher fitness
                elif executions > 0:
                    return (1, -fitness, -generation) # Priority: >0 executions, higher fitness, younger
                else: # executions < 0 (e.g., -1 if key was missing)
                    return (2, -fitness, -generation) # Lowest priority

            candidates_for_rescue.sort(key=rescue_priority_key)
            
            agent_to_rescue_data = candidates_for_rescue[0]
            agent_to_rescue_original_config = agent_to_rescue_data['config']
            agent_to_rescue_name = agent_to_rescue_original_config.get('name')
            agent_to_rescue_metrics = agent_to_rescue_data['fitness_metrics']

            log(f"MutationEngine: Attempting to rescue '{agent_to_rescue_name}' (Fitness: {agent_to_rescue_metrics.get('fitness', 0.0):.3f}, Execs: {agent_to_rescue_metrics.get('executions', 'N/A')}) for lineage '{lineage_base_name}'.", level="INFO")
            
            # Mutate the config of the rescued agent and add it to the next generation.
            mutated_rescued_config = self.mutate_config(agent_to_rescue_original_config, "skill", all_current_agent_names)
            
            # Add the mutated rescued agent to the list for the next generation.
            # We avoid complex replacement logic for now; this might slightly increase population
            # if many lineages need rescuing, but ensures survival.
            new_skill_agent_configs.append(mutated_rescued_config)
            log(f"MutationEngine: Rescued and added mutated '{mutated_rescued_config.get('name')}' for lineage '{lineage_base_name}' to next generation.", level="INFO")
        # --- END Rescue default skill lineages ---

        # --- START Ensure default skill lineages are represented in the next generation ---
        # Get lineage IDs of skill agents planned for the next generation
        current_new_skill_lineages = set()
        for cfg in new_skill_agent_configs:
            # lineage_id should be the base lineage, e.g., "skill_data_analysis"
            lineage_id = cfg.get('lineage_id')
            if not lineage_id and 'name' in cfg: 
                # Ensure we get the base lineage ID, consistent with how DEFAULT_SKILL_LINEAGE_BASES is populated
                lineage_id = cfg['name'].split('-gen')[0].split('_0')[0] 

            if lineage_id:
                current_new_skill_lineages.add(lineage_id)
        
        for default_skill_cfg in self.meta_agent.default_skill_agent_configs:
            # Ensure default_lineage_id is derived consistently with how
            # DEFAULT_SKILL_LINEAGE_BASES and lineage_id in new_skill_agent_configs are handled.
            default_lineage_id = default_skill_cfg.get('name').split('-gen')[0].split('_0')[0]
            if default_lineage_id not in current_new_skill_lineages:
                log(f"MutationEngine: Default skill lineage '{default_lineage_id}' not in next gen. Re-seeding from default config.", level="INFO")
                new_skill_agent_configs.append(copy.deepcopy(default_skill_cfg)) # Add a fresh copy
        # --- END Ensure default skill lineages are represented ---

        log(f"MutationEngine: Removing {len(self.meta_agent.task_agents) + len(self.meta_agent.skill_agents)} agents...")
        self.meta_agent.task_agents.clear()
        self.meta_agent.skill_agents.clear()

        for config in new_task_agent_configs:
            self.meta_agent.add_agent_from_config(config)
        
        for config in new_skill_agent_configs:
            self.meta_agent.add_agent_from_config(config)

        if not self.meta_agent.task_agents:
            log("MutationEngine: Task agent population extinct. Re-seeding default task agent.", level="WARNING")
            self.meta_agent.add_agent_from_config(copy.deepcopy(self.meta_agent.default_task_agent_config))

        if not self.meta_agent.skill_agents:
            log("MutationEngine: Skill agent population extinct. Re-seeding all default skill agents.", level="WARNING")
            for skill_config in self.meta_agent.default_skill_agent_configs:
                self.meta_agent.add_agent_from_config(copy.deepcopy(skill_config))

        log("MutationEngine: Assessment and mutation cycle finished.")

    def _attempt_code_generation_for_evolution(self, base_agent_config: Dict[str, Any], current_tick: int):
        """
        Initiates an asynchronous CodeGenAgent request to generate a new or evolved skill.
        """
        if not self.code_gen_agent:
            log("[MutationEngine] CodeGenAgent not available, skipping code generation attempt.", level="DEBUG")
            return

        agent_type = base_agent_config.get("agent_type", "unknown")
        original_description = base_agent_config.get("description", f"A {agent_type} agent with capabilities: {base_agent_config.get('capabilities', [])}")
        
        new_feature_ideas = ["perform advanced statistical calculations", "integrate with a calendar API", "parse complex data formats", "generate creative text summaries", "control a virtual robot arm"]
        added_feature_request = random.choice(new_feature_ideas)

        prompt_description = (
            f"Generate Python code for a new standalone skill module. This skill should be an evolution of, or inspired by, "
            f"a concept described as: '{original_description}'.\n"
            f"The key new functionality to incorporate is: '{added_feature_request}'.\n"
            f"The skill should be encapsulated in one or more Python functions or a class."
        )
        
        guidelines = (
            "The generated Python code should be functional and include docstrings. "
            "If it's a class, it should have an `execute(command_string)` method. "
            "If it's a function, ensure it's clearly named based on its primary new capability. "
            "Only output the raw Python code."
        )

        log(f"[MutationEngine] Attempting ASYNC code generation for evolved skill based on '{base_agent_config.get('name')}'. New feature: '{added_feature_request}'", level="INFO")
        
        request_id = self.code_gen_agent.write_new_capability(prompt_description, guidelines)

        if request_id:
            self.pending_code_generation_requests[request_id] = {
                "type": "skeleton_generation", # Mark this as a skeleton generation request
                "base_agent_name": base_agent_config.get("name"),
                "requested_feature": added_feature_request,
                "initiated_at_tick": current_tick,
                "timeout_at_tick": current_tick + self.code_gen_request_timeout_ticks,
                "request_id": request_id # Store the request_id for linking stub requests
            }
            log(f"[MutationEngine] Code generation request '{request_id}' sent for agent evolution based on '{base_agent_config.get('name')}'.", level="INFO")
        else:
            log(f"[MutationEngine] Failed to send code generation request for agent evolution based on '{base_agent_config.get('name')}'.", level="ERROR")

    def _analyze_code_for_stubs(self, code_string: str) -> List[Dict[str, Any]]:
        """
        Analyzes Python code string using AST to find function/method stubs
        that only contain a 'pass' statement or a docstring followed by 'pass'.
        Returns a list of dictionaries, each describing a stub.
        """
        stubs = []
        if not code_string:
            return stubs
        try:
            tree = ast.parse(code_string)
            
            def get_full_signature_from_node(node: ast.FunctionDef, parent_code: str) -> str:
                """
                Extracts the full signature line (def name(args):) from the AST node.
                Relies on ast.get_source_segment for accuracy.
                """
                try:
                    # Attempt to get the source segment for the function definition
                    # up to the colon. This is more robust for complex signatures.
                    # We need to find the end of the signature (the ':').
                    # The node.lineno and node.col_offset give the start of 'def'.
                    # node.end_lineno and node.end_col_offset give the end of the entire function.
                    
                    # Get the lines of the function
                    func_lines = ast.get_source_segment(parent_code, node).splitlines()
                    signature_line = ""
                    for line in func_lines:
                        stripped_line = line.strip()
                        if signature_line: # If we've started accumulating the signature
                            signature_line += " " + stripped_line # Add subsequent lines of a multi-line signature
                        else:
                            signature_line = stripped_line

                        if stripped_line.endswith(":"):
                            break # Found the end of the signature
                    
                    return signature_line if signature_line.startswith("def ") or signature_line.startswith("async def ") else f"def {node.name}(...): # Fallback"

                except Exception as e_sig:
                    log(f"[MutationEngine] Error getting source segment for signature of {node.name}: {e_sig}", level="WARN")
                    return f"def {node.name}(...): # Signature reconstruction fallback"

            def get_docstring_from_node(node: ast.FunctionDef) -> Optional[str]:
                return ast.get_docstring(node, clean=False) # clean=False preserves indentation for LLM

            for item in tree.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)): # Top-level functions or async functions
                    is_stub = False
                    # Check if body is just 'pass' or a docstring followed by 'pass'
                    if len(item.body) == 1 and isinstance(item.body[0], ast.Pass):
                        is_stub = True
                    elif len(item.body) >= 1 and isinstance(item.body[0], ast.Expr) and \
                         isinstance(item.body[0].value, (ast.Constant, ast.Str)) and \
                         (len(item.body) == 1 or (len(item.body) == 2 and isinstance(item.body[1], ast.Pass))):
                        # This handles docstring only, or docstring + pass
                        if len(item.body) == 2 and not isinstance(item.body[1], ast.Pass): # Docstring + something else not pass
                            is_stub = False
                        else: # Docstring only, or docstring + pass
                            is_stub = True 

                    if is_stub:
                        stubs.append({
                            "name": item.name,
                            "signature": get_full_signature_from_node(item, code_string),
                            "docstring": get_docstring_from_node(item),
                            "class_context_code": None, # No class context for top-level functions
                            "is_method": False,
                            "node_lineno": item.lineno # For later integration
                        })
                elif isinstance(item, ast.ClassDef):
                    class_source_segment = ast.get_source_segment(code_string, item) # Get source of the whole class
                    for sub_item in item.body:
                        if isinstance(sub_item, (ast.FunctionDef, ast.AsyncFunctionDef)): # Methods in class
                            is_stub = False
                            if len(sub_item.body) == 1 and isinstance(sub_item.body[0], ast.Pass):
                                is_stub = True
                            elif len(sub_item.body) >= 1 and isinstance(sub_item.body[0], ast.Expr) and \
                                 isinstance(sub_item.body[0].value, (ast.Constant, ast.Str)) and \
                                 (len(sub_item.body) == 1 or (len(sub_item.body) == 2 and isinstance(sub_item.body[1], ast.Pass))):
                                if len(sub_item.body) == 2 and not isinstance(sub_item.body[1], ast.Pass):
                                    is_stub = False
                                else:
                                    is_stub = True
                                
                            if is_stub:
                                stubs.append({
                                    "name": sub_item.name,
                                    "signature": get_full_signature_from_node(sub_item, class_source_segment or code_string),
                                    "docstring": get_docstring_from_node(sub_item),
                                    "class_context_code": class_source_segment,
                                    "is_method": True,
                                    "node_lineno": sub_item.lineno # For later integration
                                })
        except SyntaxError as e:
            log(f"[MutationEngine] Syntax error analyzing code for stubs: {e}. Code: {code_string[:200]}", level="ERROR")
        except Exception as e:
            log(f"[MutationEngine] Error analyzing code for stubs: {e}. Code: {code_string[:200]}", level="ERROR", exc_info=True)
        return stubs

    def _initiate_stub_implementation_requests(self, skeleton_code: str, stubs_info: List[Dict[str, Any]], original_request_details: Dict[str, Any], current_tick: int):
        """Initiates asynchronous LLM calls to implement identified stubs."""
        if not self.code_gen_agent or not stubs_info:
            return

        overall_skill_goal = f"Evolved skill based on {original_request_details.get('base_agent_name', 'unknown_base')}, new feature: {original_request_details.get('requested_feature', 'unknown_feature')}"

        for stub in stubs_info:
            request_id = self.code_gen_agent.implement_function_body_async(
                function_signature=stub["signature"],
                class_context=stub.get("class_context_code"),
                docstring=stub.get("docstring"),
                overall_skill_goal=overall_skill_goal
            )
            if request_id:
                self.pending_code_generation_requests[request_id] = {
                    "type": "stub_implementation",
                    "original_skeleton_code": skeleton_code, # Store the skeleton this stub belongs to
                    "stub_signature": stub["signature"], # Identify which stub this is for
                    "stub_name": stub["name"],
                    "is_method": stub["is_method"],
                    "class_context_code_if_method": stub.get("class_context_code"),
                    "node_lineno": stub.get("node_lineno"), # Store line number for AST integration
                    "base_agent_name": original_request_details.get("base_agent_name"),
                    "initiated_at_tick": current_tick,
                    "timeout_at_tick": current_tick + self.code_gen_request_timeout_ticks,
                    "parent_request_id": original_request_details.get("request_id") # Link to the skeleton request
                }
                log(f"[MutationEngine] Stub implementation request '{request_id}' sent for '{stub['name']}'.", level="INFO")
            else:
                log(f"[MutationEngine] Failed to send stub implementation request for '{stub['name']}'.", level="ERROR")

    def _integrate_method_body_ast(self, skeleton_code: str, target_func_name: str, target_func_lineno: int, new_body_code_str: str) -> str:
        """
        Integrates the new_body_code_str into the skeleton_code for a specific function
        identified by name and line number, using AST manipulation.
        """
        log(f"[MutationEngine] AST Integration: Attempting to integrate body for '{target_func_name}' at line {target_func_lineno}.", level="DEBUG")
        try:
            skeleton_ast = ast.parse(skeleton_code)
            
            # The new_body_code_str is just the *body*, not a full function.
            # We need to parse it as if it were inside a dummy function to get its AST nodes.
            # Ensure it's correctly indented if it's multi-line.
            # A common way is to wrap it in a dummy function for parsing.
            # The LLM is prompted to provide the body already indented if it's for a method.
            # If it's not indented, we might need to adjust.
            # For now, assume the LLM provides the body correctly formatted.
            
            # A simple way to parse a block of statements:
            # Wrap in a dummy function, parse, then extract the body.
            # Ensure the body string doesn't have leading/trailing newlines that mess up parsing.
            new_body_code_str = new_body_code_str.strip()
            if not new_body_code_str: # If LLM returned empty body
                log(f"[MutationEngine] AST Integration: LLM returned empty body for '{target_func_name}'. No changes made.", level="WARN")
                return skeleton_code

            # Create a dummy function string for parsing the body
            # The indentation of new_body_code_str matters here.
            # If the LLM provides it unindented:
            indented_new_body_lines = [f"    {line}" for line in new_body_code_str.splitlines()]
            dummy_func_for_body_parsing = f"def __dummy_func_for_body_parsing__():\n" + "\n".join(indented_new_body_lines)
            
            try:
                body_ast_module = ast.parse(dummy_func_for_body_parsing)
                if not body_ast_module.body or not isinstance(body_ast_module.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
                    raise ValueError("Could not parse new body into a function definition.")
                new_body_nodes = body_ast_module.body[0].body
            except SyntaxError as se:
                log(f"[MutationEngine] AST Integration: Syntax error parsing new body for '{target_func_name}': {se}. Body: \n{new_body_code_str}", level="ERROR")
                return skeleton_code # Return original on error

            target_node_found = False
            for node in ast.walk(skeleton_ast):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                   node.name == target_func_name and \
                   node.lineno == target_func_lineno:
                    
                    # Preserve docstring if it exists and new body doesn't have one
                    original_docstring_node = None
                    if node.body and isinstance(node.body[0], ast.Expr) and \
                       isinstance(node.body[0].value, (ast.Constant, ast.Str)):
                        original_docstring_node = node.body[0]

                    new_body_has_docstring = False
                    if new_body_nodes and isinstance(new_body_nodes[0], ast.Expr) and \
                       isinstance(new_body_nodes[0].value, (ast.Constant, ast.Str)):
                        new_body_has_docstring = True

                    final_body_nodes = []
                    if original_docstring_node and not new_body_has_docstring:
                        final_body_nodes.append(original_docstring_node)
                    
                    final_body_nodes.extend(new_body_nodes)
                    
                    node.body = final_body_nodes
                    target_node_found = True
                    log(f"[MutationEngine] AST Integration: Successfully replaced body for '{target_func_name}' at line {target_func_lineno}.", level="INFO")
                    break
            
            if not target_node_found:
                log(f"[MutationEngine] AST Integration: Could not find target function '{target_func_name}' at line {target_func_lineno} in skeleton AST.", level="ERROR")
                return skeleton_code

            if sys.version_info >= (3, 9):
                return ast.unparse(skeleton_ast)
            else:
                import astor # Requires astor to be installed for Python < 3.9
                return astor.to_source(skeleton_ast)

        except Exception as e:
            log(f"[MutationEngine] AST Integration: Error integrating method body for '{target_func_name}': {e}", level="ERROR", exc_info=True)
            return skeleton_code # Return original on error

    def _handle_pending_code_generation_responses(self):
        """Checks for and processes responses to asynchronous code generation requests."""
        if not self.pending_code_generation_requests:
            return

        current_tick = self.context.get_tick()
        completed_request_ids = []

        for req_id, req_details in list(self.pending_code_generation_requests.items()):
            if current_tick >= req_details["timeout_at_tick"]:
                log(f"[MutationEngine] Code generation request '{req_id}' for '{req_details['base_agent_name']}' timed out.", level="WARN")
                completed_request_ids.append(req_id)
                continue

            llm_response_data = self.context.get_llm_response_if_ready(req_id)
            if llm_response_data and llm_response_data.get("status") != "pending":
                raw_content = llm_response_data.get("response")
                is_stub_implementation_response = req_details.get("type") == "stub_implementation"

                if llm_response_data.get("status") == "completed" and raw_content:
                    # Use the static method from LLMInterface for parsing
                    from agents.code_gen_agent import LLMInterface # Ensure import
                    parsed_content = LLMInterface.parse_llm_code_output(raw_content)

                    if is_stub_implementation_response:
                        log(f"[MutationEngine] Received Implemented Body for stub '{req_details['stub_name']}' (ReqID '{req_id}'):\n{parsed_content}", level="INFO")
                        original_skeleton = req_details.get("original_skeleton_code")
                        
                        refined_code = self._integrate_method_body_ast(
                            skeleton_code=original_skeleton,
                            target_func_name=req_details["stub_name"],
                            target_func_lineno=req_details["node_lineno"],
                            new_body_code_str=parsed_content
                        )
                        log(f"[MutationEngine] Code after attempting AST integration for stub '{req_details['stub_name']}':\n{refined_code}", level="DEBUG")
                        
                        # TODO: Update the 'original_skeleton_code' for the parent_request_id (if managing multi-stub skills)
                        # For now, we log and assume this refined_code is the one to potentially validate/test.
                        # If all stubs for a parent_request_id are done, then the parent request is truly complete.
                        log(f"Further refined code for {req_details['base_agent_name']} (feature: {req_details.get('requested_feature', 'N/A')}):\n{refined_code}", level="INFO")
                        # Here, you'd eventually trigger the validation/testing/integration of `refined_code`.

                    else: # It's an initial skeleton
                        log(f"[MutationEngine] Received Skeleton Code for ReqID '{req_id}' (Base: {req_details['base_agent_name']}, Feature: {req_details['requested_feature']}):\n{parsed_content}", level="INFO")
                        stubs = self._analyze_code_for_stubs(parsed_content)
                        if stubs:
                            log(f"[MutationEngine] Found {len(stubs)} stubs in skeleton for '{req_details['base_agent_name']}'. Initiating implementation requests.", level="INFO")
                            self._initiate_stub_implementation_requests(parsed_content, stubs, req_details, current_tick)
                        else:
                            log(f"[MutationEngine] No stubs found in skeleton for '{req_details['base_agent_name']}'. Proceeding with integration of skeleton.", level="INFO")
                            # TODO: Implement validation, testing, and integration of 'parsed_content' (the complete skeleton)
                elif llm_response_data.get("status") == "error":
                    log(f"[MutationEngine] Code generation request '{req_id}' for '{req_details['base_agent_name']}' failed. Error: {llm_response_data.get('error_details')}", level="ERROR")
                
                completed_request_ids.append(req_id) # Mark this specific request (skeleton or stub) as processed for this cycle

        for req_id in completed_request_ids:
            self.pending_code_generation_requests.pop(req_id, None)

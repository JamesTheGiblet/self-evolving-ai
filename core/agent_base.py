# c:/Users/gilbe/Desktop/self-evolving-ai/core/agent_base.py

import copy
import random
from typing import Dict, Any, Optional, List
from utils.logger import log
import config # For accessing BASE_TICK_ENERGY_COST and DEFAULT_INITIAL_ENERGY
from engine.communication_bus import CommunicationBus # Assuming this path
from memory.knowledge_base import KnowledgeBase # Assuming this path
from core.context_manager import ContextManager # Assuming this path
from engine.identity_engine import IdentityEngine # Forward declaration or import

class BaseAgent:
    # Define known behavior modes at the class level
    BEHAVIOR_MODES = ["explore", "observer", "reactive"]

    def __init__(self,
                 name: str,
                 context_manager: ContextManager,
                 knowledge_base: KnowledgeBase,
                 communication_bus: CommunicationBus,
                 agent_type: str = "base",
                 capabilities: Optional[List[str]] = None,
                 capability_params: Optional[Dict[str, Any]] = None,
                 initial_energy: float = config.DEFAULT_INITIAL_ENERGY, # Use config default
                 max_age: Optional[int] = None,
                 lineage_id: Optional[str] = None,
                 generation: int = 0,
                 behavior_mode: str = "observer", # Added behavior_mode
                 agent_id: Optional[str] = None, # Added agent_id parameter
                 identity_engine: Optional[IdentityEngine] = None): 
        self.name = name
        self.context_manager = context_manager
        self.knowledge_base = knowledge_base
        self.communication_bus = communication_bus
        self.agent_type = agent_type
        self.capabilities = capabilities if capabilities is not None else []
        self.capability_params = capability_params if capability_params is not None else {}
        self.id = agent_id if agent_id is not None else name # Use provided agent_id or default to name
        
        self.energy = float(initial_energy)
        self.max_age = max_age if max_age is not None else config.DEFAULT_MAX_AGENT_AGE
        self.age = 0
        self.lineage_id = lineage_id if lineage_id else name # Default lineage to name if not provided
        self.generation = generation
        self.behavior_mode = behavior_mode # Store behavior_mode
        
        self.state: Dict[str, Any] = {"status": "active"} # General purpose state dictionary
        self.state["lineage_id"] = self.lineage_id # Ensure lineage_id is in the state dict
        self.base_tick_energy_cost = float(config.BASE_TICK_ENERGY_COST)
        
        self.agent_info_map: Dict[str, Any] = {} # For storing info about other agents

        log(f"[{self.name}] BaseAgent initialized. Type: {self.agent_type}, Lineage: {self.lineage_id}, Gen: {self.generation}, Initial Energy: {self.energy:.2f}, Max Age: {self.max_age}")

    def _process_communication(self):
        """
        Retrieves and processes messages from the communication bus.
        Delegates message handling to _handle_message.
        """
        if not self.communication_bus:
            log(f"[{self.name}] No communication bus available.", level="WARNING")
            return

        # Call the new method in CommunicationBus
        messages = self.communication_bus.get_messages_for_agent(self.name) 
        if not messages:
            return

        for msg_envelope in messages:
            msg_id = msg_envelope['id']
            sender_id = msg_envelope['sender']
            message_content = msg_envelope['content']

            log(f"[{self.name}] Received message ID {msg_id} from {sender_id}: {str(message_content)[:150]}", level="TRACE")

            if not self._handle_message(sender_id, message_content):
                log(f"[{self.name}] Message from {sender_id} not specifically handled: {str(message_content)[:100]}", level="DEBUG")
            
            self.communication_bus.mark_message_processed(msg_id)

    def _handle_message(self, sender_id: str, message_content: Dict[str, Any]) -> bool:
        """
        Handles a received message. Subclasses should override this to process
        specific message types relevant to them.

        Args:
            sender_id: The ID of the agent that sent the message.
            message_content: The content of the message.

        Returns:
            True if the message was handled by this method (or an override), False otherwise.
        """
        # Check for specific message types handled by the base class
        action = message_content.get('action')
        message_type = message_content.get('type') # Check for the new 'type' key

        # Example: Basic handling for a generic broadcast or system message
        if action == "system_info_broadcast":
            log(f"[{self.name}] BaseHandler: Received system info broadcast from {sender_id}: {message_content.get('data')}", level="INFO")
            return True

        # Handle generic broadcasts identified by the new 'type' key
        if message_type == "broadcast":
            log(f"[{self.name}] BaseHandler: Received generic broadcast from {sender_id}. Original content: {str(message_content.get('original_content'))[:100]}...", level="DEBUG")
            return True # Indicate message was handled (as a recognized broadcast type)
        
        return False # Not handled by the base class's generic handler

    def run_cycle(self) -> bool:
        """
        Core operational cycle for the agent. Handles aging, communication,
        energy consumption, and status checks.
        Returns True if the agent can proceed with its actions, False otherwise.
        """
        current_tick = self.context_manager.get_tick()
        log(f"[{self.name} Tick:{current_tick}] Starting run_cycle. Age: {self.age}, Energy: {self.energy:.2f}, Status: {self.state['status']}", level="TRACE")

        self._process_communication()
        self.age += 1

        if self.state["status"] == "exhausted":
            log(f"[{self.name} Tick:{current_tick}] Is exhausted. Cannot perform actions.", level="DEBUG")
            return False
        
        if self.state["status"] == "retired":
            log(f"[{self.name} Tick:{current_tick}] Is retired. Cannot perform actions.", level="DEBUG")
            return False

        # Energy consumption
        if self.base_tick_energy_cost > 0:
            previous_energy = self.energy
            self.energy = max(0.0, self.energy - self.base_tick_energy_cost)
            energy_consumed_this_tick = previous_energy - self.energy
            log(f"[{self.name} Tick:{current_tick}] Consumed {energy_consumed_this_tick:.2f} base energy. New level: {self.energy:.2f}. Cost per tick: {self.base_tick_energy_cost}", level="TRACE")

            if self.energy == 0.0 and self.state["status"] != "exhausted":
                self.state["status"] = "exhausted"
                log(f"[{self.name} Tick:{current_tick}] Has run out of energy and is now exhausted.", level="WARNING")
                # Optionally, publish an event about becoming exhausted
                # self.communication_bus.publish("agent_status_update", {"agent_id": self.name, "status": "exhausted", "tick": current_tick})
                return False # Cannot proceed further this tick

        # Max age check
        if self.max_age is not None and self.age > self.max_age:
            if self.state["status"] != "retired":
                log(f"[{self.name} Tick:{current_tick}] Reached max age ({self.max_age}). Retiring.", level="INFO")
                self.state["status"] = "retired"
            return False # Indicate agent should be removed or stopped
            
        return True # Agent is active and can proceed

    def _get_rl_state_representation(self) -> tuple:
        """Placeholder for RL state representation."""
        # More sophisticated state might include energy level, current goal type, etc.
        energy_discrete = int(self.energy / 20) # Example discretization
        return (self.agent_type, len(self.capabilities), self.state.get("status"), energy_discrete)

    def _update_q_value(self, state_tuple, action, reward, next_state_tuple):
        """Placeholder for Q-value update. To be implemented by agents with RL."""
        if hasattr(self, 'rl_system') and self.rl_system:
            # Assuming rl_system.update_q_value takes available_next_actions
            # This part needs to be fleshed out based on how available_next_actions is determined
            available_next_actions = self.available_capabilities() if hasattr(self, 'available_capabilities') else self.capabilities
            self.rl_system.update_q_value(state_tuple, action, reward, next_state_tuple, available_next_actions, self.name)
        else:
            log(f"[{self.name}] Attempted to update Q-value, but no RL system found.", level="TRACE")


    def _execute_capability(self, capability_name: str, context: ContextManager, knowledge: KnowledgeBase, all_agent_names_in_system: List[str], **kwargs: Any) -> Dict[str, Any]:
        """
        Executes a specified capability by dispatching to the central capability executor.

        This method resolves capability parameters by merging global defaults from
        the CAPABILITY_REGISTRY with agent-specific overrides (self.capability_params).
        It then calls `core.capability_executor.execute_capability_by_name`
        to perform the actual execution.

        Args:
            capability_name: The name of the capability to execute.
            context: The current system context (ContextManager).
            knowledge: The agent's knowledge base (KnowledgeBase).
            all_agent_names_in_system: A list of all agent names currently in the system.
            **kwargs: Additional inputs required by the capability (cap_inputs).
                      These are typically prepared by a CapabilityInputPreparer.

        Returns:
            A dictionary containing the result of the capability execution.
        """
        # Local imports are used here to prevent potential circular dependencies
        # if capability_executor or capability_registry were to import agent_base at the module level.
        from core.capability_executor import execute_capability_by_name
        from core.capability_registry import CAPABILITY_REGISTRY as GLOBAL_CAPABILITY_REGISTRY
        
        # Determine parameters to be used for this capability execution.
        # Start with global default parameters defined in the capability registry.
        params_used: Dict[str, Any] = {}
        if capability_name in GLOBAL_CAPABILITY_REGISTRY:
            # .copy() creates a shallow copy, which is generally fine for flat param dicts.
            params_used.update(GLOBAL_CAPABILITY_REGISTRY[capability_name].get("params", {}).copy())

        # Apply agent-specific parameter overrides for this capability.
        if capability_name in self.capability_params:
            params_used.update(self.capability_params[capability_name])

        # The **kwargs received are the specific inputs for this capability execution.
        cap_inputs: Dict[str, Any] = kwargs

        # If cap_inputs contains 'params_override', apply them to params_used.
        # This is specifically for sequence_executor_v1 passing step-specific param overrides.
        if "params_override" in cap_inputs and isinstance(cap_inputs["params_override"], dict):
            params_used.update(cap_inputs["params_override"])

        log(f"[{self.name}] Dispatching execution for capability '{capability_name}'. Params Used: {params_used}, Cap Inputs: {str(cap_inputs)[:200]}...", level="DEBUG")
        
        return execute_capability_by_name(
            capability_name=capability_name,
            agent=self,
            params_used=params_used,
            cap_inputs=cap_inputs,
            knowledge=knowledge,
            context=context,
            all_agent_names_in_system=all_agent_names_in_system
        )

    def get_fitness(self) -> Dict[str, float]:
        """
        Calculates a basic fitness score for the agent.
        Subclasses should override this for more specific fitness calculations.
        Returns a dictionary with "fitness", "executions", and "average_reward".
        """
        # Default base fitness is low, assuming the base agent doesn't perform complex tasks.
        # This provides a fallback if subclasses call super().get_fitness()
        # without BaseAgent having its own complex calculation.
        return {"fitness": 0.01, "executions": 0.0, "average_reward": 0.0}

    # Placeholder for a method that might be used by sequence_executor_v1 for smarter target resolution
    def find_best_skill_agent_for_action(self, skill_action: str, preferred_target_id: Optional[str] = None) -> Optional[str]:
        # This method is more relevant for TaskAgent which has the agent_info_map.
        # BaseAgent provides a fallback.
        log(f"[{self.name}] BaseAgent.find_best_skill_agent_for_action called for '{skill_action}'. This should ideally be handled by TaskAgent.", level="WARNING")
        
        # Basic implementation: check self.agent_info_map if populated (e.g., by a subclass)
        if not self.agent_info_map:
            log(f"[{self.name}] No agent_info_map available in BaseAgent to find skill agent.", level="DEBUG")
            return None

        from core.skill_definitions import SKILL_CAPABILITY_MAPPING # Local import

        available_skill_agents_info = {
            name: info for name, info in self.agent_info_map.items() 
            if info.get("agent_type") == "skill" and info.get("is_active", True)
        }

        suitable_agents = []
        for sa_name, sa_info in available_skill_agents_info.items():
            sa_configured_caps = sa_info.get("capabilities", [])
            performable_by_sa = []
            for conf_cap in sa_configured_caps:
                performable_by_sa.extend(SKILL_CAPABILITY_MAPPING.get(conf_cap, []))
            if skill_action in set(performable_by_sa):
                suitable_agents.append(sa_name)
        
        if preferred_target_id and preferred_target_id in suitable_agents:
            return preferred_target_id
        if suitable_agents:
            return random.choice(suitable_agents)
        return None

    def get_config(self) -> dict:
        """Returns the agent's current configuration."""
        return {
            "name": self.name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities[:], # Shallow copy
            "capability_params": copy.deepcopy(self.capability_params),
            "initial_energy": self.energy, # Current energy becomes initial for next gen if this config is used
            "max_age": self.max_age,
            "age": self.age,
            "lineage_id": self.lineage_id,
            "generation": self.generation,
            "state": copy.deepcopy(self.state), # Include current state
            "behavior_mode": self.behavior_mode # Include behavior_mode
        }

    def has_capability(self, capability_name: str) -> bool:
        """Checks if the agent possesses a given capability."""
        return capability_name in self.capabilities

    def available_capabilities(self) -> List[str]:
        """Returns a list of capabilities the agent can currently execute."""
        # This could be more dynamic in the future, e.g., based on energy or cooldowns
        return self.capabilities[:]

    def _prepare_capability_inputs(self,
                                   capability_name: str,
                                   base_inputs_override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares inputs for a sub-capability, typically within a sequence.

        For sequence execution, `base_inputs_override` already contains
        resolved inputs from the sequence definition (e.g., from 'inputs' field of a step,
        resolved placeholders, or outputs passed from a previous step).
        This method primarily passes through these overrides. It can be extended
        to augment with standard contextual information if needed for all sub-capability calls.

        Args:
            capability_name (str): The name of the sub-capability.
            base_inputs_override (Dict[str, Any]): The inputs already prepared by the
                                                 calling context (e.g., sequence executor).

        Returns:
            Dict[str, Any]: The dictionary of inputs to be passed as **kwargs to the sub-capability.
        """
        final_inputs = base_inputs_override.copy()
        log(f"[{self.name}] BaseAgent._prepare_capability_inputs for '{capability_name}'. Base overrides: {str(base_inputs_override)[:100]}. Returning: {str(final_inputs)[:100]}", level="TRACE")
        return final_inputs

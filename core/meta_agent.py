# core/meta_agent.py
import json
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import uuid # Add if not already imported
from core import context_manager
from core.context_manager import ContextManager
from core.skill_agent import SkillAgent
from core.task_router import TaskRouter
from memory.knowledge_base import KnowledgeBase
from engine.communication_bus import CommunicationBus
from utils.logger import log # Explicitly import log
from core.task_agent import TaskAgent # Import TaskAgent for instantiation
from utils import local_llm_connector
import config
import copy # For deepcopy

if TYPE_CHECKING: # TYPE_CHECKING is True for static analysis
    from .task_router import TaskRouter
    # from .skill_agent import SkillAgent # Already imported above
    from engine.identity_engine import IdentityEngine
    from agents.code_gen_agent import LLMInterface # For type hinting
    from agents.code_gen_agent import CodeGenAgent # If MetaAgent manages CodeGenAgent lifecycle


class MetaAgent: # Ensure it inherits from BaseAgent for message handling
    AGENT_TYPE = "meta" # Class attribute for agent type

    def __init__(self, 
                 context: ContextManager, 
                 knowledge: KnowledgeBase, 
                 communication_bus: CommunicationBus, 
                 skill_agents: List['SkillAgent'],
                 identity_engine: 'IdentityEngine', # Accept IdentityEngine instance
                 default_task_agent_config: Dict[str, Any],  # Added
                 default_skill_agent_configs: List[Dict[str, Any]],
                 code_gen_agent: Optional['CodeGenAgent'] = None, # Optional CodeGenAgent
                 general_llm_interface: Optional['LLMInterface'] = None, # Added
                 initial_task_agents: int = 1): # Added to control initial task agents
        self.name = "MetaAgent" # Added name attribute

        self.context = context
        self.knowledge = knowledge
        self.communication_bus = communication_bus

        # Task agents will be added from config or by mutation engine
        self.task_agents: List[TaskAgent] = [] 
        
        # Skill agents provided at init are the initial population
        self.skill_agents: List[SkillAgent] = skill_agents 
        
        # Combined list for convenience, will be updated when agents are added/removed
        self.agents: List[Any] = list(self.task_agents) + list(self.skill_agents) 
        
        if self.communication_bus:
            self.communication_bus.register_agent(self.name) # Register MetaAgent by its name
            log(f"MetaAgent '{self.name}' initialized and registered on communication bus.", level="INFO")

        self.identity_engine = identity_engine # Use the passed IdentityEngine instance
        self.code_gen_agent = code_gen_agent # Store CodeGenAgent if provided
        self.general_llm_interface = general_llm_interface # Store general LLM interface
        
        self.default_task_agent_config = default_task_agent_config
        self.default_skill_agent_configs = default_skill_agent_configs # Store the passed list
        
        # Store default skill configurations in a dictionary for easy lookup by lineage_id.
        # These default_skill_agent_configs from main.py contain the actual skill_tool instances.
        self.default_skill_configs_by_lineage: Dict[str, Dict[str, Any]] = {}
        for cfg_item in default_skill_agent_configs: # Renamed cfg to cfg_item for clarity
            lineage = cfg_item.get("lineage_id")
            if lineage:
                # Original problematic line:
                # self.default_skill_configs_by_lineage[lineage] = copy.deepcopy(cfg_item)
                
                # Create a new dictionary, selectively deepcopying items.
                # The 'skill_tool' instance itself will not be deepcopied to avoid pickling errors
                # with objects like thread locks held by shared components (KB, CommBus, ContextManager).
                new_config_for_lineage = {}
                skill_tool_instance_to_preserve = None

                for key, value in cfg_item.items():
                    if key == "skill_tool":
                        skill_tool_instance_to_preserve = value # Preserve the original instance
                    else:
                        new_config_for_lineage[key] = copy.deepcopy(value) # Deepcopy other items
                
                if skill_tool_instance_to_preserve is not None: # Should always be true if cfg_item is valid
                    new_config_for_lineage["skill_tool"] = skill_tool_instance_to_preserve
                
                self.default_skill_configs_by_lineage[lineage] = new_config_for_lineage
            else:
                log(f"MetaAgent Init: Default skill config missing 'lineage_id'. Config: {cfg_item}", level="WARN")

        self.task_router: Optional['TaskRouter'] = None
        log(f"MetaAgent initialized. Initial skill agents: {len(self.skill_agents)}. Default skill configs by lineage: {len(self.default_skill_configs_by_lineage)}.", level="INFO")

        # Dynamic registry for skill actions -> list of agent names providing that action
        self.skill_action_registry: Dict[str, List[str]] = {}
        self._update_skill_action_registry() # Initial population
        
        # To store received service advertisements
        self.service_advertisements: Dict[str, Dict[str, Any]] = {} # agent_id -> advertisement_payload

        # Initialize initial TaskAgents
        for i in range(initial_task_agents):
            self._provision_initial_task_agent(i)


    def set_task_router(self, task_router: 'TaskRouter'):
        self.task_router = task_router
        log("TaskRouter has been set for MetaAgent.", level="INFO")

    def get_skill_agents(self) -> List['SkillAgent']: # Method for main.py to get skill_agents for TaskRouter
        return self.skill_agents

    def handle_user_request(self, user_request_text: str) -> str:
        log(f"[MetaAgent] Handling user request: '{user_request_text}'", level="INFO")
        if not self.task_router:
            log("[MetaAgent] TaskRouter not set. Cannot process request via router.", level="ERROR")
            return self._fallback_to_general_llm(user_request_text, "TaskRouter not available.")

        skill_name, command_name, args, explanation = self.task_router.route_request(user_request_text)

        if skill_name and command_name:
            target_skill_agent = None
            for agent in self.skill_agents:
                # Skill agents are named like "skill_calendar_ops_0"
                # TaskRouter's skill_name is "Calendar"
                # We need to match based on the skill_tool's name or a derived lineage.
                # For now, let's assume TaskRouter returns the agent's direct name if it can.
                # If TaskRouter returns the skill_tool's class name (e.g., "Calendar"),
                # we need to match against agent.skill_tool.skill_name or similar.
                
                # Option 1: TaskRouter returns the SkillAgent's unique name (e.g., "skill_calendar_ops_0")
                # if agent.name == skill_name: # This would work if TaskRouter returns the agent's unique name

                # Option 2: TaskRouter returns the SkillTool's class name (e.g., "Calendar")
                # We need to check if the agent's skill_tool matches this.
                if hasattr(agent, 'skill_tool') and agent.skill_tool and \
                   hasattr(agent.skill_tool, 'skill_name') and agent.skill_tool.skill_name == skill_name:
                    target_skill_agent = agent
                    break
            
            if target_skill_agent:
                # Reconstruct the command string for the skill agent's execute method
                # BaseSkillTool.execute expects a single command string.
                command_parts = [command_name]
                if args: # args is a list of strings
                    command_parts.extend(args)
                
                command_str_for_skill = " ".join(command_parts)
                 # If args might contain spaces and need quoting, shlex.join would be better here,
                 # but BaseSkillTool.execute uses shlex.split, so simple join is fine if args are simple.
                 # For robustness with args containing spaces:
                 # import shlex
                 # command_str_for_skill = shlex.join(command_parts)

                log(f"[MetaAgent] Executing routed command on {target_skill_agent.name} (Skill: {skill_name}): '{command_str_for_skill}'", level="INFO")
                # SkillAgent.execute_skill_action is the method that takes the command string.
                # It's called internally by SkillAgent when it receives a message.
                # For MetaAgent to directly call it, it would need to simulate that message or
                # call a more direct execution path if available.
                # For now, let's assume SkillAgent has a direct `execute` method that maps to its tool.
                # This depends on SkillAgent's interface.
                # If SkillAgent.execute() is the intended public method:
                # result_json_str = target_skill_agent.execute(command_str_for_skill)
                
                # If we need to use the more detailed execute_skill_action:
                # This requires knowing the invoking_agent_id and task_id.
                # For a direct user request, MetaAgent can be the invoking_agent_id.
                task_id_for_direct_request = f"meta_direct_{uuid.uuid4().hex[:8]}"
                result_dict = target_skill_agent.execute_skill_action(
                    skill_command_str=command_str_for_skill,
                    params={}, # Params are already in command_str_for_skill for BaseSkillTool
                    invoking_agent_id=self.name,
                    task_id=task_id_for_direct_request
                )
                # execute_skill_action returns a dict, convert to JSON string if needed by caller
                result_json_str = json.dumps(result_dict)

                log(f"[MetaAgent] Result from {skill_name}: {result_json_str[:200]}...", level="INFO")
                return result_json_str # Return the JSON string from the skill
            else:
                log(f"[MetaAgent] TaskRouter suggested skill '{skill_name}', but no such SkillAgent found.", level="ERROR")
                return self._fallback_to_general_llm(user_request_text, f"Routed skill '{skill_name}' not found.")
        else:
            log(f"[MetaAgent] No specific skill routed for '{user_request_text}'. Reason: {explanation}. Using general LLM.", level="INFO")
            return self._fallback_to_general_llm(user_request_text, explanation)

    def _fallback_to_general_llm(self, user_request_text: str, reason: str) -> str:
        # This is a simplified fallback. You'd likely have more sophisticated LLM interaction.
        log(f"[MetaAgent] Falling back to general LLM for: '{user_request_text}'. Reason: {reason}", level="INFO")
        response_content = local_llm_connector.call_local_llm_api(
            [{"role": "user", "content": f"User request: {user_request_text}\nReason for direct LLM: {reason}"}],
            model_name=config.DEFAULT_LLM_MODEL
        )
        return response_content if response_content else "LLM fallback failed to produce a response."

    def receive_user_goal(self, goal_description: str):
        # This is where the MetaAgent would start processing a new goal,
        # potentially using handle_user_request or a more complex planning mechanism.
        log(f"[MetaAgent] Received new user goal: {goal_description}", level="INFO")
        
        # Option 1: Try to route it like a direct request
        # response = self.handle_user_request(goal_description)
        # log(f"[MetaAgent] Response to user goal '{goal_description}': {response[:200]}...", level="INFO")

        # Option 2: Assign it to a TaskAgent
        # Find an idle or suitable TaskAgent
        target_task_agent = None
        if self.task_agents:
            # Simple strategy: pick the first one or one with least load (if trackable)
            target_task_agent = self.task_agents[0] 
        
        if target_task_agent:
            log(f"[MetaAgent] Assigning user goal '{goal_description}' to TaskAgent '{target_task_agent.name}'.", level="INFO")
            # TaskAgent needs a method to receive and process such goals.
            # Example: target_task_agent.set_goal({"type": "user_defined_goal", "details": {"description": goal_description}})
            if hasattr(target_task_agent, 'set_goal'):
                target_task_agent.set_goal({"type": "user_defined_goal", "details": {"description": goal_description}})
            else:
                log(f"[MetaAgent] TaskAgent '{target_task_agent.name}' does not have 'set_goal' method. Cannot assign goal.", level="ERROR")
                # Fallback or error handling
        else:
            log("[MetaAgent] No TaskAgents available to handle the user goal. Goal not assigned.", level="WARN")
            # Fallback or error handling

    def run_agents(self):
        """Runs the operational cycle for all managed agents (Task and Skill)."""
        self._update_skill_action_registry() # Update the registry based on current skill agents
        self._process_meta_agent_messages() # Process messages for MetaAgent actions

        current_tick = self.context.get_tick()
        log(f"[{self.name} Tick:{current_tick}] Running all agents. Task Agents: {len(self.task_agents)}, Skill Agents: {len(self.skill_agents)}", level="DEBUG")

        # Prepare data that might be needed by agents during their run
        all_agent_names = self.get_all_agent_names()
        
        agent_info_map: Dict[str, Dict[str, Any]] = {}
        for agent_instance in self.agents: 
            if hasattr(agent_instance, 'get_config'):
                agent_config = agent_instance.get_config()
                agent_info_map[agent_instance.name] = {
                    "agent_type": agent_instance.agent_type,
                    "name": agent_instance.name,
                    "generation": agent_instance.generation,
                    "lineage_id": agent_instance.lineage_id,
                    "capabilities": agent_instance.capabilities[:], 
                    "is_active": agent_config.get("state", {}).get("status") == "active",
                    # Add other relevant info from agent_config if needed
                }
            else: # Fallback for agents that might not have get_config (should not happen for BaseAgent derivatives)
                 agent_info_map[agent_instance.name] = {
                    "agent_type": getattr(agent_instance, 'agent_type', "unknown"),
                    "name": getattr(agent_instance, 'name', "UnknownAgent"),
                    "is_active": True 
                 }

        for task_agent in self.task_agents:
            try:
                task_agent.run(
                    context=self.context, 
                    knowledge=self.knowledge, 
                    all_agent_names_in_system=all_agent_names,
                    agent_info_map=agent_info_map,
                    skill_action_registry=self.skill_action_registry # Pass the dynamic registry
                )
            except Exception as e:
                log(f"Error running TaskAgent {task_agent.name}: {e}", level="ERROR", exc_info=True)

        for skill_agent in self.skill_agents:
            try:
                skill_agent.run(
                    context=self.context, 
                    knowledge=self.knowledge,
                    all_agent_names_in_system=all_agent_names,
                    agent_info_map=agent_info_map
                ) 
            except Exception as e:
                log(f"Error running SkillAgent {skill_agent.name}: {e}", level="ERROR", exc_info=True)
        
        log(f"[{self.name} Tick:{current_tick}] Finished running all agents.", level="DEBUG")

    def _process_meta_agent_messages(self):
        """
        MetaAgent processes its own messages from the communication bus.
        This now includes handling SERVICE_ADVERTISEMENT messages.
        """
        if not self.communication_bus:
            return
        
        messages = self.communication_bus.get_messages_for_agent(self.name)
        for msg_envelope in messages:
            sender_id = msg_envelope.get('sender')
            content = msg_envelope.get('content', {}) # Content is the advertisement_message itself
            message_type = content.get('type') 
            message_id = msg_envelope.get('id')

            log(f"[{self.name}] Received message from '{sender_id}'. Type: '{message_type}'. Content: {str(content)[:150]}", level="DEBUG")

            if message_type == "SERVICE_ADVERTISEMENT":
                payload = content.get('payload', {})
                advertised_agent_id = payload.get('agent_id')
                services_offered = payload.get('services_offered')
                service_details = payload.get('service_details')

                log(f"[{self.name}] Received SERVICE_ADVERTISEMENT from Agent ID: {advertised_agent_id}, Services: {services_offered}", level="INFO")

                if advertised_agent_id:
                    self.service_advertisements[advertised_agent_id] = copy.deepcopy(payload)
                    log(f"[{self.name}] Updated/recorded advertisement for {advertised_agent_id}. Details: {service_details}", level="DEBUG")
                    
                    # Optional: If a new skill agent advertises that MetaAgent wasn't aware of,
                    # you might want to update registries here.
                    # For now, we assume initial registration covers all static skills.
                    # This part becomes more relevant if SkillAgents can be added dynamically post-boot.
                    # Example: if advertised_agent_id not in [sa.id for sa in self.skill_agents]:
                    #    log(f"[{self.name}] New SkillAgent '{advertised_agent_id}' advertised. Consider dynamic registration.", level="INFO")
                    #    # Potentially trigger logic to formally add/recognize this agent if it's truly new
                    #    # and not just an update from an existing one.
                    #    # This might involve checking if it's a known lineage or a completely novel agent.
                    
                    # Update KnowledgeBase with this service listing
                    if self.knowledge and hasattr(self.knowledge, 'store_service_listing'):
                        self.knowledge.store_service_listing(
                            agent_id=advertised_agent_id,
                            agent_name=payload.get('agent_name'),
                            agent_type=payload.get('agent_type'),
                            services_offered=services_offered,
                            service_details=service_details,
                            timestamp=payload.get('timestamp', self.context.get_tick())
                        )
                        log(f"[{self.name}] Stored service listing for {advertised_agent_id} in KnowledgeBase.", level="DEBUG")


            elif content.get('action') == "provision_temporary_skill_agent": # Existing action
                lineage_id_to_provision = content.get('lineage_id')
                requesting_agent_id = content.get('requesting_agent_id') 
                original_request_details = content.get('original_request_details', {})

                log(f"[{self.name}] Received request from '{requesting_agent_id}' to provision temporary skill agent for lineage '{lineage_id_to_provision}'.", level="INFO")
                
                provisioning_success = self._provision_temporary_skill_agent(
                    lineage_id=lineage_id_to_provision,
                    requesting_agent_id=requesting_agent_id,
                    original_request_details=original_request_details
                )
                
                if requesting_agent_id:
                    response_content = {
                        "action": "provisioning_status_response",
                        "lineage_id": lineage_id_to_provision,
                        "provisioning_successful": provisioning_success,
                        "original_request_details": original_request_details 
                    }
                    self.communication_bus.send_direct_message(self.name, requesting_agent_id, response_content)
            
            if message_id: 
                self.communication_bus.mark_message_processed(message_id)


    def _provision_temporary_skill_agent(self, lineage_id: str, requesting_agent_id: Optional[str] = None, original_request_details: Optional[Dict] = None) -> bool:
        """
        Provisions a new, potentially temporary, skill agent of the given lineage.
        Returns True if successful, False otherwise.
        """
        if not lineage_id:
            log(f"[{self.name}] Cannot provision skill agent: lineage_id is missing.", level="ERROR")
            return False

        default_config = self.default_skill_configs_by_lineage.get(lineage_id)
        if not default_config:
            log(f"[{self.name}] No default skill configuration found for lineage_id: '{lineage_id}'. Cannot provision.", level="ERROR")
            return False

        temp_agent_config = copy.deepcopy(default_config)
        
        current_time_tick = self.context.get_tick() if self.context else 0
        temp_id_suffix = f"temp_{current_time_tick}_{uuid.uuid4().hex[:4]}"
        
        # Ensure the name is unique and reflects it's temporary
        temp_agent_config["name"] = f"{lineage_id}-{temp_id_suffix}"
        temp_agent_config["agent_id"] = temp_agent_config["name"]
        temp_agent_config["generation"] = 0 # Or some indicator for temporary agents

        # Use new config values for temporary agents
        temp_agent_config["max_age"] = config.TEMP_AGENT_DEFAULT_MAX_AGE

        # For initial_energy, SkillAgent's __init__ currently sets it to:
        # config.DEFAULT_INITIAL_ENERGY * 0.5
        # To use TEMP_AGENT_DEFAULT_INITIAL_ENERGY, we need to ensure SkillAgent's
        # __init__ (or BaseAgent's __init__ via kwargs) can accept and prioritize
        # an 'initial_energy' value passed in its configuration.
        # Assuming BaseAgent's __init__ already takes 'initial_energy':
        temp_agent_config["initial_energy"] = config.TEMP_AGENT_DEFAULT_INITIAL_ENERGY
        # We might also need to remove any conflicting energy settings from the copied default_config
        # if it had 'initial_state_override' for energy.
        if "initial_state_override" in temp_agent_config:
            temp_agent_config["initial_state_override"].pop("energy", None)
            temp_agent_config["initial_state_override"].pop("energy_level", None)

        log(f"[{self.name}] Attempting to add temporary SkillAgent '{temp_agent_config['name']}' for lineage '{lineage_id}' with MaxAge: {temp_agent_config['max_age']}, InitialEnergy: {temp_agent_config['initial_energy']}.", level="INFO")
        new_agent_instance = self.add_agent_from_config(temp_agent_config)
        if new_agent_instance:
            log(f"[{self.name}] Successfully provisioned temporary SkillAgent: {new_agent_instance.name} for lineage '{lineage_id}'.", level="INFO")
            # Note: TaskRouter is initialized once in main.py. For it to be aware of this new agent,
            # TaskRouter would need a method to dynamically add skill agents and update its internal registry.
            # The following lines are conditional on TaskRouter having such a method.
            if self.task_router and hasattr(self.task_router, 'add_skill_agent'):
                self.task_router.add_skill_agent(new_agent_instance) # 
                log(f"[{self.name}] Updated TaskRouter with new temporary agent: {new_agent_instance.name}", level="DEBUG")
            else:
                log(f"[{self.name}] TaskRouter not updated with new temporary agent '{new_agent_instance.name}' (TaskRouter missing 'add_skill_agent' method or not set).", level="DEBUG")
            # self._update_skill_action_registry() # Registry will be updated at the start of the next run_agents cycle
            return True
        else:
            log(f"[{self.name}] Failed to provision temporary SkillAgent for lineage '{lineage_id}'. add_agent_from_config returned None.", level="ERROR")
            return False

    def _provision_initial_task_agent(self, index: int):
        """Provisions an initial TaskAgent based on the default config."""
        if not self.default_task_agent_config:
            log(f"[{self.name}] Cannot provision initial TaskAgent: default_task_agent_config is missing.", level="ERROR")
            return

        initial_config = copy.deepcopy(self.default_task_agent_config)
        # Ensure unique name and ID for initial agents if multiple are created
        base_name = initial_config.get("name", "TaskAgent-Gen0")
        if not base_name.endswith(f"_{index}"): # Avoid double suffixing if already there
            initial_config["name"] = f"{base_name}_{index}"
            initial_config["agent_id"] = initial_config["name"]
        
        log(f"[{self.name}] Attempting to add initial TaskAgent: {initial_config['name']}", level="INFO")
        new_agent_instance = self.add_agent_from_config(initial_config)
        if new_agent_instance:
            log(f"[{self.name}] Successfully provisioned initial TaskAgent: {new_agent_instance.name}", level="INFO")
        else:
            log(f"[{self.name}] Failed to provision initial TaskAgent: {initial_config['name']}", level="ERROR")

    def add_agent_from_config(self, agent_config: Dict[str, Any]) -> Optional[Any]:
        """Adds a new agent to the system based on its configuration."""
        agent_type = agent_config.get("agent_type")
        agent_name = agent_config.get("name", "UnnamedAgent")
        log(f"[{self.name}] MetaAgent: Adding agent from config. Type: {agent_type}, Name: {agent_name}", level="INFO")

        if agent_type == "task":
            try:
                # Prepare agent_config for TaskAgent constructor
                task_agent_specific_config = agent_config.copy() # Work on a copy
                
                # The MutationEngine should have already set initial_state_override["energy"]
                # to the default (e.g., 100.0) for new TaskAgents.
                # We need to ensure that no other 'initial_energy' key from the parent's
                # old config interferes with BaseAgent's initialization.
                # BaseAgent.__init__ likely uses initial_state_override.
                # Popping 'initial_energy' ensures it doesn't conflict if BaseAgent
                # also looks at kwargs.get('initial_energy').
                if "initial_energy" in task_agent_specific_config:
                    parent_energy = task_agent_specific_config.pop("initial_energy")
                    # Log if the popped energy is different from what's in initial_state_override,
                    # just for debugging to confirm MutationEngine's override is present.
                    iso_energy = task_agent_specific_config.get("initial_state_override", {}).get("energy")
                    if iso_energy is not None and parent_energy != iso_energy:
                        log(f"[{self.name}] add_agent_from_config: Popped 'initial_energy': {parent_energy} for TaskAgent '{agent_name}'. 'initial_state_override.energy' is {iso_energy}.", level="DEBUG")
                    elif iso_energy is None:
                        log(f"[{self.name}] add_agent_from_config: Popped 'initial_energy': {parent_energy} for TaskAgent '{agent_name}'. 'initial_state_override.energy' was not set.", level="WARN")

                task_agent_specific_config.pop("initial_energy_config", None) # Not used by TaskAgent

                # Remove agent_type as TaskAgent constructor handles it internally
                task_agent_specific_config.pop("agent_type", None)

                # Remove 'age' as new agents start at age 0 (handled by BaseAgent)
                task_agent_specific_config.pop("age", None)
                # Remove 'state' as new agents initialize their own state; specific overrides are handled
                task_agent_specific_config.pop("state", None)

                task_agent = TaskAgent(
                    context_manager=self.context,
                    knowledge_base=self.knowledge,
                    communication_bus=self.communication_bus,
                    llm_interface=self.general_llm_interface, # Pass the LLM interface
                    identity_engine=self.identity_engine, # Pass IdentityEngine
                    **task_agent_specific_config  # Unpack the modified config
                )
                self.task_agents.append(task_agent)
                self._update_combined_agents_list()
                log(f"[{self.name}] Successfully added TaskAgent: {agent_name}", level="INFO")
                return task_agent
            except Exception as e:
                log(f"[{self.name}] Failed to add TaskAgent '{agent_name}' from config: {e}", level="ERROR", exc_info=True)
                return None

        elif agent_type == "skill":
            lineage_id = agent_config.get("lineage_id")
            if not lineage_id:
                log(f"[{self.name}] Skill agent config for '{agent_name}' is missing 'lineage_id'. Cannot add.", level="ERROR")
                return None

            original_default_config = self.default_skill_configs_by_lineage.get(lineage_id)

            if not original_default_config:
                log(f"[{self.name}] No original default skill configuration found for lineage_id: '{lineage_id}'. "
                    f"Cannot add SkillAgent '{agent_name}'. "
                    f"Available default lineages: {list(self.default_skill_configs_by_lineage.keys())}", level="ERROR")
                return None

            if "skill_tool" not in original_default_config or original_default_config["skill_tool"] is None:
                log(f"[{self.name}] Original default config for lineage_id '{lineage_id}' is missing the 'skill_tool' instance. "
                    f"Cannot add SkillAgent '{agent_name}'. Default config found: {original_default_config}", level="CRITICAL")
                return None
            
            skill_tool_instance = original_default_config["skill_tool"]

            if not hasattr(skill_tool_instance, 'skill_name'):
                 log(f"[{self.name}] The 'skill_tool' instance for lineage_id '{lineage_id}' is invalid (e.g., missing 'skill_name' attribute). "
                     f"Tool: {skill_tool_instance}. Cannot add SkillAgent '{agent_name}'.", level="CRITICAL")
                 return None

            try:
                # Prepare agent_config for SkillAgent constructor
                skill_agent_specific_config = agent_config.copy()

                # These are passed as named arguments to SkillAgent, so remove from kwargs
                skill_agent_specific_config.pop("skill_tool", None)
                # context_manager, knowledge_base, communication_bus, identity_engine are not in agent_config
                # agent_id is passed explicitly to SkillAgent constructor, so remove from skill_agent_specific_config
                # to prevent "got multiple values for keyword argument 'agent_id'" in SkillAgent.__init__
                skill_agent_specific_config.pop("agent_id", None)

                # Pop 'name' as it will be passed as an explicit argument to SkillAgent constructor
                name_for_constructor = agent_config.get("name") # Get name before popping
                skill_agent_specific_config.pop("name", None)

                skill_agent_specific_config.pop("agent_type", None)
                skill_agent_specific_config.pop("age", None)
                skill_agent_specific_config.pop("state", None)
                
                # These are specific to skill_loader or MetaAgent's default config structure,
                # not directly used by SkillAgent.__init__ via **kwargs.
                # SkillAgent.__init__ will derive/set its own values or get them from config_kwargs if they are standard.
                skill_agent_specific_config.pop("skill_tool_class_name", None)
                skill_agent_specific_config.pop("skill_module_name", None)
                skill_agent_specific_config.pop("initial_energy_config", None) # Old key, ensure it's not passed

                # The agent_id from agent_config will be used for the agent_id parameter in SkillAgent constructor
                agent_id_for_constructor = agent_config.get("agent_id", agent_config.get("name"))

                skill_agent = SkillAgent(
                    skill_tool=skill_tool_instance, 
                    context_manager=self.context,
                    knowledge_base=self.knowledge,
                    communication_bus=self.communication_bus,
                    identity_engine=self.identity_engine, # Pass IdentityEngine
                    name=name_for_constructor,           # Pass name explicitly
                    agent_id=agent_id_for_constructor,   # Pass agent_id explicitly
                    **skill_agent_specific_config        # Pass the rest (name, initial_energy, max_age, capabilities, lineage_id, etc.)
                )
                self.skill_agents.append(skill_agent)
                self._update_combined_agents_list()
                # self._update_skill_action_registry() # Registry will be updated at the start of the next run_agents cycle
                log(f"[{self.name}] Successfully added SkillAgent: {agent_name} of lineage '{lineage_id}'.", level="INFO")
                return skill_agent
            except Exception as e:
                log(f"[{self.name}] Failed to instantiate SkillAgent '{agent_name}' (lineage: '{lineage_id}') from config. Error: {e}", level="ERROR", exc_info=True)
                return None
        else:
            log(f"[{self.name}] Unknown agent type '{agent_type}' in config for agent '{agent_name}'. Skipping.", level="WARN")
            return None

    def _update_combined_agents_list(self):
        """Helper to keep self.agents synchronized with task_agents and skill_agents."""
        self.agents = list(self.task_agents) + list(self.skill_agents)

    def get_all_agent_names(self) -> List[str]:
        """Returns a list of names of all current agents (task and skill)."""
        agent_names = [agent.name for agent in self.task_agents if hasattr(agent, 'name')]
        agent_names.extend([agent.name for agent in self.skill_agents if hasattr(agent, 'name')])
        return agent_names

    def _update_skill_action_registry(self):
        """
        Rebuilds the skill_action_registry based on the current active SkillAgents
        and the capabilities their skill_tools offer.
        """
        self.skill_action_registry.clear()
        for skill_agent_instance in self.skill_agents:
            if hasattr(skill_agent_instance, 'skill_tool') and skill_agent_instance.skill_tool:
                tool = skill_agent_instance.skill_tool
                if hasattr(tool, 'get_capabilities') and callable(tool.get_capabilities):
                    try:
                        tool_capabilities = tool.get_capabilities()
                        # tool_capabilities is expected to be like:
                        # {"skill_name": "MathsTool", "commands": {"add": {...}, "subtract": {...}}}
                        for command_name in tool_capabilities.get("commands", {}).keys():
                            if command_name not in self.skill_action_registry:
                                self.skill_action_registry[command_name] = []
                            if skill_agent_instance.name not in self.skill_action_registry[command_name]:
                                self.skill_action_registry[command_name].append(skill_agent_instance.name)
                    except Exception as e:
                        log(f"[{self.name}] Error getting/processing capabilities from skill_tool {type(tool)} for agent {skill_agent_instance.name}: {e}", level="ERROR")
        log(f"[{self.name}] Skill action registry updated. {len(self.skill_action_registry)} actions mapped. Example action 'add' providers: {self.skill_action_registry.get('add', [])}", level="DEBUG")

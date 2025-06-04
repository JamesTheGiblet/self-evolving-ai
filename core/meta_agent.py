# core/meta_agent.py
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from core import context_manager
from core.context_manager import ContextManager
from core.skill_agent import SkillAgent
from core.task_router import TaskRouter
from memory.knowledge_base import KnowledgeBase
from engine.communication_bus import CommunicationBus
from utils.logger import log
from core.task_agent import TaskAgent # Import TaskAgent for instantiation
from utils import local_llm_connector
import config
import copy # For deepcopy

if TYPE_CHECKING: # TYPE_CHECKING is True for static analysis
    from .task_router import TaskRouter
    # from .skill_agent import SkillAgent # Already imported above
    from engine.identity_engine import IdentityEngine

class MetaAgent:
    def __init__(self, 
                 context: ContextManager, 
                 knowledge: KnowledgeBase, 
                 communication_bus: CommunicationBus, 
                 skill_agents: List['SkillAgent'],
                 identity_engine: 'IdentityEngine', # Accept IdentityEngine instance
                 default_task_agent_config: Dict[str, Any],  # Added
                 default_skill_agent_configs: List[Dict[str, Any]]): # Added
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
        
        self.identity_engine = identity_engine # Use the passed IdentityEngine instance
        
        self.default_task_agent_config = default_task_agent_config
        self.default_skill_agent_configs = default_skill_agent_configs # Store the passed list
        
        # Store default skill configurations in a dictionary for easy lookup by lineage_id.
        # These default_skill_agent_configs from main.py contain the actual skill_tool instances.
        self.default_skill_configs_by_lineage: Dict[str, Dict[str, Any]] = {}
        for cfg in default_skill_agent_configs:
            lineage = cfg.get("lineage_id")
            if lineage:
                self.default_skill_configs_by_lineage[lineage] = copy.deepcopy(cfg) 
            else:
                log(f"MetaAgent Init: Default skill config missing 'lineage_id'. Config: {cfg}", level="WARN")

        self.task_router: Optional['TaskRouter'] = None
        log(f"MetaAgent initialized. Initial skill agents: {len(self.skill_agents)}. Default skill configs by lineage: {len(self.default_skill_configs_by_lineage)}.", level="INFO")

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
                if agent.name == skill_name: # Matching by SkillAgent's name
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

                log(f"[MetaAgent] Executing routed command on {skill_name}: '{command_str_for_skill}'", level="INFO")
                result_json_str = target_skill_agent.execute(command_str_for_skill)
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
        # For now, let's just try to handle it as a direct request
        response = self.handle_user_request(goal_description)
        log(f"[MetaAgent] Response to user goal '{goal_description}': {response[:200]}...", level="INFO")
        # In a real system, this response would be communicated back or used to drive further actions.

    def run_agents(self):
        """
        Runs the operational cycle for all managed agents (Task and Skill).
        """
        current_tick = self.context.get_tick()
        log(f"[{self.name} Tick:{current_tick}] Running all agents. Task Agents: {len(self.task_agents)}, Skill Agents: {len(self.skill_agents)}", level="DEBUG")

        # Prepare data that might be needed by agents during their run
        all_agent_names = self.get_all_agent_names()
        
        agent_info_map: Dict[str, Dict[str, Any]] = {}
        for agent_instance in self.agents: 
            if hasattr(agent_instance, 'get_config'):
                agent_info_map[agent_instance.name] = {
                    "agent_type": agent_instance.agent_type,
                    "name": agent_instance.name,
                    "generation": agent_instance.generation,
                    "lineage_id": agent_instance.lineage_id,
                    "capabilities": agent_instance.capabilities[:], 
                    "is_active": agent_instance.state.get("status") == "active" if hasattr(agent_instance, 'state') else True,
                }
            else:
                 agent_info_map[agent_instance.name] = {
                    "agent_type": "unknown",
                    "name": agent_instance.name,
                    "is_active": True 
                 }

        for task_agent in self.task_agents:
            try:
                task_agent.run(
                    context=self.context, 
                    knowledge=self.knowledge, 
                    all_agent_names_in_system=all_agent_names,
                    agent_info_map=agent_info_map
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
                # Remove skill_tool if present, as it's passed explicitly
                skill_agent_specific_config.pop("skill_tool", None)
                # Remove agent_type as SkillAgent constructor handles it internally via BaseAgent
                skill_agent_specific_config.pop("agent_type", None)
                # Remove 'name' as SkillAgent.__init__ does not expect it directly (per TypeError).
                # SkillAgent or BaseAgent is assumed to handle name assignment internally,
                # possibly using other config values like lineage_id and generation.
                skill_agent_specific_config.pop("name", None)
                # Remove 'age' as new agents start at age 0 (handled by BaseAgent)
                skill_agent_specific_config.pop("age", None)
                # Remove 'state' as new agents initialize their own state
                skill_agent_specific_config.pop("state", None)
                # Remove 'initial_energy' as SkillAgent sets its own initial energy for BaseAgent
                skill_agent_specific_config.pop("initial_energy", None)
                skill_agent_specific_config.pop("initial_energy_config", None) # Also remove this if present
                # Remove 'max_age' as SkillAgent sets its own max_age for BaseAgent
                skill_agent_specific_config.pop("max_age", None)
                # Remove 'skill_tool_class_name' as it's not used by SkillAgent.__init__
                skill_agent_specific_config.pop("skill_tool_class_name", None)
                # Remove 'skill_module_name' as it's not used by SkillAgent.__init__
                skill_agent_specific_config.pop("skill_module_name", None)
                # Remove 'skill_tool_name' as it's not used by SkillAgent.__init__
                skill_agent_specific_config.pop("skill_tool_name", None)

                skill_agent = SkillAgent(
                    skill_tool=skill_tool_instance, 
                    context_manager=self.context,
                    knowledge_base=self.knowledge,
                    communication_bus=self.communication_bus,
                    identity_engine=self.identity_engine, # Pass IdentityEngine
                    **skill_agent_specific_config # Unpack the modified config
                )
                self.skill_agents.append(skill_agent)
                self._update_combined_agents_list()
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
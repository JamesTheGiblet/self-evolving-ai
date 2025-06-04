# self-evolving-ai/main.py
import os
import sys
import signal
import time # Assuming time is used elsewhere in your main
import threading # Assuming threading is used elsewhere

# Add the project root to sys.path to allow absolute imports from main.py
# This is crucial if main.py is in the root and imports modules from subdirectories like core, skills etc.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now, standard imports should work assuming your project structure
from core.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
from engine.communication_bus import CommunicationBus # Ensure this is used or remove if not
from core.skill_agent import SkillAgent # For type hinting if needed
from core.task_agent import TaskAgent
from core.meta_agent import MetaAgent
from core.task_router import TaskRouter
from core.mutation_engine import MutationEngine # Ensure MutationEngine is imported
from gui import SimulationGUI
from utils import local_llm_connector # Assuming this exists and is setup
import json # For pretty printing config
from utils.logger import log
import config # Your main config file

# Import the dynamic skill loader
from core.skill_loader import load_skills_dynamically, generate_lineage_id_from_skill_name


# Global reference for shutdown handler
app_gui_instance = None
global_context_manager_instance = None # For shutdown handler

def shutdown_handler(signum, frame):
    log(f"Signal {signum} received. Initiating graceful shutdown...")
    if app_gui_instance and hasattr(app_gui_instance, 'on_closing') and callable(app_gui_instance.on_closing):
        log("Attempting to close GUI gracefully...")
        # Schedule the on_closing method to be called in the Tkinter main loop
        app_gui_instance.after(0, app_gui_instance.on_closing)
    else:
        log("GUI instance not available or on_closing not callable. Attempting direct context stop and exit.", level="WARN")
        if global_context_manager_instance and hasattr(global_context_manager_instance, 'stop') and callable(global_context_manager_instance.stop):
            global_context_manager_instance.stop()
        sys.exit(0) # Fallback exit

def main():
    global global_context_manager_instance, app_gui_instance

    # --- Setup Logging and Output Redirection ---
    # Ensure the log directory exists if it's not the root
    log_dir = os.path.join(config.PROJECT_ROOT_PATH, "logs") # Assuming a 'logs' subdirectory
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    log_file_path = os.path.join(config.PROJECT_ROOT_PATH, "simulation.log") # Log file in root
    sys.stdout = open(log_file_path, 'a', buffering=1) # Redirect stdout to log file, line buffered


    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Initialize core components
    context_manager = ContextManager(tick_interval=config.TICK_INTERVAL)
    global_context_manager_instance = context_manager # For shutdown handler
    
    # If local_llm_connector needs the context manager
    if hasattr(local_llm_connector, 'set_llm_connector_context_manager'):
        local_llm_connector.set_llm_connector_context_manager(context_manager)
    
    knowledge_base = KnowledgeBase()
    communication_bus = CommunicationBus(enable_logging=True)

    # Instantiate IdentityEngine early, as it's needed by skill_loader and MetaAgent
    # MetaAgent will now receive this instance instead of creating its own.
    from engine.identity_engine import IdentityEngine # Ensure correct import path
    identity_engine_instance = IdentityEngine(
        knowledge_base=knowledge_base,
        meta_agent_instance=None, # MetaAgent instance will be set later if needed, or refactor IdentityEngine
        context_manager=context_manager,
        # llm_planner and fitness_engine are optional for IdentityEngine
    )

    # --- Dynamic Skill Loading ---
    # Determine the absolute path to the 'skills' directory relative to this main.py file
    # Assumes main.py is in the project root, and 'skills' is a subdirectory.
    skills_dir = os.path.join(PROJECT_ROOT, "skills")
    log(f"Attempting to load skills from: {skills_dir}", level="INFO")
    
    # `dynamic_skill_agents` will be a list of instantiated SkillAgent objects.
    # `dynamic_default_skill_agent_configs` will be a list of config dictionaries.
    dynamic_skill_agents, dynamic_default_skill_agent_configs = load_skills_dynamically(
        skills_dir_path=skills_dir,
        knowledge_base_instance=knowledge_base,
        context_manager_instance=context_manager,
        communication_bus_instance=communication_bus,
        identity_engine_instance=identity_engine_instance # Pass IdentityEngine
    )
    
    log(f"Dynamically initialized {len(dynamic_skill_agents)} skill agents.", level="INFO")
    # For debugging, you might want to print the generated configs:
    # import json
    # log(f"Dynamically generated default_skill_agent_configs: {json.dumps(dynamic_default_skill_agent_configs, indent=2, default=lambda o: f'<object {type(o).__name__}>')}", level="DEBUG")


    # --- Default Task Agent Configuration ---
    default_task_agent_config = {
        "agent_id": "TaskAgent-Gen0_0", # Unique ID for the agent instance
        "name": "TaskAgent-Gen0_0",     # Display name, can be same as agent_id or more descriptive
        "agent_type": "task",
        "capabilities": [
            "knowledge_storage_v1", "knowledge_retrieval_v1", 
            "communication_broadcast_v1", "sequence_executor_v1",
            "invoke_skill_agent_v1", "interpret_goal_with_llm_v1", "export_agent_evolution_v1",
            "triangulated_insight_v1"
            # Add other capabilities as defined in capability_definitions.py
        ],
        "capability_params": {
            "interpret_goal_with_llm_v1": {"llm_model": config.DEFAULT_LLM_MODEL, "energy_cost": 1.0}, # example param
            "sequence_executor_v1": {"default_sequence_name": "standard_observe_orient_decide_act"}
        },
        "behavior_mode": "explore", # or "exploit"
        "role": "generalist_task",  # As defined in roles.py
        "initial_state_override": {"energy": config.DEFAULT_INITIAL_ENERGY}, # Example state override
        "max_age": config.DEFAULT_MAX_AGENT_AGE,
        "lineage_id": "TaskAgent-Gen0", # Base lineage ID for this type of task agent
        "generation": 0 # Initial generation
    }
    log(f"Default Task Agent Config: {json.dumps(default_task_agent_config, indent=2)}", level="DEBUG")

    # --- Initialize MetaAgent ---
    # MetaAgent now receives the list of instantiated skill agents and their default configs
    meta_agent = MetaAgent(
        context=context_manager,
        knowledge=knowledge_base,
        communication_bus=communication_bus, 
        skill_agents=dynamic_skill_agents, # Pass the list of SkillAgent instances
        identity_engine=identity_engine_instance, # Pass the pre-created IdentityEngine
        default_task_agent_config=default_task_agent_config,
        default_skill_agent_configs=dynamic_default_skill_agent_configs # Pass dynamically generated configs
    )
    
    # The MetaAgent's __init__ should handle adding the initial_skill_agents
    # and creating the default task agent. If not, you might need to call:
    # meta_agent.add_default_agents() or similar method if it exists.
    # For clarity, let's assume MetaAgent handles this. If you need to manually add the task agent:
    # task_agent_instance = TaskAgent(context_manager=context_manager, knowledge_base=knowledge_base, communication_bus=communication_bus, **default_task_agent_config)
    # meta_agent.add_agent(task_agent_instance) # Assuming add_agent exists and categorizes correctly

    # Ensure TaskRouter gets the dynamically loaded skill agents
    # The TaskRouter likely expects the list of skill agents directly.
    # We call meta_agent.get_skill_agents() to get the current list.
    # Assuming TaskRouter's __init__ expects a 'skill_agents' parameter.
    task_router = TaskRouter(skill_agents=meta_agent.get_skill_agents())
    meta_agent.set_task_router(task_router)

    # Initialize MutationEngine
    # The MutationEngine needs to know about the "service capabilities" that skill agents can provide.
    # We can extract these from the dynamically loaded default configs.
    all_known_service_capabilities = list(set(
        cap for config_entry in dynamic_default_skill_agent_configs if config_entry and isinstance(config_entry, dict) for cap in config_entry.get("capabilities", [])
    ))
    log(f"All known service capabilities for MutationEngine: {all_known_service_capabilities}", level="DEBUG")
    
    mutation_engine = MutationEngine(
        meta_agent_instance=meta_agent,
        knowledge_base_instance=knowledge_base,
        context_manager_instance=context_manager,
        # Pass the list of dynamically discovered service capabilities if your MutationEngine uses it
        # e.g., known_skill_service_capabilities=all_known_service_capabilities
    )
    # If MutationEngine's MUTATABLE_SKILL_AGENT_CAPABILITIES is a global or class var,
    # you might need a method to update it, or pass these during init.
    # For example, if it's a class variable:
    # MutationEngine.MUTATABLE_SKILL_AGENT_CAPABILITIES.extend(all_known_service_capabilities)

    # Ensure ContextManager has a reference to IdentityEngine for capabilities that might need it
    if hasattr(context_manager, 'set_identity_engine'):
        context_manager.set_identity_engine(identity_engine_instance)
        log("[Main] IdentityEngine set on ContextManager.", level="INFO")
    else:
        # Fallback if setter doesn't exist, though it should
        context_manager.identity_engine = identity_engine_instance 
        log("[Main] IdentityEngine directly set on ContextManager (fallback).", level="WARN")

    log("SYSTEM BOOTING...", level="INFO")

    # Initialize GUI *before* starting the simulation loop thread
    app_gui = SimulationGUI(context_manager=context_manager,
                            meta_agent=meta_agent,
                            mutation_engine=mutation_engine, # Pass the mutation engine
                            knowledge_base=knowledge_base)
    app_gui_instance = app_gui # For signal handler
    context_manager.set_gui_instance(app_gui) # Link GUI to context for updates
    
    app_gui.mainloop() # This will block until the GUI is closed

    log("Mainloop finished. System shutdown sequence concluding.")
    if context_manager.is_running():
        log("ContextManager still running post-mainloop, attempting stop.")
        context_manager.stop()
    log("System shutdown complete.")

if __name__ == "__main__":
    # Ensure the logger is configured before any logging calls
    # from utils.logger import setup_logging
    # setup_logging() # Call your logger setup if it's not automatically done on import
    main()

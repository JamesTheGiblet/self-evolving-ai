# main.py - Entry point for self-evolving-ai
import os
import sys
import signal

# Ensure project root is in sys.path for absolute imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
from engine.communication_bus import CommunicationBus
from core.meta_agent import MetaAgent
from core.task_router import TaskRouter
from core.mutation_engine import MutationEngine
from gui import SimulationGUI
from utils import local_llm_connector
import json
from utils.logger import log
from urllib.parse import urlparse # For parsing Ollama host from URL
from agents.code_gen_agent import LLMInterface, CodeGenAgent # Import CodeGen components
import config
from core.skill_loader import load_skills_dynamically

# Global references for shutdown handler
app_gui_instance = None
global_context_manager_instance = None

def shutdown_handler(signum, frame):
    """
    Handles graceful shutdown on SIGINT/SIGTERM.
    Attempts to close the GUI if running, otherwise stops the context manager.
    """
    log(f"Signal {signum} received. Initiating graceful shutdown...")
    gui_closed_by_this_handler = False
    if app_gui_instance and hasattr(app_gui_instance, 'on_closing') and callable(app_gui_instance.on_closing):
        try:
            if app_gui_instance.winfo_exists():  # Check if window object still exists
                if not app_gui_instance._is_closing:
                    log("Attempting to close GUI gracefully by scheduling on_closing()...")
                    # Schedule on_closing to be run in the GUI's main thread
                    app_gui_instance.after(0, app_gui_instance.on_closing)
                    gui_closed_by_this_handler = True
                else:
                    log("GUI is already in the process of closing. Signal handler will not intervene further with GUI.")
            else:
                log("GUI window object no longer exists. Will attempt to stop ContextManager directly if needed.", level="WARN")
        except Exception as e:  # Catch potential TclError if GUI is in a bad state
            log(f"Error interacting with GUI during shutdown: {e}. Will attempt to stop ContextManager directly.", level="ERROR")

    if not gui_closed_by_this_handler:
        # This block runs if GUI wasn't told to close by this handler invocation,
        # or if there was an issue with the GUI.
        log("GUI not closed by this handler or GUI unavailable/error. Checking ContextManager.", level="INFO")
        if global_context_manager_instance and \
           hasattr(global_context_manager_instance, 'is_running') and \
           callable(global_context_manager_instance.is_running) and \
           global_context_manager_instance.is_running():
            log("Attempting to stop ContextManager directly.", level="WARN")
            if hasattr(global_context_manager_instance, 'stop') and callable(global_context_manager_instance.stop):
                global_context_manager_instance.stop()
            else:
                log("ContextManager does not have a callable stop method.", level="ERROR")
        elif global_context_manager_instance:
            log("ContextManager exists but is not running or is_running not callable.", level="INFO")
        else:
            log("Global ContextManager instance not available for direct stop.", level="WARN")
    # The program should exit naturally when mainloop terminates and main() function completes.

def main():
    global global_context_manager_instance, app_gui_instance

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Initialize core components
    context_manager = ContextManager(tick_interval=config.TICK_INTERVAL)
    global_context_manager_instance = context_manager

    # Optionally set context manager on LLM connector if supported
    if hasattr(local_llm_connector, 'set_llm_connector_context_manager'):
        local_llm_connector.set_llm_connector_context_manager(context_manager)

    knowledge_base = KnowledgeBase()
    communication_bus = CommunicationBus(enable_logging=True)

    # Instantiate IdentityEngine (needed by skill loader and MetaAgent)
    from engine.identity_engine import IdentityEngine
    identity_engine_instance = IdentityEngine(
        knowledge_base=knowledge_base,
        meta_agent_instance=None,
        context_manager=context_manager,
    )

    # Initialize LLMInterface and CodeGenAgent
    # Extract Ollama host from the base URL in config
    ollama_host = None
    if config.LOCAL_LLM_API_BASE_URL:
        try:
            parsed_url = urlparse(config.LOCAL_LLM_API_BASE_URL)
            if parsed_url.scheme and parsed_url.netloc:
                ollama_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        except Exception as e:
            log(f"Could not parse LOCAL_LLM_API_BASE_URL for Ollama host: {e}. Using default.", level="WARN")

    log(f"Initializing LLMInterface for CodeGenAgent with model: {config.LOCAL_LLM_DEFAULT_MODEL} and host: {ollama_host or 'default'}")
    code_gen_llm_interface = LLMInterface(
        model_name=config.LOCAL_LLM_DEFAULT_MODEL,
        # host=ollama_host # Removed: LLMInterface.__init__ does not accept 'host'.
                           # It likely configures the host internally, possibly using config.LOCAL_LLM_API_BASE_URL.
    )
    code_gen_agent_instance = CodeGenAgent(llm_interface=code_gen_llm_interface)
    log("[Main] CodeGenAgent instance created.", level="INFO")
    
    # Initialize a general-purpose LLMInterface for other skills (e.g., creative text generation)
    # For now, it can use the same model, but this allows for future specialization.
    general_llm_interface = LLMInterface(
        model_name=config.LOCAL_LLM_DEFAULT_MODEL 
    )
    log("[Main] General LLMInterface instance created.", level="INFO")

    # Load skill agents dynamically from the 'skills' directory
    skills_dir = os.path.join(PROJECT_ROOT, "skills")
    log(f"Attempting to load skills from: {skills_dir}", level="INFO")
    dynamic_skill_agents, dynamic_default_skill_agent_configs = load_skills_dynamically(
        skills_dir_path=skills_dir,
        knowledge_base_instance=knowledge_base,
        context_manager_instance=context_manager,
        communication_bus_instance=communication_bus,
        identity_engine_instance=identity_engine_instance,
        code_gen_agent_instance=code_gen_agent_instance, # Pass CodeGenAgent
        general_llm_interface_instance=general_llm_interface # Pass general LLMInterface
    )
    log(f"Dynamically initialized {len(dynamic_skill_agents)} skill agents.", level="INFO")

    # Default configuration for the initial task agent
    default_task_agent_config = {
        "agent_id": "TaskAgent-Gen0_0",
        "name": "TaskAgent-Gen0_0",
        "agent_type": "task",
        "capabilities": [
            "knowledge_storage_v1", "knowledge_retrieval_v1",
            "communication_broadcast_v1", "sequence_executor_v1",
            "invoke_skill_agent_v1", "interpret_goal_with_llm_v1", "export_agent_evolution_v1",
            "triangulated_insight_v1"
        ],
        "capability_params": {
            "interpret_goal_with_llm_v1": {"llm_model": config.DEFAULT_LLM_MODEL, "energy_cost": 1.0},
            "sequence_executor_v1": {"default_sequence_name": "standard_observe_orient_decide_act"}
        },
        "behavior_mode": "explore",
        "role": "generalist_task",
        "initial_state_override": {"energy": config.DEFAULT_INITIAL_ENERGY},
        "max_age": config.DEFAULT_MAX_AGENT_AGE,
        "lineage_id": "TaskAgent-Gen0",
        "generation": 0
    }
    log(f"Default Task Agent Config: {json.dumps(default_task_agent_config, indent=2)}", level="DEBUG")

    # Initialize MetaAgent with loaded skill agents and configs
    meta_agent = MetaAgent(
        context=context_manager,
        knowledge=knowledge_base,
        communication_bus=communication_bus,
        skill_agents=dynamic_skill_agents,
        identity_engine=identity_engine_instance,
        default_task_agent_config=default_task_agent_config,
        default_skill_agent_configs=dynamic_default_skill_agent_configs,
        general_llm_interface=general_llm_interface, # Pass the general LLM interface
        initial_task_agents=1 # Explicitly create one initial task agent
    )

    # Setup TaskRouter with current skill agents
    task_router = TaskRouter(skill_agents=meta_agent.get_skill_agents())
    meta_agent.set_task_router(task_router)

    # Gather all known service capabilities for MutationEngine
    all_known_service_capabilities = list(set(
        cap for config_entry in dynamic_default_skill_agent_configs if config_entry and isinstance(config_entry, dict) for cap in config_entry.get("capabilities", [])
    ))
    log(f"All known service capabilities for MutationEngine: {all_known_service_capabilities}", level="DEBUG")

    # Initialize MutationEngine
    mutation_engine = MutationEngine(
        meta_agent_instance=meta_agent,
        knowledge_base_instance=knowledge_base,
        context_manager_instance=context_manager,
    )
    log("[Main] MutationEngine initialized.", level="INFO")

    # Set IdentityEngine reference on ContextManager
    if hasattr(context_manager, 'set_identity_engine'):
        context_manager.set_identity_engine(identity_engine_instance)
        log("[Main] IdentityEngine set on ContextManager.", level="INFO")
    else:
        context_manager.identity_engine = identity_engine_instance
        log("[Main] IdentityEngine directly set on ContextManager (fallback).", level="WARN")

    # Pass the code_gen_agent_instance to the MutationEngine
    if hasattr(mutation_engine, 'set_code_gen_agent'):
        mutation_engine.set_code_gen_agent(code_gen_agent_instance)
        log("[Main] CodeGenAgent instance set on MutationEngine.", level="INFO")

    log("SYSTEM BOOTING...", level="INFO")

    # The evolutionary cycle demo is now triggered from the GUI's "Knowledge Tools" tab.

    # Initialize and start the GUI
    app_gui = SimulationGUI(
        context_manager=context_manager,
        meta_agent=meta_agent,
        mutation_engine=mutation_engine,
        knowledge_base=knowledge_base,
        # Pass the CodeGenAgent's demonstration method to the GUI
        run_evolutionary_cycle_func=code_gen_agent_instance.demonstrate_capability_generation
    )
    app_gui_instance = app_gui
    context_manager.set_gui_instance(app_gui)

    app_gui.mainloop()

    log("Mainloop finished. System shutdown sequence concluding.")
    if context_manager.is_running():
        log("ContextManager still running post-mainloop, attempting stop.")
        context_manager.stop()
    log("System shutdown complete.")

if __name__ == "__main__":
    main()

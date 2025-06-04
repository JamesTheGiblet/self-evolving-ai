# capability_handlers/export_handlers.py
import json
import os
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
from core.context_manager import ContextManager
import config # Import config for PROJECT_ROOT_PATH

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    # Assuming IdentityEngine is accessible via agent or context
    # from core.identity_engine import IdentityEngine

def execute_export_agent_evolution_v1(agent: 'BaseAgent', params_used: Dict, cap_inputs: Dict, knowledge: 'KnowledgeBase', context: ContextManager, all_agent_names_in_system: List[str]):
    target_identifier = cap_inputs.get("target_identifier") # Attempt to get from cap_inputs
    if not target_identifier:
        target_identifier = agent.id # Default to the agent's own ID if not provided
        log(f"[{agent.name}] Cap 'export_agent_evolution_v1': No target_identifier in cap_inputs, defaulting to self ({agent.id}).", level="DEBUG")
    identifier_type = cap_inputs.get("identifier_type", params_used.get("default_identifier_type", "agent_id"))
    output_format = cap_inputs.get("output_format", params_used.get("default_output_format", "json_string"))
    
    # Construct the default file path using PROJECT_ROOT_PATH
    default_file_path_template_from_params = params_used.get("default_file_path_template", "agent_outputs/evolution_history_{identifier}.json")
    # Ensure the template path is joined with the project root
    resolved_default_file_path_template = os.path.join(config.PROJECT_ROOT_PATH, default_file_path_template_from_params)
    
    # Sanitize identifier for use in filename
    sanitized_identifier = (target_identifier.replace(":", "_").replace("/", "_")) if target_identifier else "unknown"
    default_formatted_path = resolved_default_file_path_template.format(identifier=sanitized_identifier)
    file_path = cap_inputs.get("file_path", default_formatted_path) # Use the resolved default if file_path not in cap_inputs

    if not hasattr(agent, 'identity_engine') or agent.identity_engine is None:
        # Attempt to get from context if not on agent (less ideal but a fallback)
        identity_engine_instance = getattr(context, 'identity_engine', None)
        if not identity_engine_instance:
            return {"outcome": "failure_missing_dependency", "reward": -0.2, "details": {"error": "IdentityEngine not found on agent or context."}}
    else:
        identity_engine_instance = agent.identity_engine

    try:
        current_tick = context.get_tick()
        history_data = identity_engine_instance.get_evolution_history(identifier=target_identifier, id_type=identifier_type, current_tick=current_tick)

        if not history_data:
            return {"outcome": "success_no_data_found", "reward": 0.1, "details": {"message": f"No history for {identifier_type} '{target_identifier}'"}}

        if output_format == "json_string":
            json_output = json.dumps(history_data, indent=2)
            return {"outcome": "success_json_string_generated", "reward": 0.5, "details": {"json_data": json_output, "entry_count": len(history_data)}}
        elif output_format == "file":
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(history_data, f, indent=2)
            return {"outcome": "success_file_exported", "reward": 0.6, "details": {"file_path": file_path, "entry_count": len(history_data)}}
        else:
            return {"outcome": "failure_invalid_output_format", "reward": -0.1, "details": {"error": f"Invalid output_format: {output_format}"}}
    except Exception as e:
        log(f"[{agent.name}] Cap 'export_agent_evolution_v1': Error. {e}", level="ERROR", exc_info=True)
        return {"outcome": "failure_exception", "reward": -0.5, "details": {"error": str(e)}}
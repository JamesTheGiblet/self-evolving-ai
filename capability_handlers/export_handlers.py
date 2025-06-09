# capability_handlers/export_handlers.py
from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
import json # For pretty printing JSON in text format

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.identity_engine import IdentityEngine # For evolution history
    from core.meta_agent import MetaAgent # For agent summaries

# --- Handler function definitions ---
def execute_export_agent_evolution_v1(
    agent: 'BaseAgent',
    params_used: Dict,
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles exporting agent evolution data.
    Uses IdentityEngine to retrieve evolution history.
    `params_used` can specify "format" ("json" or "summary_text").
    `cap_inputs` should specify "target_identifier" (agent_id or lineage_id)
    and "identifier_type" ("agent_id" or "lineage_id").
    """
    export_format = params_used.get("format", "json") # Default format
    target_identifier = cap_inputs.get("target_identifier", agent.state.get("lineage_id", agent.agent_id))
    identifier_type = cap_inputs.get("identifier_type", "lineage_id") # Default to lineage_id

    if not target_identifier:
        return {"outcome": "failure_missing_target_identifier", "reward": -0.1, "details": {"error": "target_identifier is required in cap_inputs."}}
    if identifier_type not in ["agent_id", "lineage_id"]:
        return {"outcome": "failure_invalid_identifier_type", "reward": -0.1, "details": {"error": "identifier_type must be 'agent_id' or 'lineage_id'."}}

    log(f"[{agent.name}] Executing export_agent_evolution_v1. Format: {export_format}. Target: {target_identifier} (Type: {identifier_type})", level="INFO")

    identity_engine: 'IdentityEngine' = getattr(agent, 'identity_engine', None)
    if not identity_engine: # Fallback if not directly on agent, try via meta_agent
        meta_agent_ref: 'MetaAgent' = getattr(agent, 'meta_agent', None)
        if meta_agent_ref:
            identity_engine = getattr(meta_agent_ref, 'identity_engine', None)

    if not identity_engine:
        return {"outcome": "failure_identity_engine_not_found", "reward": -0.2, "details": {"error": "IdentityEngine instance not accessible."}}

    evolution_history = identity_engine.get_evolution_history(identifier=target_identifier, id_type=identifier_type, current_tick=context.get_tick())

    if not evolution_history:
        return {"outcome": "success_no_history_found", "reward": 0.05, "details": {"format": export_format, "identifier_queried": target_identifier, "status": "No evolution history found for identifier."}}

    exported_data_preview = ""
    if export_format == "json":
        # In a real scenario, this data would be saved to a file or returned.
        # For simulation, we'll just provide a preview.
        exported_data_preview = str(evolution_history[:2]) + ("..." if len(evolution_history) > 2 else "")
    elif export_format == "summary_text":
        summary = f"Evolution History for {identifier_type} '{target_identifier}':\n"
        for event in evolution_history[:5]: # Summarize first 5 events
            summary += f"  - Tick {event.get('tick', 'N/A')}: {event.get('event_type', 'N/A')} - Details: {str(event.get('details', {}))[:50]}...\n"
        if len(evolution_history) > 5:
            summary += f"  ... and {len(evolution_history) - 5} more events.\n"
        exported_data_preview = summary
    else:
        return {"outcome": "failure_unsupported_format", "reward": -0.1, "details": {"error": f"Unsupported export format: {export_format}"}}

    return {"outcome": "success_export_generated", "reward": 0.3, "details": {"format": export_format, "identifier_exported": target_identifier, "events_count": len(evolution_history), "data_preview": exported_data_preview}}

def execute_export_system_snapshot_v1(
    agent: 'BaseAgent',
    params_used: Dict, # Not typically used here, snapshot type comes from cap_inputs
    cap_inputs: Dict,
    knowledge: 'KnowledgeBase',
    context: 'ContextManager',
    all_agent_names_in_system: List[str]
) -> Dict[str, Any]:
    """
    Handles exporting a snapshot of the system or its components.
    `cap_inputs` should contain:
        - "snapshot_type": e.g., "active_agents_summary", "knowledge_base_stats", "system_identity_full", "system_performance_profile".
        - "format": e.g., "json", "text".
    """
    snapshot_type = cap_inputs.get("snapshot_type")
    export_format = cap_inputs.get("format", "json")

    if not snapshot_type:
        return {"outcome": "failure_missing_snapshot_type", "reward": -0.2, "details": {"error": "Missing 'snapshot_type' in cap_inputs."}}

    log(f"[{agent.name}] Executing export_system_snapshot_v1. Type: '{snapshot_type}'. Format: {export_format}", level="INFO")

    details = {"snapshot_type_processed": snapshot_type, "format_used": export_format}
    reward = 0.0
    outcome = "pending"
    exported_content = None # This would be the actual data to export

    # Placeholder for actual data retrieval logic based on snapshot_type
    # This would involve calls to MetaAgent, KnowledgeBase, IdentityEngine etc.
    # For now, we simulate some data.
    if snapshot_type == "active_agents_summary":
        exported_content = {"info": "Simulated summary of active agents", "count": len(all_agent_names_in_system)}
        outcome = "success_agents_summary_exported"
        reward = 0.25
    elif snapshot_type == "knowledge_base_stats":
        exported_content = {"info": "Simulated KB statistics", "size": knowledge.get_size() if hasattr(knowledge, 'get_size') else "N/A"}
        outcome = "success_kb_stats_exported"
        reward = 0.2
    elif snapshot_type == "system_identity_full":
        identity_engine: 'IdentityEngine' = getattr(agent, 'identity_engine', getattr(getattr(agent, 'meta_agent', None), 'identity_engine', None))
        exported_content = identity_engine.get_identity() if identity_engine else {"error": "IdentityEngine not found"}
        outcome = "success_system_identity_exported"
        reward = 0.3
    elif snapshot_type == "system_performance_profile":
        identity_engine: 'IdentityEngine' = getattr(agent, 'identity_engine', getattr(getattr(agent, 'meta_agent', None), 'identity_engine', None))
        # Assuming IdentityEngine has a way to get the latest profile, or it's part of get_identity()
        exported_content = identity_engine.get_identity().get("dominant_traits", {}) if identity_engine else {"error": "IdentityEngine not found"}
        outcome = "success_system_performance_exported"
        reward = 0.3
    else:
        outcome = "failure_unsupported_snapshot_type"
        details["error"] = f"Unsupported snapshot_type: {snapshot_type}"
        reward = -0.15

    if outcome.startswith("success"):
        if export_format == "json":
            details["exported_data_preview"] = str(exported_content)[:200] + "..." if len(str(exported_content)) > 200 else str(exported_content)
        elif export_format == "text":
            details["exported_data_preview"] = json.dumps(exported_content, indent=2)[:200] + "..." if exported_content else "N/A"
        else:
            outcome = "failure_unsupported_format"
            details["error"] = f"Unsupported export format: {export_format}"
            reward = -0.1

    return {"outcome": outcome, "reward": reward, "details": details}

# --- Self-registration ---
try:
    from core.capability_executor import register_capability
    register_capability("export_agent_evolution_v1", execute_export_agent_evolution_v1)
    register_capability("export_system_snapshot_v1", execute_export_system_snapshot_v1)
    log("[ExportHandlers] Successfully registered export handlers.", level="DEBUG")
except ImportError:
    log("[ExportHandlers] Critical: Could not import 'register_capability'. Handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[ExportHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)
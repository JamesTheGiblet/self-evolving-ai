# c:/Users/gilbe/Desktop/self-evolving-ai/capability_handlers/insight_handlers.py
"""
Capability Handlers for Insight Generation and Diagnostics.
"""
import copy
import json
import re
import time
import uuid
from typing import Dict, List, Any, TYPE_CHECKING, Optional

from utils.logger import log
from core.utils.data_extraction import _get_value_from_path

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager


def _compare_values(value_to_check: Any, operator: str, rule_value: Any) -> bool:
    """Helper to evaluate a single condition for insight rules."""
    if value_to_check is None and operator not in ["exists", "not_exists"]: # Most operators fail if value is None
        return False
    try:
        if operator == "==": return value_to_check == rule_value
        if operator == "!=": return value_to_check != rule_value
        if operator == ">": return float(value_to_check) > float(rule_value)
        if operator == "<": return float(value_to_check) < float(rule_value)
        if operator == ">=": return float(value_to_check) >= float(rule_value)
        if operator == "<=": return float(value_to_check) <= float(rule_value)
        if operator == "contains": return isinstance(value_to_check, (str, list, dict)) and rule_value in value_to_check
        if operator == "not_contains": return isinstance(value_to_check, (str, list, dict)) and rule_value not in value_to_check
        if operator == "exists": return value_to_check is not None
        if operator == "not_exists": return value_to_check is None
        if operator == "in": # Added 'in' operator for checking if value_to_check is in rule_value (list)
            return isinstance(rule_value, list) and value_to_check in rule_value
    except (ValueError, TypeError) as e:
        log(f"Condition evaluation error: {e} for value '{value_to_check}' {operator} '{rule_value}'", level="WARN")
        return False
    log(f"Unsupported operator: {operator} for value '{value_to_check}' and rule_value '{rule_value}'", level="WARN")
    return False

def _format_insight_text(template_text: str, symptom: Dict, context_data: Dict) -> str:
    """Formats insight text by replacing placeholders."""
    def replace_match(match):
        full_path = match.group(1)
        if full_path.startswith("symptom."):
            return str(_get_value_from_path(symptom, full_path[len("symptom."):]))
        elif full_path.startswith("context."):
            # Path like "context.dataSourceName.key.subkey"
            parts = full_path[len("context."):].split('.', 1)
            if len(parts) == 2:
                source_name, key_path = parts
                if source_name in context_data:
                    return str(_get_value_from_path(context_data[source_name], key_path))
        return match.group(0) # Return original if not replaceable

    return re.sub(r"\{([^}]+)\}", replace_match, template_text)


def execute_triangulated_insight_v1(agent: 'BaseAgent', params_used: dict, cap_inputs: dict, knowledge: 'KnowledgeBase', context: 'ContextManager', all_agent_names_in_system: list):
    """
    Synthesizes insights by correlating a primary symptom with multiple contextual data points.
    """
    symptom_source_param = params_used.get("symptom_source", "agent_state")
    symptom_key_in_state_param = params_used.get("symptom_key_in_state", "last_failed_skill_details")
    default_symptom_param = params_used.get("default_symptom_if_none", {"type": "generic_observation", "detail": "No specific symptom."})
    contextual_data_sources_config = params_used.get("contextual_data_sources", [])
    insight_rules_config = params_used.get("insight_rules", [])

    log_entries_for_capability = [] # Store detailed logs for this capability execution

    primary_symptom = None
    symptom_log_details = {"source_type": symptom_source_param}

    # 1. Observe/Retrieve Primary Symptom
    if symptom_source_param == "agent_state":
        primary_symptom = agent.state.get(symptom_key_in_state_param)
        symptom_log_details["key_in_state"] = symptom_key_in_state_param
    elif symptom_source_param == "input_data":
        primary_symptom = cap_inputs.get("symptom_data") # Expecting symptom in cap_inputs
        symptom_log_details["key_in_input"] = "symptom_data"
    
    if not primary_symptom:
        primary_symptom = copy.deepcopy(default_symptom_param) # Use a copy to avoid modifying the original
        # Update timestamp and tick for default symptom
        primary_symptom["timestamp"] = time.time()
        primary_symptom["tick"] = context.get_tick()
        log(f"[{agent.name}] TriangulatedInsight: No primary symptom found/provided from '{symptom_source_param}', using default.", level="INFO")

    # Ensure primary_symptom has a 'tick' or 'timestamp' for time-based context queries
    if "tick" not in primary_symptom and "timestamp" not in primary_symptom:
        primary_symptom["tick"] = context.get_tick() # Add current tick if missing
    
    symptom_log_details["data_observed"] = copy.deepcopy(primary_symptom) if primary_symptom else None
    log_entries_for_capability.append({"step": "ObservePrimarySymptom", "details": symptom_log_details})
    
    if not primary_symptom: # Should not happen if default_symptom_param is always a dict
        log(f"[{agent.name}] TriangulatedInsight: Critical - No symptom available, even after default.", level="ERROR")
        return {"outcome": "failure_no_symptom_critical", "reward": -0.2, "details": {"error": "No symptom data available."}, "logs": log_entries_for_capability}

    best_insight_text: Optional[str] = None
    highest_confidence = -1.0
    applied_rule_name: Optional[str] = None
    final_diagnosis_output: Optional[Dict[str, Any]] = None
    contributing_factors_for_best_insight: List[Dict[str, Any]] = []

    # Log the primary symptom being processed
    current_tick = agent.context_manager.get_tick()
    log(f"[{agent.name}] TriangulatedInsight: Processing Symptom ID '{primary_symptom.get('symptom_id', 'N/A')}': {str(primary_symptom)[:200]}", level="INFO")

    # 1. Gather Contextual Data
    contextual_data: Dict[str, Any] = {}
    context_data_log_list = [] # For logging context gathering

    for src_config in contextual_data_sources_config:
        source_name = src_config.get("name", "unnamed_context_source")
        source_type = src_config.get("type")
        query_details_template = src_config.get("query_details", {})
        symptom_keys_for_query = src_config.get("symptom_keys_for_query", [])
        data_from_source = None
        log_entry_for_context = {"source_name": source_name, "type": source_type, "query_attempted": copy.deepcopy(query_details_template), "data_summary": None}

        # Check if all required symptom keys for this query are present
        can_query = True
        if symptom_keys_for_query:
            for skey in symptom_keys_for_query:
                if _get_value_from_path(primary_symptom, skey) is None:
                    can_query = False
                    log(f"[{agent.name}] TriangulatedInsight: Skipping context source '{source_name}' because required symptom key '{skey}' is missing.", level="DEBUG")
                    break
        if not can_query:
            contextual_data[source_name] = {"error": "skipped_missing_symptom_key"}
            log_entry_for_context["data_summary"] = "Skipped due to missing symptom key for query."
            context_data_log_list.append(log_entry_for_context)
            continue

        if source_type == "knowledge_base":
            final_query_params = copy.deepcopy(query_details_template)
            symptom_timestamp_for_query = primary_symptom.get("tick", primary_symptom.get("timestamp", context.get_tick()))

            if symptom_keys_for_query:
                for skey_path in symptom_keys_for_query:
                    symptom_value = _get_value_from_path(primary_symptom, skey_path)
                    if symptom_value is not None:
                        final_query_params[skey_path] = symptom_value
                    else:
                        log(f"[{agent.name}] TriangulatedInsight: Symptom key '{skey_path}' resolved to None for query construction for '{source_name}'. This might lead to an ineffective KB query.", level="WARNING")

            if "data_matches" in final_query_params and isinstance(final_query_params["data_matches"], dict):
                for key, value in list(final_query_params["data_matches"].items()): 
                    if isinstance(value, str) and value.startswith("<FROM_SYMPTOM:") and value.endswith(">"):
                        path = value[len("<FROM_SYMPTOM:"):-1]
                        resolved_value = _get_value_from_path(primary_symptom, path)
                        if resolved_value is not None:
                            final_query_params["data_matches"][key] = resolved_value
                        else:
                            log(f"[{agent.name}] TriangulatedInsight: Could not resolve placeholder '{value}' for KB query. Removing match key '{key}'.", level="WARNING")
                            del final_query_params["data_matches"][key] 
            
            if "min_tick_offset_from_symptom" in final_query_params:
                final_query_params["min_tick"] = int(symptom_timestamp_for_query + final_query_params.pop("min_tick_offset_from_symptom"))
            if "max_tick_offset_from_symptom" in final_query_params:
                final_query_params["max_tick"] = int(symptom_timestamp_for_query + final_query_params.pop("max_tick_offset_from_symptom"))

            query_lineage_id = src_config.get("lineage_id_for_query", agent.state.get("lineage_id"))
            retrieved_full_entries = knowledge.retrieve_full_entries(
                lineage_id=query_lineage_id, 
                query_params=final_query_params,
                current_tick=context.get_tick()) 
            
            if source_name == "skill_agent_performance_history":
                if retrieved_full_entries: 
                    data_from_source = retrieved_full_entries[0]['data'] 
                else: 
                    data_from_source = {"failure_rate": 0.0, "execution_count": 0, "message": "No pre-calculated performance summary found."}
            elif source_name == "recent_system_errors":
                 data_from_source = {"error_log_count": len(retrieved_full_entries), "errors_sample": [e['data'] for e in retrieved_full_entries[:2]]}
            else: 
                data_from_source = {"count": len(retrieved_full_entries), "items_sample": [e['data'] for e in retrieved_full_entries[:2]]} if retrieved_full_entries else []

            log_entry_for_context["query_executed"] = final_query_params
            log_entry_for_context["data_summary"] = f"Retrieved {len(retrieved_full_entries)} full entries. Processed to: {str(data_from_source)[:100]}..."
            log(f"[{agent.name}] TriangulatedInsight: Context from KB ('{source_name}'): {log_entry_for_context['data_summary']}")
        else:
            log(f"[{agent.name}] TriangulatedInsight: Unknown contextual data source type: {source_type}", level="WARN")
            data_from_source = {"error": f"Unknown source type: {source_type}"}
            log_entry_for_context["data_summary"] = "Unknown source type"
        
        contextual_data[source_name] = data_from_source
        context_data_log_list.append(log_entry_for_context)
    log_entries_for_capability.append({"step": "GatherContextualData", "details": context_data_log_list})

    # 2. Synthesize an Insight using Rules
    for rule_config in insight_rules_config:
        log_entry_for_rule = {"rule_name": rule_config.get("name", "unnamed_rule"), "conditions_checked": [], "triggered": False}
        rule_conditions_met = True
        rule_name = rule_config.get("name", "unnamed_rule")
        current_rule_contributing_factors: List[Dict[str, Any]] = []

        for condition_config in rule_config.get("conditions", []):
            condition_source_name = condition_config.get("source") 
            condition_key_path = condition_config.get("key_path")
            condition_operator = condition_config.get("operator")
            condition_value_config = condition_config.get("value")

            condition_check_log = {
                "source": condition_source_name,
                "key_path": condition_key_path,
                "operator": condition_operator,
                "config_value": condition_value_config
            }
            
            actual_value = None
            data_source_for_condition = None
            if condition_source_name == "symptom":
                data_source_for_condition = primary_symptom
                actual_value = _get_value_from_path(primary_symptom, condition_key_path)
            elif condition_source_name == "context":
                context_data_source_name = condition_config.get("data_source_name")
                if context_data_source_name in contextual_data:
                    data_source_for_condition = contextual_data[context_data_source_name]
                    actual_value = _get_value_from_path(contextual_data[context_data_source_name], condition_key_path)
                else:
                    log(f"[{agent.name}] TriangulatedInsight: Rule '{rule_name}', Condition: Context source '{context_data_source_name}' not found in gathered data.", level="DEBUG")
                    rule_conditions_met = False
                    break
            condition_check_log["actual_value_raw"] = actual_value

            if isinstance(condition_value_config, str) and condition_value_config.startswith("<FROM_SYMPTOM:") and condition_value_config.endswith(">"):
                placeholder_path = condition_value_config[len("<FROM_SYMPTOM:"):-1]
                condition_value = _get_value_from_path(primary_symptom, placeholder_path)
            else:
                condition_value = condition_value_config
            condition_check_log["resolved_config_value"] = condition_value

            if not _compare_values(actual_value, condition_operator, condition_value):
                rule_conditions_met = False
                log(f"[{agent.name}] TriangulatedInsight: Rule '{rule_name}', Condition FAILED: {actual_value} {condition_operator} {condition_value} (Path: {condition_key_path})", level="DEBUG")
                condition_check_log["met"] = False
                log_entry_for_rule["conditions_checked"].append(condition_check_log)
                break
            else:
                current_rule_contributing_factors.append({
                    "factor": f"Condition met: {condition_key_path} ({actual_value}) {condition_operator} {condition_value}",
                    "evidence_source": condition_source_name,
                    "data_point": {condition_key_path: actual_value}
                })
                log(f"[{agent.name}] TriangulatedInsight: Rule '{rule_name}', Condition PASSED: {actual_value} {condition_operator} {condition_value}", level="DEBUG")
                condition_check_log["met"] = True
            log_entry_for_rule["conditions_checked"].append(condition_check_log)
        
        log_entry_for_rule["triggered"] = rule_conditions_met
        log_entries_for_capability.append(log_entry_for_rule)

        if rule_conditions_met and current_rule_contributing_factors: 
            log(f"[{agent.name}] TriangulatedInsight: Rule '{rule_name}' triggered.", level="INFO")
            current_confidence = rule_config.get("confidence", 0.5)
            
            if current_confidence > highest_confidence:
                highest_confidence = current_confidence
                best_insight_text = _format_insight_text(rule_config.get("insight_text", "No insight text defined."), primary_symptom, contextual_data)
                applied_rule_name = rule_name
                contributing_factors_for_best_insight = current_rule_contributing_factors

    # 3. Determine Outcome and Reward
    outcome_status = "success_no_specific_insight"
    reward = 0.05 

    if best_insight_text:
        outcome_status = f"success_insight_generated_by_{applied_rule_name}"
        reward = 0.3 + (highest_confidence * 0.4) + (min(len(contributing_factors_for_best_insight), 5) * 0.05) 
        reward = max(0.1, min(reward, 0.95)) 

        diagnosis_id = f"diag_{current_tick}_{uuid.uuid4().hex[:6]}"
        final_diagnosis_output = {
            "diagnosis_id": diagnosis_id,
            "symptom_id": primary_symptom.get("symptom_id", "unknown_symptom"),
            "timestamp": time.time(),
            "tick": current_tick,
            "diagnosing_agent_id": agent.name,
            "rule_applied": applied_rule_name,
            "root_cause_hypothesis": best_insight_text, 
            "confidence": highest_confidence,
            "contributing_factors": contributing_factors_for_best_insight,
            "suggested_actions": rule_config.get("suggested_action_flags", []) 
        }
        log(f"[{agent.name}] TriangulatedInsight: Final Diagnosis: {final_diagnosis_output}", level="INFO")

        diagnosis_lineage_id = agent.state.get("lineage_id", "system_diagnostics") 
        knowledge.store(
            lineage_id=diagnosis_lineage_id,
            storing_agent_name=agent.name,
            item={
                "event_type": "diagnosis_report",
                "diagnosis_data": final_diagnosis_output,
                "primary_symptom_processed": primary_symptom 
            },
            tick=current_tick
        )

    if agent.context_manager and hasattr(agent.context_manager, 'post_insight_to_gui'):
        agent.context_manager.post_insight_to_gui(final_diagnosis_output)

    log(f"[{agent.name}] TriangulatedInsight: Final Outcome: {outcome_status}. Best Insight Text: {best_insight_text}", level="INFO")

    return {
        "outcome": outcome_status,
        "reward": reward,
        "diagnosis": final_diagnosis_output, 
        "raw_symptom": primary_symptom,
        "gathered_context_data": contextual_data,
        "logs": log_entries_for_capability
    }
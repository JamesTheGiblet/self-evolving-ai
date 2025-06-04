# c:\Users\gilbe\Desktop\self-evolving-ai\capability_handlers\sequence_handlers.py

import copy
import random
import time
from typing import Dict, Any, List, TYPE_CHECKING

from utils.logger import log
from core.context_manager import ContextManager
from core.skill_definitions import SKILL_CAPABILITY_MAPPING # Used by execute_sequence_executor_v1
from core.utils.data_extraction import _get_value_from_path # Import from new location

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase
else:
    BaseAgent = Any
    KnowledgeBase = Any

# If this file needs execute_invoke_skill_agent_v1 (e.g., for a very specific sequence step,
# though unlikely as invoke_skill_agent_v1 is usually called by the main executor),
# it should import it from its canonical location:
# from core.capability_handlers import execute_invoke_skill_agent_v1

def execute_sequence_executor_v1(agent: BaseAgent, params_used: dict, cap_inputs: dict, knowledge: KnowledgeBase, context: ContextManager, all_agent_names_in_system: list):
    """Executes the sequence_executor_v1 capability."""
    outcome = "pending"
    details = {}

    # --- START: Handling for sequence resumption after a synchronous step ---
    if cap_inputs.get("resuming_sequence_after_sync_step") == True:
        sequence_state_for_resume = cap_inputs.get("sequence_state_for_resume", {})
        resolved_sync_step_result = cap_inputs.get("resolved_sync_step_result")

        # Restore state from sequence_state_for_resume
        sub_sequence_def = sequence_state_for_resume.get("sequence_def_being_executed", [])
        sequence_source_log = sequence_state_for_resume.get("sequence_source_log_for_resume", "resumed_unknown_source")
        stop_on_failure = sequence_state_for_resume.get("stop_on_failure_for_sequence", True)
        pass_outputs_flag = sequence_state_for_resume.get("pass_outputs_flag_for_sequence", False)
        max_depth = sequence_state_for_resume.get("max_depth_for_sequence", 3)
        current_depth = sequence_state_for_resume.get("current_depth_for_sequence", 0)
        previous_step_full_output = sequence_state_for_resume.get("previous_step_full_output_for_resume", {})
        total_sequence_reward = sequence_state_for_resume.get("total_sequence_reward_so_far", 0.0)
        executed_sub_caps_details = sequence_state_for_resume.get("executed_sub_caps_details_so_far", [])
        
        step_idx_resuming_at = sequence_state_for_resume.get("current_step_index_paused", -1)
        log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' RESUMING sequence (Source: {sequence_source_log}) at step index {step_idx_resuming_at} after sync call.")
    # --- END: Handling for sequence resumption ---
    else: # Normal sequence start
        # Determine the actual sequence to execute
        # Priority: cap_inputs["sub_sequence"] > agent.capability_params[params_used["sub_sequence_param_key_to_use"]]["sub_sequence"] > params_used["sub_sequence"]
        sub_sequence_def = []
        sequence_source_log = "unknown"

        if "sub_sequence" in cap_inputs:
            sub_sequence_def = cap_inputs.get("sub_sequence", [])
            sequence_source_log = "cap_inputs_direct"
        elif "sub_sequence_param_key_to_use" in cap_inputs:
            key_from_inputs = cap_inputs.get("sub_sequence_param_key_to_use")
            if key_from_inputs and key_from_inputs in agent.capability_params and "sub_sequence" in agent.capability_params[key_from_inputs]:
                sub_sequence_def = agent.capability_params[key_from_inputs]["sub_sequence"]
                sequence_source_log = f"cap_inputs_key:{key_from_inputs}"

        if not sub_sequence_def: # Fallback to params_used if not found via cap_inputs
            if "sub_sequence_param_key_to_use" in params_used:
                key_from_params = params_used.get("sub_sequence_param_key_to_use")
                if key_from_params and key_from_params in agent.capability_params and "sub_sequence" in agent.capability_params[key_from_params]:
                    sub_sequence_def = agent.capability_params[key_from_params]["sub_sequence"]
                    sequence_source_log = f"params_used_key:{key_from_params}"

            if not sub_sequence_def: # Final fallback to direct sub_sequence in params_used
                sub_sequence_def = params_used.get("sub_sequence", [])
                sequence_source_log = "params_used_direct"

        # Sequence-level parameters
        # Priority: cap_inputs > params_used (capability's own default params)
        # For sub_sequence_def, priority is already handled above.
        # For other controls like stop_on_failure, pass_outputs, max_depth:
        # If a sub_sequence was loaded from agent.capability_params[key_from_inputs],
        # those params should ideally take precedence for these controls too.
        # Current logic: cap_inputs for these controls override params_used. This is simpler.
        stop_on_failure = cap_inputs.get("stop_on_failure", params_used.get("stop_on_failure", True)) # True if not in cap_inputs, then from params_used
        pass_outputs_flag = cap_inputs.get("pass_outputs", params_used.get("pass_outputs", False)) # False if not in cap_inputs, then from params_used
        max_depth = cap_inputs.get("max_depth", params_used.get("max_depth", 3))
        current_depth = cap_inputs.get("current_sequence_depth", 0)
        previous_step_full_output = cap_inputs.get("previous_step_output", {}) # For sequence resumption or initial state
        total_sequence_reward = 0.0
        executed_sub_caps_details = []
        step_idx_resuming_at = -1 # Not resuming
        resolved_sync_step_result = None # No resolved sync result for a fresh start

        if not sub_sequence_def:
            log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' received empty sequence (Source: {sequence_source_log}). Outcome: success_empty_sequence.")
            return {"outcome": "success_empty_sequence", "details": {"step_results": [], "sub_sequence_length": 0, "sequence_source": sequence_source_log}, "reward": 0.0}
        log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' starting sequence (Source: {sequence_source_log}): {str(sub_sequence_def)[:200]}... at depth {current_depth}")
    
    total_sequence_reward = 0.0
    # `total_sequence_reward` and `executed_sub_caps_details` are correctly initialized
    # within the `if` (resuming) or `else` (normal start) blocks.
    # `previous_step_full_output` is also correctly set in those blocks.
    sequence_successful = True
    
    # This stores the 'details' of the last successful step for the sequence's final report.
    final_output_details_from_last_success = previous_step_full_output.get("details", {})

    for step_idx, step_definition in enumerate(sub_sequence_def):
        # If resuming, skip steps already processed or the one that was pending
        if step_idx_resuming_at != -1 and step_idx <= step_idx_resuming_at:
            if step_idx < step_idx_resuming_at: # Already processed and in executed_sub_caps_details
                continue
            # If step_idx == step_idx_resuming_at, this is the step that was sync; use resolved_sync_step_result

        if current_depth >= max_depth:
            log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' sequence exceeded max depth ({max_depth}). Stopping.")
            sequence_successful = False
            total_sequence_reward -= 0.5 # Penalty for hitting max depth
            break

        actual_sub_cap_name = ""
        step_specific_inputs_template = {}
        step_params_override = {}

        if isinstance(step_definition, str):
            actual_sub_cap_name = step_definition
        elif isinstance(step_definition, dict):
            actual_sub_cap_name = step_definition.get("name")
            step_specific_inputs_template = step_definition.get("inputs", {})
            step_params_override = step_definition.get("params_override", {})
        else:
            log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' encountered invalid step definition format: {step_definition}. Skipping.")
            # Consider if this should be a failure based on stop_on_failure
            continue

        if not actual_sub_cap_name:
            log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' step definition missing 'name': {step_definition}. Skipping.")
            continue

        if actual_sub_cap_name == "sequence_executor_v1": # Prevent direct recursion from within its own sequence definition
            log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' attempted to execute itself directly in sequence. Skipping step to prevent infinite loop.")
            # This is usually a failure of the sequence logic, not the executor itself.
            # Depending on stop_on_failure, the sequence might continue or stop.
            # We'll treat this as a step failure for reward calculation.
            sequence_successful = False # Mark sequence as having a problem
            total_sequence_reward -= 0.5 # Penalize this misconfiguration
            executed_sub_caps_details.append({
                "name": actual_sub_cap_name,
                "outcome": "failure_recursive_self_call_skipped",
                "reward": -0.5,
                "details": {"error": "Sequence attempted to call sequence_executor_v1 recursively on itself."}
            })
            if stop_on_failure:
                break
            continue

        if actual_sub_cap_name not in agent.capabilities:
            err_msg = f"Capability '{actual_sub_cap_name}' not available to agent '{str(agent.name)}'."
            log(f"[{str(agent.name)}] SeqExec: {err_msg}", level="ERROR")
            sub_log_entry = {
                "outcome": f"failure_step_{step_idx}_{actual_sub_cap_name}_not_available",
                "reward": params_used.get("default_reward_for_failure", -0.1),
                "details": {"error": err_msg}
            }
            executed_sub_caps_details.append({"name": actual_sub_cap_name, "outcome": sub_log_entry["outcome"], "reward": sub_log_entry["reward"], "details": sub_log_entry["details"]})
            total_sequence_reward += sub_log_entry["reward"]
            sequence_successful = False
            if stop_on_failure: break
            continue

        # Prepare inputs for the current step
        current_step_inputs = {}
        # 1. Start with inputs defined in the sequence step's "inputs" field
        current_step_inputs.update(copy.deepcopy(step_specific_inputs_template))

        # 2. Handle 'pass_outputs' from the previous step to the current step.
        pass_outputs_for_this_step = step_definition.get("pass_outputs", pass_outputs_flag) if isinstance(step_definition, dict) else pass_outputs_flag

        if pass_outputs_for_this_step and previous_step_full_output: # Check if previous_step_full_output is not empty
            if isinstance(pass_outputs_for_this_step, dict): # Selective mapping from previous full output
                for prev_key, current_key in pass_outputs_for_this_step.items():
                    value_to_pass = _get_value_from_path(previous_step_full_output, prev_key)
                    if value_to_pass is not None:
                        current_step_inputs[current_key] = value_to_pass
            elif isinstance(pass_outputs_for_this_step, bool) and pass_outputs_for_this_step: # Pass 'details' part
                # Merge, ensuring step_specific_inputs_template takes precedence if keys overlap
                details_from_previous = previous_step_full_output.get("details", {})
                if details_from_previous: # Only merge if details exist
                    temp_merged = details_from_previous.copy()
                    temp_merged.update(current_step_inputs)
                    current_step_inputs = temp_merged

        # Resolve placeholders like "<FROM_PREVIOUS_STEP:key.subkey>"
        # The source for placeholders is always the full output of the previous step.
        source_for_placeholders = previous_step_full_output

        # Iterate over a copy of items for safe modification
        for key, value in list(current_step_inputs.items()):
            if isinstance(value, str) and value.startswith("<FROM_PREVIOUS_STEP:") and value.endswith(">"):
                path = value[len("<FROM_PREVIOUS_STEP:"):-1]
                try:
                    # Ensure source_for_placeholders is a dict before calling _get_value_from_path if path is not empty
                    if not isinstance(source_for_placeholders, dict) and path:
                        raise ValueError(f"Cannot resolve path '{path}' because previous step output is not a dictionary. Output: {str(source_for_placeholders)[:100]}")

                    resolved_value = _get_value_from_path(source_for_placeholders, path)
                    if resolved_value is not None:
                        current_step_inputs[key] = resolved_value
                        log(f"[{str(agent.name)}] SeqExec: Resolved placeholder '{value}' to '{str(resolved_value)[:50]}' for key '{key}'.")
                    else:
                        # If resolved_value is None, it means the path was valid but led to None, or path was invalid.
                        # This is treated as a failure to resolve if the placeholder was expected to yield a value.
                        # Allow explicit None to be passed if that's what the path resolves to.
                        # The error should be if the path itself is bad or not found, which _get_value_from_path handles by returning None.
                        log(f"[{str(agent.name)}] SeqExec: Placeholder '{value}' (path: '{path}') resolved to None or was not found in previous step output: {str(source_for_placeholders)[:100]}. Using None.", level="DEBUG")
                        current_step_inputs[key] = None # Explicitly set to None if path leads to it or is invalid
                except Exception as e:
                    err_msg = f"Failed to resolve placeholder '{value}' for key '{key}'. Error: {e}"
                    log(f"[{str(agent.name)}] SeqExec: {err_msg}", level="ERROR")
                    sub_log_entry = {
                        "outcome": f"failure_step_{step_idx}_{actual_sub_cap_name}_placeholder_resolution",
                        "reward": -0.2, # Specific penalty for placeholder failure
                        "details": {"error": err_msg, "placeholder": value}
                    }
                    executed_sub_caps_details.append({"name": actual_sub_cap_name, "outcome": sub_log_entry["outcome"], "reward": sub_log_entry["reward"], "details": sub_log_entry["details"]})
                    total_sequence_reward += sub_log_entry["reward"]
                    sequence_successful = False
                    break # Break from placeholder resolution loop for this step
            # Also resolve placeholders within nested structures if necessary (e.g., in request_data for invoke_skill_agent_v1)
            elif isinstance(value, dict):
                # Simple one-level deep resolution for common cases like request_data
                for sub_key, sub_value in list(value.items()):
                    if isinstance(sub_value, str) and sub_value.startswith("<FROM_PREVIOUS_STEP:") and sub_value.endswith(">"):
                        path = sub_value[len("<FROM_PREVIOUS_STEP:"):-1]
                        try:
                            if not isinstance(source_for_placeholders, dict) and path:
                                raise ValueError(f"Cannot resolve nested path '{path}' because previous step output is not a dictionary.")
                            resolved_sub_value = _get_value_from_path(source_for_placeholders, path)
                            if resolved_sub_value is not None:
                                current_step_inputs[key][sub_key] = resolved_sub_value
                                log(f"[{str(agent.name)}] SeqExec: Resolved nested placeholder '{sub_value}' to '{str(resolved_sub_value)[:50]}' for key '{key}.{sub_key}'.")
                            else:
                                log(f"[{str(agent.name)}] SeqExec: Nested placeholder '{sub_value}' (path: '{path}') resolved to None or was not found. Using None.", level="DEBUG")
                                current_step_inputs[key][sub_key] = None
                        except Exception as e:
                            err_msg = f"Failed to resolve nested placeholder '{sub_value}' for key '{key}.{sub_key}'. Error: {e}"
                            log(f"[{str(agent.name)}] SeqExec: {err_msg}", level="ERROR")
                            sub_log_entry = {
                                "outcome": f"failure_step_{step_idx}_{actual_sub_cap_name}_nested_placeholder_resolution",
                                "reward": -0.2,
                                "details": {"error": err_msg, "placeholder": sub_value}
                            }
                            executed_sub_caps_details.append({"name": actual_sub_cap_name, "outcome": sub_log_entry["outcome"], "reward": sub_log_entry["reward"], "details": sub_log_entry["details"]})
                            total_sequence_reward += sub_log_entry["reward"]
                            sequence_successful = False
                            break # Break from inner sub_key loop
                if not sequence_successful: # If inner loop broke due to error
                    break # Break from outer key loop

        # --- START: Default input for knowledge_storage_v1 if 'data_to_store' is missing ---
        if actual_sub_cap_name == "knowledge_storage_v1" and "data_to_store" not in current_step_inputs:
            # Try to get data from the previous step's output if pass_outputs was not explicitly false
            # and previous_step_full_output is not empty.
            # pass_outputs_for_this_step is determined earlier based on step_definition or sequence-level flag.
            data_from_prev_step_for_storage = None
            if previous_step_full_output and pass_outputs_for_this_step is not False:
                # Prefer 'details' if available and is a dict, else the whole output if it's a dict.
                if isinstance(previous_step_full_output.get("details"), dict):
                    data_from_prev_step_for_storage = previous_step_full_output["details"]
                elif isinstance(previous_step_full_output, dict): # Use the whole previous output if details isn't a dict
                    data_from_prev_step_for_storage = previous_step_full_output
            
            if data_from_prev_step_for_storage: # Ensure there's something to store
                current_step_inputs["data_to_store"] = copy.deepcopy(data_from_prev_step_for_storage) # Store a copy
                current_step_inputs.setdefault("category", "sequence_step_output") # Sensible default category
                current_step_inputs.setdefault("data_format", "application/json") # Assuming JSON-like structure
                log(f"[{str(agent.name)}] SeqExec: Auto-providing 'data_to_store' for '{actual_sub_cap_name}' from previous step output.", level="DEBUG")
            else: # Fallback default if previous step had no usable output or it's the first step
                current_step_inputs["data_to_store"] = {"source_capability": "sequence_executor_v1", "message": f"Default data stored by sequence for step {actual_sub_cap_name} at tick {context.get_tick()}", "previous_step_outcome": previous_step_full_output.get("outcome", "N/A") if previous_step_full_output else "N/A (first_step)"}
                current_step_inputs.setdefault("category", "sequence_default_log")
                log(f"[{str(agent.name)}] SeqExec: Providing default 'data_to_store' for '{actual_sub_cap_name}' as it was missing and no suitable previous output found.", level="DEBUG")
        # --- END: Default input for knowledge_storage_v1 ---

        if not sequence_successful and stop_on_failure: # If placeholder resolution failed and we should stop
            break # Stop the main sequence loop

        # --- START: Smarter target_skill_agent_id resolution for sequences ---
        resolved_target_id_for_step = None
        if actual_sub_cap_name == "invoke_skill_agent_v1":
            # Check if target_skill_agent_id is present in the step's inputs or params_override
            # Priority: step_specific_inputs_template > step_params_override > agent.capability_params
            target_id_from_step_inputs = current_step_inputs.get("target_skill_agent_id")
            target_id_from_step_params = step_params_override.get("target_skill_agent_id")
            target_id_from_agent_default_params = agent.capability_params.get(actual_sub_cap_name, {}).get("target_skill_agent_id")

            original_target_id_in_sequence_def = target_id_from_step_inputs or target_id_from_step_params or target_id_from_agent_default_params

            if original_target_id_in_sequence_def and original_target_id_in_sequence_def.split('-gen')[0] == original_target_id_in_sequence_def: # Heuristic: it's a lineage ID
                target_lineage = original_target_id_in_sequence_def
                skill_action_for_resolution = current_step_inputs.get("skill_action_to_request") or \
                                              step_params_override.get("default_skill_action_to_attempt") or \
                                              agent.capability_params.get(actual_sub_cap_name, {}).get("default_skill_action_to_attempt")

                if skill_action_for_resolution and hasattr(agent, 'find_best_skill_agent_for_action'):
                    best_match_agent = agent.find_best_skill_agent_for_action(skill_action_for_resolution, preferred_target_id=target_lineage) # Pass lineage as preferred
                    if best_match_agent:
                        # Override the target_skill_agent_id in current_step_inputs if it was there,
                        # or in step_params_override if it came from there.
                        # The _execute_capability will merge params, so we need to ensure the resolved one is used.
                        # A simple way is to put it into current_step_inputs, which _execute_capability uses.
                        current_step_inputs["target_skill_agent_id"] = best_match_agent
                        resolved_target_id_for_step = best_match_agent
                        log(f"[{str(agent.name)}] SeqExec: Resolved lineage target '{target_lineage}' to live agent '{best_match_agent}' for action '{skill_action_for_resolution}'.")
                    else:
                        log(f"[{str(agent.name)}] SeqExec: Could not resolve lineage target '{target_lineage}' for action '{skill_action_for_resolution}'. Using original: '{original_target_id_in_sequence_def}'.", level="WARNING")
                else:
                    log(f"[{str(agent.name)}] SeqExec: Cannot resolve lineage target '{original_target_id_in_sequence_def}'. Missing skill_action or agent lacks find_best_skill_agent_for_action.", level="WARNING")
         # --- END: Smarter target_skill_agent_id resolution ---


        # Check if resolution failed for an invoke_skill_agent_v1 step that used a lineage ID
        is_lineage_id_target_heuristic = False
        if actual_sub_cap_name == "invoke_skill_agent_v1":
            # Check if the target_skill_agent_id (after potential overrides) looks like a lineage ID
            final_target_id_for_check = current_step_inputs.get("target_skill_agent_id") or \
                                        step_params_override.get("target_skill_agent_id") or \
                                        agent.capability_params.get(actual_sub_cap_name, {}).get("target_skill_agent_id")
            if final_target_id_for_check and final_target_id_for_check.split('-gen')[0] == final_target_id_for_check:
                is_lineage_id_target_heuristic = True

        if actual_sub_cap_name == "invoke_skill_agent_v1" and is_lineage_id_target_heuristic and resolved_target_id_for_step is None:
            log(f"[{str(agent.name)}] SeqExec: Failing step for '{actual_sub_cap_name}' because lineage-based target '{final_target_id_for_check}' could not be resolved to a live, capable agent.", level="ERROR")
            sub_log_entry = {
                "outcome": "failure_target_resolution",
                "reward": -0.3,
                "details": {"error": f"Lineage target '{final_target_id_for_check}' for action '{current_step_inputs.get('skill_action_to_request')}' could not be resolved."}
            }
        else:
            # Explicitly prepare inputs for the sub-capability.
            # `current_step_inputs` contains inputs resolved from the sequence definition (placeholders, pass_outputs, etc.).
            # These act as overrides to any defaults the preparer might generate.
            prepared_inputs_for_sub_step = agent._prepare_capability_inputs(
                capability_name=actual_sub_cap_name,
                base_inputs_override=current_step_inputs
            )

            # Build the kwargs for _execute_capability.
            # This includes the fully prepared inputs and any step-specific parameter overrides.
            kwargs_for_execute_capability = prepared_inputs_for_sub_step.copy()

            if actual_sub_cap_name == "sequence_executor_v1": # Handle depth for recursive calls
                kwargs_for_execute_capability["current_sequence_depth"] = current_depth + 1
            if step_params_override: # Add step-specific params_override if defined
                kwargs_for_execute_capability["params_override"] = step_params_override

            # If resuming and this is the step that was sync, use the resolved result
            if step_idx_resuming_at != -1 and step_idx == step_idx_resuming_at and resolved_sync_step_result:
                sub_log_entry = resolved_sync_step_result
                log(f"[{str(agent.name)}] SeqExec: Using resolved sync step result for '{actual_sub_cap_name}': {sub_log_entry.get('outcome')}")
            else:
                sub_log_entry = agent._execute_capability(
                    actual_sub_cap_name,
                    context,
                    knowledge,
                    all_agent_names_in_system,
                    **kwargs_for_execute_capability
                )

        # --- START: Handle if sub-capability initiated a sync response ---
        if sub_log_entry.get("outcome") == "sync_request_sent_pending_response":
            log(f"[{str(agent.name)}] SeqExec: Step '{actual_sub_cap_name}' initiated a sync request. Pausing sequence.")
            # Sequence needs to pause and return a special outcome.
            # TaskAgent will store this state and resume sequence_executor later.
            return {
                "outcome": "sequence_paused_waiting_for_sync_step",
                "reward": 0.0, # No reward for the sequence itself yet
                "details": {
                    "sync_step_details": sub_log_entry["details"], # Contains request_id, timeout_at_tick, etc.
                    "current_step_index_paused": step_idx,
                    "sequence_def_being_executed": sub_sequence_def,
                    "pass_outputs_flag_for_sequence": pass_outputs_flag,
                    "stop_on_failure_for_sequence": stop_on_failure,
                    "max_depth_for_sequence": max_depth,
                    "current_depth_for_sequence": current_depth,
                    "previous_step_full_output_for_resume": previous_step_full_output,
                    "total_sequence_reward_so_far": total_sequence_reward,
                    "executed_sub_caps_details_so_far": executed_sub_caps_details,
                    "sequence_source_log_for_resume": sequence_source_log
                }
            }
        # --- END: Handle if sub-capability initiated a sync response ---

        executed_sub_caps_details.append({"name": actual_sub_cap_name, "outcome": sub_log_entry.get("outcome"), "reward": sub_log_entry.get("reward",0.0), "details": sub_log_entry.get("details", {})})
        total_sequence_reward += sub_log_entry.get("reward", 0.0)
        if 'success' in sub_log_entry.get("outcome", "").lower():
            previous_step_full_output = sub_log_entry # Store full output for next iteration's placeholders
            final_output_details_from_last_success = sub_log_entry.get("details", {}) # For sequence's final report
        else:
            previous_step_full_output = {} # Reset if step failed
            # final_output_details_from_last_success remains as is from the true last successful step

        if 'failure' in sub_log_entry.get("outcome", "").lower():
            sequence_successful = False
            if stop_on_failure:
                log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' sequence stopped due to failure in '{actual_sub_cap_name}'. Outcome: {sub_log_entry.get('outcome')}")
                break
            else:
                log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' failure in '{actual_sub_cap_name}' (stop_on_failure=False). Outcome: {sub_log_entry.get('outcome')}")

    outcome = "success" if sequence_successful else "failure_in_sub_sequence"
    details["sub_sequence_results"] = executed_sub_caps_details
    details["sub_sequence_length"] = len(sub_sequence_def)
    details["final_output_details"] = final_output_details_from_last_success # Include the details of the last successful step
    details["sequence_source"] = sequence_source_log

    # Reward scaling: Base reward is sum of step rewards.
    # Bonus for completing the whole sequence successfully.
    # Penalty if sequence fails overall but stop_on_failure was false.
    immediate_reward = total_sequence_reward
    if outcome == "success" and len(sub_sequence_def) > 0 :
        immediate_reward += 0.1 * len(sub_sequence_def) # Small bonus for successful completion
    elif outcome == "failure_in_sub_sequence" and not stop_on_failure:
        immediate_reward -= 0.2 # Small penalty for failing but continuing

    log(f"[{str(agent.name)}] Cap 'sequence_executor_v1' finished sequence. Outcome: {outcome}, Final Reward: {immediate_reward:.2f}")
    return {"outcome": outcome, "details": details, "reward": immediate_reward}

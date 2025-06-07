# core/capability_registry.py

import config # For default LLM model
import config as global_config # Import the main config file for global settings

CAPABILITY_REGISTRY = {
    "communication_broadcast_v1": {
        "id": "communication_broadcast_v1",
        "name": "Broadcast Message",
        "description": "Broadcasts a message to all other agents in the system.",
        "handler": "execute_communication_broadcast_v1", # Points to the function name string
        "params": { # Default parameters for this capability
            "message_content": "Default broadcast message",
            "signal_strength": 10, # Example: affects reach or energy cost
            "energy_cost": 0.1
        },
        "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "recipients_count": {"type": "integer"}}}
    },
    "knowledge_storage_v1": {
        "id": "knowledge_storage_v1",
        "name": "Store Knowledge",
        "description": "Stores a piece of information into the agent's memory or the shared knowledge base.",
        "handler": "execute_knowledge_storage_v1",
        "params": {
            "storage_type": "agent_memory", # or "knowledge_base"
            "data_format": "json",
            "energy_cost": 0.2,
            "compression_level": 1 # Example: 0 (none) to 9 (max)
        },
        "input_schema": {"type": "object", "properties": {"data_to_store": {"type": "object"}, "tags": {"type": "array", "items": {"type": "string"}}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "storage_id": {"type": "string"}}}
    },
    "knowledge_retrieval_v1": {
        "id": "knowledge_retrieval_v1",
        "name": "Retrieve Knowledge",
        "description": "Retrieves information from memory or knowledge base based on a query.",
        "handler": "execute_knowledge_retrieval_v1",
        "params": {
            "source_preference": ["agent_memory", "knowledge_base"],
            "max_results": 5,
            "energy_cost": 0.15,
            "max_depth": 3, # For hierarchical or linked data
            "specificity_filter": 0.5 # 0.0 (any match) to 1.0 (exact match)
        },
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "filters": {"type": "object"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "retrieved_data": {"type": "array"}}}
    },
    "data_analysis_basic_v1": {
        "id": "data_analysis_basic_v1",
        "name": "Basic Data Analysis",
        "description": "Performs basic statistical analysis on provided data or recent logs.",
        "handler": "execute_data_analysis_basic_v1",
        "params": {
            "analysis_depth": 2, # 1 (simple counts), 2 (mean/median), 3 (stddev/outliers)
            "data_source": "recent_logs", # or "input_data"
            "log_count_for_analysis": 20,
            "energy_cost": 0.3,
            "outlier_std_devs": 2.0, # Number of std deviations to consider an outlier
            "top_n_keywords": 5    # For text analysis part
        },
        "input_schema": {"type": "object", "properties": {"input_data_array": {"type": "array"}, "text_data_for_keywords": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "analysis_summary": {"type": "object"}}}
    },
    "data_analysis_v1": {
        "id": "data_analysis_v1",
        "name": "Advanced Data Analysis",
        "description": "Performs more advanced data analysis, potentially using external libraries or complex algorithms.",
        "handler": "execute_data_analysis_v1",
        "params": {
            "analysis_type": "correlation", # e.g., "correlation", "time_series", "clustering"
            "energy_cost": 0.7,
            "keywords": [], # For text analysis
            "regex_pattern": "" # For pattern matching in text
        },
        "input_schema": {"type": "object", "properties": {"dataset_ref": {"type": "string"}, "analysis_params": {"type": "object"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "report_summary": {"type": "object"}, "visualization_ref": {"type": "string"}}}
    },
    "invoke_skill_agent_v1": {
        "id": "invoke_skill_agent_v1",
        "name": "Invoke Skill Agent",
        "description": "Requests a SkillAgent to perform a specific skill/action.",
        "handler": "execute_invoke_skill_agent_v1",
        "params": {
            "default_skill_action_to_attempt": None, # e.g., "file_operation:read"
            "target_skill_agent_id": None, # Can be specified, or system tries to find suitable
            "timeout_duration": 5.0, # Seconds to wait for skill agent response
            "energy_cost": 0.25, # Base cost for invoking
            "success_reward": 0.75, # Reward multiplier on successful skill execution
            "failure_reward": -0.25, # Penalty on skill failure
            "timeout_reward": -0.1   # Penalty on timeout
        },
        "input_schema": {"type": "object", "properties": {"skill_action": {"type": "string"}, "skill_params": {"type": "object"}, "preferred_target_lineage": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "skill_response": {"type": "object"}, "target_agent_id": {"type": "string"}}}
    },
    "triangulated_insight_v1": {
        "id": "triangulated_insight_v1",
        "name": "Triangulated Insight Generation",
        "description": "Combines multiple data points (symptoms, logs, KB entries) to generate a diagnostic insight or hypothesis.",
        "handler": "execute_triangulated_insight_v1",
        "params": {
            "energy_cost": 0.8,
            "min_confidence_threshold": 0.6, # Minimum confidence for an insight to be considered significant
            "max_context_sources": 5,
            "symptom_source": "input_data", # "input_data" or "agent_state"
            "symptom_key_in_state": "last_reported_symptom", # if symptom_source is agent_state
            "default_symptom_if_none": {
                "symptom_id": "default_symptom_000", "timestamp": 0.0, "tick": 0,
                    "type": "generic_observation", "severity": "low", # Ensure 'type' is present
                "source_agent_id": "system", "source_agent_name": "SystemDefault",
                "details": {"description": "No specific symptom provided or found in state."},
                "related_data_refs": []
            },
            "contextual_data_sources": [ # Default configuration for data sources
                # Example: {"name": "recent_system_errors", "type": "knowledge_base", "query_details": {...}}
            ],
            "insight_rules": [ # Default configuration for insight generation rules
                # Example: {"name": "service_failure_correlation", "conditions": [...], "insight_text": "..."}
            ],
            "auto_trigger_on_high_failure": global_config.DEFAULT_AUTO_DIAGNOSIS_ENABLED,
            "min_attempts_for_failure_check": global_config.DEFAULT_MIN_ATTEMPTS_FOR_FAILURE_CHECK,
            "failure_rate_threshold_for_insight": global_config.DEFAULT_FAILURE_RATE_THRESHOLD_FOR_INSIGHT,
        },
        "input_schema": {"type": "object", "properties": {"primary_symptom_details": {"type": "object"}, "additional_context_data": {"type": "array"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "best_insight": {"type": "object"}, "all_insights": {"type": "array"}}}
    },
    "sequence_executor_v1": {
        "id": "sequence_executor_v1",
        "name": "Sequence Executor",
        "description": "Executes a predefined or dynamically generated sequence of capabilities.",
        "handler": "execute_sequence_executor_v1", # Points to the function name string
        "params": { # Default parameters for this capability
            "default_sequence_name": "default_operational_sequence", # To be defined in agent's capability_params
            "energy_cost_factor_per_step": 0.02 # Additional small cost per step in sequence
        },
        "input_schema": {"type": "object", "properties": {"sequence_name": {"type": "string"}, "dynamic_sequence": {"type": "array"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "total_reward": {"type": "number"}}}
    },
    "interpret_goal_with_llm_v1": {
        "id": "interpret_goal_with_llm_v1",
        "name": "Interpret Goal with LLM",
        "description": "Uses an LLM to parse a natural language user goal into a structured plan or internal goal.",
        "handler": "execute_interpret_goal_with_llm_v1",
        "params": {
            "llm_model": config.DEFAULT_LLM_MODEL,
            "energy_cost": 1.5, # Higher energy cost for LLM calls
            "max_tokens_response": 300
        },
        "input_schema": {"type": "object", "properties": {"user_query": {"type": "string"}, "current_system_context": {"type": "object"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "details": {"type": "object"}}}
    },
    "conversational_exchange_llm_v1": {
        "id": "conversational_exchange_llm_v1",
        "name": "Conversational Exchange with LLM",
        "description": "Engages in a conversational turn with a user or another entity using an LLM.",
        "handler": "execute_conversational_exchange_llm_v1",
        "params": {
            "llm_model": config.DEFAULT_LLM_MODEL,
            "energy_cost": 1.0,
            "max_history_turns": 5, # How many previous turns to consider
            "max_tokens_response": 200
        },
        "input_schema": {"type": "object", "properties": {"user_input_text": {"type": "string"}, "conversation_history": {"type": "array"}}},
        "output_schema": {"type": "object", "properties": {"outcome": {"type": "string"}, "details": {"type": "object"}}}
    },
    "export_agent_evolution_v1": {
        "id": "export_agent_evolution_v1",
        "name": "Export Agent Evolution History",
        "description": "Exports the evolution history of a specified agent or lineage to JSON or a file.",
        "handler": "execute_export_agent_evolution_v1",
        "params": {
            "default_identifier_type": "agent_id",
            "default_output_format": "json_string",
            "default_file_path_template": "agent_outputs/evolution_history_{identifier}.json",
            "energy_cost": 0.25
        },
        "input_schema": {
            "target_identifier": {"type": "string", "required": True, "description": "The agent_id or lineage_id to export history for."},
            "identifier_type": {"type": "string", "required": False, "description": "Type of identifier: 'agent_id' or 'lineage_id'."},
            "output_format": {"type": "string", "required": False, "description": "Output format: 'json_string' or 'file'."},
            "file_path": {"type": "string", "required": False, "description": "Path to save the file if output_format is 'file'."}
        },
        "output_schema": {
            "json_data": {"type": "string", "description": "JSON string of the history if output_format is 'json_string'."},
            "file_path": {"type": "string", "description": "Path to the saved file if output_format is 'file'."},
            "entry_count": {"type": "integer", "description": "Number of history entries exported."}
        }
    }
    # Add other capabilities here
}
 
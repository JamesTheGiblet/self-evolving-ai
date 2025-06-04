# core / roles.py

"""
Defines agent roles, their core/preferred capabilities, and mutation biases.
"""

AGENT_ROLES = {
    "generalist_task": {
        "description": "A general-purpose task agent.",
        "core_capabilities": ["sequence_executor_v1", "invoke_skill_agent_v1"],
        "preferred_capabilities": ["knowledge_storage_v1", "knowledge_retrieval_v1", "communication_broadcast_v1"],
        "mutation_biases": {"param_stability": 0.7} # Example bias: higher value means params are less likely to change drastically
    },
    "diagnoser_task": {
        "description": "Specialized in identifying and diagnosing system issues.",
        "core_capabilities": ["triangulated_insight_v1", "data_analysis_v1", "sequence_executor_v1"],
        "preferred_capabilities": ["knowledge_retrieval_v1", "data_analysis_basic_v1"],
        "mutation_biases": {"add_analytical_caps_factor": 1.5} # Example: 1.5x more likely to add analytical capabilities
    },
    "data_collector_task": {
        "description": "Focuses on gathering information from various sources.",
        "core_capabilities": ["knowledge_retrieval_v1", "invoke_skill_agent_v1"],
        "preferred_capabilities": ["knowledge_storage_v1", "web_services_v1", "file_services_v1"], # Assuming these map to invoke_skill_agent_v1 actions
        "mutation_biases": {"param_efficiency_web_file": 1.2} # Example: bias params for web/file ops towards efficiency
    },
    "data_analyzer_skill": {
        "description": "A skill agent focused on data analysis.",
        "core_capabilities": ["data_analysis_basic_v1"], # The capability it provides skills for
        "mutation_biases": {} # Skill agents might have simpler or different mutation biases
    },
    "web_skill": {
        "description": "A skill agent for web operations.",
        "core_capabilities": ["web_services_v1"],
        "mutation_biases": {}
    },
    "file_skill": {
        "description": "A skill agent for file operations.",
        "core_capabilities": ["file_services_v1"],
        "mutation_biases": {}
    },
    "api_skill": {
        "description": "A skill agent for generic API calls.",
        "core_capabilities": ["api_services_v1"],
        "mutation_biases": {}
    }
    # You can add more roles for task agents or other skill specializations here.
}
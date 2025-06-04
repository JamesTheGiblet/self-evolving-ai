# core/skill_definitions.py

"""
Defines mappings between high-level skill capabilities (advertised by SkillAgents)
and the specific actions/commands those capabilities can perform.

This is used by TaskAgents (via invoke_skill_agent_v1 and find_best_skill_agent_for_action)
to discover which SkillAgent can handle a particular requested action.

The keys are the primary capability names (e.g., "maths_ops_v1", "data_analysis_ops_v1")
that SkillAgents are initialized with (often derived from their skill_tool's class name).
The values are lists of action strings that the skill can perform.
"""

SKILL_CAPABILITY_MAPPING = {
    # Example for existing skills based on TaskRouter logs
    "api_connector_ops_v1": ["get_joke", "get_weather", "get_exchange_rate"],
    "calendar_ops_v1": ["current_date", "add_event", "list_events", "list_all_events", "remove_event"],
    "echo_skill_ops_v1": ["echo"],
    "file_manager_ops_v1": ["list", "read", "write"],
    "maths_ops_v1": ["add", "subtract", "multiply", "divide", "power", "log", "sin", "cos"], # Added sin, cos if maths_tool supports them
    "weather_ops_v1": ["weather"], # Assuming 'weather' is the direct command/action
    "web_scraper_ops_v1": ["get", "get_text", "fetch"],  # Add specific commands derived by invoke_skill_agent_v1

    # --- Crucial Addition for DataAnalysisSkill ---
    # The SkillAgent for DataAnalysisSkillTool provides "data_analysis_skill_ops_v1"
    # as per skill_loader.py logic.
    # This mapping tells the system that such an agent can perform "log_summary".
    "data_analysis_skill_ops_v1": [ # Corrected key to match loaded capability
        "log_summary",
        "complexity_analysis",      # Example, if your tool supports this
        "basic_stats_analysis",     # If this is a distinct action category
        "advanced_stats",           # If these are distinct action categories
        "keyword_search",
        "regex_match",
        "correlation"
        # Add any other specific actions your DataAnalysisSkillTool can perform directly
        # or that map to analysis_types within its execute_data_analysis_v1 handler.
    ],
    # Add other skill capability mappings here
}
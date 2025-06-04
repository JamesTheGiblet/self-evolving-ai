# capability_handlers/knowledge_handlers.py

from typing import Dict, Any, List
from utils.logger import log
from core.context_manager import ContextManager

try:
    from memory.fact_memory import FactMemory
except ImportError:
    FactMemory = None # Placeholder if not available

def execute_knowledge_storage_v1(agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list):
    """Executes the knowledge_storage_v1 capability."""
    outcome = "pending"
    details = {}
    immediate_reward = 0.0

    raw_data_to_store = cap_inputs.get("data_to_store")
    # Get category and format from cap_inputs, defaulting to "text" and None if not provided
    data_category = cap_inputs.get("category", "text") # Default to text if not specified
    data_format_mime = cap_inputs.get("data_format") # e.g., "image/jpeg", "audio/mp3"

    if raw_data_to_store:
        # Include category and format in the data being stored
        data_with_context = {
            "original_agent": agent.name,
            "tick": context.get_tick(),
            "payload": raw_data_to_store,
            "category": data_category,
            "format": data_format_mime
        }

        # Assuming knowledge.store will be updated to accept category and data_format
        contribution_score = knowledge.store(
            lineage_id=agent.state.get('lineage_id'),
            storing_agent_name=agent.name,
            item=data_with_context, # The entire item dict
            tick=context.get_tick(),
            category=data_category, # Pass category explicitly if store method signature changes
            data_format=data_format_mime # Pass format explicitly
        )
        log(f"[{agent.name}] Cap 'knowledge_storage_v1' stored data (Cat: {data_category}, Fmt: {data_format_mime}) for lineage '{agent.state.get('lineage_id')}', score: {contribution_score:.2f}")
        agent.memory.log_knowledge_contribution(contribution_score)
        outcome = "success"
        details["contribution_score"] = contribution_score
        immediate_reward = 0.5 + contribution_score * 0.5 # Example reward logic
    else:
        outcome = "failure_missing_input_data"
        immediate_reward = -0.2
    return {"outcome": outcome, "details": details, "reward": immediate_reward}

def execute_knowledge_retrieval_v1(agent, params_used: dict, cap_inputs: dict, knowledge, context: ContextManager, all_agent_names_in_system: list):
    """Executes the knowledge_retrieval_v1 capability."""
    outcome = "pending"
    details = {}
    immediate_reward = 0.0

    query_params_input = cap_inputs.get("query_params", {})
    # The category filter would be part of query_params_input, e.g., {"text_query": "...", "category": "visual"}
    # No direct change here, but knowledge.retrieve needs to handle it.

    retrieved_data = knowledge.retrieve(
        lineage_id=agent.state.get('lineage_id'),
        query_params=query_params_input # query_params_input might contain a "category" key
    )
    if retrieved_data:
        outcome = "success"
        details["items_retrieved"] = len(retrieved_data)
        immediate_reward = 0.2 + min(len(retrieved_data) * 0.05, 0.3)
    else:
        outcome = "failure_no_data_found"
        immediate_reward = -0.1
    log(f"[{agent.name}] Cap 'knowledge_retrieval_v1' retrieval for lineage '{agent.state.get('lineage_id')}' with params {query_params_input}. Outcome: {outcome}, items: {details.get('items_retrieved', 0)}")
    return {"outcome": outcome, "details": details, "reward": immediate_reward}

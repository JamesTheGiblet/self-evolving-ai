# capability_handlers/knowledge_handlers.py

from typing import Dict, Any, List, TYPE_CHECKING
from utils.logger import log
from core.context_manager import ContextManager

if TYPE_CHECKING:
    from core.agent_base import BaseAgent
    from memory.knowledge_base import KnowledgeBase

def execute_knowledge_storage_v1(
    agent: 'BaseAgent', 
    params_used: dict, 
    cap_inputs: dict, 
    knowledge: 'KnowledgeBase', 
    context: ContextManager, 
    all_agent_names_in_system: List[str]
):
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

def execute_knowledge_retrieval_v1(
    agent: 'BaseAgent', 
    params_used: dict, 
    cap_inputs: dict, 
    knowledge: 'KnowledgeBase', 
    context: ContextManager, 
    all_agent_names_in_system: List[str]
):
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

def execute_knowledge_storage_v2(
    agent: 'BaseAgent', 
    params_used: dict, 
    cap_inputs: dict, 
    knowledge: 'KnowledgeBase', 
    context: ContextManager, 
    all_agent_names_in_system: List[str]
):
    """
    Executes the knowledge_storage_v2 capability.
    Expects a more structured 'knowledge_object' in cap_inputs.
    'knowledge_object' should contain:
        - content: The main data/content to store.
        - category: (e.g., "text", "image_url", "code_snippet")
        - format_mime: (e.g., "text/plain", "image/jpeg", "python") - Optional
        - source_description: (e.g., "User input from GUI", "Web scrape from example.com") - Optional
        - custom_metadata: A dictionary for any other relevant metadata. - Optional
    'tags' (optional List[str]) can also be provided in cap_inputs.
    """
    outcome = "pending"
    details = {}
    immediate_reward = 0.0

    knowledge_object = cap_inputs.get("knowledge_object")
    tags = cap_inputs.get("tags", [])

    if knowledge_object and isinstance(knowledge_object, dict) and "content" in knowledge_object and "category" in knowledge_object:
        # Augment the knowledge object with agent and tick information
        knowledge_object["_stored_by_agent_name"] = agent.name
        knowledge_object["_stored_at_tick"] = context.get_tick()
        
        # Extract category and format for the knowledge.store call, if its signature requires them separately,
        # otherwise, they are within knowledge_object.
        category = knowledge_object.get("category")
        data_format_mime = knowledge_object.get("format_mime")

        contribution_score = knowledge.store(
            lineage_id=agent.state.get('lineage_id'),
            storing_agent_name=agent.name,
            item=knowledge_object, # Pass the entire structured object
            tick=context.get_tick(),
            category=category, # Explicitly pass if store method uses it as a primary filter/index
            data_format=data_format_mime # Explicitly pass if store method uses it
        )
        log(f"[{agent.name}] Cap 'knowledge_storage_v2' stored knowledge object (Category: {category}, Format: {data_format_mime}) for lineage '{agent.state.get('lineage_id')}', score: {contribution_score:.2f}. Object keys: {list(knowledge_object.keys())}")
        agent.memory.log_knowledge_contribution(contribution_score)
        outcome = "success_structured_knowledge_stored"
        details["contribution_score"] = contribution_score
        details["stored_object_keys"] = list(knowledge_object.keys())
        immediate_reward = 0.6 + contribution_score * 0.4 # Slightly different reward for structured data
    else:
        outcome = "failure_invalid_knowledge_object"
        details["error"] = "CapInput 'knowledge_object' is missing, not a dict, or missing 'content'/'category' keys."
        immediate_reward = -0.3
        log(f"[{agent.name}] Cap 'knowledge_storage_v2' failed: {details['error']}")
    return {"outcome": outcome, "details": details, "reward": immediate_reward}

# --- Self-registration ---
# This block runs when the module is imported by the dynamic loader in capability_executor.py
try:
    from core.capability_executor import register_capability
    # Register each handler function this module provides
    register_capability("knowledge_storage_v1", execute_knowledge_storage_v1)
    register_capability("knowledge_storage_v2", execute_knowledge_storage_v2)
    register_capability("knowledge_retrieval_v1", execute_knowledge_retrieval_v1)
    log("[KnowledgeHandlers] Successfully registered knowledge handlers.", level="DEBUG")
except ImportError:
    log("[KnowledgeHandlers] Critical: Could not import 'register_capability' from 'core.capability_executor'. Knowledge handlers will not be available.", level="CRITICAL")
except Exception as e:
    log(f"[KnowledgeHandlers] Critical: Exception during self-registration: {e}", level="CRITICAL", exc_info=True)

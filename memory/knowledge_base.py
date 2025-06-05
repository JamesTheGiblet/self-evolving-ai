# memory/knowledge_base.py

from typing import Dict, List, Any, Optional, TypedDict
from utils.logger import log
from memory.fact_memory import Fact, FactMemory # Import Fact and FactMemory
import time
import re # For basic keyword searching
import uuid
from core.utils.memory_relevance_utils import update_access_metadata, calculate_relevance_score
import config
from config import (
    KB_INITIAL_RELEVANCE_SCORE, KB_MAX_RELEVANCE_SCORE, KB_DECAY_RATE_PER_DAY,
    KB_ACCESS_COUNT_WEIGHT, KB_RECENCY_WEIGHT, KB_POSITIVE_FEEDBACK_WEIGHT, KB_RECENCY_DECAY_RATE_PER_DAY,
    KB_ACCESS_COUNT_CAP_FOR_RELEVANCE, # Added new config values
    KB_NEGATIVE_FEEDBACK_PENALTY, KB_PRUNING_THRESHOLD, KB_SECONDS_PER_DAY,
    TICK_INTERVAL # Used to estimate time if tick is primary
)

class StoredItemEntry(TypedDict):
    id: str
    timestamp: float # Creation timestamp
    tick: int        # Creation tick
    storing_agent_name: str
    data: Any
    last_accessed_timestamp: float
    last_accessed_tick: int
    access_count: int
    positive_feedback_count: int
    negative_feedback_count: int
    initial_calculated_relevance: float # The relevance score at the time of creation
    current_relevance_score: float
    category: Optional[str] # Added for top-level category
    data_format: Optional[str] # Added for top-level data format

class KnowledgeBase:
    def __init__(self):
        self.store_data: Dict[str, List[StoredItemEntry]] = {} # lineage_id -> list of stored items
        self.skill_specific_memory = {} # Add this line
        self.fact_memory: FactMemory = FactMemory()
        self.relevance_params = {
            "KB_INITIAL_RELEVANCE_SCORE": config.KB_INITIAL_RELEVANCE_SCORE,
            "KB_MAX_RELEVANCE_SCORE": config.KB_MAX_RELEVANCE_SCORE,
            "KB_DECAY_RATE_PER_DAY": config.KB_DECAY_RATE_PER_DAY,
            "KB_ACCESS_COUNT_WEIGHT": config.KB_ACCESS_COUNT_WEIGHT,
            "KB_RECENCY_WEIGHT": config.KB_RECENCY_WEIGHT,
            "KB_POSITIVE_FEEDBACK_WEIGHT": config.KB_POSITIVE_FEEDBACK_WEIGHT,
            "KB_NEGATIVE_FEEDBACK_PENALTY": config.KB_NEGATIVE_FEEDBACK_PENALTY,
            "KB_SECONDS_PER_DAY": config.KB_SECONDS_PER_DAY,
            "KB_RECENCY_DECAY_RATE_PER_DAY": config.KB_RECENCY_DECAY_RATE_PER_DAY,
            "KB_ACCESS_COUNT_CAP_FOR_RELEVANCE": config.KB_ACCESS_COUNT_CAP_FOR_RELEVANCE,
            "RECENCY_DECAY_TICKS_SCALE": 1000,
            "SIM_TICKS_PER_DAY": 2000
        }
        log("[KnowledgeBase] Initialized.", level="INFO")

    def get_skill_memory_store(self, skill_name: str) -> dict:
        """Provides a dedicated dictionary for a skill to store its persistent data."""
        if skill_name not in self.skill_specific_memory:
            self.skill_specific_memory[skill_name] = {}
            log(f"Created new memory store for skill: {skill_name}", level="INFO")
        return self.skill_specific_memory[skill_name]

    def _get_item_metadata_dict(self, lineage_id: str, item_id: str) -> Dict[str, Any]:
        """
        Retrieves the metadata dictionary for an item.
        """
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"
        for entry in self.store_data.get(safe_lineage_id, []):
            if entry["id"] == item_id:
                return {
                    "creation_tick": entry.get("tick"),
                    "last_accessed_tick": entry.get("last_accessed_tick"),
                    "access_count": entry.get("access_count"),
                    "initial_relevance_score": entry.get("initial_calculated_relevance"),
                    "user_feedback_score": (
                        entry.get("positive_feedback_count", 0) * self.relevance_params["KB_POSITIVE_FEEDBACK_WEIGHT"]
                        - entry.get("negative_feedback_count", 0) * self.relevance_params["KB_NEGATIVE_FEEDBACK_PENALTY"]
                    ), # This is the net feedback effect
                    "id": entry.get("id"), # Pass ID for logging if needed
                    "timestamp": entry.get("timestamp"),
                    "last_accessed_timestamp": entry.get("last_accessed_timestamp"),
                }
        raise ValueError(f"Item {item_id} not found in lineage {safe_lineage_id}")

    def _save_item_metadata(self, lineage_id: str, item_id: str, metadata: Dict[str, Any]):
        """
        Saves the updated metadata back to the item.
        """
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"
        for entry in self.store_data.get(safe_lineage_id, []):
            if entry["id"] == item_id:
                entry["tick"] = metadata.get("creation_tick", entry["tick"])
                entry["last_accessed_tick"] = metadata.get("last_accessed_tick", entry["last_accessed_tick"])
                entry["access_count"] = metadata.get("access_count", entry["access_count"])
                entry["initial_calculated_relevance"] = metadata.get("initial_relevance_score", entry["initial_calculated_relevance"])
                # Feedback is handled separately, so we don't update it here
                entry["current_relevance_score"] = metadata.get("relevance_score", entry.get("current_relevance_score", 0.0))
                entry["timestamp"] = metadata.get("timestamp", entry["timestamp"])
                entry["last_accessed_timestamp"] = metadata.get("last_accessed_timestamp", entry["last_accessed_timestamp"])
                return
        raise ValueError(f"Item {item_id} not found in lineage {safe_lineage_id}")

    def _update_item_relevance_and_access(self, lineage_id: str, item_id: str, current_tick: int):
        """
        Updates an item's access metadata and recalculates its relevance score.
        """
        item_meta = self._get_item_metadata_dict(lineage_id, item_id)
        item_meta = update_access_metadata(item_meta, current_tick)
        new_relevance = calculate_relevance_score(item_meta, current_tick, self.relevance_params)
        item_meta["relevance_score"] = new_relevance
        self._save_item_metadata(lineage_id, item_id, item_meta)
        log(f"Updated relevance for item {item_id}: {new_relevance:.3f}", level="DEBUG")

    def store(self, lineage_id: str, storing_agent_name: str, item: Any, tick: int,
              category: Optional[str] = None, # Added category parameter
              data_format: Optional[str] = None # Added data_format parameter
              ) -> float:
        # Ensure lineage_id is a string
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"

        if safe_lineage_id not in self.store_data:
            self.store_data[safe_lineage_id] = []
        
        # Calculate the initial relevance at creation, including a small bonus for item "size" or "complexity"
        initial_relevance_at_creation = min(KB_MAX_RELEVANCE_SCORE, KB_INITIAL_RELEVANCE_SCORE + (len(str(item)) / 5000.0))
        stored_item_entry: StoredItemEntry = {
            "id": uuid.uuid4().hex,
            "timestamp": time.time(),
            "tick": tick,
            "storing_agent_name": storing_agent_name,
            "data": item,
            "last_accessed_timestamp": time.time(),
            "last_accessed_tick": tick,
            "access_count": 0, # Starts at 0, incremented upon first actual retrieval/access
            "positive_feedback_count": 0,
            "negative_feedback_count": 0,
            "initial_calculated_relevance": initial_relevance_at_creation,
            "current_relevance_score": initial_relevance_at_creation, # Initially, current score is the initial calculated score
            "category": category, # Store the passed category
            "data_format": data_format # Store the passed data_format
        }
        self.store_data[safe_lineage_id].append(stored_item_entry)
        log(f"[KnowledgeBase] Stored item '{stored_item_entry['id']}' (Cat: {category}, Fmt: {data_format}) for lineage '{safe_lineage_id}' by '{storing_agent_name}'. Initial relevance: {initial_relevance_at_creation:.2f}", level="DEBUG")
        return initial_relevance_at_creation # Return the initial relevance

    def retrieve(self, lineage_id: str, query_params: Optional[Dict[str, Any]] = None, current_tick: Optional[int] = 0) -> List[Any]:
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"
        
        if safe_lineage_id not in self.store_data:
            # log(f"[KnowledgeBase] No data found for lineage '{safe_lineage_id}' to retrieve.", level="DEBUG")
            return []

        lineage_data = self.store_data[safe_lineage_id]
        
        # Retrieve full entries first to update access and sort by relevance
        full_entries = self.retrieve_full_entries(lineage_id, query_params, current_tick)

        if not query_params:
            # log(f"[KnowledgeBase] Retrieved {len(lineage_data)} data items for lineage '{safe_lineage_id}' with query: None.", level="DEBUG")
            return [entry["data"] for entry in full_entries] # Return only the 'data' part
        
        # Filtering logic is now primarily in retrieve_full_entries.
        # This method now just extracts the "data" part from what retrieve_full_entries returns.
        # Note: The original filtering logic here is somewhat redundant if retrieve_full_entries is called first.
        # For simplicity, we'll rely on retrieve_full_entries to do the heavy lifting of filtering and sorting.
        # Then we just extract the data.
        
        # This part of the original code can be simplified as retrieve_full_entries handles most of it.
        # However, to maintain the structure of applying filters if query_params are present:

        # data_matches_filter = query_params.get("data_matches")
        # limit = query_params.get("limit") # Limit is applied in retrieve_full_entries
        # ... other filters ...
        temp_results_for_sorting = []

        for entry in reversed(lineage_data): # Iterate reversed for recent items first by default
            item_data = entry.get("data", {})
            item_tick = entry.get("tick", -1)
            item_storing_agent = entry.get("storing_agent_name")

            # This filtering is largely duplicated in retrieve_full_entries.
            # Consider removing if retrieve_full_entries is always the source.
            # For now, keeping it to show how it would work if this method did its own filtering.
            data_matches_filter = query_params.get("data_matches") # Re-fetch for this scope
            min_tick = query_params.get("min_tick")
            max_tick = query_params.get("max_tick")
            storing_agent_name_filter = query_params.get("storing_agent_name")

            # Tick filtering
            if min_tick is not None and item_tick < min_tick:
                continue
            if max_tick is not None and item_tick > max_tick:
                continue
            
            # Storing agent name filtering
            if storing_agent_name_filter and item_storing_agent != storing_agent_name_filter:
                continue

            # Data matching filter (simple key-value check in the payload)
            if data_matches_filter and isinstance(item_data, dict) and isinstance(data_matches_filter, dict):
                match = True
                for key, value in data_matches_filter.items():
                    if item_data.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            # If we are here, the item matches. Add its data.
            # However, retrieve_full_entries already did this and sorted.
            # So, this loop is not strictly necessary if full_entries is used.
            # temp_results_for_sorting.append(entry["data"])

        # If using full_entries from retrieve_full_entries:
        filtered_results = [e["data"] for e in full_entries]

        # Apply limit if it wasn't applied in retrieve_full_entries or if this method has its own limit logic
        # limit = query_params.get("limit") # Already handled by retrieve_full_entries
        # if limit is not None:
        #     filtered_results = filtered_results[:limit]
            
        log(f"[KnowledgeBase] Retrieved {len(filtered_results)} data items for lineage '{safe_lineage_id}' with query: {query_params}. Tick: {current_tick}", level="DEBUG")
        return filtered_results
    
    def retrieve_full_entries(self, lineage_id: str, query_params: Optional[Dict[str, Any]] = None, current_tick: Optional[int] = 0) -> List[StoredItemEntry]:
        """Retrieves full stored entries (including metadata) matching the query."""
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"
        
        if safe_lineage_id not in self.store_data:
            return []
        lineage_data = self.store_data[safe_lineage_id]

        if not query_params:
            # Update access for all items if no query
            for entry in lineage_data:
                # Call the existing method to update relevance and access metadata
                # The 'entry' here is a StoredItemEntry dict, so we pass its 'id'
                self._update_item_relevance_and_access(safe_lineage_id, entry["id"], current_tick)
            # After updating, sort by the newly calculated current_relevance_score
            return sorted(list(lineage_data), key=lambda x: x["current_relevance_score"], reverse=True)

        filtered_entries = []
        data_matches_filter = query_params.get("data_matches")
        limit = query_params.get("limit")
        min_tick = query_params.get("min_tick")
        max_tick = query_params.get("max_tick")
        sort_by_tick = query_params.get("sort_by_tick") # 'asc' or 'desc'
        storing_agent_name_filter = query_params.get("storing_agent_name")
        sort_by_relevance = query_params.get("sort_by_relevance", True) # Default to sort by relevance

        # Create a list of entries to sort if needed
        candidate_entries = []
        for entry in lineage_data: # Iterate in original order for now
            item_data = entry.get("data", {})
            item_tick = entry.get("tick", -1)
            item_storing_agent = entry.get("storing_agent_name")

            if min_tick is not None and item_tick < min_tick: continue
            if max_tick is not None and item_tick > max_tick: continue
            if storing_agent_name_filter and item_storing_agent != storing_agent_name_filter: continue
            
            if data_matches_filter and isinstance(item_data, dict) and isinstance(data_matches_filter, dict):
                match = True
                for key, value in data_matches_filter.items():
                    if item_data.get(key) != value:
                        match = False; break
                if not match: continue
            
            # Use the new centralized update mechanism
            self._update_item_relevance_and_access(safe_lineage_id, entry["id"], current_tick)
            candidate_entries.append(entry)

        # Primary sort by relevance (descending)
        if sort_by_relevance:
            candidate_entries.sort(key=lambda x: x["current_relevance_score"], reverse=True)
        elif sort_by_tick: # Secondary sort option
            reverse_sort = (sort_by_tick.lower() == 'desc')
            candidate_entries.sort(key=lambda x: x.get("tick", 0), reverse=reverse_sort)
        # else, original insertion order (or reversed if iterated that way)
        
        # Apply limit
        if limit is not None:
            filtered_entries = candidate_entries[:limit]
        else:
            filtered_entries = candidate_entries
        
        log(f"[KnowledgeBase] Retrieved {len(filtered_entries)} full entries for lineage '{safe_lineage_id}' with query: {query_params}. Tick: {current_tick}", level="DEBUG")

        return filtered_entries

    def add_user_fact(self, content_str: str, source: str, tags: List[str], tick: int, 
                      category: Optional[str] = "text", data_format: Optional[str] = None) -> Optional[Fact]:
        """
        Adds a fact provided by the user through the GUI.
        Uses the FactMemory component.
        """
        if not content_str:
            log("[KnowledgeBase] Attempted to add an empty fact.", level="WARNING")
            return None

        fact_content = {
            "text_content": content_str,
            "tags": tags if tags else [],
            "original_tick": tick, # Store the tick when the user provided it
            "ingestion_timestamp": time.time(), # Store the real-world time of ingestion
            # Category and data_format will be passed to FactMemory.add_fact
            # and stored in Fact.content by FactMemory/Fact constructor
        }

        # Certainty for user-injected facts is typically high, but could be made configurable
        new_fact = self.fact_memory.add_fact(
            content=fact_content, 
            source=source, 
            certainty=0.95, 
            creation_tick=tick,
            category=category,
            data_format=data_format
        )
        log(f"[KnowledgeBase] Added user fact from source '{source}' with ID '{new_fact.id}'. Cat: {category}, Fmt: {data_format}, Tags: {tags}", level="INFO")
        return new_fact

    def query_user_facts(self, query_params: Dict[str, Any], current_tick: Optional[int] = 0) -> List[Fact]:
        """
        Queries facts stored in FactMemory, typically those injected by the user.
        Performs a simple keyword search on content and tags, and filters by category.
        Updates access metadata and sorts by relevance.
        """
        text_query = query_params.get("text_query", "")
        category_filter = query_params.get("category")

        if not text_query and not category_filter: # If no query text and no category filter, return empty or all? For now, empty.
            log("[KnowledgeBase] Query user facts called with no text query or category filter.", level="DEBUG")
            return []

        all_facts = self.fact_memory.get_all_facts() # Gets all facts, does not update access yet
        matched_facts: List[Fact] = []
        query_terms = [term.lower() for term in re.split(r'\s+', text_query.strip()) if term] if text_query else []

        for fact in all_facts:
            text_match = False
            if not query_terms: # If no text query, consider it a text match (will filter by category later)
                text_match = True
            else:
                text_to_search = fact.content.get("text_content", "").lower()
                tags_to_search = [tag.lower() for tag in fact.content.get("tags", [])]
                for term in query_terms:
                    if term in text_to_search or any(term in tag_text for tag_text in tags_to_search):
                        text_match = True
                        break
            
            category_match = False
            if not category_filter or category_filter.lower() == "any" or fact.content.get("category", "").lower() == category_filter.lower():
                category_match = True

            if text_match and category_match:
                self.fact_memory._update_fact_relevance_and_access(fact, current_tick) # Corrected method name
                matched_facts.append(fact)
        
        # Sort results by relevance
        matched_facts.sort(key=lambda f: f.current_relevance_score, reverse=True)
        log(f"[KnowledgeBase] Queried user facts with params '{query_params}', found {len(matched_facts)} matches. Tick: {current_tick}", level="DEBUG")
        return matched_facts

    def get_size(self, lineage_id: Optional[str] = None) -> int:
        """Returns the number of items for a specific lineage or total items."""
        if lineage_id:
            safe_lineage_id = str(lineage_id)
            return len(self.store_data.get(safe_lineage_id, []))
        else:
            total_size = 0
            for lineage_items in self.store_data.values():
                total_size += len(lineage_items)
            total_size += len(self.fact_memory.get_all_facts()) # Add size of fact memory
            return total_size

    def clear_lineage(self, lineage_id: str):
        safe_lineage_id = str(lineage_id)
        if safe_lineage_id in self.store_data:
            del self.store_data[safe_lineage_id]
            log(f"[KnowledgeBase] Cleared all data for lineage '{safe_lineage_id}'.")

    def clear_all(self):
        self.store_data.clear()
        self.fact_memory.clear_all_facts() # Use the method from FactMemory
        log("[KnowledgeBase] Cleared all data.")

    def record_item_feedback(self, lineage_id: str, item_id: str, is_positive: bool, current_tick: int):
        """Records feedback for a specific stored item and updates its relevance."""
        safe_lineage_id = str(lineage_id) if lineage_id is not None else "default_lineage"
        if safe_lineage_id in self.store_data:
            for entry in self.store_data[safe_lineage_id]:
                if entry["id"] == item_id:
                    if is_positive:
                        entry["positive_feedback_count"] += 1
                    else:
                        entry["negative_feedback_count"] += 1
                    # Update access as feedback implies interaction
                    self._update_item_relevance_and_access(safe_lineage_id, entry["id"], current_tick)
                    log(f"[KnowledgeBase] Recorded {'positive' if is_positive else 'negative'} feedback for item '{item_id}' in lineage '{safe_lineage_id}'. New relevance: {entry.get('current_relevance_score', 'N/A'):.2f}", level="DEBUG")
                    return
            log(f"[KnowledgeBase] Could not find item '{item_id}' in lineage '{safe_lineage_id}' to record feedback.", level="WARNING")
        else:
            log(f"[KnowledgeBase] No such lineage '{safe_lineage_id}' to record feedback for item '{item_id}'.", level="WARNING")

    def apply_decay_and_pruning(self, current_tick: int, lineage_id: Optional[str] = None):
        """Applies decay to items and prunes those below threshold for specified or all lineages."""
        lineages_to_process = [lineage_id] if lineage_id and lineage_id in self.store_data else list(self.store_data.keys())

        for lid in lineages_to_process:
            if lid in self.store_data: # Double check, as list(keys()) might be stale if modified elsewhere
                updated_items = []
                pruned_count = 0
                for entry in self.store_data[lid]:
                    # Update relevance before checking for pruning
                    self._update_item_relevance_and_access(lid, entry["id"], current_tick)
                    if entry.get("current_relevance_score", 0.0) >= KB_PRUNING_THRESHOLD:
                        updated_items.append(entry)
                    else:
                        pruned_count += 1
                        log(f"[KnowledgeBase] Item '{entry['id']}' in lineage '{lid}' marked for pruning. Relevance: {entry.get('current_relevance_score', 0.0):.2f}", level="TRACE")
                self.store_data[lid] = updated_items
                if pruned_count > 0:
                    log(f"[KnowledgeBase] Pruned {pruned_count} items from lineage '{lid}' due to low relevance. Tick: {current_tick}", level="INFO")
        
        if lineage_id is None: # Only log general message if processing all
            log(f"[KnowledgeBase] Applied decay and pruning to stored items. Tick: {current_tick}", level="DEBUG")
        
        # Also apply to fact memory
        self.fact_memory.apply_decay_and_pruning(current_tick)

    def get_recent_facts(self, limit: int = 10, category: Optional[str] = None, 
                         source: Optional[str] = None, keywords: Optional[str] = None) -> List[Fact]:
        """
        Retrieves the most recent facts from FactMemory, sorted by creation timestamp.
        Optionally filters by category, source, or keywords.
        """
        all_facts = self.fact_memory.get_all_facts()
        if not all_facts:
            return []

        filtered_facts: List[Fact] = []
        query_terms = [term.lower() for term in re.split(r'\s+', keywords.strip()) if term] if keywords else []

        for fact in all_facts:
            # Apply category filter
            if category is not None and fact.content.get('category', '').lower() != category.lower():
                continue

            # Apply source filter (case-insensitive substring match)
            if source is not None and source.lower() not in fact.source.lower():
                continue

            # Apply keyword filter (check text_content and tags)
            if query_terms:
                text_to_search = fact.content.get("text_content", "").lower()
                tags_to_search = [tag.lower() for tag in fact.content.get("tags", [])]
                keyword_match = False
                for term in query_terms:
                    if term in text_to_search or any(term in tag_text for tag_text in tags_to_search):
                        keyword_match = True
                        break
                if not keyword_match:
                    continue

            # If the fact passes all filters, update its access and add to filtered list
            self.fact_memory._update_fact_relevance_and_access(fact, None) # Update access using timestamp if tick is None
            filtered_facts.append(fact)

        # Sort filtered facts by creation_timestamp (most recent first)
        sorted_filtered_facts = sorted(filtered_facts, key=lambda f: f.creation_timestamp, reverse=True)
        return sorted_filtered_facts[:limit]

# memory/fact_memory.py

from typing import Dict, List, Any, Optional
import time
import uuid
import config # Import the main config module
from config import (
    KB_INITIAL_RELEVANCE_SCORE, KB_MAX_RELEVANCE_SCORE, KB_DECAY_RATE_PER_DAY,
    KB_ACCESS_COUNT_WEIGHT, KB_RECENCY_WEIGHT, KB_POSITIVE_FEEDBACK_WEIGHT,
    KB_NEGATIVE_FEEDBACK_PENALTY, KB_PRUNING_THRESHOLD, KB_SECONDS_PER_DAY,
    KB_RECENCY_DECAY_RATE_PER_DAY, KB_ACCESS_COUNT_CAP_FOR_RELEVANCE # Ensure these are available
)
from utils.logger import log
from utils.memory_relevance_utils import update_access_metadata, calculate_relevance_score

class Fact:
    """Represents a single piece of factual information."""
    def __init__(self, fact_id: str, content: Dict[str, Any], source: str = "unknown", 
                 certainty: float = 1.0, creation_tick: Optional[int] = None,
                 category: Optional[str] = "text", data_format: Optional[str] = None): # Added category and data_format
        self.id = fact_id
        # Ensure content includes category and format if provided, otherwise they are part of the main content dict
        self.content = content if isinstance(content, dict) else {} 
        self.content.setdefault("category", category) # Ensure category is in content
        self.content.setdefault("format", data_format) # Ensure format is in content
        self.source = source    # Where this fact came from
        self.certainty = certainty  # How sure the system is about this fact (0.0 to 1.0)
        
        current_time = time.time()
        self.creation_timestamp: float = current_time
        self.creation_tick: Optional[int] = creation_tick
        self.last_accessed_timestamp: float = current_time
        self.last_accessed_tick: Optional[int] = creation_tick
        self.access_count: int = 0
        self.positive_feedback_count: int = 0
        self.negative_feedback_count: int = 0
        # Initial relevance combines certainty and a base score
        self.current_relevance_score: float = min(KB_MAX_RELEVANCE_SCORE, certainty * KB_INITIAL_RELEVANCE_SCORE)

    def __repr__(self):
        return (f"Fact(id='{self.id}', source='{self.source}', certainty={self.certainty:.2f}, "
                f"relevance={self.current_relevance_score:.2f}, content={self.content})")

class FactMemory:
    """
    A memory component for storing and retrieving facts.
    Facts are pieces of information an agent believes to be true.
    """
    def __init__(self):
        self._facts: Dict[str, Fact] = {}  # Store facts by ID for quick access
        self._fact_counter: int = 0        # For generating unique IDs if not provided
        self.relevance_params = { # Populate from config
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
            # Add any other params needed by calculate_relevance_score
            "RECENCY_DECAY_TICKS_SCALE": 1000, # Example, if tick-based recency was used
            "SIM_TICKS_PER_DAY": 2000 # Example, if tick-based decay was used
        }

    def _generate_fact_id(self) -> str:
        """Generates a unique ID for a new fact."""
        self._fact_counter += 1
        return f"fact_{uuid.uuid4().hex[:8]}_{self._fact_counter}"

    def _get_fact_metadata_dict(self, fact: Fact) -> Dict[str, Any]:
        """Converts a Fact object to a metadata dictionary for utility functions."""
        # For facts, the 'initial_relevance_score' is tied to certainty.
        # The utility function expects 'initial_relevance_score'.
        initial_relevance = fact.certainty * self.relevance_params.get("KB_INITIAL_RELEVANCE_SCORE", 0.5)
        return {
            "id": fact.id,
            "initial_relevance_score": initial_relevance,
            "creation_tick": fact.creation_tick,
            "last_accessed_tick": fact.last_accessed_tick,
            "access_count": fact.access_count,
            "user_feedback_score": (
                fact.positive_feedback_count * self.relevance_params["KB_POSITIVE_FEEDBACK_WEIGHT"]
                - fact.negative_feedback_count * self.relevance_params["KB_NEGATIVE_FEEDBACK_PENALTY"]
            ),
            "timestamp": fact.creation_timestamp,
            "last_accessed_timestamp": fact.last_accessed_timestamp,
        }

    def _save_fact_metadata(self, fact: Fact, metadata: Dict[str, Any]):
        """Updates a Fact object from a metadata dictionary."""
        fact.last_accessed_tick = metadata.get("last_accessed_tick", fact.last_accessed_tick)
        fact.access_count = metadata.get("access_count", fact.access_count)
        fact.current_relevance_score = metadata.get("relevance_score", fact.current_relevance_score)
        fact.last_accessed_timestamp = metadata.get("last_accessed_timestamp", fact.last_accessed_timestamp)

    def _update_fact_relevance_and_access(self, fact: Fact, current_tick: Optional[int]):
        """Updates a fact's access metadata and recalculates its relevance score using utilities."""
        fact_meta = self._get_fact_metadata_dict(fact)
        current_timestamp = time.time()
        fact_meta = update_access_metadata(fact_meta, current_tick, current_timestamp)
        new_relevance = calculate_relevance_score(fact_meta, self.relevance_params)
        fact_meta["relevance_score"] = new_relevance
        self._save_fact_metadata(fact, fact_meta)

    def add_fact(self, content: Dict[str, Any], source: str = "internal", 
                 certainty: float = 1.0, fact_id: Optional[str] = None, creation_tick: Optional[int] = None,
                 text_content: Optional[str] = None, tags: Optional[List[str]] = None, # For convenience from KB.add_user_fact
                 category: Optional[str] = "text", data_format: Optional[str] = None) -> Fact:
        """
        Adds a new fact to memory.
        If fact_id is None, a new one will be generated.
        If fact_id is provided and already exists, the existing fact will be updated.
        """
        if fact_id is None:
            fact_id = self._generate_fact_id()

        # Construct the content dictionary carefully
        final_content = {}
        if isinstance(content, dict): # If a full content dict is passed
            final_content.update(content)
        
        if text_content is not None: # If text_content is passed separately (e.g., from KB.add_user_fact)
            final_content["text_content"] = text_content
        if tags is not None:
            final_content["tags"] = tags
        
        # Ensure category and format are in the final_content
        final_content.setdefault("category", category)
        final_content.setdefault("format", data_format)

        if fact_id in self._facts: # Update existing fact
            fact = self._facts[fact_id]
            fact.content = final_content # Overwrite content
            fact.source = source
            fact.certainty = certainty
            # Update relevance using the new mechanism
            self._update_fact_relevance_and_access(fact, creation_tick)
            log(f"[FactMemory] Updated fact '{fact_id}' from source '{source}'. Relevance: {fact.current_relevance_score:.2f}", level="DEBUG")
        else: # Add new fact
            fact = Fact(fact_id=fact_id, content=final_content, source=source, 
                        certainty=certainty, creation_tick=creation_tick, 
                        category=category, data_format=data_format) # Pass category/format to Fact constructor
            self._facts[fact_id] = fact
            # Initial relevance is set in Fact constructor, potentially re-evaluate if needed after adding
            log(f"[FactMemory] Added fact '{fact_id}' (Cat: {category}, Fmt: {data_format}) from source '{source}'. Relevance: {fact.current_relevance_score:.2f}", level="DEBUG")
        return fact

    def get_fact_by_id(self, fact_id: str, current_tick: Optional[int] = None) -> Optional[Fact]:
        """Retrieves a specific fact by its ID."""
        fact = self._facts.get(fact_id)
        if fact:
            self._update_fact_relevance_and_access(fact, current_tick)
        return fact

    def find_facts(self, query_criteria: Dict[str, Any], current_tick: Optional[int] = None,
                   sort_by_relevance: bool = True) -> List[Fact]:
        """
        Finds facts that match the given query criteria.
        Criteria is a dictionary where keys are attributes of the Fact object (e.g., 'source', 'certainty')
        or keys within the fact's 'content' dictionary.
        """
        matched_facts: List[Fact] = []
        if not query_criteria: # If no criteria, return all facts (after updating access)
            all_facts = list(self._facts.values())
            for fact in all_facts:
                self._update_fact_relevance_and_access(fact, current_tick)
            if sort_by_relevance:
                all_facts.sort(key=lambda f: (f.current_relevance_score, f.certainty), reverse=True)
            return all_facts


        for fact in self._facts.values():
            match = True
            for key, value in query_criteria.items():
                if hasattr(fact, key) and getattr(fact, key) == value:
                    continue
                elif isinstance(fact.content, dict) and key in fact.content and fact.content[key] == value:
                    continue
                else: # Key not found or value mismatch
                    match = False
                    break
            if match:
                self._update_fact_relevance_and_access(fact, current_tick) # Update access if it's a candidate
                matched_facts.append(fact)
        
        if sort_by_relevance:
            # Sort by relevance descending, then by certainty descending as a tie-breaker
            matched_facts.sort(key=lambda f: (f.current_relevance_score, f.certainty), reverse=True)
            
        return matched_facts

    def remove_fact(self, fact_id: str) -> bool:
        """Removes a fact by its ID. Returns True if successful, False otherwise."""
        if fact_id in self._facts:
            del self._facts[fact_id]
            return True
        log(f"[FactMemory] Attempted to remove non-existent fact '{fact_id}'.", level="WARNING")
        return False

    def get_all_facts(self) -> List[Fact]:
        """Returns a list of all facts in memory."""
        return list(self._facts.values())

    def clear_all_facts(self):
        """Removes all facts from memory."""
        self._facts.clear()
        self._fact_counter = 0 # Reset counter
        log("[FactMemory] Cleared all facts.")

    def record_fact_feedback(self, fact_id: str, is_positive: bool, current_tick: Optional[int] = None):
        """Records feedback for a fact and updates its relevance."""
        fact = self.get_fact_by_id(fact_id, current_tick) # This also updates access
        # get_fact_by_id already calls _update_fact_relevance_and_access
        if fact:
            if is_positive:
                fact.positive_feedback_count += 1
            else:
                fact.negative_feedback_count += 1
            self._update_fact_relevance_and_access(fact, current_tick) # Recalculate after feedback counts change
            log(f"[FactMemory] Recorded {'positive' if is_positive else 'negative'} feedback for fact '{fact_id}'. New relevance: {fact.current_relevance_score:.2f}", level="DEBUG")
        else:
            log(f"[FactMemory] Could not record feedback for non-existent fact '{fact_id}'.", level="WARNING")

    def apply_decay_and_pruning(self, current_tick: Optional[int] = None):
        """Periodically apply decay to all facts and prune those below threshold."""
        facts_to_prune = []
        for fact_id, fact in list(self._facts.items()): # Iterate over a copy for safe deletion
            # Update relevance using the new mechanism
            self._update_fact_relevance_and_access(fact, current_tick)
            if fact.current_relevance_score < KB_PRUNING_THRESHOLD:
                facts_to_prune.append(fact_id)
        
        pruned_count = 0
        for fact_id in facts_to_prune:
            log_fact_relevance = self._facts.get(fact_id).current_relevance_score if fact_id in self._facts else "N/A"
            if self.remove_fact(fact_id): # Ensure fact is removed before logging its (potentially old) relevance
                log(f"[FactMemory] Pruned fact '{fact_id}' due to low relevance ({log_fact_relevance:.2f} < {KB_PRUNING_THRESHOLD}).", level="INFO")
                pruned_count +=1
        if pruned_count > 0:
            log(f"[FactMemory] Applied decay and pruning. Pruned {pruned_count} facts.", level="DEBUG")
        elif not self._facts: # If no facts left, or started empty
            log(f"[FactMemory] Applied decay and pruning. No facts to process or prune.", level="DEBUG")
        else: # No facts were pruned
            log(f"[FactMemory] Applied decay and pruning. No facts met pruning threshold.", level="DEBUG")

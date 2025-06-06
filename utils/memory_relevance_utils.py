# c:/Users/gilbe/Desktop/self-evolving-ai/core/utils/memory_relevance_utils.py

import time
import math
from typing import Dict, Any, Optional
from utils.logger import log

# Assuming config.py contains these, or they are passed in via a config dict
# from core import config # Or pass relevant config values directly

def update_access_metadata(item_metadata: Dict[str, Any], current_tick: int) -> Dict[str, Any]:
    """
    Updates the access-related metadata (tick and count) for a memory item.
    Timestamp is updated separately if needed.

    Args:
        item_metadata: A dictionary containing at least 'last_accessed_tick' and 'access_count'.
        current_tick: The current simulation tick.

    Returns:
        The updated item_metadata dictionary.
    """
    if current_tick is not None:
        item_metadata["last_accessed_tick"] = current_tick
    current_timestamp = time.time()  # Define current_timestamp
    item_metadata["last_accessed_timestamp"] = current_timestamp # Always update timestamp
    item_metadata["access_count"] = item_metadata.get("access_count", 0) + 1
    return item_metadata

def calculate_relevance_score(
    item_metadata: Dict[str, Any],
    relevance_config: Dict[str, Any]
) -> float:
    """
    Calculates the relevance score for a memory item based on various factors.

    Args:
        item_metadata: A dictionary containing metadata like:
            'creation_tick', 'last_accessed_tick', 'access_count',
            'initial_relevance_score', 'user_feedback_score'.
        current_tick: The current simulation tick.
        relevance_config: A dictionary with configuration parameters like:
            'KB_RECENCY_WEIGHT', 'KB_ACCESS_COUNT_WEIGHT', 'KB_POSITIVE_FEEDBACK_WEIGHT',
            'KB_NEGATIVE_FEEDBACK_PENALTY', 'KB_DECAY_RATE_PER_DAY', 'KB_SECONDS_PER_DAY',
            'KB_ACCESS_COUNT_CAP_FOR_RELEVANCE', 'KB_MAX_RELEVANCE_SCORE'.

    Returns:
        The calculated relevance score.
    """
    current_time_sec = time.time() # Use current real time for calculations

    # 1. Decay of the item's original intrinsic value based on its total age
    initial_relevance = item_metadata.get("initial_relevance_score", relevance_config.get("KB_INITIAL_RELEVANCE_SCORE", 0.5))
    creation_timestamp = item_metadata.get("timestamp", current_time_sec) # Fallback to current time if missing
    
    age_days = (current_time_sec - creation_timestamp) / relevance_config.get("KB_SECONDS_PER_DAY", 86400)
    decay_factor = max(0, 1.0 - (age_days * relevance_config.get("KB_DECAY_RATE_PER_DAY", 0.05)))
    base_value_after_decay = initial_relevance * decay_factor    
    
    # 2. Recency component: how recently was it accessed?
    # Use creation_timestamp if last_accessed_timestamp is not available (e.g. item never accessed)
    last_accessed_timestamp = item_metadata.get("last_accessed_timestamp", creation_timestamp)
    time_since_last_access_days = (current_time_sec - last_accessed_timestamp) / relevance_config.get("KB_SECONDS_PER_DAY", 86400)
    
    # Recency value decays from 1.0 towards 0 as time since last access increases
    recency_decay_rate = relevance_config.get("KB_RECENCY_DECAY_RATE_PER_DAY", 0.1) # Default if not in config
    recency_value = max(0, 1.0 - (time_since_last_access_days * recency_decay_rate))
    recency_score_component = recency_value * relevance_config.get("KB_RECENCY_WEIGHT", 0.15)
    
    
    # 3. Access count component
    access_count = item_metadata.get("access_count", 0)
    access_count_cap = relevance_config.get("KB_ACCESS_COUNT_CAP_FOR_RELEVANCE", 10)
    normalized_access_count = min(access_count, access_count_cap) / access_count_cap if access_count_cap > 0 else 0
    access_score_component = normalized_access_count * relevance_config.get("KB_ACCESS_COUNT_WEIGHT", 0.05)

    # 4. User feedback component
    # The 'user_feedback_score' from _get_item_metadata_dict is already the net effect:
    # (pos_count * POS_WEIGHT) - (neg_count * NEG_PENALTY)
    feedback_score_component = item_metadata.get("user_feedback_score", 0.0)
    
    # Combine all factors
    combined_score = base_value_after_decay \
                     + recency_score_component \
                     + access_score_component \
                     + feedback_score_component
    
    final_score = max(0.0, min(combined_score, relevance_config.get("KB_MAX_RELEVANCE_SCORE", 1.0)))

    log(f"Util relevance: item_id={item_metadata.get('id','N/A')} score={final_score:.3f} (base_decayed={base_value_after_decay:.3f}, recency={recency_score_component:.3f}, access={access_score_component:.3f}, feedback={feedback_score_component:.3f})", level="TRACE")
    return final_score
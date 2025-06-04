# c:/Users/gilbe/Desktop/self-evolving-ai/engine/identity_engine.py

import datetime
import json
import os
import re
import random
import math
import time
from typing import List, Dict, Any, TYPE_CHECKING, Optional
import config # Import config for PROJECT_ROOT_PATH
from utils.logger import log # Use your centralized logger

if TYPE_CHECKING:
    from core.llm_planner import LLMPlanner
    from engine.fitness_engine import FitnessEngine, MemoryProtocol
    from memory.knowledge_base import KnowledgeBase
    from core.meta_agent import MetaAgent # Add MetaAgent for type hinting
    from core.context_manager import ContextManager # Added for new methods

DEFAULT_SYSTEM_NAME = "EvoSystem_v0.1"
MIN_TICKS_FOR_NAMING = 500    # System must run for at least this many ticks
MIN_AGENTS_FOR_NAMING = 3       # Minimum number of concurrent agents
MIN_PERFORMANCE_FOR_NAMING = 0.5 # Minimum average capability performance

class IdentityEngine:
    EVOLUTION_LOG_CATEGORY = "agent_evolution_log" # For agent-specific evolution events

    def __init__(self,
                 knowledge_base: 'KnowledgeBase',
                 meta_agent_instance: 'MetaAgent', # Added to get all agent names
                 context_manager: 'ContextManager', # Added for new methods
                 llm_planner: Optional['LLMPlanner'] = None, # Made optional
                 fitness_engine: Optional['FitnessEngine'] = None, # Made optional
                 log_dir_base: str = config.PROJECT_ROOT_PATH): # Use config for default
        self.llm_planner = llm_planner
        self.fitness_engine = fitness_engine
        self.knowledge_base = knowledge_base
        self.meta_agent = meta_agent_instance # Store MetaAgent instance
        self.context_manager = context_manager # Store ContextManager instance

        # Ensure the base path from the INI file is used correctly
        # The INI file path is c:\Users\gilbe\Desktop\self-evolving-ai\Plan-of-action.ini
        # So, log_dir_base should be c:\Users\gilbe\Desktop\self-evolving-ai
        # Ensure log_dir_base is an absolute path if it's relative from config
        resolved_log_dir_base = os.path.abspath(log_dir_base)
        log_dir = os.path.join(resolved_log_dir_base, "identity_data")
        self.identity_log_path = os.path.join(log_dir, "identity_log.jsonl")
        os.makedirs(log_dir, exist_ok=True)

        self.initial_default_name = DEFAULT_SYSTEM_NAME
        self.current_name = self.initial_default_name # Initial default name
        self.current_purpose = "To learn, adapt, and perform tasks efficiently." # Initial default purpose
        self.dominant_traits = {}

        self._load_latest_system_identity() # Renamed for clarity

    def _log_event(self, event_type, data):
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "data": data,
            "current_name": self.current_name,
            "current_purpose": self.current_purpose,
            "dominant_traits": self.dominant_traits # Log traits at the time of event
        }
        try:
            with open(self.identity_log_path, "a") as f:
                json.dump(log_entry, f)
                f.write("\n")
            log(f"[IdentityEngine] Event logged: {event_type}", level="INFO")
        except Exception as e:
            log(f"[IdentityEngine] Error writing to identity log: {e}", level="ERROR")

    def _load_latest_system_identity(self):
        if not os.path.exists(self.identity_log_path):
            self._log_event("initialization", {"name": self.current_name, "purpose": self.current_purpose})
            return
        last_entry = None
        try:
            with open(self.identity_log_path, "r") as f:
                for line in f:
                    if line.strip():
                        last_entry = json.loads(line)
            if last_entry:
                self.current_name = last_entry.get("current_name", self.current_name)
                self.current_purpose = last_entry.get("current_purpose", self.current_purpose)
                self.dominant_traits = last_entry.get("dominant_traits", self.dominant_traits)
                log(f"[IdentityEngine] Loaded latest identity: Name='{self.current_name}'", level="INFO")
        except Exception as e:
            log(f"[IdentityEngine] Error loading identity log: {e}. Using defaults.", level="WARNING")
            self._log_event("load_error", {"error": str(e)})

    def update_and_reflect_on_identity(self, all_agent_memories: List['MemoryProtocol'], current_tick: int):
        """
        Periodically called to assess traits, and potentially synthesize new name/purpose.
        Accepts current_tick for maturity checks.
        Requires a list of all agent memories to calculate the system profile.
        """
        # 1. Monitor dominant traits
        if not self.fitness_engine:
            log("[IdentityEngine] FitnessEngine not available for trait monitoring.", level="ERROR")
            return

        current_traits = self.fitness_engine.calculate_current_performance_profile(all_agent_memories)

        if current_traits and current_traits != self.dominant_traits:
            self.dominant_traits = current_traits
            self._log_event("traits_update", {"new_traits": self.dominant_traits})
            log(f"[IdentityEngine] Dominant traits updated: {self.dominant_traits}", level="INFO")

        # 2. Synthesize a name and purpose if conditions are met
        if self._should_resynthesize_identity(current_tick):
            self._synthesize_identity_elements(current_tick)

    def _should_resynthesize_identity(self, current_tick: int) -> bool:
        """
        Determines if the system should attempt to synthesize a new name and purpose.
        This is designed to happen once when maturity criteria are met and it's still using the default name.
        """
        if self.current_name != self.initial_default_name:
            return False # Already named itself, stick with it.

        if current_tick < MIN_TICKS_FOR_NAMING:
            return False # Not mature enough yet (by ticks)

        if not self.dominant_traits or self.dominant_traits.get("num_agents", 0) < MIN_AGENTS_FOR_NAMING:
            return False # Not enough agents active

        if self.dominant_traits.get("avg_capability_performance", 0.0) < MIN_PERFORMANCE_FOR_NAMING:
            return False # Performance not high enough yet

        log(f"[IdentityEngine] Conditions met for self-naming attempt at tick {current_tick}.", level="INFO")
        return True

    def _derive_qualitative_traits(self) -> List[str]:
        """
        Derives a list of qualitative trait descriptors based on the quantitative dominant_traits.
        """
        qualitative = []
        if not self.dominant_traits:
            return ["nascent", "unprofiled"] # Default if no traits calculated yet

        # Efficiency
        if self.dominant_traits.get("avg_capability_performance", 0.0) > 0.70 and \
           self.dominant_traits.get("system_success_rate", 0.0) > 0.75:
            qualitative.append("highly_efficient")
        elif self.dominant_traits.get("avg_capability_performance", 0.0) > 0.55:
            qualitative.append("efficient_performer")

        # Knowledge & Learning
        if self.dominant_traits.get("avg_knowledge_factor", 0.0) > 0.65:
            qualitative.append("knowledge_centric")
        elif self.dominant_traits.get("avg_knowledge_factor", 0.0) > 0.45:
            qualitative.append("inquisitive_learner")

        # Communication & Interaction
        if self.dominant_traits.get("avg_comms_factor", 0.0) > 0.55 or \
           self.dominant_traits.get("avg_interaction_factor", 0.0) > 0.55:
            qualitative.append("collaborative_communicator")

        # System Complexity & Activity
        if self.dominant_traits.get("num_agents", 0) > MIN_AGENTS_FOR_NAMING + 1: # e.g., if MIN is 3, then > 4 agents
            qualitative.append("complex_adaptive_system")
        if self.dominant_traits.get("total_actions_executed", 0) > (MIN_TICKS_FOR_NAMING * 0.5): # Active if many actions relative to ticks
            qualitative.append("highly_active")

        if not qualitative: # Fallback if no strong traits emerge from above
            qualitative.append("adaptive_system") # General descriptor

        return list(set(qualitative)) # Ensure unique traits

    def _get_historical_names(self) -> List[str]:
        historical_names = []
        if not os.path.exists(self.identity_log_path):
            return []
        try:
            with open(self.identity_log_path, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("event_type") == "name_synthesis":
                            # Use "new_name" from data, or "current_name" from the log entry itself
                            historical_names.append(entry.get("data", {}).get("new_name", entry.get("current_name")))
            return list(set(historical_names)) # Ensure uniqueness
        except Exception as e:
            log(f"[IdentityEngine] Error reading historical names from log: {e}", level="ERROR")
            return []

    def _generate_candidate_names(self, dominant_traits: Dict[str, Any], qualitative_traits: List[str], current_tick: int, existing_names: List[str]) -> List[str]:
        candidates = []

        # 1. Rule-based Variations & Combinatorial Generation
        prefixes = ["Evo", "Adapt", "Synap", "Cogni", "Meta", "Omni", "Core", "Flexi", "Neuro"]
        suffixes = ["Mind", "Nexus", "Flow", "System", "Intel", "Forge", "Sphere", "Matrix"]
        core_words = ["Agent", "Data", "Learn", "Comm", "Opti", "Insight", "Helix"]

        # Combinations
        for p in prefixes:
            for c in core_words:
                candidates.append(p + c)
                if random.random() < 0.5 and suffixes:
                    candidates.append(p + c + random.choice(suffixes))
        for c in core_words:
            for s in suffixes:
                candidates.append(c + s)

        # 2. Trait-based variations
        for trait in qualitative_traits:
            if "efficient" in trait: candidates.extend(["OptiCore", "StreamlineAI"])
            if "knowledge" in trait: candidates.extend(["InfoHive", "CogniBase"])
            if "collaborative" in trait: candidates.extend(["SyncMind", "NexusFlow"])
            if "adaptive" in trait: candidates.extend(["EvoMind", "FlexiGrid"])
            if "active" in trait: candidates.extend(["PulseAI", "DynamoSys"])

        # 3. Numerics/Versionings
        candidates.append(f"Evo-{current_tick}")
        candidates.append(f"SynapseV{current_tick // 100}")
        candidates.append(f"AI-{int(dominant_traits.get('avg_capability_performance', 0)*100)}")

        # 4. Controlled Randomized Elements
        for _ in range(3): # Add 3 random-ish names
            random_part = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4))
            candidates.append(f"{random.choice(prefixes)}{random_part}")

        # Filter out duplicates and existing names
        unique_candidates = list(set(candidates))
        final_candidates = [c for c in unique_candidates if c.lower() not in [n.lower() for n in existing_names]]

        log(f"[IdentityEngine] Generated {len(final_candidates)} candidate names.", level="DEBUG")
        return final_candidates # Do not limit here, let evaluation handle it

    def _evaluate_name_fitness(self, candidate_name: str, dominant_traits: Dict[str, Any], qualitative_traits: List[str], existing_names: List[str]) -> float:
        fitness = 0.0

        # Relevance Score (0-1) - based on keywords matching traits
        relevance_score = 0.0
        name_lower = candidate_name.lower()
        relevant_keywords = set(qualitative_traits + [
            "evo", "adapt", "synap", "cogni", "meta", "omni", "core", "flexi", "neuro",
            "mind", "nexus", "flow", "system", "intel", "forge", "sphere", "matrix",
            "agent", "data", "learn", "comm", "opti", "insight", "helix", "pulse", "dynamo"
        ])
        for keyword in relevant_keywords:
            if keyword in name_lower:
                relevance_score += 0.1 # Small bonus for each relevant keyword
        
        # Increase relevance if the name directly reflects strong quantitative traits
        if dominant_traits.get("avg_capability_performance", 0.0) > 0.7 and ("opti" in name_lower or "efficient" in name_lower):
            relevance_score += 0.2
        if dominant_traits.get("avg_knowledge_factor", 0.0) > 0.6 and ("cogni" in name_lower or "info" in name_lower):
            relevance_score += 0.2

        fitness += relevance_score * 0.4 # 40% weight

        # Uniqueness Score (0-1) - penalize similarity to existing names
        uniqueness_score = 1.0
        for existing_name in existing_names:
            sim = self._jaccard_similarity(name_lower, existing_name.lower())
            uniqueness_score -= sim * 0.5 # Penalize based on similarity, max 0.5 reduction
        fitness += uniqueness_score * 0.3 # 30% weight

        # Conciseness/Memorability Score (0-1) - reward shorter names
        length_penalty = max(0, (len(candidate_name) - 10) * 0.05) # Penalize names over 10 chars
        memorability_score = max(0, 1.0 - length_penalty)
        fitness += memorability_score * 0.2 # 20% weight

        # Novelty Score (0-1) - simple heuristic to reward uniqueness in structure
        novelty_score = 0.5
        if re.search(r'\d+$', candidate_name): # Penalize names ending with numbers
            novelty_score -= 0.1
        if any(f"{p}{s}" in name_lower for p in ["evo", "synap"] for s in ["sys", "net"]):
            novelty_score -= 0.05 # Slightly penalize very common combos
        fitness += novelty_score * 0.1 # 10% weight

        return max(0.0, min(fitness, 1.0)) # Clamp score between 0 and 1

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        """Calculates Jaccard similarity between two strings based on character trigrams."""
        def get_trigrams(text):
            return set(text[i:i+3] for i in range(len(text) - 2))

        trigrams1 = get_trigrams(s1)
        trigrams2 = get_trigrams(s2)

        if not trigrams1 and not trigrams2: return 1.0 # Both empty, considered identical
        if not trigrams1 or not trigrams2: return 0.0 # One empty, one not

        intersection = len(trigrams1.intersection(trigrams2))
        union = len(trigrams1.union(trigrams2))
        return intersection / union

    def _synthesize_identity_elements(self, current_tick: int):
        if not self.llm_planner:
            log("[IdentityEngine] LLM Planner not available for synthesis.", level="WARNING")
            return

        derived_qualitative_traits = self._derive_qualitative_traits()
        historical_names = self._get_historical_names()
        all_current_agent_names = self.meta_agent.get_all_agent_names()
        existing_names = list(set(historical_names + all_current_agent_names)) # Combine all known names

        candidate_names = self._generate_candidate_names(
            self.dominant_traits, derived_qualitative_traits, current_tick, existing_names
        )

        best_candidate_name = None
        highest_fitness = -1.0

        for candidate_name in candidate_names:
            fitness = self._evaluate_name_fitness(
                candidate_name, self.dominant_traits, derived_qualitative_traits, existing_names
            )
            log(f"[IdentityEngine] Candidate: '{candidate_name}', Fitness: {fitness:.3f}", level="DEBUG")
            if fitness > highest_fitness:
                highest_fitness = fitness
                best_candidate_name = candidate_name

        if best_candidate_name and best_candidate_name != self.current_name:
            old_name = self.current_name
            self.current_name = best_candidate_name
            self._log_event("name_synthesis", {"old_name": old_name, "new_name": self.current_name, "fitness": highest_fitness})
            log(f"[IdentityEngine] Name synthesized: {self.current_name} (Fitness: {highest_fitness:.3f})", level="INFO")

            # For purpose, ask LLM based on chosen name and traits
            purpose_prompt = f"""
            The AI system has adopted the name "{self.current_name}".
            Its dominant traits are: {json.dumps(self.dominant_traits)}.
            Its key characteristics are: {', '.join(derived_qualitative_traits)}.
            Based on this, suggest a concise and refined primary purpose statement for this AI.
            New Suggested Purpose:
            """
            try:
                response_text = self.llm_planner.generate_text(purpose_prompt, max_tokens=100, temperature=0.5)
                if response_text:
                    # Attempt to extract text after "New Suggested Purpose:"
                    if "New Suggested Purpose:" in response_text:
                        new_purpose_suggestion = response_text.split("New Suggested Purpose:", 1)[-1].strip()
                    else: # Fallback if LLM doesn't follow exact format
                        new_purpose_suggestion = response_text.strip()

                    if new_purpose_suggestion and new_purpose_suggestion != self.current_purpose:
                        old_purpose = self.current_purpose
                        self.current_purpose = new_purpose_suggestion
                        self._log_event("purpose_synthesis", {"old_purpose": old_purpose, "new_purpose": self.current_purpose})
                        log(f"[IdentityEngine] Purpose synthesized: {self.current_purpose}", level="INFO")
            except Exception as e:
                log(f"[IdentityEngine] Error during purpose synthesis: {e}", level="ERROR", exc_info=True)
                self._log_event("purpose_synthesis_error", {"error": str(e)})

    def get_identity(self):
        return {
            "name": self.current_name,
            "purpose": self.current_purpose,
            "dominant_traits": self.dominant_traits
        }

    def get_identity_log_path(self):
        return self.identity_log_path

    # --- Methods for Agent Evolution Tracking (merged from core.identity_engine suggestion) ---

    def record_event(self,
                     agent_id: str,
                     agent_name: str,
                     agent_lineage_id: str,
                     agent_generation: int,
                     event_type: str,
                     event_details: Dict[str, Any],
                     tick: Optional[int] = None):
        """
        Records a significant evolutionary event for an agent.
        The event is stored in the KnowledgeBase, grouped by the agent_id.
        """
        if tick is None:
            tick = self.context_manager.get_tick()

        log_entry_data = {
            "event_id": f"{event_type}_{tick}_{agent_id[:8]}", # Unique enough for logging
            "timestamp": time.time(), # Use time module, ensure it's imported if not already
            "tick": tick,
            "agent_id": agent_id,
            "agent_name_at_event": agent_name,
            "agent_lineage_id": agent_lineage_id,
            "agent_generation_at_event": agent_generation,
            "event_type": event_type,
            "details": event_details
        }

        self.knowledge_base.store(
            lineage_id=agent_id, # Use agent_id as the KB lineage_id for grouping its events
            storing_agent_name="IdentityEngine",
            item=log_entry_data,
            tick=tick,
            category=self.EVOLUTION_LOG_CATEGORY,
            data_format="application/json"
        )
        log(f"[IdentityEngine] Recorded agent event '{event_type}' for agent '{agent_id}'. Tick: {tick}", level="DEBUG")

    def get_evolution_history(self, identifier: str, id_type: str = "agent_id", current_tick: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves the evolution history for a specific agent_id or an agent's true lineage_id.
        """
        if current_tick is None:
            current_tick = self.context_manager.get_tick()

        history_event_data = []
        if id_type == "agent_id":
            kb_entries = self.knowledge_base.retrieve_full_entries(
                lineage_id=identifier, # This is the agent_id used for KB storage
                query_params={"category": self.EVOLUTION_LOG_CATEGORY, "sort_by_tick": "asc"},
                current_tick=current_tick
            )
            history_event_data = [entry.get("data") for entry in kb_entries if entry.get("data")]
        elif id_type == "lineage_id": # This part remains potentially slow, as discussed
            all_agent_ids_in_kb = list(self.knowledge_base.store_data.keys())
            for agent_id_key in all_agent_ids_in_kb:
                kb_entries = self.knowledge_base.retrieve_full_entries(lineage_id=agent_id_key, query_params={"category": self.EVOLUTION_LOG_CATEGORY}, current_tick=current_tick)
                for entry in kb_entries:
                    data = entry.get("data")
                    if data and data.get("agent_lineage_id") == identifier: history_event_data.append(data)
            if history_event_data: history_event_data.sort(key=lambda x: x.get("tick", 0))
        else:
            log(f"[IdentityEngine] Unknown id_type '{id_type}' for get_evolution_history.", level="ERROR")
            return []
        return [entry for entry in history_event_data if entry]
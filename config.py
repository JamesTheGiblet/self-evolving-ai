# c:/Users/gilbe/Desktop/self-evolving-ai/config.py
from dotenv import load_dotenv
import os
load_dotenv() # Load variables from .env file into environment variables

# Simulation timing
TICK_INTERVAL = 0.5  # seconds for ContextManager tick, 0 for max speed
MAIN_LOOP_SLEEP = 0.01 # seconds, to prevent 100% CPU usage if tasks are very fast

# API Configuration
API_HOST = '0.0.0.0'
API_PORT = 5001
API_DEBUG_MODE = False # Flask debug mode
API_USE_RELOADER = False # Flask use_reloader

# Agent Configuration
DEFAULT_MAX_AGENT_AGE = 1000 # Default lifespan in ticks if not overridden
DEFAULT_INITIAL_ENERGY = 100.0 # Default starting energy for agents
BASE_TICK_ENERGY_COST = 0.05 # Small passive energy drain per tick for all agents

# --- Configuration for Temporary Agents ---
TEMP_AGENT_DEFAULT_MAX_AGE = 200  # Default lifespan in ticks for temporary agents (e.g., shorter than normal)
TEMP_AGENT_DEFAULT_INITIAL_ENERGY = 50.0 # Default starting energy for temporary agents (e.g., less than normal)
# -----------------------------------------

# Task Agent Behavior Switching
TASK_AGENT_MIN_EXECS_FOR_EXPLOIT = 10 # Minimum capability executions before considering switching from explore
TASK_AGENT_MIN_AVG_REWARD_FOR_EXPLOIT = 0.1 # Minimum average reward required to switch from explore

# LLM Configuration
LOCAL_LLM_API_BASE_URL = os.environ.get("LOCAL_LLM_API_BASE_URL", "http://localhost:11434/api/chat") # Default Ollama chat endpoint
LOCAL_LLM_DEFAULT_MODEL = os.environ.get("LOCAL_LLM_DEFAULT_MODEL", "mistral") # If you pulled mistral
DEFAULT_LLM_MODEL = LOCAL_LLM_DEFAULT_MODEL # Set the local model as the default for the system
LOCAL_LLM_REQUEST_TIMEOUT = 180 # Default timeout in seconds for local LLM requests
LOCAL_LLM_MAX_RETRIES = 2       # Number of retries for LLM calls
LOCAL_LLM_RETRY_DELAY = 5       # Seconds to wait between LLM call retries

# Knowledge Base and Fact Memory Configuration
KB_INITIAL_RELEVANCE_SCORE = 0.5  # Default relevance for new items
KB_MAX_RELEVANCE_SCORE = 1.0
KB_DECAY_RATE_PER_DAY = 0.05       # How much score reduces if not accessed for a day
KB_ACCESS_COUNT_WEIGHT = 0.05     # Weight for access frequency
KB_RECENCY_WEIGHT = 0.15          # Weight for how recently an item was accessed
KB_POSITIVE_FEEDBACK_WEIGHT = 0.25 # Weight for positive feedback
KB_NEGATIVE_FEEDBACK_PENALTY = 0.3 # Penalty for negative feedback
KB_PRUNING_THRESHOLD = 0.05       # Relevance score below which items might be pruned
KB_SECONDS_PER_DAY = 86400        # For calculating decay based on time

# Identity Engine Configuration
IDENTITY_REFLECTION_INTERVAL_TICKS = 100 # How many ticks between identity reflection attempts
PROJECT_ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) # Base path for logs, etc.
KB_RECENCY_DECAY_RATE_PER_DAY = 0.1  # Daily decay rate for the recency effect (0.0 to 1.0)
KB_ACCESS_COUNT_CAP_FOR_RELEVANCE = 10 # Max access count to consider for relevance bonus

# Triangulated Insight Auto-Trigger Defaults (can be overridden in agent's capability_params)
DEFAULT_AUTO_DIAGNOSIS_ENABLED = True
DEFAULT_MIN_ATTEMPTS_FOR_FAILURE_CHECK = 10 # Min attempts of a capability before checking its failure rate
DEFAULT_FAILURE_RATE_THRESHOLD_FOR_INSIGHT = 0.60 # e.g., 60% failure rate

# Mutation Engine Configuration
DEFAULT_STOP_WORDS = set([
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "of", "to", "for", "and",
    "it", "this", "that", "he", "she", "they", "i", "you", "we", "me", "my", "your", "our",
    "with", "by", "from", "as", "if", "or", "not", "be", "has", "had", "do", "does", "did",
    "will", "can", "could", "should", "would", "p", "br", "div", "span", "href", "www", "http", "https"
])
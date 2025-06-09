"""
Standalone script to demonstrate CodeGenAgent's capability generation.
"""

# Assuming this script is run from the 'self-evolving-ai' directory,
# Python can find the 'agents' package.
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.code_gen_agent import CodeGenAgent, LLMInterface # noqa: E402 (LLMInterface for direct use if needed)
import config # noqa: E402
from utils.logger import log # Import the centralized logger
import json

def run_standalone_demonstration():
    """
    Runs a standalone demonstration of the CodeGenAgent's
    `demonstrate_capability_generation` method.
    """
    log("--- Starting Standalone CodeGenAgent Demonstration ---", level="INFO")

    # Initialize LLMInterface (CodeGenAgent will use this)
    llm_interface = LLMInterface(
        model_name=config.LOCAL_LLM_DEFAULT_MODEL
    )
    log("LLMInterface initialized for CodeGenAgent.", level="DEBUG")

    # Initialize the CodeGenAgent
    code_gen = CodeGenAgent(llm_interface=llm_interface)
    log("CodeGenAgent instance created for demonstration.", level="INFO")

    # Example capability request
    desc = "Create a Python function that takes a list of numbers and returns their sum."
    guide = "The function should be named 'calculate_sum_standalone_demo' and include a comprehensive docstring explaining its purpose, arguments, and return value."

    outcome = code_gen.demonstrate_capability_generation(
        capability_description=desc,
        capability_guidelines=guide
    )

    log(f"\n--- Standalone Demonstration Outcome ---", level="INFO")
    log(json.dumps(outcome, indent=2), level="INFO")
    log("--- Standalone CodeGenAgent Demonstration Complete ---", level="INFO")

if __name__ == "__main__":
    run_standalone_demonstration()
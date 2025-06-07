"""
CodeGen Skill Agent

This module defines the CodeGenAgent, a specialized agent responsible for
writing and modifying Python code using a Large Language Model (LLM).
Its capabilities include refactoring existing code, scaffolding new
functionalities, and performing radical code mutations.
"""

from typing import List, Dict, Any, Optional
import requests
import json
import config # For LLM API settings
from utils.logger import log # For logging


class LLMInterface:
    """
    An interface to interact with a Large Language Model,
    specifically designed for chat-based interactions like Ollama's /api/chat.
    """

    def __init__(self, model_name: str = "default_code_model"):
        self.model_name = model_name
        self.api_url = config.LOCAL_LLM_API_BASE_URL
        self.timeout = config.LOCAL_LLM_REQUEST_TIMEOUT
        log(f"LLMInterface initialized with model: {self.model_name}, API URL: {self.api_url}", level="INFO")

    def generate_code(self, messages: List[Dict[str, str]]) -> str:
        """
        Sends a request to the LLM for code generation using a list of messages.

        Args:
            messages: A list of message dictionaries, e.g.,
                      [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

        Returns:
            A string representing the LLM-generated code.
        """
        log(f"\n--- LLM Query ---", level="DEBUG")
        log(f"Model: {self.model_name}", level="DEBUG")
        log(f"Messages: {json.dumps(messages, indent=2)}", level="DEBUG")
        log(f"--- End LLM Query ---\n", level="DEBUG")

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False  # Get the full response at once
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_data = response.json()
            
            if response_data and "message" in response_data and "content" in response_data["message"]:
                generated_content = response_data["message"]["content"]
                log("LLM response received successfully.", level="INFO")
                # Attempt to strip markdown code block delimiters
                stripped_content = generated_content.strip()
                if stripped_content.startswith("```python") and stripped_content.endswith("```"):
                    stripped_content = stripped_content[len("```python"):-len("```")].strip()
                elif stripped_content.startswith("```") and stripped_content.endswith("```"):
                    # Generic markdown block
                    stripped_content = stripped_content[len("```"):-len("```")].strip()
                    # If there was a language hint on the first line after ```, remove it
                    if '\n' in stripped_content:
                        first_line, rest_of_content = stripped_content.split('\n', 1)
                        if not first_line.strip().isalnum(): # Heuristic: if the first line isn't just a word (like 'python')
                            stripped_content = rest_of_content
                return stripped_content
            else:
                log(f"LLM response missing expected content. Response: {response_data}", level="ERROR")
                return f"# Error: LLM response missing expected content. Response: {response_data}"

        except requests.exceptions.RequestException as e:
            log(f"LLM API request failed: {e}", level="ERROR")
            return f"# Error: LLM API request failed: {e}"
        except json.JSONDecodeError as e:
            log(f"Failed to decode LLM API response: {e}. Response text: {response.text}", level="ERROR")
            return f"# Error: Failed to decode LLM API response: {e}"


class CodeGenAgent:
    """
    A SkillAgent specialized in Python code generation and modification.
    It uses an LLM-powered skill to perform its tasks.
    """

    def __init__(self, llm_interface: Optional[LLMInterface] = None):
        """
        Initializes the CodeGenAgent.

        Args:
            llm_interface: An instance of LLMInterface to interact with an LLM.
                           If None, a default one will be created.
        """
        self.llm_interface = llm_interface if llm_interface else LLMInterface(model_name=config.LOCAL_LLM_DEFAULT_MODEL)
        log("CodeGenAgent initialized.", level="INFO")

    def _code_generation_skill(self, system_prompt: str, user_prompt: str) -> str:
        """
        The core skill that uses an LLM to generate or modify code.

        Args:
            system_prompt: The system message to guide the LLM's behavior.
            user_prompt: The user's specific request for code generation.

        Returns:
            The generated or modified code as a string.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.llm_interface.generate_code(messages=messages)

    def refactor_code(self, existing_code: str, refactoring_goal: str) -> str:
        """
        Identifies and refactors inefficient or redundant code blocks.

        Args:
            existing_code: The Python code string to be refactored.
            refactoring_goal: A description of the desired refactoring
                              (e.g., "improve efficiency of this loop",
                               "remove redundant checks", "make this function more readable").

        Returns:
            The refactored Python code string.
        """
        log(f"CodeGenAgent: Attempting to refactor code. Goal: {refactoring_goal}", level="INFO")
        system_prompt = (
            "You are an expert Python programming assistant. Your task is to refactor Python code based on the user's goal. "
            "You must only output the raw refactored Python code itself, without any surrounding text, explanations, or markdown code block syntax. "
            "Do not include the original code or the prompt in your response unless it's part of the refactored code."
        )
        user_prompt = f"Refactor the following Python code to achieve this goal: '{refactoring_goal}'.\n\nOriginal Code:\n```python\n{existing_code}\n```"
        return self._code_generation_skill(system_prompt=system_prompt, user_prompt=user_prompt)

    def write_new_capability(self, capability_description: str, architectural_guidelines: Optional[str] = None) -> str:
        """
        Writes boilerplate or new capability handlers based on a high-level goal.

        Args:
            capability_description: A high-level description of the new capability.
            architectural_guidelines: Optional string describing architectural patterns,
                                      interfaces to implement, or other constraints.

        Returns:
            The generated Python code string for the new capability.
        """
        log(f"CodeGenAgent: Attempting to write new capability: {capability_description}", level="INFO")
        system_prompt = (
            "You are an expert Python programming assistant. Your task is to write clean, functional Python code for a new capability based on the user's request. "
            "You must only output the raw Python code itself, without any surrounding text, explanations, or markdown code block syntax (e.g., ```python ... ```). "
            "Do not include the prompt in your response."
        )
        
        user_prompt_content = f"Generate Python code for a new capability described as: '{capability_description}'."
        if architectural_guidelines:
            user_prompt_content += f"\n\nFollow these architectural guidelines:\n{architectural_guidelines}"
        
        return self._code_generation_skill(system_prompt=system_prompt, user_prompt=user_prompt_content)

    def implement_radical_mutation(self, mutation_directive: str, existing_code_snippets: List[str]) -> str:
        """
        Performs radical mutations, like combining existing capabilities.

        Args:
            mutation_directive: A specific instruction for the radical mutation
                                (e.g., "Combine function_a and function_b into a new,
                                 more efficient function_c that achieves X").
            existing_code_snippets: A list of relevant existing code strings.

        Returns:
            The Python code string resulting from the radical mutation.
        """
        log(f"CodeGenAgent: Attempting radical mutation: {mutation_directive}", level="INFO")
        system_prompt = (
            "You are an expert Python programming assistant specializing in complex code transformations and integrations. "
            "Your task is to perform radical code mutations as described by the user, combining or altering existing code snippets. "
            "You must only output the raw Python code itself, without any surrounding text, explanations, or markdown code block syntax. "
            "Do not include the prompt in your response."
        )
        context = "\n\n".join([f"```python\n{snippet}\n```" for snippet in existing_code_snippets])
        user_prompt = f"Perform the following radical code mutation: '{mutation_directive}'.\n\nRelevant existing code snippets:\n{context}"
        return self._code_generation_skill(system_prompt=system_prompt, user_prompt=user_prompt)

if __name__ == "__main__":
    log("Demonstrating CodeGenAgent capabilities:", level="INFO")
    agent = CodeGenAgent()

    # Example: Refactor code
    sample_code_to_refactor = "def old_function(n):\n    result = []\n    for i in range(n):\n        if i % 2 == 0:\n            result.append(i)\n    return result"
    refactor_goal = "Make this function more Pythonic and efficient using a list comprehension."
    refactored_code = agent.refactor_code(sample_code_to_refactor, refactor_goal)
    log(f"Refactored Code:\n{refactored_code}\n", level="INFO")

    # Example: Write new capability
    new_cap_desc = "A new capability to fetch data from a REST API endpoint and parse the JSON response."
    arch_guide = "The function should take a URL as input, use the 'requests' library, and handle potential HTTP errors."
    new_capability_code = agent.write_new_capability(new_cap_desc, arch_guide)
    log(f"New Capability Code:\n{new_capability_code}\n", level="INFO")

    # Example: Implement radical mutation
    mutation_dir = "Combine the following two functions into a single class method that processes data and then logs it."
    func_a = "def process_data(data):\n    return data * 2"
    func_b = "def log_data(processed_data):\n    print(f'Processed: {processed_data}')"
    mutated_code = agent.implement_radical_mutation(mutation_dir, [func_a, func_b])
    log(f"Mutated Code:\n{mutated_code}\n", level="INFO")
    log("CodeGenAgent demonstration complete.", level="INFO")
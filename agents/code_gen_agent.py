"""
CodeGen Skill Agent

This module defines the CodeGenAgent, a specialized agent responsible for
writing and modifying Python code using a Large Language Model (LLM).
Its capabilities include refactoring existing code, scaffolding new
functionalities, and performing radical code mutations.
"""

from typing import List, Dict, Any, Optional
import requests
import time # For retry delay
import re # For improved markdown parsing
import json
import config # For LLM API settings
from utils.logger import log # For logging
from utils import local_llm_connector # For async LLM calls


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

    @staticmethod
    def parse_llm_code_output(generated_content: str) -> str:
        """
        Parses the LLM's raw output to extract Python code,
        stripping markdown code blocks.
        """
        if not generated_content:
            return ""
        
        stripped_content = generated_content.strip()
        # Try to find ```python ... ```
        match_python = re.search(r"```python\s*([\s\S]+?)\s*```", stripped_content, re.DOTALL)
        if match_python:
            return match_python.group(1).strip()
        
        # Try to find ``` ... ``` (generic)
        match_generic = re.search(r"```\s*([\s\S]+?)\s*```", stripped_content, re.DOTALL)
        if match_generic:
            content_in_block = match_generic.group(1).strip()
            lines = content_in_block.split('\n', 1)
            # Common language hints to strip if they are the first line inside the block
            language_hints = ["python", "py", "javascript", "java", "csharp", "cpp", "go", "rust", "text", "json", "yaml", "xml", "html", "css", "markdown", "sql"]
            if len(lines) > 1 and lines[0].strip().lower() in language_hints:
                return lines[1].strip()
            return content_in_block
        
        # If no markdown blocks are found, return the content as is, assuming it's raw code.
        return stripped_content

    def generate_code(self, messages: List[Dict[str, str]]) -> str:
        """
        Sends a request to the LLM for code generation using a list of messages.
        Primarily for direct use or testing where blocking is acceptable.

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

        last_exception = None
        for attempt in range(config.LOCAL_LLM_MAX_RETRIES + 1):
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
                    log(f"LLM response received successfully (attempt {attempt + 1}).", level="INFO")
                    return LLMInterface.parse_llm_code_output(generated_content)
                else:
                    log(f"LLM response missing expected content (attempt {attempt + 1}). Response: {response_data}", level="ERROR")
                    last_exception = ValueError(f"LLM response missing expected content. Response: {response_data}")

            except requests.exceptions.RequestException as e:
                log(f"LLM API request failed (attempt {attempt + 1}/{config.LOCAL_LLM_MAX_RETRIES + 1}): {e}", level="WARNING")
                last_exception = e
            except json.JSONDecodeError as e:
                log(f"Failed to decode LLM API response (attempt {attempt + 1}): {e}. Response text: {response.text}", level="ERROR")
                last_exception = e # Treat as a non-retryable error for this attempt, but allow overall retries if it was a transient server issue returning bad JSON

            if attempt < config.LOCAL_LLM_MAX_RETRIES:
                log(f"Waiting {config.LOCAL_LLM_RETRY_DELAY}s before retrying LLM call.", level="INFO")
                time.sleep(config.LOCAL_LLM_RETRY_DELAY)
        
        log(f"LLM call failed after {config.LOCAL_LLM_MAX_RETRIES + 1} attempts. Last error: {last_exception}", level="ERROR")
        return f"# Error: LLM call failed after multiple retries. Last error: {last_exception}"

    def generate_code_async(self, messages: List[Dict[str, str]], **llm_kwargs: Any) -> Optional[str]:
        """
        Initiates an asynchronous request to the LLM for code generation.
        The actual LLM call is handled by local_llm_connector, which should
        notify the ContextManager upon completion.

        Args:
            messages: A list of message dictionaries for the LLM.
            **llm_kwargs: Additional keyword arguments for the LLM call (e.g., temperature).

        Returns:
            A request_id string if the async call was successfully initiated, None otherwise.
        """
        log(f"\n--- LLM ASYNC Query Init ---", level="DEBUG")
        log(f"Model: {self.model_name}", level="DEBUG")
        log(f"Messages: {json.dumps(messages, indent=2)}", level="DEBUG")
        log(f"--- End LLM ASYNC Query Init ---\n", level="DEBUG")

        request_id = local_llm_connector.call_local_llm_api_async(
            prompt_messages=messages,
            model_name=self.model_name,
            **llm_kwargs
        )
        return request_id


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

    def _code_generation_skill_async(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        The core skill that initiates an asynchronous LLM call to generate or modify code.

        Args:
            system_prompt: The system message to guide the LLM's behavior.
            user_prompt: The user's specific request for code generation.

        Returns:
            A request_id if the async call was initiated, None otherwise.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        # Use the asynchronous method of LLMInterface
        return self.llm_interface.generate_code_async(messages=messages)

    # Note: refactor_code and implement_radical_mutation would also need to become async
    # if they are to be used by MutationEngine in a non-blocking way.
    # For now, focusing on write_new_capability as it's directly used by MutationEngine's evolution.
    def refactor_code(self, existing_code: str, refactoring_goal: str) -> Optional[str]:
        """
        Identifies and refactors inefficient or redundant code blocks.

        Args:
            existing_code: The Python code string to be refactored.
            refactoring_goal: A description of the desired refactoring
                              (e.g., "improve efficiency of this loop",
                               "remove redundant checks", "make this function more readable").

        Returns:
            A request_id if the async call was initiated, None otherwise.
        """
        log(f"CodeGenAgent: Attempting to refactor code. Goal: {refactoring_goal}", level="INFO")
        system_prompt = (
            "You are an expert Python programming assistant. Your task is to refactor Python code based on the user's goal. "
            "You must only output the raw refactored Python code itself, without any surrounding text, explanations, or markdown code block syntax. "
            "Do not include the original code or the prompt in your response unless it's part of the refactored code."
        )
        user_prompt = f"Refactor the following Python code to achieve this goal: '{refactoring_goal}'.\n\nOriginal Code:\n```python\n{existing_code}\n```"
        return self._code_generation_skill_async(system_prompt=system_prompt, user_prompt=user_prompt)

    def write_new_capability(self, capability_description: str, architectural_guidelines: Optional[str] = None) -> Optional[str]:
        """
        Writes boilerplate or new capability handlers based on a high-level goal.

        Args:
            capability_description: A high-level description of the new capability.
            architectural_guidelines: Optional string describing architectural patterns,
                                      interfaces to implement, or other constraints.

        Returns:
            A request_id if the async call was initiated, None otherwise.
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
        
        return self._code_generation_skill_async(system_prompt=system_prompt, user_prompt=user_prompt_content)

    def implement_radical_mutation(self, mutation_directive: str, existing_code_snippets: List[str]) -> Optional[str]:
        """
        Performs radical mutations, like combining existing capabilities.

        Args:
            mutation_directive: A specific instruction for the radical mutation
                                (e.g., "Combine function_a and function_b into a new,
                                 more efficient function_c that achieves X").
            existing_code_snippets: A list of relevant existing code strings.

        Returns:
            A request_id if the async call was initiated, None otherwise.
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
        return self._code_generation_skill_async(system_prompt=system_prompt, user_prompt=user_prompt)

    def implement_function_body_async(self,
                                      function_signature: str,
                                      class_context: Optional[str],
                                      docstring: Optional[str],
                                      overall_skill_goal: str) -> Optional[str]:
        """
        Generates the body for a specific function/method stub using an async LLM call.

        Args:
            function_signature: The full signature of the function/method (e.g., "def my_method(self, arg1):").
            class_context: The source code of the class if the stub is a method, otherwise None.
            docstring: The docstring of the function/method, if available.
            overall_skill_goal: A description of what the entire skill/class is supposed to do.

        Returns:
            A request_id if the async call was initiated, None otherwise.
        """
        log(f"CodeGenAgent: Requesting implementation for stub: {function_signature}", level="INFO")
        system_prompt = (
            "You are an expert Python programmer. Your task is to implement the body of the given function/method. "
            "Focus only on the internal logic of this specific function. "
            "Output only the raw Python code for the function's body (indented appropriately if it's a method body, "
            "otherwise just the statements). Do NOT include the function signature itself or any surrounding class definitions."
        )
        user_prompt = f"Implement the body for the following Python function/method:\n\n"
        if class_context:
            user_prompt += f"Within the class context:\n```python\n{class_context}\n```\n\n"
        user_prompt += f"Function/Method Signature:\n```python\n{function_signature}\n```\n"
        if docstring:
            user_prompt += f"Docstring (intent):\n```python\n{docstring}\n```\n"
        user_prompt += f"The overall goal of the skill/class this function belongs to is: '{overall_skill_goal}'.\n"
        user_prompt += "Provide only the Python code for the body of this function/method, ready to be inserted."
        
        return self._code_generation_skill_async(system_prompt=system_prompt, user_prompt=user_prompt)

if __name__ == "__main__":
    log("Demonstrating CodeGenAgent capabilities:", level="INFO")
    agent = CodeGenAgent()

    # Example: Refactor code
    sample_code_to_refactor = "def old_function(n):\n    result = []\n    for i in range(n):\n        if i % 2 == 0:\n            result.append(i)\n    return result"
    refactor_goal = "Make this function more Pythonic and efficient using a list comprehension."
    refactor_req_id = agent.refactor_code(sample_code_to_refactor, refactor_goal)
    if refactor_req_id:
        log(f"Refactor request sent. Request ID: {refactor_req_id}. Monitor ContextManager for response.", level="INFO")
    else:
        log(f"Failed to send refactor request.", level="ERROR")

    # Example: Write new capability
    new_cap_desc = "A new capability to fetch data from a REST API endpoint and parse the JSON response."
    arch_guide = "The function should take a URL as input, use the 'requests' library, and handle potential HTTP errors."
    new_cap_req_id = agent.write_new_capability(new_cap_desc, arch_guide)
    if new_cap_req_id:
        log(f"New capability request sent. Request ID: {new_cap_req_id}. Monitor ContextManager for response.", level="INFO")
    else:
        log(f"Failed to send new capability request.", level="ERROR")

    # Example: Implement radical mutation
    mutation_dir = "Combine the following two functions into a single class method that processes data and then logs it."
    func_a = "def process_data(data):\n    return data * 2"
    func_b = "def log_data(processed_data):\n    print(f'Processed: {processed_data}')"
    mutation_req_id = agent.implement_radical_mutation(mutation_dir, [func_a, func_b])
    if mutation_req_id:
        log(f"Radical mutation request sent. Request ID: {mutation_req_id}. Monitor ContextManager for response.", level="INFO")
    else:
        log(f"Failed to send radical mutation request.", level="ERROR")

    # To see results in this standalone demo, you'd need a mock ContextManager
    # or a simple loop checking for responses. For the full system, TaskAgent's
    # _handle_pending_llm_operations is a good example of how to poll.
    # For this demo, we'll just log that requests were sent.
    # In a real test, you might:
    # time.sleep(config.LOCAL_LLM_REQUEST_TIMEOUT + 5) # Wait for LLM
    # response_data = context_manager_mock.get_llm_response_if_ready(new_cap_req_id)
    # if response_data and response_data.get("status") == "completed":
    #     parsed_code = LLMInterface.parse_llm_code_output(response_data.get("response"))
    #     log(f"Received and Parsed New Capability Code:\n{parsed_code}\n", level="INFO")
    log("CodeGenAgent demonstration complete.", level="INFO")
"""
CodeGen Skill Agent

This module defines the CodeGenAgent, a specialized agent responsible for
writing and modifying Python code using a Large Language Model (LLM).
Its capabilities include refactoring existing code, scaffolding new
functionalities, and performing radical code mutations.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests
import time # For retry delay
import re # For improved markdown parsing
import os # For file operations in demonstrate_capability_generation
import ast # For syntax validation in demonstrate_capability_generation
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
        log(f"CodeGenAgent v0.3 initialized.", level="INFO")

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

    def generate_capability_code(self, capability_description: str, capability_guidelines: str) -> Optional[str]:
        """
        Generates Python code for a new capability using the LLM (synchronously).
        This method returns the raw code string.
        """
        log(f"[CodeGenAgent] Generating capability code (sync). Description: '{capability_description}', Guidelines: '{capability_guidelines}'", level="INFO")
        system_prompt = (
            "You are an expert Python programmer. Your task is to write a single, self-contained Python function "
            "based on the provided description and guidelines. The function should be robust and include a clear docstring. "
            "Only output the Python code for the function, without any introductory text, explanations, or markdown code blocks."
        )
        user_prompt = (
            f"Capability Description: {capability_description}\n"
            f"Guidelines: {capability_guidelines}\n"
            f"Please generate the Python code for this function."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        # Uses the synchronous method of LLMInterface
        generated_code = self.llm_interface.generate_code(messages)
        
        if generated_code and not generated_code.startswith("# Error: LLM call failed"):
            # LLMInterface.parse_llm_code_output is static, so call it directly
            parsed_code = LLMInterface.parse_llm_code_output(generated_code)
            log(f"[CodeGenAgent] Successfully generated code snippet (sync).", level="INFO")
            return parsed_code.strip()
        else:
            log(f"[CodeGenAgent] Failed to generate code from LLM (sync). Raw response: {generated_code}", level="WARN")
            return None

    def _get_first_function_name(self, code_string: str) -> Optional[str]:
        try:
            tree = ast.parse(code_string)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError:
            return None
        return None

    def _has_docstring(self, parsed_ast_node: ast.AST, function_name: str) -> bool:
        for node in ast.walk(parsed_ast_node):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                if node.body and isinstance(node.body[0], ast.Expr) and \
                   isinstance(node.body[0].value, ast.Constant) and \
                   isinstance(node.body[0].value.value, str):
                    return True
                elif node.body and isinstance(node.body[0], ast.Expr) and \
                     isinstance(node.body[0].value, ast.Str): # Python < 3.8
                    return True
        return False

    def demonstrate_capability_generation(self, capability_description: str, capability_guidelines: str) -> Dict[str, Any]:
        """
        Demonstrates the full cycle: code generation, validation, (conditional) testing, and saving.
        Used by the GUI and standalone demo. This is a synchronous operation.
        Returns a dictionary with the outcome.
        """
        log(f"[CodeGenAgent] Starting demonstration of capability generation.", level="INFO")
        log(f"Description: '{capability_description}'", level="INFO")
        log(f"Guidelines: '{capability_guidelines}'", level="INFO")

        outcome = {"success": False, "message": "Demonstration started.", "generated_code_path": None, "test_results": None}

        new_code = self.generate_capability_code(capability_description, capability_guidelines)

        if not new_code:
            outcome["message"] = "Code generation failed: No code returned from LLM."
            log(outcome["message"], level="ERROR")
            return outcome

        log(f"[CodeGenAgent] Generated code for demonstration:\n{new_code}\n", level="INFO")
        outcome["generated_code_preview"] = new_code[:200] + "..." if len(new_code) > 200 else new_code

        try:
            parsed_ast = ast.parse(new_code)
            log("Generated code is syntactically valid Python.", level="INFO")
            outcome["validation_syntax"] = "Valid"

            function_name_from_code = self._get_first_function_name(new_code)
            if function_name_from_code:
                docstring_present = self._has_docstring(parsed_ast, function_name_from_code)
                log(f"Docstring check for '{function_name_from_code}': {'Present' if docstring_present else 'Missing'}",
                    level="INFO" if docstring_present else "WARN")
                outcome["validation_docstring"] = 'Present' if docstring_present else 'Missing'
            else:
                log("Could not determine function name from AST.", level="WARN")
                outcome["validation_docstring"] = 'N/A (no function found)'

            # Conditional Testing: Only for the specific "sum list" example
            is_sum_example = "sum" in capability_description.lower() and "list" in capability_description.lower()
            all_tests_passed = not is_sum_example 

            if is_sum_example and function_name_from_code:
                log(f"Attempting to test generated function '{function_name_from_code}' (sum example).", level="INFO")
                local_scope = {}
                exec(compile(parsed_ast, filename="<ast_test>", mode="exec"), {'__builtins__': __builtins__}, local_scope)
                if function_name_from_code in local_scope and callable(local_scope[function_name_from_code]):
                    generated_function = local_scope[function_name_from_code]
                    test_cases = [{"input": [1, 2, 3], "expected": 6, "name": "Simple Sum"}] # Simplified test
                    outcome["test_results"] = []
                    for tc in test_cases:
                        actual = generated_function(tc["input"])
                        passed = actual == tc["expected"]
                        outcome["test_results"].append({"name": tc["name"], "status": "PASSED" if passed else "FAILED", "actual": actual, "expected": tc["expected"]})
                        if not passed: all_tests_passed = False
                    log(f"Testing for '{function_name_from_code}' completed. All passed: {all_tests_passed}", level="INFO")

            if all_tests_passed:
                generated_code_dir = os.path.join(config.PROJECT_ROOT_PATH, "generated_capabilities")
                os.makedirs(generated_code_dir, exist_ok=True)
                file_name = os.path.join(generated_code_dir, f"{function_name_from_code or 'generated_code'}_{int(time.time())}.py")
                with open(file_name, "w") as f:
                    f.write(f"# Generated by CodeGenAgent\n# Description: {capability_description}\n# Guidelines: {capability_guidelines}\n\n{new_code}")
                log(f"Successfully saved generated code to: '{os.path.abspath(file_name)}'", level="INFO")
                outcome["success"] = True
                outcome["message"] = f"Code generated, validated, {'tested, ' if is_sum_example else ''}and saved."
                outcome["generated_code_path"] = os.path.abspath(file_name)
            else:
                outcome["message"] = "Code generated and validated, but testing failed or was skipped. Code not saved as final."
                log(outcome["message"], level="WARN")

        except SyntaxError as se:
            outcome["message"] = f"Generated code has a syntax error: {se}"
            log(outcome["message"], level="ERROR")
            outcome["validation_syntax"] = f"Invalid: {se}"
        except Exception as e:
            outcome["message"] = f"An error occurred during validation/testing/saving: {e}"
            log(outcome["message"], level="ERROR", exc_info=True)

        log(f"[CodeGenAgent] Demonstration outcome: {outcome['message']}", level="INFO")
        return outcome

if __name__ == "__main__":
    log("Demonstrating CodeGenAgent capabilities:", level="INFO")
    agent = CodeGenAgent()

    # Demonstrate the synchronous full cycle generation
    desc = "Create a Python function that takes a list of numbers and returns their sum."
    guide = "The function should be named 'calculate_sum_standalone_demo' and include a comprehensive docstring."
    
    outcome = agent.demonstrate_capability_generation(
        capability_description=desc,
        capability_guidelines=guide
    )

    log(f"\n--- CodeGenAgent Standalone Demonstration Outcome ---", level="INFO")
    log(json.dumps(outcome, indent=2), level="INFO")
    log("--- CodeGenAgent Standalone Demonstration Complete ---", level="INFO")

    # The async methods like write_new_capability, refactor_code, etc.,
    # would require a running ContextManager and an event loop to see their results,
    # as they return request_ids for asynchronous processing.
    # Their demonstration is better suited within the full application context.
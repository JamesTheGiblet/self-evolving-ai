"""
Main application script demonstrating the use of CodeGenAgent.
"""

# Assuming this script is run from the 'self-evolving-ai' directory,
# Python can find the 'agents' package.
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.code_gen_agent import CodeGenAgent, LLMInterface # noqa: E402
import config # noqa: E402
import ast # For syntax validation
from urllib.parse import urlparse # noqa: E402
from typing import Optional # Import Optional for type hinting
from utils.logger import log # Import the centralized logger

def run_evolutionary_cycle(capability_description: str, capability_guidelines: str):
    log("Starting an evolutionary cycle demonstration...")

    # Initialize LLMInterface for CodeGenAgent using Ollama settings from config
    ollama_host = None
    if config.LOCAL_LLM_API_BASE_URL:
        parsed_url = urlparse(config.LOCAL_LLM_API_BASE_URL)
        if parsed_url.scheme and parsed_url.netloc:
            ollama_host = f"{parsed_url.scheme}://{parsed_url.netloc}"

    log(f"Attempting to initialize LLMInterface with model: {config.LOCAL_LLM_DEFAULT_MODEL}")
    if ollama_host:
        log(f"Derived Ollama host (for reference, LLMInterface uses config directly): {ollama_host}")
    else:
        log(f"Ollama host not derived from LOCAL_LLM_API_BASE_URL: '{config.LOCAL_LLM_API_BASE_URL}'. LLMInterface uses this URL directly from config. Ensure it's correctly set if using Ollama.", level="WARN")

    llm_interface = LLMInterface(
        model_name=config.LOCAL_LLM_DEFAULT_MODEL
    ) # host argument removed, LLMInterface should use config.LOCAL_LLM_API_BASE_URL internally

    # Initialize the CodeGenAgent
    code_gen = CodeGenAgent(llm_interface=llm_interface)
    log("CodeGenAgent initialized for demonstration.", level="INFO")

    log(f"\n--- Task: Requesting a new capability ---", level="INFO")
    log(f"Description: '{capability_description}'", level="INFO")
    log(f"Guidelines: '{capability_guidelines}'", level="INFO")

    def get_first_function_name(code_string: str) -> Optional[str]:
        try:
            tree = ast.parse(code_string)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError:
            return None
        return None

    def has_docstring(parsed_ast_node: ast.AST, function_name: str) -> bool:
        for node in ast.walk(parsed_ast_node):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    return True
                # For Python < 3.8, docstrings are ast.Str
                elif node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
                    return True
        return None

    new_code = None
    try:
        # The CodeGenAgent itself logs the LLM query details at DEBUG level
        new_code = code_gen.write_new_capability(capability_description, capability_guidelines)
    except Exception as e:
        log(f"Error calling CodeGenAgent: {e}", level="ERROR", exc_info=True)

    if new_code:
        log(f"Generated code:\n{new_code}\n", level="INFO")

        # 1. Validate the generated code
        log("--- Validating generated code ---", level="INFO")
        try:
            # Attempt to parse for syntax validation
            parsed_ast = ast.parse(new_code) # Keep the parsed AST
            log("Generated code is syntactically valid Python.", level="INFO")

            # Dynamically get the function name from the parsed code
            function_name_from_code = get_first_function_name(new_code)

            if function_name_from_code:
                docstring_present = has_docstring(parsed_ast, function_name_from_code)
                log(f"Docstring check for '{function_name_from_code}': {'Present' if docstring_present else 'Missing or not detected'}", level="INFO" if docstring_present else "WARN")
            # We can decide later if missing docstring should halt the process or just be a warning. For now, it's a log.

            # Attempt to execute the code in a restricted scope
            # and test the function
            local_scope = {}
            # Provide a restricted global scope, allowing only built-ins.
            # This is safer than passing the full globals() of the script.
            exec(compile(parsed_ast, filename="<ast>", mode="exec"), {'__builtins__': __builtins__}, local_scope)

            if function_name_from_code and function_name_from_code in local_scope and callable(local_scope[function_name_from_code]):
                generated_function = local_scope[function_name_from_code]
                log(f"Successfully defined '{function_name_from_code}' function in local scope.", level="INFO")

                # 3. Test the new capability (basic test)
                log(f"\n--- Testing '{function_name_from_code}' ---", level="INFO")
                test_cases = [
                    {"input": [1, 2, 3, 4, 5], "expected": 15, "name": "Positive Integers"},
                    {"input": [], "expected": 0, "name": "Empty List"},
                    {"input": [-1, -2, 3], "expected": 0, "name": "Mixed Integers"},
                    {"input": [10], "expected": 10, "name": "Single Element"},
                    {"input": [1.5, 2.5, 3.0], "expected": 7.0, "name": "Floating Point Numbers"}
                ]
                all_tests_passed = True
                for test_case in test_cases:
                    test_input = test_case["input"]
                    expected_output = test_case["expected"]
                    test_name = test_case["name"]
                    try:
                        actual_output = generated_function(test_input)
                        if actual_output == expected_output:
                            log(f"Test '{test_name}' PASSED: {function_name_from_code}({test_input}) = {actual_output}", level="INFO")
                        else:
                            log(f"Test '{test_name}' FAILED: {function_name_from_code}({test_input}) = {actual_output}, expected {expected_output}", level="WARN")
                            all_tests_passed = False
                    except Exception as e:
                        log(f"Test '{test_name}' ERRORED: {function_name_from_code}({test_input}) raised {e}", level="ERROR", exc_info=True)
                        all_tests_passed = False

                if all_tests_passed:
                    log("All basic tests PASSED.", level="INFO")
                    # 4. Save the code (simulated)
                    log("\n--- Saving generated code ---", level="INFO")
                    
                    # Define a directory for generated capabilities
                    generated_code_dir = os.path.join(PROJECT_ROOT, "generated_capabilities")
                    if not os.path.exists(generated_code_dir):
                        os.makedirs(generated_code_dir)
                        log(f"Created directory for generated code: {generated_code_dir}", level="INFO")

                    file_name = os.path.join(generated_code_dir, f"{function_name_from_code or 'generated_code'}.py")
                    try:
                        with open(file_name, "w") as f:
                            f.write(new_code)
                        log(f"Successfully saved generated code to: '{os.path.abspath(file_name)}'", level="INFO")
                    except IOError as e:
                        log(f"Error saving code to '{file_name}': {e}", level="ERROR", exc_info=True)
                else:
                    log("Some basic tests FAILED. Code not saved.", level="WARN")
            else:
                if function_name_from_code:
                    log(f"Error: Function '{function_name_from_code}' (derived from AST) not found in local_scope or is not callable.", level="ERROR")
                else:
                    log("Error: Could not determine function name from generated code AST, or function not found/callable.", level="ERROR")

        except SyntaxError as e:
            log(f"Generated code has a syntax error: {e}", level="ERROR")
        except Exception as e:
            log(f"An error occurred while validating or testing the generated code: {e}", level="ERROR", exc_info=True)
    else:
        log("No code was generated or an error occurred during generation.", level="WARN")

    log("Evolutionary cycle demonstration complete.", level="INFO")

if __name__ == "__main__":
    # Example usage with parameterized capability request
    desc = "Create a Python function that takes a list of numbers and returns their sum."
    guide = "The function should be named 'calculate_sum' and include a docstring."
    run_evolutionary_cycle(capability_description=desc, capability_guidelines=guide)

    # You could add more calls to run_evolutionary_cycle with different descriptions/guidelines here
    # desc2 = "Create a Python function to reverse a string."
    # guide2 = "The function should be named 'reverse_string' and handle empty strings."
    # run_evolutionary_cycle(capability_description=desc2, capability_guidelines=guide2)
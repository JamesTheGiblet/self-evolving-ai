# skills / maths_tool.py

import math 
from typing import Dict, Any, TYPE_CHECKING # Added TYPE_CHECKING
from .base_skill import BaseSkillTool # Import BaseSkillTool
from utils.logger import log # Assuming logger is needed

# For type hinting core components to avoid circular imports at runtime
if TYPE_CHECKING:
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus

# Helper functions (mostly remain the same, ensure they raise ValueErrors for invalid input)
def _add(a: float, b: float) -> float:
    return a + b

def _subtract(a: float, b: float) -> float:
    return a - b

def _multiply(a: float, b: float) -> float:
    return a * b

def _divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero is not allowed.")
    return a / b

def _power(base: float, exponent: float) -> float:
    return math.pow(base, exponent)

def _log(number: float, base: float = math.e) -> float:
    if number <= 0:
        raise ValueError("Logarithm undefined for non-positive numbers.")
    if base <= 0 or base == 1:
        raise ValueError("Logarithm base must be positive and not equal to 1.")
    return math.log(number, base)

def _sin(angle_degrees: float) -> float:
    return math.sin(math.radians(angle_degrees))

def _cos(angle_degrees: float) -> float:
    return math.cos(math.radians(angle_degrees))

class MathsTool(BaseSkillTool):
    def __init__(self,
                 skill_config: Dict[str, Any],
                 knowledge_base: 'KnowledgeBase',
                 context_manager: 'ContextManager',
                 communication_bus: 'CommunicationBus',
                 agent_name: str,
                 agent_id: str,
                 **kwargs: Any):
        """
        Initializes the MathsTool skill.

        Args:
            skill_config (dict): Configuration specific to this skill instance.
            knowledge_base (KnowledgeBase): Instance of the knowledge base.
            context_manager (ContextManager): Instance of the context manager.
            communication_bus (CommunicationBus): Instance of the communication bus.
            agent_name (str): Name of the agent this skill is associated with.
            agent_id (str): ID of the agent this skill is associated with.
        """
        super().__init__(skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id, **kwargs)
        # Define a dictionary of operations that take 2 arguments
        self.two_arg_ops = {
            "add": _add,
            "subtract": _subtract,
            "multiply": _multiply,
            "divide": _divide,
            "power": _power,
            "log": _log # _log can take 1 or 2, handle 2 args here
        }
        # Define a dictionary of operations that take 1 argument
        self.one_arg_ops = {
            "sin": _sin,
            "cos": _cos
            # Add other unary ops like "sqrt", "abs" etc.
        }
        log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}).", level="INFO")

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": "Performs various mathematical calculations.",
            "commands": {
                "add": {
                    "description": "Adds two numbers.",
                    "args_usage": "<number1> <number2>",
                    "example": "add 5 3.5",
                    "keywords": ["add", "sum", "plus", "addition", "calculate sum"]
                },
                "subtract": {
                    "description": "Subtracts the second number from the first.",
                    "args_usage": "<number1> <number2>",
                    "example": "subtract 10 4",
                    "keywords": ["subtract", "minus", "difference", "deduct"]
                },
                "multiply": {
                    "description": "Multiplies two numbers.",
                    "args_usage": "<number1> <number2>",
                    "example": "multiply 7 6",
                    "keywords": ["multiply", "times", "product", "calculation"]
                },
                "divide": {
                    "description": "Divides the first number by the second. Handles division by zero.",
                    "args_usage": "<number1> <number2>",
                    "example": "divide 20 4",
                    "keywords": ["divide", "division", "quotient"]
                },
                "power": {
                    "description": "Raises the first number to the power of the second.",
                    "args_usage": "<base> <exponent>",
                    "example": "power 2 8",
                    "keywords": ["power", "exponent", "raise to power", "involution"]
                },
                "log": {
                    "description": "Calculates the logarithm of a number with a specified base.",
                    "args_usage": "<number> <base>",
                    "example": "log 100 10",
                    "keywords": ["logarithm", "log", "calculate log"]
                }
                # sin and cos are also available but might be less common for direct LLM routing
            }
        }

    def _execute_skill(self, args: list) -> Dict[str, Any]:
        """
        Executes a math operation based on parsed arguments.
        Always returns a JSON string via _create_json_response.
        """
        log(f"[{self.skill_name}] Executing with args: {args}", level="INFO")
        command_str_for_logging = " ".join(args)

        if not args:
            return self._build_response_dict(success=False, error="No command provided.")

        command = args[0].lower() # Ensure command is lowercase for matching

        try:
            if command in self.two_arg_ops:
                if len(args) != 3:
                    # Raise ValueError which will be caught and formatted by the outer try-except
                    raise ValueError(f"Command '{command}' requires 2 arguments (e.g., '{command} N1 N2'). Got {len(args)-1}.")
                num1, num2 = float(args[1]), float(args[2])
                result = self.two_arg_ops[command](num1, num2)
                response_data = {
                    "operation": command,
                    "operands": [num1, num2],
                    "result": result
                }
                return self._build_response_dict(success=True, data=response_data)

            elif command in self.one_arg_ops:
                if len(args) != 2:
                    raise ValueError(f"Command '{command}' requires 1 argument (e.g., '{command} N1'). Got {len(args)-1}.")
                num1 = float(args[1])
                result = self.one_arg_ops[command](num1)
                response_data = {
                    "operation": command,
                    "operand": num1,
                    "result": result
                }
                return self._build_response_dict(success=True, data=response_data)
            
            else:
                return self._build_response_dict(success=False, error=f"Unknown command or incorrect arguments. Received: '{command_str_for_logging}'")

        except ValueError as e: # Catches float conversion errors and arg count errors
            return self._build_response_dict(success=False, error=f"Invalid number format or operation argument: {e}. Received: '{command_str_for_logging}'")
        except ZeroDivisionError: # Specific catch for ZeroDivisionError from _divide
            return self._build_response_dict(success=False, error="Division by zero is not allowed.")
        except Exception as e:
            # Catch any other unexpected exceptions and return a generic error.
            log(f"[{self.skill_name}] Error during maths operation '{command_str_for_logging}': {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error=f"An unexpected error occurred: {str(e)}", data={"input_command": command_str_for_logging})
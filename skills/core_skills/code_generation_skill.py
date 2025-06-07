# c:/Users/gilbe/Desktop/self-evolving-ai/skills/core_skills/code_generation_skill.py
from utils.logger import log
from skills.base_skill import BaseSkillTool # Import the correct base class

class CodeGenerationSkill(BaseSkillTool):
    def __init__(self, skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id, code_gen_agent):
        super().__init__(skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id)
        self.code_gen_agent = code_gen_agent
        log(f"[CodeGenerationSkill] Initialized for agent {agent_name} ({agent_id}) with CodeGenAgent.", level="INFO")

    def refactor_code(self, params: dict):
        """
        Attempts to refactor existing code.
        Params:
            existing_code (str): The code to refactor.
            refactoring_goal (str): Description of the refactoring objective.
            guidelines (str, optional): Specific guidelines for the LLM.
        Returns:
            dict: {"status": "success/failure", "refactored_code": "...", "message": "..."}
        """
        existing_code = params.get("existing_code")
        refactoring_goal = params.get("refactoring_goal")
        guidelines = params.get("guidelines", "Refactor the provided Python code to meet the goal. Only output raw Python code.")

        if not existing_code or not refactoring_goal:
            return {"status": "failure", "message": "Missing existing_code or refactoring_goal."}

        # Construct a more detailed prompt for refactoring
        description = f"Refactor the following Python code: \n```python\n{existing_code}\n```\n\nRefactoring Goal: {refactoring_goal}"
        try:
            new_code = self.code_gen_agent.write_new_capability(description, guidelines) # Reusing this method, might need a dedicated one
            if new_code:
                # TODO: Add validation and testing here before returning
                return {"status": "success", "refactored_code": new_code, "message": "Code refactored successfully (pending validation)."}
            else:
                return {"status": "failure", "message": "CodeGenAgent returned no code."}
        except Exception as e:
            log(f"[CodeGenerationSkill] Error during refactor_code: {e}", level="ERROR", exc_info=True)
            return {"status": "failure", "message": f"Error during code refactoring: {e}"}

    def generate_new_capability_code(self, params: dict):
        """
        Generates code for a new capability.
        Params:
            capability_description (str): Description of the new capability.
            guidelines (str): Architectural guidelines (e.g., function name, docstring requirements).
        Returns:
            dict: {"status": "success/failure", "generated_code": "...", "message": "..."}
        """
        description = params.get("capability_description")
        guidelines = params.get("guidelines")

        if not description or not guidelines:
            return {"status": "failure", "message": "Missing capability_description or guidelines."}

        try:
            new_code = self.code_gen_agent.write_new_capability(description, guidelines)
            if new_code:
                # TODO: Add validation and testing here before returning
                return {"status": "success", "generated_code": new_code, "message": "Code generated successfully (pending validation)."}
            else:
                return {"status": "failure", "message": "CodeGenAgent returned no code."}
        except Exception as e:
            log(f"[CodeGenerationSkill] Error during generate_new_capability_code: {e}", level="ERROR", exc_info=True)
            return {"status": "failure", "message": f"Error during code generation: {e}"}

    # Add more methods for other code generation tasks, e.g., implement_radical_mutation

    def execute(self, SQS_message_body: dict) -> dict:
        # SQS_message_body example:
        # {
        #   "skill_name": "code_generation_skill",
        #   "method_name": "generate_new_capability_code",
        #   "method_params": {
        #     "capability_description": "Create a Python function that calculates a factorial.",
        #     "guidelines": "Function name: calculate_factorial. Include a docstring."
        #   }
        # }
        method_name = SQS_message_body.get("method_name")
        method_params = SQS_message_body.get("method_params", {})

        if method_name == "refactor_code":
            return self.refactor_code(method_params)
        elif method_name == "generate_new_capability_code":
            return self.generate_new_capability_code(method_params)
        else:
            return {"status": "failure", "message": f"Unknown method: {method_name}"}

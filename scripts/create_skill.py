import argparse
import os
import re
from pathlib import Path

SKILL_TEMPLATE = """\
import os

class {class_name}:
    \"\"\"
    {description}
    \"\"\"
    def __init__(self, config=None):
        \"\"\"
        Initializes the {class_name}.
        :param config: A dictionary containing configuration for the skill (e.g., API keys, endpoints).
        \"\"\"
        self.config = config or {{}}
        # TODO: Initialize any required clients or settings here.
        # Example: self.api_key = self.config.get("API_KEY") or os.getenv("YOUR_SERVICE_API_KEY")
        #          if not self.api_key:
        #              raise ValueError(f"API key not provided for {{{{self.__class__.__name__}}}}")
        print(f"{{{{self.__class__.__name__}}}} initialized.")

    def perform_action(self, **kwargs):
        \"\"\"
        Performs the main action of this skill.
        This method should be implemented to contain the core logic of the skill.

        :param kwargs: A dictionary of parameters required for the skill's action.
                       These parameters are specific to the skill's functionality.
                       For example, for a GitHub skill, kwargs might include:
                       'repository_url', 'issue_number', 'action_type' (e.g., 'get_issue_details').
        :return: The result of the action. This could be a string, a dictionary, or any other relevant data.
        \"\"\"
        print(f"Executing {{{{self.__class__.__name__}}}} with parameters: {{{{kwargs}}}}")
        # TODO: Implement the skill's core logic here.
        # Access configuration using self.config if needed.
        # Example:
        # action_type = kwargs.get("action_type")
        # if action_type == "get_user_info":
        #     username = kwargs.get("username")
        #     # Call an API: return self._get_github_user_info(username) # Replace with actual call
        # else:
        #     return f"Unsupported action type: {{{{action_type}}}}"
        return "Action logic not yet implemented. Please complete the TODO sections."

    # TODO: Add helper methods specific to this skill if needed.
    # Example:
    # def _call_some_api(self, endpoint, method="GET", data=None):
    #     # Logic to make an API call
    #     # import requests
    #     # headers = {{"Authorization": f"Bearer {{{{self.api_key}}}}"}} # Ensure self.api_key is initialized
    #     # response = requests.request(method, endpoint, headers=headers, json=data)
    #     # response.raise_for_status() # Raise an exception for HTTP errors
    #     # return response.json()
    #     pass

# Example usage (for testing purposes)
if __name__ == "__main__":
    # This section is for testing the skill independently.
    # It will not be executed when the skill is loaded by an agent.
    print(f"Testing {class_name}...")
    
    # Example configuration (replace with actual config if needed for testing)
    # Ensure any sensitive information like API keys are handled securely,
    # e.g., through environment variables or a config file not committed to VCS.
    skill_config = {{
        # "API_KEY": os.getenv("YOUR_SERVICE_API_KEY_FOR_TESTING") 
    }}
    
    skill_instance = {class_name}(config=skill_config)
    
    # Example action parameters (customize for your skill's expected inputs)
    action_params = {{
        "task_description": "Example task for {class_name}",
        # "example_param": "example_value"
    }}
    
    try:
        result = skill_instance.perform_action(**action_params)
        print(f"Skill action result: {{{{result}}}}")
    except Exception as e:
        print(f"Error during skill action: {{{{e}}}}")

"""

def to_pascal_case(name):
    """Converts a string to PascalCase. Handles spaces, underscores, hyphens."""
    name = re.sub(r'[-_]+', ' ', name) # Replace separators with space
    return "".join(word.capitalize() for word in name.split())

def to_snake_case_from_pascal(pascal_case_name):
    """Converts a PascalCase string to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pascal_case_name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def create_skill_file(skill_name_input, description, skills_dir_str="skills"):
    base_class_name = to_pascal_case(skill_name_input)
    class_name = f"{base_class_name}Skill"

    base_file_name = to_snake_case_from_pascal(base_class_name)
    file_name = f"{base_file_name}_skill.py"
    
    skills_dir = Path(skills_dir_str)
    skills_dir.mkdir(parents=True, exist_ok=True)
    
    skill_file_path = skills_dir / file_name
    
    if skill_file_path.exists():
        print(f"Error: Skill file {skill_file_path.resolve()} already exists. Please choose a different name or delete the existing file.")
        return None, None

    content = SKILL_TEMPLATE.format(class_name=class_name, description=description)
    
    try:
        with open(skill_file_path, "w") as f:
            f.write(content)
        abs_path = skill_file_path.resolve()
        print(f"Successfully created skill: {class_name} at {abs_path}")
        return class_name, abs_path
    except IOError as e:
        print(f"Error writing skill file {skill_file_path.resolve()}: {e}")
        return None, None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new skill boilerplate.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--name", required=True, help="The conceptual name of the skill (e.g., 'GitHub API Interaction', 'File System Operations').")
    parser.add_argument("--description", required=True, help="A brief description of what the skill does (will be used in the docstring).")
    parser.add_argument("--skills_dir", default="skills", help="The directory where skill files will be created (default: 'skills').\nThis path is relative to where the script is run, or can be an absolute path.")
    
    args = parser.parse_args()
    create_skill_file(args.name, args.description, skills_dir_str=args.skills_dir)
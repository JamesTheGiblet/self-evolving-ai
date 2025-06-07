# C:\Users\gilbe\Desktop\self-evolving-ai\skills\github_api_interaction_skill.py

import os
import requests # For actual API calls
import json
from typing import Dict, Any, List, Tuple, TYPE_CHECKING
from skills.base_skill import BaseSkillTool
from utils.logger import log

# For type hinting core components to avoid circular imports at runtime
if TYPE_CHECKING:
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus

class GithubApiInteractionSkill(BaseSkillTool):
    """
    A skill to interact with various GitHub API endpoints, such as fetching repository details or managing issues.
    """
    def __init__(self,
                 skill_config: Dict[str, Any],
                 knowledge_base: 'KnowledgeBase',
                 context_manager: 'ContextManager',
                 communication_bus: 'CommunicationBus',
                 agent_name: str,
                 agent_id: str,
                 **kwargs: Any):
        """
        Initializes the GithubApiInteractionSkill.

        Args:
            skill_config (dict): Configuration specific to this skill instance.
                                 Expected keys: "GITHUB_API_TOKEN" (optional).
            knowledge_base (KnowledgeBase): Instance of the knowledge base.
            context_manager (ContextManager): Instance of the context manager.
            communication_bus (CommunicationBus): Instance of the communication bus.
            agent_name (str): Name of the agent this skill is associated with.
            agent_id (str): ID of the agent this skill is associated with.
        """
        super().__init__(skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id, **kwargs)
        
        self.api_token = self.skill_config.get("GITHUB_API_TOKEN") or os.getenv("GITHUB_API_TOKEN")
        if not self.api_token:
            log(f"[{self.skill_name}] GITHUB_API_TOKEN not found in skill_config or environment variables. Some actions may be rate-limited or fail.", level="WARN")
        
        self.base_api_url = "https://api.github.com"
        log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}). API token {'loaded' if self.api_token else 'not loaded'}.", level="INFO")

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": "Interacts with the GitHub API to fetch repository details, user information, and manage issues.",
            "commands": {
                "get_repo_info": {
                    "description": "Fetches information about a GitHub repository.",
                    "args_usage": "<owner>/<repo_name>",
                    "example": "get_repo_info octocat/Spoon-Knife",
                    "keywords": ["github repo", "repository details", "get repository"]
                },
                "get_user_info": {
                    "description": "Fetches information about a GitHub user.",
                    "args_usage": "<username>",
                    "example": "get_user_info octocat",
                    "keywords": ["github user", "user details", "get user profile"]
                },
                # TODO: Add more commands like "list_issues <owner>/<repo_name>", "get_issue <owner>/<repo_name> <issue_number>"
            }
        }

    def _call_github_api(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Helper method to make calls to the GitHub API.
        Returns (success_bool, result_dict).
        """
        url = f"{self.base_api_url}{endpoint}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            response = requests.request(method, url, headers=headers, params=params, json=data, timeout=15)
            log(f"[{self.skill_name}] API Call: {method} {url} - Status: {response.status_code}", level="DEBUG")
            response.raise_for_status() # Raise HTTPError for bad responses (4XX or 5XX)
            return True, response.json()
        except requests.exceptions.HTTPError as e:
            error_details = {"error_type": "http_error", "status_code": e.response.status_code, "message": str(e)}
            try: # Try to get more details from GitHub's error response
                error_details["github_message"] = e.response.json().get("message", "No specific GitHub error message.")
            except json.JSONDecodeError:
                error_details["github_message"] = "Failed to parse GitHub error response."
            log(f"[{self.skill_name}] HTTPError calling GitHub API: {error_details}", level="ERROR")
            return False, error_details
        except requests.exceptions.RequestException as e:
            log(f"[{self.skill_name}] RequestException calling GitHub API: {e}", level="ERROR")
            return False, {"error_type": "request_exception", "message": str(e)}

    def _execute_skill(self, args: List[str]) -> Dict[str, Any]:
        """
        Executes a GitHub API interaction based on parsed arguments.
        """
        if not args:
            return self._build_response_dict(success=False, error="No command provided.")

        command = args[0].lower()

        if command == "get_repo_info":
            if len(args) != 2:
                return self._build_response_dict(success=False, error="'get_repo_info' requires <owner>/<repo_name> argument.")
            repo_full_name = args[1]
            success, data = self._call_github_api(f"/repos/{repo_full_name}")
            return self._build_response_dict(success=success, data=data if success else None, error=data.get("message") if not success else None, details=data if not success else None)

        elif command == "get_user_info":
            if len(args) != 2:
                return self._build_response_dict(success=False, error="'get_user_info' requires <username> argument.")
            username = args[1]
            success, data = self._call_github_api(f"/users/{username}")
            return self._build_response_dict(success=success, data=data if success else None, error=data.get("message") if not success else None, details=data if not success else None)

        # TODO: Implement other commands like list_issues, get_issue, etc.

        else:
            return self._build_response_dict(success=False, error=f"Unknown command: {command}")

# Example usage (for testing purposes)
if __name__ == "__main__":
    # This section is for testing the skill independently.
    # It will not be executed when the skill is loaded by an agent.
    print(f"Testing GithubApiInteractionSkill...")
    
    # Mock dependencies for local testing
    mock_skill_config = {
        "skill_class_name": "GithubApiInteractionSkill",
        # "GITHUB_API_TOKEN": "YOUR_ACTUAL_TOKEN_IF_NEEDED_FOR_TESTING" # Or set as ENV var
    }
    mock_kb = None # Or a mock KnowledgeBase instance
    mock_cm = None # Or a mock ContextManager instance
    mock_cb = None # Or a mock CommunicationBus instance

    skill_instance = GithubApiInteractionSkill(
        skill_config=mock_skill_config,
        knowledge_base=mock_kb,
        context_manager=mock_cm,
        communication_bus=mock_cb,
        agent_name="TestAgent",
        agent_id="test-agent-001"
    )

    try:
        # Test get_repo_info
        repo_result = skill_instance.execute("get_repo_info octocat/Spoon-Knife")
        print(f"\nGet Repo Info Result:\n{json.dumps(repo_result, indent=2)}")

        # Test get_user_info
        user_result = skill_instance.execute("get_user_info octocat")
        print(f"\nGet User Info Result:\n{json.dumps(user_result, indent=2)}")
    except Exception as e:
        print(f"Error during skill action: {e}")
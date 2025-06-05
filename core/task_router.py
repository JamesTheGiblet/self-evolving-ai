# core/task_router.py (New File)
import json
from typing import List, Dict, Any, Optional, Tuple

from utils.logger import log
# Assuming local_llm_connector is accessible, e.g., from utils
from utils import local_llm_connector
import config # For LLM model names, etc.

class TaskRouter:
    def __init__(self, skill_agents: List[Any]): # skill_agents would be your SkillAgent instances
        self.skill_capabilities: Dict[str, Dict[str, Any]] = {}
        self._register_skills(skill_agents)

    def _register_skills(self, skill_agents: List[Any]):
        """
        Registers skills by fetching their capabilities.
        Assumes skill_agents have a 'skill_tool' attribute which is an instance of BaseSkillTool.
        """
        for agent in skill_agents:
            # This part depends on your SkillAgent structure.
            # Let's assume SkillAgent has a `name` and a `skill_tool` attribute.
            skill_tool_instance = None
            if hasattr(agent, 'skill_tool') and agent.skill_tool is not None: # Check if skill_tool exists
                skill_tool_instance = agent.skill_tool
            elif hasattr(agent, 'get_skill_tool') and callable(agent.get_skill_tool): # Or a method to get it
                 skill_tool_instance = agent.get_skill_tool()
            
            if skill_tool_instance and hasattr(skill_tool_instance, 'get_capabilities'):
                try:
                    capabilities = skill_tool_instance.get_capabilities()
                    skill_name = capabilities.get("skill_name", getattr(skill_tool_instance, 'skill_name', None))
                    if skill_name:
                        self.skill_capabilities[skill_name] = capabilities
                        log(f"[TaskRouter] Registered skill: {skill_name} with commands: {list(capabilities.get('commands', {}).keys())}", level="INFO")
                    else:
                        log(f"[TaskRouter] Skill tool {type(skill_tool_instance)} did not provide a skill_name in capabilities.", level="WARN")
                except Exception as e:
                    log(f"[TaskRouter] Error getting capabilities from {type(skill_tool_instance)}: {e}", level="ERROR", exc_info=True)
            else:
                log(f"[TaskRouter] Agent {getattr(agent, 'name', type(agent))} does not have a recognizable skill_tool with get_capabilities.", level="WARN")
        log(f"[TaskRouter] Final registered skills: {list(self.skill_capabilities.keys())}", level="INFO")


    def _build_llm_routing_prompt(self, user_request: str) -> List[Dict[str, str]]:
        """Builds the prompt for the LLM to decide on skill routing."""
        system_message = (
            "You are an expert task router for an AI system. "
            "Your goal is to analyze a user request and determine if one of the available specialized tools (skills) "
            "can handle it. If so, identify the skill, the specific command, and extract the necessary arguments. "
            "Prioritize using a specialized tool if one is suitable. "
            "If no specific tool is suitable, indicate that general LLM processing is needed. "
            "Respond in JSON format only. "
            "If a tool is chosen, the JSON should be: "
            "{\"skill_name\": \"SKILL_NAME\", \"command_name\": \"COMMAND_NAME\", \"arguments\": [\"arg1\", \"arg2\", ...], \"explanation\": \"Brief reason for choice.\"}. "
            "The arguments should be strings, exactly as they should be passed to the skill. "
            "If no tool is suitable, respond with: "
            "{\"skill_name\": null, \"command_name\": null, \"arguments\": [], \"explanation\": \"Reason why no tool is suitable.\"}"
        )

        prompt = f"User request: \"{user_request}\"\n\n"
        prompt += "Available tools (skills and their commands):\n"
        for skill_name, capabilities in self.skill_capabilities.items():
            prompt += f"\n## Skill: {skill_name}\n"
            prompt += f"   Description: {capabilities.get('description', 'No overall description.')}\n"
            for command_name, command_info in capabilities.get("commands", {}).items():
                prompt += f"   - Command: `{command_name}`\n"
                prompt += f"     Description: {command_info.get('description', '')}\n"
                prompt += f"     Usage: `{command_name} {command_info.get('args_usage', '')}`\n"
                prompt += f"     Example: `{command_info.get('example', '')}`\n"
                if command_info.get('keywords'):
                    prompt += f"     Keywords: {', '.join(command_info.get('keywords'))}\n"
        
        prompt += "\nAnalyze the user request and provide your routing decision in the specified JSON format."
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

    def _parse_llm_routing_response(self, llm_response_str: Optional[str]) -> Optional[Dict[str, Any]]:
        if not llm_response_str:
            return None
        try:
            # The LLM might return a markdown code block, try to strip it
            if llm_response_str.strip().startswith("```json"):
                llm_response_str = llm_response_str.strip()[7:]
                if llm_response_str.strip().endswith("```"):
                    llm_response_str = llm_response_str.strip()[:-3]
            
            decision = json.loads(llm_response_str)
            if "skill_name" in decision and "command_name" in decision and "arguments" in decision:
                return decision
            log(f"[TaskRouter] LLM routing response missing required keys: {llm_response_str}", level="WARN")
        except json.JSONDecodeError as e:
            log(f"[TaskRouter] Failed to decode LLM routing response: {e}. Response: {llm_response_str}", level="ERROR", exc_info=True)
        except Exception as e:
            log(f"[TaskRouter] Unexpected error parsing LLM routing response: {e}. Response: {llm_response_str}", level="ERROR", exc_info=True)
        return None

    def route_request(self, user_request: str) -> Tuple[Optional[str], Optional[str], Optional[List[str]], Optional[str]]:
        """
        Routes a user request to an appropriate skill and command.
        Returns: (skill_name, command_name, arguments_list, explanation_or_error)
        """
        log(f"[TaskRouter] Routing request: '{user_request}'", level="INFO")

        # Phase 1: Simple Keyword/Exact Match (Optional, but can be faster for very common commands)
        # For example, if user_request.lower() == "get joke":
        #     return "ApiConnector", "get_joke", [], "Direct match for 'get joke'"
        # This needs to be carefully designed to avoid false positives.
        # For now, we'll rely more on the LLM for robust matching.

        # Phase 2: LLM-based Routing
        prompt_messages = self._build_llm_routing_prompt(user_request)
        
        # In a real system, you might use the async connector if this is part of a non-blocking flow
        # For simplicity here, using the synchronous call.
        llm_response_content = local_llm_connector.call_local_llm_api(
            prompt_messages,
            model_name=config.LOCAL_LLM_DEFAULT_MODEL, # Or a specific model for routing
            temperature=0.2 # Lower temperature for more deterministic routing
        )

        if not llm_response_content:
            log("[TaskRouter] No response from LLM for routing.", level="ERROR")
            return None, None, None, "LLM call for routing failed or returned no content."

        log(f"[TaskRouter] LLM routing raw response: {llm_response_content}", level="DEBUG")
        decision = self._parse_llm_routing_response(llm_response_content)

        if decision:
            skill = decision.get("skill_name")
            command = decision.get("command_name")
            args = decision.get("arguments", [])
            explanation = decision.get("explanation", "LLM provided routing decision.")

            if skill and command:
                # Validate that the skill and command are known
                if skill in self.skill_capabilities and command in self.skill_capabilities[skill].get("commands", {}):
                    log(f"[TaskRouter] LLM routed '{user_request}' to {skill}.{command} with args {args}. Explanation: {explanation}", level="INFO")
                    return skill, command, args, explanation
                else:
                    log(f"[TaskRouter] LLM suggested an unknown skill/command: {skill}.{command}. Falling back.", level="WARN")
                    return None, None, None, f"LLM suggested unknown skill/command: {skill}.{command}."
            else:
                log(f"[TaskRouter] LLM indicated no specific tool for '{user_request}'. Explanation: {explanation}", level="INFO")
                return None, None, None, explanation # General LLM processing needed
        
        log(f"[TaskRouter] Could not parse LLM decision or LLM failed to route '{user_request}'.", level="WARN")
        return None, None, None, "Failed to parse LLM routing decision."

    def add_skill_agent(self, skill_agent_instance: Any):
        """
        Registers a single new skill agent's capabilities after initial setup.
        """
        if not (hasattr(skill_agent_instance, 'skill_tool') and skill_agent_instance.skill_tool):
            log(f"[TaskRouter] New agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')} has no skill_tool.", level="WARN")
            return

        skill_tool = skill_agent_instance.skill_tool
        if not hasattr(skill_tool, 'get_capabilities'):
            log(f"[TaskRouter] Skill tool for agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')} has no get_capabilities method.", level="WARN")
            return
            
        try:
            capabilities = skill_tool.get_capabilities()
            skill_name_from_cap = capabilities.get("skill_name", getattr(skill_tool, 'skill_name', None))

            if skill_name_from_cap and skill_name_from_cap not in self.skill_capabilities:
                self.skill_capabilities[skill_name_from_cap] = capabilities
                log(f"[TaskRouter] Dynamically registered new skill: '{skill_name_from_cap}' from agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')}.", level="INFO")
            elif skill_name_from_cap in self.skill_capabilities:
                log(f"[TaskRouter] Skill '{skill_name_from_cap}' from agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')} already registered. Skipping dynamic add.", level="DEBUG")
            else:
                log(f"[TaskRouter] New skill agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')}'s tool did not provide a usable skill_name in its capabilities structure.", level="WARN")
        except Exception as e:
            log(f"[TaskRouter] Error dynamically registering skill from agent {getattr(skill_agent_instance, 'name', 'UnknownAgent')}: {e}", level="ERROR", exc_info=True)
# Example of how MetaAgent might use it:
# class MetaAgent:
#     def __init__(self, context, knowledge, communication_bus, skill_agents_list):
#         # ... other initializations ...
#         self.task_router = TaskRouter(skill_agents_list) # skill_agents_list comes from MetaAgent's own list
#
#     def handle_user_request(self, user_request_text: str):
#         skill_name, command_name, args, explanation = self.task_router.route_request(user_request_text)
#
#         if skill_name and command_name:
#             # Find the actual SkillAgent instance
#             target_skill_agent = None
#             for agent in self.skill_agents: # Assuming self.skill_agents is a list of SkillAgent instances
#                 # This matching logic depends on how SkillAgent stores its skill_tool's name
#                 current_agent_skill_name = ""
#                 if hasattr(agent, 'skill_tool') and agent.skill_tool:
#                     current_agent_skill_name = getattr(agent.skill_tool, 'skill_name', None)
#                 
#                 if current_agent_skill_name == skill_name:
#                     target_skill_agent = agent
#                     break
#            
#             if target_skill_agent:
#                 command_str_for_skill = f"{command_name}"
#                 if args: # shlex.join might be better if args can contain spaces
#                     command_str_for_skill += " " + " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
#                
#                 log.info(f"[MetaAgent] Executing routed command on {skill_name}: '{command_str_for_skill}'")
#                 # Assuming SkillAgent has an execute method that takes the full command string
#                 # or you adapt it to take command_name and args list separately.
#                 # The BaseSkillTool.execute() method expects a single command string.
#                 result_json = target_skill_agent.execute(command_str_for_skill) 
#                 log.info(f"[MetaAgent] Result from {skill_name}: {result_json}")
#                 # Process result_json
#             else:
#                 log.error(f"[MetaAgent] TaskRouter suggested skill '{skill_name}', but no such SkillAgent found.")
#                 # Fallback to general LLM
#         else:
#             log.info(f"[MetaAgent] No specific skill routed for '{user_request_text}'. Reason: {explanation}. Using general LLM.")
#             # Fallback to general LLM using user_request_text
#             # response_content = local_llm_connector.call_local_llm_api(
#             #     [{"role": "user", "content": user_request_text}],
#             # )
#             # Process response_content

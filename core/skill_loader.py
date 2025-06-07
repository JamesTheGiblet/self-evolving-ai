# self-evolving-ai/core/skill_loader.py
"""
Handles dynamic loading of skill tools and creation of SkillAgent instances.
"""
import os
import importlib.util
import inspect
import re
import sys
from typing import List, Tuple, Dict, Type, Optional

# Assuming these are the correct paths based on your project structure
# If skill_loader.py is in core/, and skills/ and memory/ are siblings of core/
# we might need to adjust sys.path or use relative imports carefully if this file is run directly.
# However, when imported by main.py (in the root), these should resolve.
from skills.base_skill import BaseSkillTool
from core.skill_agent import SkillAgent # core. is if skill_loader is outside core
from memory.knowledge_base import KnowledgeBase
from core.context_manager import ContextManager
from engine.communication_bus import CommunicationBus
from engine.identity_engine import IdentityEngine # For type hinting
from agents.code_gen_agent import CodeGenAgent # For type hinting
from utils.logger import log

# --- Helper Function to Generate Lineage IDs ---
def generate_lineage_id_from_skill_name(skill_class_name: str) -> str:
    """
    Generates a standardized lineage ID from a skill class name.
    Example: "Calendar" -> "skill_calendar_ops", "MathsTool" -> "skill_maths_tool_ops"
    """
    # Convert CamelCase to snake_case
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', skill_class_name)
    snake_case_name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    # Remove common suffixes like '_tool' if they exist from class name
    if snake_case_name.endswith("_tool"):
        snake_case_name = snake_case_name[:-5] # Remove '_tool'
    
    # Ensure it ends with '_ops'
    if not snake_case_name.endswith("_ops"):
        # If there's already an underscore, it implies multiple words, so just append _ops
        # e.g., "api_connector" -> "api_connector_ops"
        # If no underscore, it's a single word, e.g., "calendar" -> "calendar_ops"
        snake_case_name += "_ops"
        
    return f"skill_{snake_case_name}"

# --- Dynamic Skill Loading Function ---
def load_skills_dynamically(
    skills_dir_path: str,
    knowledge_base_instance: KnowledgeBase,
    context_manager_instance: ContextManager,
    communication_bus_instance: CommunicationBus,
    identity_engine_instance: IdentityEngine, # Added
    code_gen_agent_instance: Optional[CodeGenAgent] = None # Added for CodeGenAgent
) -> Tuple[List[SkillAgent], List[Dict]]:
    """
    Dynamically loads skill tools from the specified directory,
    creates SkillAgent instances, and prepares default skill agent configurations.

    Args:
        skills_dir_path: Path to the directory containing skill modules.
        knowledge_base_instance: Instance of KnowledgeBase.
        context_manager_instance: Instance of ContextManager.
        communication_bus_instance: Instance of CommunicationBus.
        identity_engine_instance: Instance of IdentityEngine.
        code_gen_agent_instance: Optional instance of CodeGenAgent.

    Returns:
        A tuple containing:
        - A list of instantiated SkillAgent objects.
        - A list of configurations for default skill agents (for MetaAgent).
    """
    loaded_skill_agents: List[SkillAgent] = []
    default_skill_agent_configs_list: List[Dict] = []

    # Specific dependencies for skills, can be expanded
    skill_dependencies = {
        "Calendar": {"memory_store": knowledge_base_instance.get_skill_memory_store("Calendar")}
        # Add other skills and their specific dependencies here if needed
    }

    if not os.path.isdir(skills_dir_path):
        log(f"Skills directory '{skills_dir_path}' not found. No skills will be loaded dynamically.", level="ERROR")
        return loaded_skill_agents, default_skill_agent_configs_list

    log(f"Scanning for skills in directory: {skills_dir_path}", level="INFO")

    for filename in os.listdir(skills_dir_path):
        if filename.endswith(".py") and filename not in ["__init__.py", "base_skill.py"] and not filename.startswith("test_"):
            module_name_from_file = filename[:-3] # e.g., "api_connector"
            module_full_path = os.path.join(skills_dir_path, filename)
            
            # Construct a unique module name for importlib to avoid conflicts
            # This is important if skills_dir_path is not directly in sys.path
            # or if there are name clashes.
            # Using "skills." prefix assumes skills_dir is treated as a package.
            # If skills_dir is, for example, project_root/skills, then this is fine.
            qualified_module_name = f"skills.{module_name_from_file}"


            try:
                spec = importlib.util.spec_from_file_location(qualified_module_name, module_full_path)
                if spec is None or spec.loader is None:
                    log(f"Could not create module spec or loader for skill module {module_name_from_file} at {module_full_path}", level="WARN")
                    continue
                
                skill_module = importlib.util.module_from_spec(spec)
                
                # Add to sys.modules BEFORE exec_module to handle circular dependencies within the skill module if any
                # and to make it available for subsequent imports if the skill module itself imports other local things.
                sys.modules[qualified_module_name] = skill_module 
                spec.loader.exec_module(skill_module)
                log(f"Successfully loaded module: {qualified_module_name}", level="DEBUG")

                skill_class_to_instantiate: Type[BaseSkillTool] | None = None
                expected_class_name = "".join(word.capitalize() for word in module_name_from_file.split('_')) # e.g. api_connector -> ApiConnector

                for attribute_name in dir(skill_module):
                    attribute = getattr(skill_module, attribute_name)
                    if inspect.isclass(attribute) and issubclass(attribute, BaseSkillTool) and attribute is not BaseSkillTool:
                        if attribute_name == expected_class_name: # Prioritize exact match
                            skill_class_to_instantiate = attribute
                            break 
                        elif skill_class_to_instantiate is None: # Fallback to first found
                            skill_class_to_instantiate = attribute
                
                if skill_class_to_instantiate is None and expected_class_name: # If primary strategy failed, try again without strict name match
                     for attribute_name in dir(skill_module):
                        attribute = getattr(skill_module, attribute_name)
                        if inspect.isclass(attribute) and issubclass(attribute, BaseSkillTool) and attribute is not BaseSkillTool:
                            skill_class_to_instantiate = attribute # Take the first one
                            log(f"Found skill class '{attribute_name}' (fallback) in {module_name_from_file}.py", level="DEBUG")
                            break


                if skill_class_to_instantiate:
                    skill_class_name = skill_class_to_instantiate.__name__
                    log(f"Found skill class: {skill_class_name} in {module_name_from_file}.py", level="INFO")

                    lineage_id = generate_lineage_id_from_skill_name(skill_class_name)
                    agent_id_for_skill = f"{lineage_id}_0" 
                    agent_name_for_skill = agent_id_for_skill # Or a more descriptive name

                    # Prepare arguments for the skill tool's constructor
                    # This 'skill_config_for_tool' is passed as the 'skill_config' argument
                    # to the skill tool's __init__ method (e.g., CodeGenerationSkill.__init__)
                    skill_config_for_tool = {
                        "name": agent_name_for_skill,
                        "lineage_id": lineage_id,
                        "skill_class_name": skill_class_name,
                        # Add other skill-specific parameters here if they were defined elsewhere
                    }

                    tool_constructor_args = {
                        "skill_config": skill_config_for_tool,
                        "knowledge_base": knowledge_base_instance,
                        "context_manager": context_manager_instance,
                        "communication_bus": communication_bus_instance,
                        "agent_name": agent_name_for_skill,
                        "agent_id": agent_id_for_skill,
                    }

                    # Add specific dependencies from skill_dependencies
                    tool_constructor_args.update(skill_dependencies.get(skill_class_name, {}))

                    # Check if the skill tool's constructor expects 'code_gen_agent'
                    requires_code_gen_agent_flag = False
                    init_params = inspect.signature(skill_class_to_instantiate.__init__).parameters
                    if 'code_gen_agent' in init_params and code_gen_agent_instance:
                        tool_constructor_args['code_gen_agent'] = code_gen_agent_instance
                        requires_code_gen_agent_flag = True
                        log(f"Passing CodeGenAgent to {skill_class_name}", level="DEBUG")

                    skill_tool_instance: BaseSkillTool = skill_class_to_instantiate(**tool_constructor_args)
                    
                    # The primary capability this SkillAgent offers (its "service")
                    # This should be derived from the skill tool itself, or by convention.
                    # Assuming a convention: skill_name_ops_v1 (e.g., calendar_ops_v1)
                    service_capability_name = lineage_id.replace("skill_", "", 1) + "_v1" 
                    # If your skill tools have a method to declare their primary service capability, use that.
                    # Example: service_capability_name = skill_tool_instance.get_service_capability_name()

                    skill_agent_instance = SkillAgent(
                        skill_tool=skill_tool_instance,
                        context_manager=context_manager_instance,
                        knowledge_base=knowledge_base_instance,
                        communication_bus=communication_bus_instance,
                        name=agent_name_for_skill, # Pass name explicitly
                        agent_id=agent_id_for_skill,
                        capabilities=[service_capability_name], # Agent offers this service
                        lineage_id=lineage_id,
                        generation=0,
                        identity_engine=identity_engine_instance # Pass IdentityEngine
                    )
                    loaded_skill_agents.append(skill_agent_instance)

                    default_config_entry = {
                        "name": agent_name_for_skill,
                        "agent_type": "skill",
                        "capabilities": [service_capability_name],
                        "skill_tool_class_name": skill_class_name, # Store class name for potential re-instantiation
                        "skill_module_name": qualified_module_name, # Store module for re-import if needed
                        "lineage_id": lineage_id,
                        "generation": 0,
                        "requires_code_gen_agent": requires_code_gen_agent_flag, # Store if it needed CodeGenAgent
                        "skill_tool": skill_tool_instance, # Store the actual instance for MetaAgent's re-seeding
                    }
                    default_skill_agent_configs_list.append(default_config_entry)
                    log(f"Dynamically prepared: SkillAgent '{agent_id_for_skill}' providing '{service_capability_name}'", level="DEBUG")

                else:
                    log(f"No class inheriting from BaseSkillTool found or matched in {module_name_from_file}.py (expected: {expected_class_name})", level="WARN")

            except Exception as e:
                log(f"Error loading skill from {filename} ({qualified_module_name}): {e}", level="ERROR", exc_info=True)
                # Clean up from sys.modules if it was added and loading failed partway
                if qualified_module_name in sys.modules:
                    del sys.modules[qualified_module_name]
                    
    return loaded_skill_agents, default_skill_agent_configs_list

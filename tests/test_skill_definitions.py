import pytest
from core.skill_definitions import SKILL_CAPABILITY_MAPPING
from core import skill_handlers # To check if handlers exist

class TestSkillCapabilityMapping:

    def test_mapping_is_dictionary(self):
        """Test that SKILL_CAPABILITY_MAPPING is a dictionary."""
        assert isinstance(SKILL_CAPABILITY_MAPPING, dict), "SKILL_CAPABILITY_MAPPING should be a dictionary."

    def test_mapping_keys_are_strings(self):
        """Test that all keys in the mapping are non-empty strings."""
        assert SKILL_CAPABILITY_MAPPING, "SKILL_CAPABILITY_MAPPING should not be empty."
        for capability_name in SKILL_CAPABILITY_MAPPING.keys():
            assert isinstance(capability_name, str), \
                f"Capability name (key) '{capability_name}' should be a string."
            assert capability_name.strip(), \
                f"Capability name (key) '{capability_name}' should not be an empty or whitespace-only string."

    def test_mapping_values_are_lists_of_strings(self):
        """Test that all values in the mapping are lists of non-empty strings."""
        for capability_name, skill_list in SKILL_CAPABILITY_MAPPING.items():
            assert isinstance(skill_list, list), \
                f"Value for capability '{capability_name}' should be a list, got {type(skill_list)}."
            assert skill_list, \
                f"Skill list for capability '{capability_name}' should not be empty."
            for skill_name in skill_list:
                assert isinstance(skill_name, str), \
                    f"Skill name '{skill_name}' in list for '{capability_name}' should be a string."
                assert skill_name.strip(), \
                    f"Skill name '{skill_name}' in list for '{capability_name}' should not be an empty string."

    def test_skill_names_correspond_to_known_handlers(self):
        """
        Test that skill names in the mapping correspond to handlers
        recognized by SkillAgent's registration logic or skill_handlers module.
        """
        # These are the skill_names that SkillAgent._register_default_skills explicitly checks for
        # and attempts to get a handler for from core.skill_handlers
        known_skill_handler_references = {
            "basic_stats": skill_handlers.handle_basic_stats,
            "log_summary": skill_handlers.handle_log_summary,
            "complexity": skill_handlers.handle_generic_complexity,
            "maths_operation": skill_handlers.handle_maths_operation,
            "web_operation": skill_handlers.handle_web_operation,
            "file_operation": skill_handlers.handle_file_operation,
            "api_call": skill_handlers.handle_api_call,
        }

        for capability_name, skill_list in SKILL_CAPABILITY_MAPPING.items():
            for skill_name in skill_list:
                assert skill_name in known_skill_handler_references, \
                    f"Skill name '{skill_name}' from capability '{capability_name}' does not have a corresponding " \
                    f"known handler reference in SkillAgent or skill_handlers.py. Please check SkillAgent._register_default_skills."
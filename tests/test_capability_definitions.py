# tests/test_capability_definitions.py

import unittest
import os
import sys

# Ensure the core modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.capability_definitions import CAPABILITY_REGISTRY

class TestCapabilityDefinitions(unittest.TestCase):

    def test_capability_registry_is_dict(self):
        """Test that CAPABILITY_REGISTRY is a dictionary."""
        self.assertIsInstance(CAPABILITY_REGISTRY, dict, "CAPABILITY_REGISTRY should be a dictionary.")

    def test_capability_entry_structure(self):
        """Test the structure of each capability entry in the registry."""
        self.assertTrue(CAPABILITY_REGISTRY, "CAPABILITY_REGISTRY should not be empty.")

        for cap_name, cap_def in CAPABILITY_REGISTRY.items():
            with self.subTest(capability_name=cap_name):
                self.assertIsInstance(cap_def, dict, f"Capability '{cap_name}' definition should be a dictionary.")

                # Check for essential keys
                self.assertIn("params", cap_def, f"Capability '{cap_name}' must have a 'params' key.")
                self.assertIn("critical", cap_def, f"Capability '{cap_name}' must have a 'critical' key.")
                self.assertIn("description", cap_def, f"Capability '{cap_name}' must have a 'description' key.")
                self.assertIn("handler", cap_def, f"Capability '{cap_name}' must have a 'handler' key.")

                # Check types of essential keys
                self.assertIsInstance(cap_def["params"], dict,
                                      f"'params' for capability '{cap_name}' should be a dictionary.")
                self.assertIsInstance(cap_def["critical"], bool,
                                      f"'critical' for capability '{cap_name}' should be a boolean.")
                self.assertIsInstance(cap_def["description"], str,
                                      f"'description' for capability '{cap_name}' should be a string.")
                self.assertIsInstance(cap_def["handler"], str,
                                      f"'handler' for capability '{cap_name}' should be a string.")

                # Optional: Check if handler string follows a pattern (e.g., starts with "execute_")
                self.assertTrue(cap_def["handler"].startswith("execute_"),
                                f"Handler for '{cap_name}' should typically start with 'execute_'. Found: {cap_def['handler']}")

                # Optional: Check if description is not empty
                self.assertTrue(len(cap_def["description"].strip()) > 0,
                                f"Description for '{cap_name}' should not be empty.")


if __name__ == '__main__':
    unittest.main()
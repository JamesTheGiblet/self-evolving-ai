# tests/unit/test_performance_tracker.py

import unittest
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.performance_tracker import CapabilityPerformanceTracker

class TestCapabilityPerformanceTracker(unittest.TestCase):

    def test_initialization_empty(self):
        tracker = CapabilityPerformanceTracker()
        self.assertEqual(tracker.performance, {})
        self.assertEqual(tracker.usage_frequency, {})

    def test_initialization_with_capabilities(self):
        initial_caps = ["cap_a", "cap_b"]
        tracker = CapabilityPerformanceTracker(initial_capabilities=initial_caps)
        self.assertIn("cap_a", tracker.performance)
        self.assertEqual(tracker.performance["cap_a"], {"attempts": 0, "successes": 0, "total_reward": 0.0})
        self.assertEqual(tracker.usage_frequency["cap_a"], 0)
        self.assertIn("cap_b", tracker.performance)
        self.assertEqual(tracker.performance["cap_b"], {"attempts": 0, "successes": 0, "total_reward": 0.0})
        self.assertEqual(tracker.usage_frequency["cap_b"], 0)


    def test_add_capability(self):
        tracker = CapabilityPerformanceTracker()
        tracker.add_capability("new_cap")
        self.assertIn("new_cap", tracker.performance)
        self.assertEqual(tracker.performance["new_cap"], {"attempts": 0, "successes": 0, "total_reward": 0.0})
        self.assertEqual(tracker.usage_frequency["new_cap"], 0)
        # Adding again should not change anything
        tracker.add_capability("new_cap")
        self.assertEqual(tracker.performance["new_cap"]["attempts"], 0)

    def test_record_capability_chosen(self):
        tracker = CapabilityPerformanceTracker()
        tracker.record_capability_chosen("cap_chosen")
        self.assertEqual(tracker.usage_frequency["cap_chosen"], 1)
        tracker.record_capability_chosen("cap_chosen")
        self.assertEqual(tracker.usage_frequency["cap_chosen"], 2)

    def test_record_capability_execution(self):
        tracker = CapabilityPerformanceTracker()
        cap_name = "cap_exec"
        # First execution: success
        tracker.record_capability_execution(cap_name, True, 1.0)
        self.assertEqual(tracker.performance[cap_name]["attempts"], 1)
        self.assertEqual(tracker.performance[cap_name]["successes"], 1)
        self.assertEqual(tracker.performance[cap_name]["total_reward"], 1.0)

        # Second execution: failure
        tracker.record_capability_execution(cap_name, False, -0.5)
        self.assertEqual(tracker.performance[cap_name]["attempts"], 2)
        self.assertEqual(tracker.performance[cap_name]["successes"], 1) # Still 1 success
        self.assertEqual(tracker.performance[cap_name]["total_reward"], 0.5) # 1.0 - 0.5

    def test_get_stats_for_capability(self):
        tracker = CapabilityPerformanceTracker(initial_capabilities=["cap_stats"])
        tracker.record_capability_execution("cap_stats", True, 0.8)
        stats = tracker.get_stats_for_capability("cap_stats")
        self.assertEqual(stats["attempts"], 1)
        self.assertEqual(stats["successes"], 1)
        self.assertEqual(stats["total_reward"], 0.8)
        self.assertIsNone(tracker.get_stats_for_capability("non_existent_cap"))

    def test_get_overall_average_reward(self):
        tracker = CapabilityPerformanceTracker()
        self.assertEqual(tracker.get_overall_average_reward(), 0.0)
        tracker.record_capability_execution("cap1", True, 1.0)
        tracker.record_capability_execution("cap2", False, -0.4)
        tracker.record_capability_execution("cap1", True, 0.8) # cap1 again
        # Total reward = 1.0 - 0.4 + 0.8 = 1.4
        # Total attempts = 3
        # Avg reward = 1.4 / 3
        self.assertAlmostEqual(tracker.get_overall_average_reward(), 1.4 / 3)

    def test_config_data_load_save(self):
        tracker = CapabilityPerformanceTracker()
        tracker.record_capability_execution("cap_config", True, 0.9)
        tracker.record_capability_chosen("cap_config")
        tracker.record_capability_chosen("cap_other")

        config_data = tracker.get_config_data()

        new_tracker = CapabilityPerformanceTracker()
        new_tracker.load_config_data(config_data)

        self.assertEqual(new_tracker.performance, tracker.performance)
        self.assertEqual(new_tracker.usage_frequency, tracker.usage_frequency)

if __name__ == '__main__':
    unittest.main()
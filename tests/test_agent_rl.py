# tests/unit/test_agent_rl.py

import unittest
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import patch # Add this import

from core.agent_rl import AgentRLSystem

class TestAgentRLSystem(unittest.TestCase):

    def setUp(self):
        self.rl_system = AgentRLSystem(alpha=0.1, gamma=0.9, epsilon=0.1)
        self.agent_name = "test_agent"

    def test_initialization(self):
        self.assertEqual(self.rl_system.alpha, 0.1)
        self.assertEqual(self.rl_system.gamma, 0.9)
        self.assertEqual(self.rl_system.epsilon, 0.1)
        self.assertEqual(self.rl_system.q_table, {})

    def test_choose_action_no_available_actions(self):
        result = self.rl_system.choose_action(
            current_rl_state_tuple=("state1",),
            available_actions=[], # Empty list
            agent_name=self.agent_name # Pass agent_name
        )
        self.assertIsNone(result) # Expect None when no actions are available

    def test_choose_action_explore_forced(self):
        available_actions = ["cap1", "cap2", "cap3"]
        action, method = self.rl_system.choose_action(
            current_rl_state_tuple=("state1",),
            available_actions=available_actions,
            agent_name=self.agent_name,
            explore_mode_active=True
        )
        self.assertIn(action, available_actions)
        self.assertEqual(method, "explore_forced")

    def test_choose_action_epsilon_greedy_exploration(self):
        # Force exploration by setting epsilon high and mocking random
        self.rl_system.epsilon = 1.0 
        available_actions = ["cap1", "cap2", "cap3"]
        
        # Mock random.random() to ensure the exploration path is taken using the imported patch
        with patch('random.random', return_value=0.05): # Use patch directly
            action, method = self.rl_system.choose_action(
                current_rl_state_tuple=("state1",),
                available_actions=available_actions,
                agent_name=self.agent_name,
                explore_mode_active=False # Epsilon greedy, not forced
            )
        self.assertIn(action, available_actions)
        self.assertEqual(method, "explore_epsilon_greedy")
        self.rl_system.epsilon = 0.1 # Reset epsilon

    def test_choose_action_exploit_no_q_values(self):
        # Force exploitation
        self.rl_system.epsilon = 0.0
        available_actions = ["cap1", "cap2", "cap3"]
        action, method = self.rl_system.choose_action(
            current_rl_state_tuple=("state_new",), # A state with no Q-values yet
            available_actions=available_actions,
            agent_name=self.agent_name
        )
        self.assertIn(action, available_actions)
        self.assertEqual(method, "exploit_random_tie_break")

    def test_choose_action_exploit_with_q_values(self):
        self.rl_system.epsilon = 0.0
        state = ("state_q",)
        actions = ["cap_low", "cap_high", "cap_mid"]
        self.rl_system.q_table[(state, "cap_low")] = 0.1
        self.rl_system.q_table[(state, "cap_high")] = 1.0
        self.rl_system.q_table[(state, "cap_mid")] = 0.5

        action, method = self.rl_system.choose_action(state, actions, self.agent_name)
        self.assertEqual(action, "cap_high")
        self.assertEqual(method, "exploit_max_q")

    def test_choose_action_exploit_tie_break(self):
        self.rl_system.epsilon = 0.0
        state = ("state_tie",)
        actions = ["cap_tie1", "cap_tie2", "cap_low"]
        self.rl_system.q_table[(state, "cap_tie1")] = 0.8
        self.rl_system.q_table[(state, "cap_tie2")] = 0.8
        self.rl_system.q_table[(state, "cap_low")] = 0.2

        action, method = self.rl_system.choose_action(state, actions, self.agent_name)
        self.assertIn(action, ["cap_tie1", "cap_tie2"])
        self.assertEqual(method, "exploit_max_q") # Still max_q, but random choice among best

    def test_update_q_value(self):
        state = ("s1",)
        action = "act1"
        reward = 1.0
        next_state = ("s2",)
        available_next_actions = ["next_act1", "next_act2"]

        self.rl_system.q_table[(next_state, "next_act1")] = 0.5
        self.rl_system.q_table[(next_state, "next_act2")] = 0.3

        # Initial Q-value is 0
        self.assertEqual(self.rl_system.q_table.get((state, action), 0.0), 0.0)

        self.rl_system.update_q_value(state, action, reward, next_state, available_next_actions, self.agent_name)

        # Expected: old_q + alpha * (reward + gamma * max_next_q - old_q)
        # 0.0 + 0.1 * (1.0 + 0.9 * 0.5 - 0.0) = 0.1 * (1.0 + 0.45) = 0.1 * 1.45 = 0.145
        self.assertAlmostEqual(self.rl_system.q_table[(state, action)], 0.145)

if __name__ == '__main__':
    unittest.main()
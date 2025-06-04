# core/agent_rl.py

import random
from typing import Dict, List, Any, Tuple, Optional
from utils.logger import log

class AgentRLSystem:
    """
    Manages the Reinforcement Learning (Q-learning) aspects for an agent.
    """
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.1):
        self.q_table: Dict[Tuple[Any, str], float] = {}
        self.alpha = alpha  # Learning rate
        self.gamma = gamma  # Discount factor
        self.epsilon = epsilon  # Exploration rate
        log(f"[AgentRLSystem] Initialized with alpha={alpha}, gamma={gamma}, epsilon={epsilon}")

    def choose_action(self,
                      current_rl_state_tuple: Tuple,
                      available_actions: List[str],
                      agent_name: str, # For logging
                      explore_mode_active: bool = False) -> Tuple[Optional[str], str]:
        """
        Chooses an action based on the current state, available actions,
        and epsilon-greedy strategy.
        """
        if not available_actions:
            log(f"[{agent_name}] RLSystem: No actions available to choose from.", level="WARNING")
            return None

        exploration_method = "exploit" # Default

        if explore_mode_active or random.random() < self.epsilon:
            # Exploration
            chosen_action = random.choice(available_actions)
            exploration_method = "explore_epsilon_greedy" if not explore_mode_active else "explore_forced"
            log(f"[{agent_name}] RLSystem: {exploration_method.capitalize()} - Chose action '{chosen_action}' randomly from {len(available_actions)} options.")
        else:
            # Exploitation
            q_values_for_state = {action: self.q_table.get((current_rl_state_tuple, action), 0.0)
                                  for action in available_actions}
            
            if not q_values_for_state or all(v == 0 for v in q_values_for_state.values()):
                chosen_action = random.choice(available_actions)
                exploration_method = "exploit_random_tie_break"
                log(f"[{agent_name}] RLSystem: {exploration_method.capitalize()} (no Q-values/all zero) - Chose '{chosen_action}' randomly.")
            else:
                max_q = max(q_values_for_state.values())
                best_actions = [action for action, q_val in q_values_for_state.items() if q_val == max_q]
                chosen_action = random.choice(best_actions) # Handle ties by random choice
                exploration_method = "exploit_max_q"
                log(f"[{agent_name}] RLSystem: {exploration_method.capitalize()} - Chose action '{chosen_action}' (Q-value: {max_q:.2f}). Candidates: {best_actions}")
        
        return chosen_action, exploration_method

    def update_q_value(self,
                       state_tuple: Tuple,
                       action: str,
                       reward: float,
                       next_state_tuple: Tuple,
                       available_next_actions: List[str],
                       agent_name: str): # For logging
        """
        Updates the Q-value for a given state-action pair.
        """
        old_q_value = self.q_table.get((state_tuple, action), 0.0)
        
        next_state_q_values = [self.q_table.get((next_state_tuple, next_action), 0.0)
                               for next_action in available_next_actions]
        max_next_q_value = max(next_state_q_values) if next_state_q_values else 0.0
        
        new_q_value = old_q_value + self.alpha * (reward + self.gamma * max_next_q_value - old_q_value)
        self.q_table[(state_tuple, action)] = new_q_value
        # log(f"[{agent_name}] RLSystem: Updated Q-value for ({state_tuple}, {action}): {old_q_value:.2f} -> {new_q_value:.2f} (Reward: {reward:.2f})", level="TRACE")


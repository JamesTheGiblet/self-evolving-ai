# test/test_context_manager.py
import pytest
import time
import threading
from unittest.mock import Mock, patch

# Adjust the import path if your project structure is different
# Assuming 'core' and 'utils' are in the project root
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.context_manager import ContextManager
from utils.logger import log # Import your actual logger

# Mock the logger to prevent actual log output during tests and assert on log calls
@pytest.fixture(autouse=True)
def mock_logger():
    with patch('core.context_manager.log') as mock_log:
        yield mock_log

@pytest.fixture
def context_manager():
    """Provides a fresh ContextManager instance for each test."""
    cm = ContextManager(tick_interval=0.01)  # Use a small interval for faster tests
    yield cm
    if cm.is_running():
        cm.stop()
    # Ensure the thread is truly stopped before the next test runs
    if cm._thread and cm._thread.is_alive():
        cm._thread.join(timeout=0.1)


class TestContextManager:

    def test_initialization(self, context_manager, mock_logger):
        """Test ContextManager initializes with correct default values."""
        assert context_manager.tick == 0
        assert context_manager.env_state == {"tick": 0} # Tick is set in init
        assert context_manager.gui_instance is None
        assert context_manager.current_fitness_weights == {
            "tick_factor_weight": 0.05,
            "comms_factor_weight": 0.15,
            "interaction_factor_weight": 0.10,
            "knowledge_factor_weight": 0.30,
            "capability_performance_factor_weight": 0.40,
        }
        assert context_manager.active_goals == []
        assert context_manager.user_feedback_scores == {}
        assert context_manager.tick_interval == 0.01
        assert not context_manager.running
        assert context_manager._thread is None
        mock_logger.assert_any_call("[ContextManager] Initialized.")

    def test_set_gui_instance(self, context_manager, mock_logger):
        """Test setting the GUI instance."""
        mock_gui = Mock()
        context_manager.set_gui_instance(mock_gui)
        assert context_manager.gui_instance == mock_gui
        mock_logger.assert_any_call("[ContextManager] GUI instance reference set.")

    def test_post_insight_to_gui_with_gui(self, context_manager):
        """Test posting insight to GUI when a GUI instance is set."""
        mock_gui = Mock()
        context_manager.set_gui_instance(mock_gui)
        insight_data = {"type": "test", "data": "some insight"}
        context_manager.post_insight_to_gui(insight_data)
        mock_gui.display_system_insight.assert_called_once_with(insight_data)

    def test_post_insight_to_gui_no_gui(self, context_manager, mock_logger):
        """Test posting insight to GUI when no GUI instance is set."""
        insight_data = {"type": "test", "data": "some insight"}
        context_manager.post_insight_to_gui(insight_data)
        # Verify that a warning is logged and no error occurs
        mock_logger.assert_called_with(
            "[ContextManager] Cannot post insight to GUI: No GUI instance or display_system_insight method.",
            level="WARN"
        )

    def test_start_and_stop(self, context_manager, mock_logger):
        """Test starting and stopping the context manager thread."""
        assert not context_manager.is_running()
        context_manager.start()
        time.sleep(0.05)  # Give the thread some time to start and tick
        assert context_manager.is_running()
        assert context_manager.get_tick() > 0
        mock_logger.assert_any_call("[ContextManager] Worker thread started.")

        context_manager.stop()
        time.sleep(0.05)  # Give the thread some time to stop
        assert not context_manager.is_running()
        mock_logger.assert_any_call("[ContextManager] Stop requested.")
        mock_logger.assert_any_call("[ContextManager] Worker thread stopped.")
        mock_logger.assert_any_call("[ContextManager] Stopped.")

    def test_start_already_running(self, context_manager, mock_logger):
        """Test calling start when the thread is already running."""
        context_manager.start()
        time.sleep(0.01)
        initial_thread = context_manager._thread
        context_manager.start() # Call start again
        assert context_manager._thread == initial_thread # Should be the same thread
        mock_logger.assert_called_with(
            "[ContextManager] Start called, but worker thread is already running.",
            level="WARN"
        )

    def test_tick_progression(self, context_manager):
        """Test that the tick increments over time."""
        initial_tick = context_manager.get_tick()
        context_manager.start()
        time.sleep(0.05)  # Wait for a few ticks
        current_tick = context_manager.get_tick()
        assert current_tick > initial_tick
        context_manager.stop()

    def test_tick_progression_zero_interval(self, mock_logger):
        """Test tick progression with tick_interval set to 0 (max speed)."""
        cm_fast = ContextManager(tick_interval=0)
        initial_tick = cm_fast.get_tick()
        cm_fast.start()
        time.sleep(0.02) # Even a short sleep should allow many ticks
        current_tick = cm_fast.get_tick()
        assert current_tick > initial_tick + 5 # Expect a significant number of ticks
        cm_fast.stop()
        assert "sleep(0)" in str(mock_logger.call_args_list) # Check if time.sleep(0) was implicitly called

    def test_get_state(self, context_manager):
        """Test retrieving the environment state."""
        context_manager.start()
        time.sleep(0.02) # Allow some ticks to occur
        state = context_manager.get_state()
        assert "tick" in state
        assert state["tick"] == context_manager.get_tick()
        context_manager.stop()

    def test_get_fitness_weights(self, context_manager):
        """Test retrieving fitness weights."""
        weights = context_manager.get_fitness_weights()
        assert isinstance(weights, dict)
        assert "knowledge_factor_weight" in weights
        assert weights["knowledge_factor_weight"] == 0.30  # Initial value

    def test_fitness_weight_adjustment(self, context_manager, mock_logger):
        """Test that fitness weights adjust at tick 50."""
        context_manager.tick_interval = 0.001 # Make ticks fast for this test
        context_manager.start()

        # Wait until tick 50 is reached
        timeout = 5 # seconds
        start_time = time.time()
        while context_manager.get_tick() < 50 and (time.time() - start_time) < timeout:
            time.sleep(0.001)

        assert context_manager.get_tick() >= 50
        updated_weights = context_manager.get_fitness_weights()

        # Check for adjustment if knowledge_factor_weight was initially > 0.15
        assert updated_weights["knowledge_factor_weight"] == round(0.30 - 0.10, 2)
        assert updated_weights["capability_performance_factor_weight"] == round(0.40 + 0.10, 2)

        # Check for logging of adjustment
        mock_logger.assert_any_call(f"[ContextManager] Adjusting fitness weights at tick 50")
        mock_logger.assert_any_call(f"[ContextManager] New weights: {updated_weights}")

        # Wait until tick 100 to check reset
        start_time = time.time()
        while context_manager.get_tick() < 100 and (time.time() - start_time) < timeout:
            time.sleep(0.001)

        assert context_manager.get_tick() >= 100
        reset_weights = context_manager.get_fitness_weights()
        assert reset_weights["knowledge_factor_weight"] == 0.30
        assert reset_weights["capability_performance_factor_weight"] == 0.40

        context_manager.stop()

    def test_record_and_get_user_feedback(self, context_manager, mock_logger):
        """Test recording and retrieving user feedback."""
        agent_name = "AgentX"
        feedback1 = 0.5
        feedback2 = 0.3

        context_manager.record_user_feedback(agent_name, feedback1)
        assert context_manager.get_user_feedback_score(agent_name) == feedback1
        mock_logger.assert_called_with(
            f"[ContextManager] Recorded feedback for '{agent_name}': {feedback1}. New total: {feedback1}"
        )

        context_manager.record_user_feedback(agent_name, feedback2)
        expected_total = feedback1 + feedback2
        assert context_manager.get_user_feedback_score(agent_name) == expected_total
        mock_logger.assert_called_with(
            f"[ContextManager] Recorded feedback for '{agent_name}': {feedback2}. New total: {expected_total}"
        )

        assert context_manager.get_user_feedback_score("NonExistentAgent") == 0.0

    def test_update_method_warning(self, context_manager, mock_logger):
        """Test that calling the update method logs a warning."""
        context_manager.update()
        mock_logger.assert_called_with(
            "[ContextManager] update() called - tick progression is now managed internally by a thread.",
            level="WARN"
        )

    def test_thread_safety_get_tick(self, context_manager):
        """Test thread safety of get_tick."""
        context_manager.start()
        time.sleep(0.01) # Allow some ticks to start

        results = []
        num_threads = 5
        num_reads_per_thread = 100

        def read_tick():
            for _ in range(num_reads_per_thread):
                results.append(context_manager.get_tick())

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=read_tick)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        context_manager.stop()
        # Basic check: ensure no exceptions were raised and results were collected
        assert len(results) == num_threads * num_reads_per_thread
        # More robust check would be to ensure monotonicity, but that's harder with concurrent reads.
        # Just checking that it didn't crash is a good start for thread safety.

    def test_thread_safety_record_user_feedback(self, context_manager):
        """Test thread safety of record_user_feedback."""
        agent_name = "ConcurrentAgent"
        num_threads = 10
        feedback_per_thread = 0.1
        total_expected_feedback = num_threads * feedback_per_thread

        def give_feedback():
            context_manager.record_user_feedback(agent_name, feedback_per_thread)

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=give_feedback)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        final_score = context_manager.get_user_feedback_score(agent_name)
        # Using pytest.approx for floating point comparison
        assert final_score == pytest.approx(total_expected_feedback)

    def test_stop_timeout_warning(self, context_manager, mock_logger):
        """Test that a warning is logged if the thread doesn't stop in time."""
        context_manager.tick_interval = 100 # Make interval very long so join times out
        context_manager.start()

        # Override the join to simulate a timeout, but still let the thread *eventually* stop
        # In a real scenario, we might mock threading.Thread.join directly.
        # Here, we set a very short join timeout relative to the long tick_interval.
        context_manager.stop()
        mock_logger.assert_any_call("[ContextManager] Worker thread did not stop in time.", level="WARN")
        mock_logger.assert_any_call("[ContextManager] Stopped.")
# File: /c:/Users/gilbe/Desktop/self-evolving-ai/gui.py

import customtkinter as ctk
import threading
import logging
import time
import _tkinter
from utils.logger import log as gui_log
import config

class GUITextHandler(logging.Handler):
    """Custom logging handler to send log messages to the GUI."""
    def __init__(self, textbox_widget):
        super().__init__()
        self.textbox_widget = textbox_widget
        self.gui_instance = textbox_widget.master

    def emit(self, record):
        # Send formatted log message to the GUI's log display
        msg = self.format(record)
        if hasattr(self.gui_instance, 'log_to_gui') and callable(getattr(self.gui_instance, 'log_to_gui')):
            self.gui_instance.log_to_gui(msg)

class SimulationGUI(ctk.CTk):
    """Main GUI class for the Self-Evolving AI Monitor."""
    def __init__(self, context_manager, meta_agent, mutation_engine, knowledge_base):
        super().__init__()
        self._is_closing = False

        # Window setup
        self.title("Self-Evolving AI Monitor")
        self.geometry("950x850")
        self.grid_rowconfigure(0, weight=0)

        # Store references to simulation components
        self.context_manager = context_manager
        self.meta_agent = meta_agent
        self.mutation_engine = mutation_engine
        self.knowledge_base = knowledge_base

        self.selected_agent_name = None
        self.simulation_thread = None
        self.simulation_running = False
        self.stop_simulation_event = threading.Event()

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        current_row = 0

        # System name label
        self.system_name_label = ctk.CTkLabel(self, text=f"System Name: {self.meta_agent.identity_engine.get_identity()['name']}", font=("Arial", 16, "bold"))
        self.system_name_label.grid(row=current_row, column=0, columnspan=2, pady=(10,5), padx=10, sticky="ew")
        current_row += 1

        # Tick label
        self.tick_label = ctk.CTkLabel(self, text="Tick: N/A", font=("Arial", 14))
        self.tick_label.grid(row=current_row, column=0, columnspan=2, pady=(0,10), padx=10, sticky="ew")
        current_row += 1

        content_start_row = current_row

        # Agent and system info labels
        self.task_agents_label = ctk.CTkLabel(self, text="Task Agents: N/A", font=("Arial", 12))
        self.task_agents_label.grid(row=content_start_row, column=0, pady=2, padx=10, sticky="w")

        self.skill_agents_label = ctk.CTkLabel(self, text="Skill Agents: N/A", font=("Arial", 12))
        self.skill_agents_label.grid(row=content_start_row + 1, column=0, pady=2, padx=10, sticky="w")

        self.avg_fitness_label = ctk.CTkLabel(self, text="Avg. Fitness: N/A", font=("Arial", 12))
        self.avg_fitness_label.grid(row=content_start_row + 2, column=0, pady=2, padx=10, sticky="w")

        self.kb_size_label = ctk.CTkLabel(self, text="KB Size: N/A", font=("Arial", 12))
        self.kb_size_label.grid(row=content_start_row + 3, column=0, pady=2, padx=10, sticky="w")

        # Import visualization frames
        from gui_visualizations import AgentMapFrame, MemoryStreamFrame, KnowledgeInjectionFrame, KnowledgeQueryFrame, AgentSummaryFrame, SystemMetricsChartFrame

        # System metrics chart
        self.system_metrics_chart_frame = SystemMetricsChartFrame(self, context_manager=self.context_manager, mutation_engine=self.mutation_engine)
        self.system_metrics_chart_frame.grid(row=content_start_row, column=1, rowspan=4, pady=(0,5), padx=10, sticky="nsew")

        # Agent map and memory stream
        self.agent_map_frame = AgentMapFrame(self, meta_agent=self.meta_agent)
        self.memory_stream_frame = MemoryStreamFrame(self, knowledge_base=self.knowledge_base, context_manager=self.context_manager)
        self.memory_stream_frame.grid(row=content_start_row + 4, column=1, rowspan=6, pady=(5,10), padx=10, sticky="nsew")

        current_row = content_start_row + 4

        # Agent summary
        self.agent_summary_frame = AgentSummaryFrame(self, meta_agent_ref=self.meta_agent, on_agent_select_callback=self.on_agent_select)
        self.agent_summary_frame.grid(row=current_row, column=0, pady=5, padx=10, sticky="nsew")
        current_row += 1

        # Feedback section
        self.feedback_label = ctk.CTkLabel(self, text="Feedback for Selected Agent:", font=("Arial", 14))
        self.feedback_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        current_row += 1

        self.upvote_button = ctk.CTkButton(self, text="Upvote Selected", command=lambda: self.submit_feedback("upvote"))
        self.upvote_button.grid(row=current_row, column=0, pady=5, padx=10, sticky="ew")

        self.downvote_button = ctk.CTkButton(self, text="Downvote Selected", command=lambda: self.submit_feedback("downvote"))
        self.downvote_button.grid(row=current_row, column=1, pady=5, padx=10, sticky="ew")
        current_row += 1

        self.feedback_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.feedback_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="w")
        current_row += 1

        # Simulation control buttons
        self.start_button = ctk.CTkButton(self, text="Start Simulation", command=self.start_simulation)
        self.start_button.grid(row=current_row, column=0, pady=20, padx=10, sticky="ew")

        self.stop_button = ctk.CTkButton(self, text="Stop Simulation", command=self.stop_simulation, state="disabled")
        self.stop_button.grid(row=current_row, column=1, pady=20, padx=10, sticky="ew")
        current_row += 1

        # Log area
        self.log_textbox_label = ctk.CTkLabel(self, text="Simulation Log:", font=("Arial", 14))
        self.log_textbox_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        current_row += 1

        self.log_textbox = ctk.CTkTextbox(self, height=150, state="disabled")
        self.log_textbox.grid(row=current_row, column=0, columnspan=2, pady=10, padx=10, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1)
        current_row += 1

        # Custom goal submission
        self.goal_input_label = ctk.CTkLabel(self, text="Submit Custom Goal to System:", font=("Arial", 14))
        self.goal_input_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        self.goal_entry = ctk.CTkEntry(self, placeholder_text="Enter goal description...")
        self.goal_entry.grid(row=current_row, column=0, pady=5, padx=10, sticky="ew")
        self.grid_rowconfigure(current_row, weight=0)

        self.send_goal_button = ctk.CTkButton(self, text="Send Goal", command=self.submit_custom_goal)
        self.send_goal_button.grid(row=current_row, column=1, pady=5, padx=10, sticky="ew")
        current_row += 1

        self.goal_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.goal_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="w")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        # Knowledge injection section
        self.knowledge_injection_frame = KnowledgeInjectionFrame(self,
                                                                 knowledge_base_ref=self.knowledge_base,
                                                                 context_manager_ref=self.context_manager,
                                                                 gui_logger_func=self.log_to_gui)
        self.knowledge_injection_frame.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        # Knowledge query section
        self.knowledge_query_frame = KnowledgeQueryFrame(self,
                                                         knowledge_base_ref=self.knowledge_base,
                                                         gui_logger_func=self.log_to_gui)
        self.knowledge_query_frame.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        # System insights and notifications
        self.insights_label = ctk.CTkLabel(self, text="System Insights & Notifications:", font=("Arial", 14))
        self.insights_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        self.insights_textbox = ctk.CTkTextbox(self, height=120, state="disabled")
        self.insights_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1)
        current_row += 1

        # Start periodic UI update and set up window close protocol
        self.update_ui_elements()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Setup GUI logging
        self.gui_log_handler = GUITextHandler(self.log_textbox)
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.gui_log_handler.setFormatter(formatter)

        app_logger = logging.getLogger()
        app_logger.addHandler(self.gui_log_handler)
        app_logger.setLevel(logging.INFO)

        # Initial log messages for debugging
        gui_log("[GUI] Simulation references set.")
        gui_log(f"[GUI DEBUG] Context set? {self.context_manager is not None}")
        gui_log(f"[GUI DEBUG] Meta agent set? {self.meta_agent is not None}")
        gui_log(f"[GUI DEBUG] Knowledge Base set? {self.knowledge_base is not None}")
        gui_log(f"[GUI DEBUG] Mutation Engine set? {self.mutation_engine is not None}")

    def log_to_gui(self, message):
        """Safely appends a message to the log_textbox from any thread."""
        if self._is_closing:
            print(f"GUI_LOG_SKIPPED (closing): {message}")
            return

        def _append_log():
            if self._is_closing or not self.winfo_exists() or not hasattr(self, 'log_textbox') or not self.log_textbox.winfo_exists():
                return
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.configure(state="disabled")
            self.log_textbox.see("end")

        # Ensure thread-safe GUI updates
        if threading.current_thread() != threading.main_thread():
            self.after(0, _append_log)
        else:
            _append_log()

    def on_agent_select(self, agent_name):
        """Handles selection of an agent from the list."""
        self.selected_agent_name = agent_name
        gui_log(f"Selected agent for feedback: {self.selected_agent_name}")
        self.feedback_status_label.configure(text=f"Selected: {self.selected_agent_name}")

    def update_ui_elements(self):
        """Updates UI elements with current simulation data."""
        if self._is_closing or not self.winfo_exists():
            return

        try:
            current_tick_for_debug = "N/A"
            if self.context_manager:
                current_tick_for_debug = self.context_manager.get_tick()

            # Only update if all simulation components are available
            if not (self.context_manager and self.meta_agent and self.mutation_engine and self.knowledge_base):
                if self.simulation_running and not self._is_closing and self.winfo_exists():
                    self.after(500, self.update_ui_elements)
                return

            # Update system name and notify if changed
            identity_info = self.meta_agent.identity_engine.get_identity()
            if not isinstance(identity_info, dict):
                 identity_info = {}

            new_system_name = identity_info.get("name", "EvoSystem_v0.1")
            displayed_name_text = f"System Name: {new_system_name}"

            # Show insight if system name changes
            if self.system_name_label.cget("text") != displayed_name_text and new_system_name != "EvoSystem_v0.1":
                self.display_system_insight({"tick": self.context_manager.get_tick(), "diagnosing_agent_id": "IdentityEngine", "root_cause_hypothesis": f"System has adopted a new name: {new_system_name}", "confidence": 1.0, "suggested_actions": ["Observe new identity"]})
            self.system_name_label.configure(text=displayed_name_text)

            # Update tick and agent/system info
            self.tick_label.configure(text=f"Tick: {self.context_manager.get_tick()}")
            self.task_agents_label.configure(text=f"Task Agents: {len(self.meta_agent.task_agents)}")
            self.skill_agents_label.configure(text=f"Skill Agents: {len(self.meta_agent.skill_agents)}")

            # Calculate and update average fitness
            avg_fitness = 0.0
            if hasattr(self.mutation_engine, 'last_agent_fitness_scores') and self.mutation_engine.last_agent_fitness_scores:
                fitness_scores = list(self.mutation_engine.last_agent_fitness_scores.values())
                if fitness_scores:
                    avg_fitness = sum(fitness_scores) / len(fitness_scores)
            self.avg_fitness_label.configure(text=f"Avg. Fitness: {avg_fitness:.3f}")

            # Update knowledge base size
            kb_size = self.knowledge_base.get_size()
            self.kb_size_label.configure(text=f"KB Size: {kb_size}")

            # Update visualization frames
            if hasattr(self, 'agent_map_frame') and self.agent_map_frame.winfo_exists(): self.agent_map_frame.update_display()
            if hasattr(self, 'memory_stream_frame') and self.memory_stream_frame.winfo_exists(): self.memory_stream_frame.update_display()
            if hasattr(self, 'agent_summary_frame') and self.agent_summary_frame.winfo_exists(): self.agent_summary_frame.update_display()
            if hasattr(self, 'system_metrics_chart_frame') and self.system_metrics_chart_frame.winfo_exists(): self.system_metrics_chart_frame.update_display()

        except _tkinter.TclError as e:
            if not self._is_closing:
                gui_log(f"TclError in update_ui_elements: {e}", level="WARN")
            return

        # Schedule next update if simulation is running
        if self.simulation_running and not self._is_closing:
            self.after(500, self.update_ui_elements)

    def submit_feedback(self, feedback_type):
        """Submits user feedback to the simulation."""
        if not self.selected_agent_name:
            self.feedback_status_label.configure(text="Error: No agent selected for feedback.")
            gui_log("Feedback submission attempt failed: No agent selected.", level="WARN")
            return
        if feedback_type not in ("upvote", "downvote"):
            self.feedback_status_label.configure(text="Error: Invalid feedback type.")
            gui_log(f"Invalid feedback type: {feedback_type}", level="ERROR")
            return

        if self.context_manager:
            feedback_value = 1.0 if feedback_type == "upvote" else -1.0
            self.context_manager.record_user_feedback(self.selected_agent_name, feedback_value)
            gui_log(f"Recorded '{feedback_type}' (value: {feedback_value}) for '{self.selected_agent_name}'.")
            self.feedback_status_label.configure(text=f"Submitted {feedback_type} for {self.selected_agent_name}.")
        else:
            self.feedback_status_label.configure(text="Error: Context manager not available.")
            gui_log("Feedback submission failed: Context manager not available.", level="ERROR")

    def submit_custom_goal(self):
        """Submits a custom goal from the user to the MetaAgent."""
        goal_description = self.goal_entry.get()
        if not goal_description:
            self.goal_status_label.configure(text="Error: Goal description cannot be empty.")
            gui_log("Custom goal submission failed: Empty description.", level="WARN")
            return

        if self.meta_agent and hasattr(self.meta_agent, 'receive_user_goal'):
            try:
                self.meta_agent.receive_user_goal(goal_description)
                gui_log(f"User submitted custom goal: '{goal_description}' to MetaAgent.")
                self.goal_status_label.configure(text=f"Goal '{goal_description[:30]}...' submitted.")
                self.goal_entry.delete(0, "end")
            except Exception as e:
                gui_log(f"Error submitting custom goal to MetaAgent: {e}", level="ERROR", exc_info=True)
                self.goal_status_label.configure(text=f"Error submitting goal: {e}")
        else:
            self.goal_status_label.configure(text="Error: MetaAgent not available or doesn't support custom goals.")
            gui_log("Custom goal submission failed: MetaAgent not available or 'receive_user_goal' method missing.", level="ERROR")

    def display_system_insight(self, insight_data: dict):
        """Displays a system-generated insight or notification in the GUI."""
        if self._is_closing or not self.winfo_exists():
            print(f"INSIGHT_SKIPPED (closing): {insight_data.get('root_cause_hypothesis', 'N/A')}")
            return

        def _append_insight():
            if self._is_closing or not self.winfo_exists() or \
               not hasattr(self, 'insights_textbox') or not self.insights_textbox.winfo_exists():
                return

            try:
                if insight_data is None:
                    return

                self.insights_textbox.configure(state="normal")
                # Format and display the insight
                formatted_insight = f"--- Insight/Notification (Tick: {insight_data.get('tick', 'N/A')}) ---\n"
                formatted_insight += f"Agent: {insight_data.get('diagnosing_agent_id', 'System')}\n"
                formatted_insight += f"Hypothesis: {insight_data.get('root_cause_hypothesis', 'N/A')}\n"
                formatted_insight += f"Confidence: {insight_data.get('confidence', 'N/A'):.2f}\n"
                if insight_data.get('suggested_actions'):
                    formatted_insight += f"Suggested Actions: {', '.join(insight_data.get('suggested_actions'))}\n"
                formatted_insight += "-------------------------------------------\n\n"
                self.insights_textbox.insert("end", formatted_insight)
                self.insights_textbox.configure(state="disabled")
                self.insights_textbox.see("end")
            except _tkinter.TclError as e:
                if not self._is_closing:
                    gui_log(f"TclError in _append_insight: {e}", level="WARN")
                else:
                    print(f"TclError in _append_insight (GUI closing): {e}")

        # Ensure thread-safe GUI updates
        if threading.current_thread() != threading.main_thread():
            self.after(0, _append_insight)
        else:
            _append_insight()

    def _simulation_loop(self):
        """Main simulation loop running in a background thread."""
        gui_log("SIMULATION THREAD STARTED...")
        last_processed_tick_in_loop = -1

        try:
            while not self.stop_simulation_event.is_set():
                # Wait for context manager to be running
                if not self.context_manager or not self.context_manager.is_running():
                    time.sleep(0.1)
                    continue

                current_tick_from_context = self.context_manager.get_tick()

                # Only process if tick has advanced
                if current_tick_from_context > last_processed_tick_in_loop:
                    gui_log(f"Simulation loop: Processing for new tick {current_tick_from_context}", level="DEBUG")

                    # Run meta agent logic
                    if self.meta_agent:
                        self.meta_agent.run_agents()

                    # Finalize tick processing in context manager
                    if self.context_manager and hasattr(self.context_manager, 'finalize_tick_processing'):
                        gui_log(f"Calling context_manager.finalize_tick_processing(tick={current_tick_from_context}) before mutation.", level="DEBUG")
                        self.context_manager.finalize_tick_processing(current_tick_from_context)

                    # Run mutation/assessment
                    if self.mutation_engine:
                        self.mutation_engine.run_assessment_and_mutation()

                    last_processed_tick_in_loop = current_tick_from_context
                else:
                    time.sleep(config.MAIN_LOOP_SLEEP if config.MAIN_LOOP_SLEEP > 0 else 0.001)
        except Exception as e:
            gui_log(f"Exception in simulation thread: {e}", level="ERROR", exc_info=True)
        finally:
            gui_log("Simulation thread: Loop exited. Beginning finalization...", level="INFO")

            # Ensure context manager is stopped
            if self.context_manager and self.context_manager.is_running():
                gui_log("Simulation thread: Requesting ContextManager stop.", level="INFO")
                self.context_manager.stop()
                gui_log("Simulation thread: ContextManager stop request completed.", level="INFO")

            def _finalize_stop_ui():
                if self._is_closing or not self.winfo_exists():
                    gui_log("GUI is closing/destroyed, skipping _finalize_stop_ui's UI updates.", level="DEBUG")
                    self.simulation_running = False
                    return

                gui_log("Simulation thread: Executing _finalize_stop_ui on main thread.", level="DEBUG")
                self.simulation_running = False
                self.update_button_states()
                self.update_ui_elements()

            # Schedule UI updates on main thread after stopping
            if not self._is_closing:
                self.after(0, _finalize_stop_ui)
            else:
                self.simulation_running = False
                gui_log("GUI already closing, _finalize_stop_ui not scheduled. Set simulation_running=False.", level="DEBUG")

            gui_log("Simulation thread: Finalization complete. Thread is now finishing.", level="INFO")

    def start_simulation(self):
        """Starts the simulation and its background thread."""
        if not self.simulation_running:
            self.simulation_running = True
            # Ensure stop event is cleared before starting
            if hasattr(self.stop_simulation_event, 'is_set') and self.stop_simulation_event.is_set():
                gui_log("Clearing stop_simulation_event before starting simulation.", level="DEBUG")
                self.stop_simulation_event.clear()
            elif not hasattr(self.stop_simulation_event, 'is_set'):
                gui_log("stop_simulation_event not properly initialized!", level="ERROR")
                self.stop_simulation_event = threading.Event()
            self.stop_simulation_event.clear()

            # Start context manager if not running
            if self.context_manager and not self.context_manager.is_running():
                self.context_manager.start()
            elif not self.context_manager:
                gui_log("Cannot start simulation: Context manager not initialized.", level="ERROR")
                self.simulation_running = False
                self.after(0, lambda: self.update_button_states())
                return

            # Start simulation thread
            self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.simulation_thread.name = "SimulationLoopThread"
            self.simulation_thread.start()

            self.after(0, lambda: self.update_button_states())
            self.update_ui_elements()
            gui_log("Simulation started via GUI.")

    def stop_simulation(self):
        """Stops the simulation and its background thread."""
        if self.simulation_running or (self.context_manager and self.context_manager.is_running()):
            gui_log("Stop signal initiated via GUI...")
            self.simulation_running = False
            self.stop_simulation_event.set()
            self.after(0, self.update_button_states)
            gui_log("Stop signal processed by GUI. Simulation thread will now terminate and clean up ContextManager.")
        else:
            gui_log("Stop called, but simulation or context manager not considered running by GUI.", level="DEBUG")
            self.simulation_running = False
            if hasattr(self.stop_simulation_event, 'set'):
                self.stop_simulation_event.set()
            self.after(0, self.update_button_states)

    def update_button_states(self):
        """Enables or disables start/stop buttons based on simulation state."""
        if self._is_closing or not self.winfo_exists():
            return

        try:
            if self.simulation_running:
                if hasattr(self, 'start_button') and self.start_button.winfo_exists():
                    self.start_button.configure(state="disabled")
                if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
                    context_is_running = self.context_manager and self.context_manager.is_running()
                    if self.simulation_thread and self.simulation_thread.is_alive() or context_is_running:
                        self.stop_button.configure(state="normal")
                    else:
                        self.stop_button.configure(state="disabled")
            else:
                if hasattr(self, 'start_button') and self.start_button.winfo_exists():
                    self.start_button.configure(state="normal")
                if hasattr(self, 'stop_button') and self.stop_button.winfo_exists():
                    self.stop_button.configure(state="disabled")
        except _tkinter.TclError as e:
            gui_log(f"TclError in update_button_states (likely during shutdown): {e}", level="WARN")
        except Exception as e:
            gui_log(f"Unexpected error in update_button_states: {e}", level="ERROR", exc_info=True)

    def on_closing(self):
        """Handles GUI window close event and cleanup."""
        if self._is_closing:
            return
        self._is_closing = True

        gui_log("GUI closing sequence started.")
        self.stop_simulation()

        # Wait for simulation thread to finish
        if self.simulation_thread and self.simulation_thread.is_alive():
            gui_log("Waiting for simulation thread to join...")
            join_timeout = config.TICK_INTERVAL * 4 if config.TICK_INTERVAL > 0 else 2.0
            join_timeout = max(join_timeout, 2.0)
            self.simulation_thread.join(timeout=join_timeout)
            if self.simulation_thread.is_alive():
                gui_log("Simulation thread did not join in time. It may be blocked.", level="WARN")
                if self.context_manager and self.context_manager.is_running():
                    gui_log("Fallback: Forcing ContextManager stop as thread is unresponsive.", level="WARN")
                    self.context_manager.stop()
        else:
            if self.context_manager and self.context_manager.is_running():
                gui_log("GUI closing: Simulation thread not active, ensuring ContextManager is stopped.", level="INFO")
                self.context_manager.stop()

        # Remove GUI log handler from logger
        if hasattr(self, 'gui_log_handler') and self.gui_log_handler:
            root_logger = logging.getLogger()
            if self.gui_log_handler in root_logger.handlers:
                root_logger.removeHandler(self.gui_log_handler)
            self.gui_log_handler = None

        gui_log("Destroying GUI window.")
        self.destroy()

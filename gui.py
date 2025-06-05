# gui.py

import customtkinter as ctk
import threading
import logging # For GUI log handler
import time
import _tkinter  # <-- Add this import for TclError
from typing import Any, Dict, List, Optional # Import necessary types
from utils.logger import log as gui_log # Using your existing logger
import config # To access MAIN_LOOP_SLEEP


class GUITextHandler(logging.Handler): # Moved this class definition up
    """A custom logging handler that directs logs to a CTkTextbox widget."""
    def __init__(self, textbox_widget):
        super().__init__()
        self.textbox_widget = textbox_widget
        self.gui_instance = textbox_widget.master # Assuming textbox is direct child of GUI

    def emit(self, record):
        msg = self.format(record)
        # Ensure the call to update the textbox is thread-safe
        # by scheduling it on the main GUI thread via the GUI instance's `log_to_gui` method.
        if hasattr(self.gui_instance, 'log_to_gui') and callable(getattr(self.gui_instance, 'log_to_gui')):
            self.gui_instance.log_to_gui(msg)


class SimulationGUI(ctk.CTk):
    def __init__(self, context_manager, meta_agent, mutation_engine, knowledge_base):
        super().__init__()
        self._is_closing = False # Flag to indicate if the GUI is in the process of closing

        self.title("Self-Evolving AI Monitor")
        self.geometry("950x850") # Further Increased size for new section
        self.grid_rowconfigure(0, weight=0) # Status row
        # Simulation component references
        # These are set by the constructor when the GUI is initialized.
        self.context_manager = context_manager
        self.meta_agent = meta_agent
        self.mutation_engine = mutation_engine
        self.knowledge_base = knowledge_base

        self.selected_agent_name = None # Used for feedback
        self.simulation_thread = None
        self.simulation_running = False
        self.stop_simulation_event = threading.Event()

        # --- UI Elements ---
        self.grid_columnconfigure(0, weight=1) # Left column for status/controls/logs
        self.grid_columnconfigure(1, weight=1) # Right column for visualizations
        current_row = 0

        # --- Status Display Area ---
        self.system_name_label = ctk.CTkLabel(self, text=f"System Name: {self.meta_agent.identity_engine.get_identity()['name']}", font=("Arial", 16, "bold"))
        self.system_name_label.grid(row=current_row, column=0, columnspan=2, pady=(10,5), padx=10, sticky="ew")
        current_row += 1

        self.tick_label = ctk.CTkLabel(self, text="Tick: N/A", font=("Arial", 14)) # Slightly smaller font
        self.tick_label.grid(row=current_row, column=0, columnspan=2, pady=(0,10), padx=10, sticky="ew")
        current_row += 1

        content_start_row = current_row # This will be 2, after system name and tick

        # Column 0 labels (Status details)
        self.task_agents_label = ctk.CTkLabel(self, text="Task Agents: N/A", font=("Arial", 12))
        self.task_agents_label.grid(row=content_start_row, column=0, pady=2, padx=10, sticky="w")

        self.skill_agents_label = ctk.CTkLabel(self, text="Skill Agents: N/A", font=("Arial", 12))
        self.skill_agents_label.grid(row=content_start_row + 1, column=0, pady=2, padx=10, sticky="w")

        self.avg_fitness_label = ctk.CTkLabel(self, text="Avg. Fitness: N/A", font=("Arial", 12))
        self.avg_fitness_label.grid(row=content_start_row + 2, column=0, pady=2, padx=10, sticky="w")

        self.kb_size_label = ctk.CTkLabel(self, text="KB Size: N/A", font=("Arial", 12))
        self.kb_size_label.grid(row=content_start_row + 3, column=0, pady=2, padx=10, sticky="w")

        # --- Visualizations Area (New Column) ---
        # Import all visualization frames needed
        from gui_visualizations import AgentMapFrame, MemoryStreamFrame, KnowledgeInjectionFrame, KnowledgeQueryFrame, AgentSummaryFrame, SystemMetricsChartFrame

        # System Metrics Chart Frame (New)
        self.system_metrics_chart_frame = SystemMetricsChartFrame(self, context_manager=self.context_manager, mutation_engine=self.mutation_engine)
        self.system_metrics_chart_frame.grid(row=content_start_row, column=1, rowspan=4, pady=(0,5), padx=10, sticky="nsew") # Starts at row 2, spans 4 rows

        # Agent Map Frame (Adjusted row/rowspan)
        self.agent_map_frame = AgentMapFrame(self, meta_agent=self.meta_agent)
        self.memory_stream_frame = MemoryStreamFrame(self, knowledge_base=self.knowledge_base, context_manager=self.context_manager)
        self.memory_stream_frame.grid(row=content_start_row + 4, column=1, rowspan=6, pady=(5,10), padx=10, sticky="nsew") # Below AgentMapFrame

        current_row = content_start_row + 4 # Next available row for column 0 items

        # --- Agent Summary List ---
        self.agent_summary_frame = AgentSummaryFrame(self, meta_agent_ref=self.meta_agent, on_agent_select_callback=self.on_agent_select)
        self.agent_summary_frame.grid(row=current_row, column=0, pady=5, padx=10, sticky="nsew")
        current_row += 1

        # --- Feedback Submission ---
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

        # Control Buttons
        self.start_button = ctk.CTkButton(self, text="Start Simulation", command=self.start_simulation)
        self.start_button.grid(row=current_row, column=0, pady=20, padx=10, sticky="ew")

        self.stop_button = ctk.CTkButton(self, text="Stop Simulation", command=self.stop_simulation, state="disabled")
        self.stop_button.grid(row=current_row, column=1, pady=20, padx=10, sticky="ew")
        current_row += 1

        # Log Text Area
        self.log_textbox_label = ctk.CTkLabel(self, text="Simulation Log:", font=("Arial", 14))
        self.log_textbox_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        current_row += 1

        self.log_textbox = ctk.CTkTextbox(self, height=150, state="disabled")
        self.log_textbox.grid(row=current_row, column=0, columnspan=2, pady=10, padx=10, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1) # Make log area expand
        current_row += 1
        # The log area is the primary expanding element.
        
        # --- Custom Goal Submission ---
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

        # --- Knowledge Injection Section ---
        self.knowledge_injection_frame = KnowledgeInjectionFrame(self,
                                                                 knowledge_base_ref=self.knowledge_base,
                                                                 context_manager_ref=self.context_manager,
                                                                 gui_logger_func=self.log_to_gui)
        self.knowledge_injection_frame.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        # --- Knowledge Query Section ---
        self.knowledge_query_frame = KnowledgeQueryFrame(self,
                                                         knowledge_base_ref=self.knowledge_base,
                                                         gui_logger_func=self.log_to_gui)
        self.knowledge_query_frame.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="ew")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        # --- System Insights & Notifications Section ---
        self.insights_label = ctk.CTkLabel(self, text="System Insights & Notifications:", font=("Arial", 14))
        self.insights_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=10, sticky="w")
        self.grid_rowconfigure(current_row, weight=0)
        current_row += 1

        self.insights_textbox = ctk.CTkTextbox(self, height=120, state="disabled")
        self.insights_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=10, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1) 
        current_row += 1

        # Initial UI update
        self.update_ui_elements()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Setup GUI Logging ---
        self.gui_log_handler = GUITextHandler(self.log_textbox)
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.gui_log_handler.setFormatter(formatter)

        app_logger = logging.getLogger() # Get root logger
        app_logger.addHandler(self.gui_log_handler)
        app_logger.setLevel(logging.INFO) 

        gui_log("[GUI] Simulation references set.")
        gui_log(f"[GUI DEBUG] Context set? {self.context_manager is not None}")
        gui_log(f"[GUI DEBUG] Meta agent set? {self.meta_agent is not None}")
        gui_log(f"[GUI DEBUG] Knowledge Base set? {self.knowledge_base is not None}")
        gui_log(f"[GUI DEBUG] Mutation Engine set? {self.mutation_engine is not None}")
    # self.start_simulation() # Optionally start simulation automatically on GUI launch

    def log_to_gui(self, message):
        """Safely appends a message to the log_textbox from any thread."""
        if self._is_closing: # Don't attempt to log if GUI is shutting down
            # Fallback to console print if GUI log is unavailable during shutdown
            print(f"GUI_LOG_SKIPPED (closing): {message}")
            return

        def _append_log():
            # Double check here as well, as the 'after' might execute late
            if self._is_closing or not self.winfo_exists() or not hasattr(self, 'log_textbox') or not self.log_textbox.winfo_exists():
                return
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.configure(state="disabled")
            self.log_textbox.see("end")

        if threading.current_thread() != threading.main_thread():
            self.after(0, _append_log)
        else:
            _append_log()

    def on_agent_select(self, agent_name):
        """Handles selection of an agent from the list (callback for AgentSummaryFrame)."""
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
            # gui_log(f"[GUI DEBUG] Current tick for UI update: {current_tick_for_debug}", level="DEBUG") # Can be noisy

            if not (self.context_manager and self.meta_agent and self.mutation_engine and self.knowledge_base):
                if self.simulation_running and not self._is_closing and self.winfo_exists():
                    self.after(500, self.update_ui_elements)
                return

            # Proceed with UI updates if components are available

            # Update System Name (moved inside try)
            identity_info = self.meta_agent.identity_engine.get_identity()
            # Ensure identity_info is a dictionary before using .get()
            if not isinstance(identity_info, dict):
                 identity_info = {} # Default to empty dict if not valid

            new_system_name = identity_info.get("name", "EvoSystem_v0.1")
            displayed_name_text = f"System Name: {new_system_name}"
            
            if self.system_name_label.cget("text") != displayed_name_text and new_system_name != "EvoSystem_v0.1":
                # Name has changed from default to something new
                self.display_system_insight({"tick": self.context_manager.get_tick(), "diagnosing_agent_id": "IdentityEngine", "root_cause_hypothesis": f"System has adopted a new name: {new_system_name}", "confidence": 1.0, "suggested_actions": ["Observe new identity"]})
            self.system_name_label.configure(text=displayed_name_text)

            self.tick_label.configure(text=f"Tick: {self.context_manager.get_tick()}")
            self.task_agents_label.configure(text=f"Task Agents: {len(self.meta_agent.task_agents)}")
            self.skill_agents_label.configure(text=f"Skill Agents: {len(self.meta_agent.skill_agents)}")

            avg_fitness = 0.0
            if hasattr(self.mutation_engine, 'last_agent_fitness_scores') and self.mutation_engine.last_agent_fitness_scores:
                fitness_scores = list(self.mutation_engine.last_agent_fitness_scores.values())
                if fitness_scores: 
                    avg_fitness = sum(fitness_scores) / len(fitness_scores)
            self.avg_fitness_label.configure(text=f"Avg. Fitness: {avg_fitness:.3f}")

            kb_size = self.knowledge_base.get_size()
            self.kb_size_label.configure(text=f"KB Size: {kb_size}")

            # Update the new visualization frames
            if hasattr(self, 'agent_map_frame') and self.agent_map_frame.winfo_exists(): self.agent_map_frame.update_display()
            if hasattr(self, 'memory_stream_frame') and self.memory_stream_frame.winfo_exists(): self.memory_stream_frame.update_display()
            if hasattr(self, 'agent_summary_frame') and self.agent_summary_frame.winfo_exists(): self.agent_summary_frame.update_display()
            
            # Update the new chart frame
            if hasattr(self, 'system_metrics_chart_frame') and self.system_metrics_chart_frame.winfo_exists(): self.system_metrics_chart_frame.update_display()

        except _tkinter.TclError as e:
            # Log only if not expecting closure, to reduce noise during normal shutdown
            if not self._is_closing:
                gui_log(f"TclError in update_ui_elements: {e}", level="WARN")
            return # Stop further processing and rescheduling if TclError occurs

        if self.simulation_running and not self._is_closing: # Only reschedule if not closing
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
                # If GUI is closing, this is expected. Don't log an error, just print.
                if not self._is_closing:
                    gui_log(f"TclError in _append_insight: {e}", level="WARN")
                else:
                    print(f"TclError in _append_insight (GUI closing): {e}")

        if threading.current_thread() != threading.main_thread():
            self.after(0, _append_insight)
        else:
            _append_insight()

    def _simulation_loop(self):
        gui_log("SIMULATION THREAD STARTED...")
        last_processed_tick_in_loop = -1 # Tracks the tick number this loop has processed

        try:
            while not self.stop_simulation_event.is_set():
                if not self.context_manager or not self.context_manager.is_running():
                    time.sleep(0.1) # Wait if context manager isn't ready
                    continue

                current_tick_from_context = self.context_manager.get_tick()

                # Only run agent and mutation logic if the ContextManager's tick has advanced
                if current_tick_from_context > last_processed_tick_in_loop:
                    gui_log(f"Simulation loop: Processing for new tick {current_tick_from_context}", level="DEBUG")
                    
                    if self.meta_agent:
                        self.meta_agent.run_agents()

                    if self.context_manager and hasattr(self.context_manager, 'finalize_tick_processing'):
                        gui_log(f"Calling context_manager.finalize_tick_processing(tick={current_tick_from_context}) before mutation.", level="DEBUG")
                        self.context_manager.finalize_tick_processing(current_tick_from_context) 

                    if self.mutation_engine:
                        self.mutation_engine.run_assessment_and_mutation()

                    last_processed_tick_in_loop = current_tick_from_context # Update to the tick just processed
                else:
                    time.sleep(config.MAIN_LOOP_SLEEP if config.MAIN_LOOP_SLEEP > 0 else 0.001)
        except Exception as e:
            gui_log(f"Exception in simulation thread: {e}", level="ERROR", exc_info=True)
        finally:
            gui_log("Simulation thread: Loop exited. Beginning finalization...", level="INFO")
            
            if self.context_manager and self.context_manager.is_running():
                gui_log("Simulation thread: Requesting ContextManager stop.", level="INFO")
                self.context_manager.stop() 
                gui_log("Simulation thread: ContextManager stop request completed.", level="INFO")
            
            def _finalize_stop_ui():
                if self._is_closing or not self.winfo_exists():
                    gui_log("GUI is closing/destroyed, skipping _finalize_stop_ui's UI updates.", level="DEBUG")
                    self.simulation_running = False # Still update non-UI state
                    return

                gui_log("Simulation thread: Executing _finalize_stop_ui on main thread.", level="DEBUG")
                self.simulation_running = False
                self.update_button_states() # Guarded internally
                self.update_ui_elements()   # Guarded internally
            
            if not self._is_closing: # Only schedule if GUI is not already in the process of closing
                self.after(0, _finalize_stop_ui)
            else:
                self.simulation_running = False # Ensure state is updated
                gui_log("GUI already closing, _finalize_stop_ui not scheduled. Set simulation_running=False.", level="DEBUG")

            gui_log("Simulation thread: Finalization complete. Thread is now finishing.", level="INFO")
            
    def start_simulation(self):
        if not self.simulation_running:
            self.simulation_running = True
            if hasattr(self.stop_simulation_event, 'is_set') and self.stop_simulation_event.is_set():
                gui_log("Clearing stop_simulation_event before starting simulation.", level="DEBUG")
                self.stop_simulation_event.clear()
            elif not hasattr(self.stop_simulation_event, 'is_set'): 
                gui_log("stop_simulation_event not properly initialized!", level="ERROR")
                self.stop_simulation_event = threading.Event() 
            self.stop_simulation_event.clear()

            if self.context_manager and not self.context_manager.is_running():
                self.context_manager.start()
            elif not self.context_manager:
                 gui_log("Cannot start simulation: Context manager not initialized.", level="ERROR")
                 self.simulation_running = False 
                 self.after(0, lambda: self.update_button_states()) 
                 return

            self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.simulation_thread.name = "SimulationLoopThread"
            self.simulation_thread.start()

            self.after(0, lambda: self.update_button_states()) 
            self.update_ui_elements() 
            gui_log("Simulation started via GUI.")

    def stop_simulation(self):
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
        except Exception as e: # Catch any other unexpected errors
            gui_log(f"Unexpected error in update_button_states: {e}", level="ERROR", exc_info=True)

    def on_closing(self):
        if self._is_closing: # Prevent re-entry if already closing
            return
        self._is_closing = True # Set the flag immediately

        gui_log("GUI closing sequence started.")
        self.stop_simulation() 

        if self.simulation_thread and self.simulation_thread.is_alive():
            gui_log("Waiting for simulation thread to join...")
            join_timeout = config.TICK_INTERVAL * 4 if config.TICK_INTERVAL > 0 else 2.0 
            join_timeout = max(join_timeout, 2.0) # Ensure at least 2 seconds
            self.simulation_thread.join(timeout=join_timeout)
            if self.simulation_thread.is_alive():
                gui_log("Simulation thread did not join in time. It may be blocked.", level="WARN")
                # As a last resort, if the thread is stuck and context manager is running, try to stop it.
                # This is risky if the thread is holding locks or in a critical section.
                if self.context_manager and self.context_manager.is_running():
                    gui_log("Fallback: Forcing ContextManager stop as thread is unresponsive.", level="WARN")
                    self.context_manager.stop()
        else:
            if self.context_manager and self.context_manager.is_running():
                gui_log("GUI closing: Simulation thread not active, ensuring ContextManager is stopped.", level="INFO")
                self.context_manager.stop()

        if hasattr(self, 'gui_log_handler') and self.gui_log_handler:
            # Check if logger and handler still exist
            root_logger = logging.getLogger()
            if self.gui_log_handler in root_logger.handlers:
                root_logger.removeHandler(self.gui_log_handler)
            self.gui_log_handler = None

        gui_log("Destroying GUI window.") 
        self.destroy()

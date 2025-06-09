# File: /c:/Users/gilbe/Desktop/self-evolving-ai/gui.py

import customtkinter as ctk
import threading
import logging
import time
import _tkinter
from gui_agent_detail_view import AgentDetailWindow
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
    def __init__(self, context_manager, meta_agent, mutation_engine, knowledge_base, run_evolutionary_cycle_func):
        super().__init__()
        self._is_closing = False

        # Window setup
        self.title("Self-Evolving AI Monitor")
        self.geometry("900x780") # Reduced window size
        self.grid_rowconfigure(0, weight=0)

        # Store references to simulation components
        self.context_manager = context_manager
        self.meta_agent = meta_agent
        self.mutation_engine = mutation_engine
        self.knowledge_base = knowledge_base
        self.run_evolutionary_cycle_func = run_evolutionary_cycle_func # Store the passed function

        self.selected_agent_name = None
        self.simulation_thread = None
        self.simulation_running = False
        self.agent_detail_window = None # To store the reference to the detail window
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

        # --- Tab View Setup ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=current_row, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0,10))
        self.grid_rowconfigure(current_row, weight=1) # Make the tab view expandable

        self.tab_landing_page = self.tab_view.add("Landing Page")
        self.tab_system_metrics = self.tab_view.add("System Metrics")
        self.tab_knowledge_tools = self.tab_view.add("Knowledge Tools")

        # Configure grid for Landing Page tab (2 columns)
        self.tab_landing_page.grid_columnconfigure(0, weight=1)
        self.tab_landing_page.grid_columnconfigure(1, weight=1)
        # Configure 3 main rows for the 6 blocks
        self.tab_landing_page.grid_rowconfigure(0, weight=1) # Top row
        self.tab_landing_page.grid_rowconfigure(1, weight=1) # Middle row
        self.tab_landing_page.grid_rowconfigure(2, weight=1) # Bottom row
        
        # --- Populate Landing Page Tab ---
        
        # --- Block 1: Goal Submission & Info Labels (Top-Left) ---
        block1_frame = ctk.CTkFrame(self.tab_landing_page)
        block1_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        block1_frame.grid_columnconfigure(0, weight=1) # Allow content to expand
        
        b1_current_row = 0
        self.goal_section_frame = ctk.CTkFrame(block1_frame)
        self.goal_section_frame.grid(row=b1_current_row, column=0, pady=(5,5), padx=5, sticky="new")
        self.goal_section_frame.grid_columnconfigure(0, weight=1) 
        self.goal_section_frame.grid_columnconfigure(1, weight=0) 

        goal_frame_current_row = 0
        self.goal_input_label = ctk.CTkLabel(self.goal_section_frame, text="Submit Custom Goal:", font=("Arial", 14))
        self.goal_input_label.grid(row=goal_frame_current_row, column=0, columnspan=2, pady=(5,0), padx=5, sticky="w")
        goal_frame_current_row += 1
        self.goal_entry = ctk.CTkEntry(self.goal_section_frame, placeholder_text="Enter goal description...")
        self.goal_entry.grid(row=goal_frame_current_row, column=0, pady=5, padx=5, sticky="ew")
        self.send_goal_button = ctk.CTkButton(self.goal_section_frame, text="Send Goal", command=self.submit_custom_goal)
        self.send_goal_button.grid(row=goal_frame_current_row, column=1, pady=5, padx=5, sticky="ew")
        goal_frame_current_row += 1
        self.goal_status_label = ctk.CTkLabel(self.goal_section_frame, text="", font=("Arial", 12))
        self.goal_status_label.grid(row=goal_frame_current_row, column=0, columnspan=2, pady=(5,5), padx=5, sticky="w")
        b1_current_row +=1
        
        # Agent and system info labels
        info_labels_frame = ctk.CTkFrame(block1_frame, fg_color="transparent")
        info_labels_frame.grid(row=b1_current_row, column=0, pady=(5,0), padx=5, sticky="ew")
        info_labels_frame.grid_columnconfigure(0, weight=1)
        
        self.task_agents_label = ctk.CTkLabel(info_labels_frame, text="Task Agents: N/A", font=("Arial", 12))
        self.task_agents_label.grid(row=0, column=0, pady=1, padx=5, sticky="w")
        self.skill_agents_label = ctk.CTkLabel(info_labels_frame, text="Skill Agents: N/A", font=("Arial", 12))
        self.skill_agents_label.grid(row=1, column=0, pady=1, padx=5, sticky="w")
        self.avg_fitness_label = ctk.CTkLabel(info_labels_frame, text="Avg. Fitness: N/A", font=("Arial", 12))
        self.avg_fitness_label.grid(row=2, column=0, pady=1, padx=5, sticky="w")
        self.kb_size_label = ctk.CTkLabel(info_labels_frame, text="KB Size: N/A", font=("Arial", 12))
        self.kb_size_label.grid(row=3, column=0, pady=1, padx=5, sticky="w")
        block1_frame.grid_rowconfigure(b1_current_row, weight=0) # Info labels don't expand much
        b1_current_row +=1
        block1_frame.grid_rowconfigure(0, weight=0) # Goal section doesn't expand much

        # Import visualization frames
        from gui_visualizations import (AgentMapFrame, MemoryStreamFrame, KnowledgeInjectionFrame,
                                        KnowledgeQueryFrame, AgentSummaryFrame, SystemMetricsChartFrame)
        from gui_agent_detail_view import AgentDetailWindow # Import the new detail window

        # --- Block 2: Memory Stream (Top-Right) ---
        self.memory_stream_frame = MemoryStreamFrame(self.tab_landing_page, knowledge_base=self.knowledge_base, context_manager=self.context_manager)
        self.memory_stream_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # --- Block 3: Agent Summary (Mid-Left) ---
        self.agent_summary_frame = AgentSummaryFrame(self.tab_landing_page, meta_agent_ref=self.meta_agent, on_agent_select_callback=self.on_agent_select)
        self.agent_summary_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        # --- Block 4: Agent Map (Mid-Right) ---
        self.agent_map_frame = AgentMapFrame(self.tab_landing_page, meta_agent=self.meta_agent, on_agent_click_callback=self.show_agent_detail)
        self.agent_map_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        # --- Block 5: Feedback & Sim Controls (Bottom-Left) ---
        block5_frame = ctk.CTkFrame(self.tab_landing_page)
        block5_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")
        block5_frame.grid_columnconfigure(0, weight=1)
        block5_frame.grid_columnconfigure(1, weight=1)
        
        b5_current_row = 0
        # Feedback section
        self.feedback_label = ctk.CTkLabel(block5_frame, text="Feedback for Selected Agent:", font=("Arial", 14))
        self.feedback_label.grid(row=b5_current_row, column=0, columnspan=2, pady=(5,0), padx=5, sticky="w")
        b5_current_row += 1

        self.upvote_button = ctk.CTkButton(block5_frame, text="Upvote Selected", command=lambda: self.submit_feedback("upvote"))
        self.upvote_button.grid(row=b5_current_row, column=0, pady=5, padx=5, sticky="ew")

        self.downvote_button = ctk.CTkButton(block5_frame, text="Downvote Selected", command=lambda: self.submit_feedback("downvote"))
        self.downvote_button.grid(row=b5_current_row, column=1, pady=5, padx=5, sticky="ew")
        b5_current_row += 1

        self.feedback_status_label = ctk.CTkLabel(block5_frame, text="", font=("Arial", 12))
        self.feedback_status_label.grid(row=b5_current_row, column=0, columnspan=2, pady=(5,5), padx=5, sticky="w")
        b5_current_row += 1

        # Simulation control buttons
        self.start_button = ctk.CTkButton(block5_frame, text="Start Simulation", command=self.start_simulation)
        self.start_button.grid(row=b5_current_row, column=0, pady=(10,5), padx=5, sticky="ew")

        self.stop_button = ctk.CTkButton(block5_frame, text="Stop Simulation", command=self.stop_simulation, state="disabled")
        self.stop_button.grid(row=b5_current_row, column=1, pady=(10,5), padx=5, sticky="ew")
        b5_current_row += 1
        block5_frame.grid_rowconfigure(b5_current_row, weight=1) # Allow space below buttons to fill

        # --- Block 6: Log & Insights (Bottom-Right) ---
        block6_frame = ctk.CTkFrame(self.tab_landing_page)
        block6_frame.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")
        block6_frame.grid_columnconfigure(0, weight=1)
        block6_frame.grid_rowconfigure(1, weight=1) # Log textbox
        block6_frame.grid_rowconfigure(3, weight=1) # Insights textbox
        
        b6_current_row = 0
        # Log area
        self.log_textbox_label = ctk.CTkLabel(block6_frame, text="Simulation Log:", font=("Arial", 14))
        self.log_textbox_label.grid(row=b6_current_row, column=0, pady=(5,0), padx=5, sticky="w")
        b6_current_row += 1

        self.log_textbox = ctk.CTkTextbox(block6_frame, height=120, state="disabled") 
        self.log_textbox.grid(row=b6_current_row, column=0, pady=5, padx=5, sticky="nsew")
        b6_current_row += 1
        
        # System Insights and notifications
        self.insights_label = ctk.CTkLabel(block6_frame, text="System Insights & Notifications:", font=("Arial", 14))
        self.insights_label.grid(row=b6_current_row, column=0, pady=(5,0), padx=5, sticky="w")
        b6_current_row += 1

        self.insights_textbox = ctk.CTkTextbox(block6_frame, height=100, state="disabled") 
        self.insights_textbox.grid(row=b6_current_row, column=0, pady=5, padx=5, sticky="nsew")
        # --- End of Landing Page Tab ---

        # --- Populate System Metrics Tab ---
        self.tab_system_metrics.grid_rowconfigure(0, weight=1)
        self.tab_system_metrics.grid_columnconfigure(0, weight=1)
        self.system_metrics_chart_frame = SystemMetricsChartFrame(self.tab_system_metrics, context_manager=self.context_manager, mutation_engine=self.mutation_engine)
        self.system_metrics_chart_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # --- End of System Metrics Tab ---

        # --- Populate Knowledge Tools Tab ---
        self.tab_knowledge_tools.grid_columnconfigure(0, weight=1) # Allow frames to expand width
        self.tab_knowledge_tools.grid_columnconfigure(1, weight=1) # Add second column with equal weight
        self.tab_knowledge_tools.grid_rowconfigure(0, weight=1) # Allow vertical expansion for the frames

        # Knowledge injection section
        self.knowledge_injection_frame = KnowledgeInjectionFrame(self.tab_knowledge_tools,
                                                                 knowledge_base_ref=self.knowledge_base,
                                                                 context_manager_ref=self.context_manager,
                                                                 gui_logger_func=self.log_to_gui)
        self.knowledge_injection_frame.grid(row=0, column=0, pady=(10,5), padx=5, sticky="nsew")

        # Knowledge query section
        self.knowledge_query_frame = KnowledgeQueryFrame(self.tab_knowledge_tools,
                                                         knowledge_base_ref=self.knowledge_base,
                                                         gui_logger_func=self.log_to_gui)
        self.knowledge_query_frame.grid(row=0, column=1, pady=(10,5), padx=5, sticky="nsew")

        # --- Evolutionary Cycle Demo Frame (in Knowledge Tools Tab) ---
        self.evo_cycle_demo_frame = ctk.CTkFrame(self.tab_knowledge_tools)
        self.evo_cycle_demo_frame.grid(row=1, column=0, columnspan=2, pady=(10,5), padx=5, sticky="nsew")
        self.tab_knowledge_tools.grid_rowconfigure(1, weight=0) # This frame won't expand as much

        evo_current_row = 0
        ctk.CTkLabel(self.evo_cycle_demo_frame, text="Evolutionary Cycle Demo (CodeGenAgent):", font=("Arial", 14, "bold")).grid(row=evo_current_row, column=0, columnspan=2, pady=(5,0), padx=5, sticky="w")
        evo_current_row += 1

        ctk.CTkLabel(self.evo_cycle_demo_frame, text="Capability Description:").grid(row=evo_current_row, column=0, pady=2, padx=5, sticky="w")
        self.evo_desc_entry = ctk.CTkEntry(self.evo_cycle_demo_frame, placeholder_text="e.g., Create a Python function that sums a list.")
        self.evo_desc_entry.grid(row=evo_current_row, column=1, pady=2, padx=5, sticky="ew")
        evo_current_row += 1

        ctk.CTkLabel(self.evo_cycle_demo_frame, text="Capability Guidelines:").grid(row=evo_current_row, column=0, pady=2, padx=5, sticky="w")
        self.evo_guide_entry = ctk.CTkEntry(self.evo_cycle_demo_frame, placeholder_text="e.g., Name it 'calculate_sum_demo', include docstring.")
        self.evo_guide_entry.grid(row=evo_current_row, column=1, pady=2, padx=5, sticky="ew")
        evo_current_row += 1

        self.run_evo_cycle_button = ctk.CTkButton(self.evo_cycle_demo_frame, text="Run Evolutionary Cycle Demo", command=self.trigger_evolutionary_cycle_demo)
        self.run_evo_cycle_button.grid(row=evo_current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        evo_current_row += 1

        self.evo_cycle_status_label = ctk.CTkLabel(self.evo_cycle_demo_frame, text="", font=("Arial", 12))
        self.evo_cycle_status_label.grid(row=evo_current_row, column=0, columnspan=2, pady=5, padx=5, sticky="w")
        self.evo_cycle_demo_frame.grid_columnconfigure(1, weight=1) # Make entry fields expand
        # --- End of Knowledge Tools Tab ---

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

    def show_agent_detail(self, agent_name: str):
        """Shows a detailed view of the specified agent."""
        if not self.meta_agent:
            gui_log("Cannot show agent detail: MetaAgent not available.", level="WARN")
            return

        selected_agent = None
        # Iterate through the live list of agents from meta_agent
        for agent in self.meta_agent.agents: # Make sure this is the correct list of all agents
            if getattr(agent, 'name', None) == agent_name:
                selected_agent = agent
                break

        if not selected_agent:
            gui_log(f"Agent '{agent_name}' not found for detail view.", level="WARN")
            return

        if self.agent_detail_window is None or not self.agent_detail_window.winfo_exists():
            self.agent_detail_window = AgentDetailWindow(self, agent=selected_agent)
        else:
            self.agent_detail_window.update_details(selected_agent) # Update existing window
        self.agent_detail_window.deiconify() # Ensure it's visible if it was iconified
        self.agent_detail_window.lift()      # Bring to front

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

    def trigger_evolutionary_cycle_demo(self):
        """Triggers the evolutionary cycle demo from main_app.py via a GUI button."""
        desc = self.evo_desc_entry.get()
        guide = self.evo_guide_entry.get()

        if not desc or not guide:
            self.evo_cycle_status_label.configure(text="Error: Description and Guidelines are required.")
            self.log_to_gui("Evolutionary cycle demo trigger failed: Missing inputs.")
            return

        if not callable(self.run_evolutionary_cycle_func):
            self.evo_cycle_status_label.configure(text="Error: Evolutionary cycle function not available.")
            self.log_to_gui("Evolutionary cycle demo trigger failed: Function not callable.")
            return

        self.evo_cycle_status_label.configure(text="Running evolutionary cycle demo...")
        self.run_evo_cycle_button.configure(state="disabled")
        self.log_to_gui(f"Starting evolutionary cycle demo with Desc: '{desc}', Guide: '{guide}'")

        def _run_in_thread():
            try:
                # The run_evolutionary_cycle_func logs its own progress extensively
                # It now returns an outcome dictionary
                outcome = self.run_evolutionary_cycle_func(capability_description=desc, capability_guidelines=guide)
                
                status_message = outcome.get("message", "Evolutionary cycle demo completed. Check logs.")
                self.after(0, lambda: self.evo_cycle_status_label.configure(text=status_message))
                
                log_message = f"Evolutionary cycle demo thread finished. Success: {outcome.get('success', False)}. Message: {status_message}"
                self.log_to_gui(log_message)
            except Exception as e:
                self.after(0, lambda: self.evo_cycle_status_label.configure(text=f"Error running demo: {str(e)[:100]}..."))
                self.log_to_gui(f"Error in evolutionary cycle demo thread: {str(e)[:150]}...") # Log to GUI log as well
            finally:
                self.after(0, lambda: self.run_evo_cycle_button.configure(state="normal"))

        thread = threading.Thread(target=_run_in_thread, daemon=True)
        thread.start()

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

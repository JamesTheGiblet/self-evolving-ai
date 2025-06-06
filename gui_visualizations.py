# File: /c:/Users/gilbe/Desktop/self-evolving-ai/gui_visualizations.py

import customtkinter as ctk
from utils.logger import log
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque

class AgentMapFrame(ctk.CTkFrame):
    """
    Displays a real-time map/list of active agents.
    """
    def __init__(self, master, meta_agent, **kwargs):
        super().__init__(master, **kwargs)
        self.meta_agent = meta_agent
        self.grid_columnconfigure(0, weight=1)
        self.agent_widgets = {}

        # Title label
        self.label = ctk.CTkLabel(self, text="Active Agents Map:", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # Scrollable frame for agent list
        self.agent_list_frame = ctk.CTkScrollableFrame(self, height=150)
        self.agent_list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.grid_rowconfigure(1, weight=1)

    def update_display(self):
        """Updates the list of agents displayed."""
        if not self.meta_agent:
            return

        # Get current agents by name
        current_agents = {agent.name: agent for agent in self.meta_agent.agents}

        # Remove widgets for agents that are no longer active
        for agent_name in list(self.agent_widgets.keys()):
            if agent_name not in current_agents:
                self.agent_widgets[agent_name].destroy()
                del self.agent_widgets[agent_name]

        # Add or update widgets for current agents
        for agent_name, agent in current_agents.items():
            agent_name_val = getattr(agent, 'name', 'Unknown')
            agent_type_val = getattr(agent, 'agent_type', 'N/A')
            agent_gen_val = getattr(agent, 'generation', -1)
            agent_energy_val = getattr(agent, 'energy', 0.0)
            agent_status_val = agent.state.get('status', 'N/A') if hasattr(agent, 'state') and isinstance(agent.state, dict) else 'N/A'

            agent_display_text = (
                f"{agent_name_val} (Type: {agent_type_val}, Gen: {agent_gen_val}, "
                f"Energy: {agent_energy_val:.2f}, Status: {agent_status_val})"
            )

            if agent_name not in self.agent_widgets:
                widget = ctk.CTkLabel(self.agent_list_frame, text=agent_display_text, anchor="w")
                widget.pack(fill="x", pady=1)
                self.agent_widgets[agent_name] = widget
            else:
                self.agent_widgets[agent_name].configure(text=agent_display_text)

        self.agent_list_frame.update_idletasks()

class MemoryStreamFrame(ctk.CTkFrame):
    """
    Displays a real-time stream of recent memory/knowledge base events.
    """
    def __init__(self, master, knowledge_base, context_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base
        self.context_manager = context_manager
        self.grid_columnconfigure(0, weight=1)

        # Title label
        self.label = ctk.CTkLabel(self, text="Recent Knowledge Base Activity:", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # Filter section
        filter_row = 1
        self.filter_label = ctk.CTkLabel(self, text="Filter:", font=("Arial", 12, "bold"))
        self.filter_label.grid(row=filter_row, column=0, sticky="w", padx=5, pady=2)
        filter_row += 1

        # Category filter
        self.category_filter_label = ctk.CTkLabel(self, text="Category:")
        self.category_filter_label.grid(row=filter_row, column=0, sticky="w", padx=(10, 5), pady=0)
        self.category_filter_combobox = ctk.CTkComboBox(self, values=["any", "text", "visual", "audio", "code", "data_table", "other"], state="readonly")
        self.category_filter_combobox.set("any")
        self.category_filter_combobox.grid(row=filter_row, column=0, sticky="ew", padx=(80, 5), pady=2)
        filter_row += 1

        # Source filter
        self.source_filter_label = ctk.CTkLabel(self, text="Source:")
        self.source_filter_label.grid(row=filter_row, column=0, sticky="w", padx=(10, 5), pady=0)
        self.source_filter_entry = ctk.CTkEntry(self, placeholder_text="e.g., user_gui_injection")
        self.source_filter_entry.grid(row=filter_row, column=0, sticky="ew", padx=(80, 5), pady=2)
        filter_row += 1

        # Keyword filter
        self.keyword_filter_label = ctk.CTkLabel(self, text="Keywords:")
        self.keyword_filter_label.grid(row=filter_row, column=0, sticky="w", padx=(10, 5), pady=0)
        self.keyword_filter_entry = ctk.CTkEntry(self, placeholder_text="e.g., goal, error")
        self.keyword_filter_entry.grid(row=filter_row, column=0, sticky="ew", padx=(80, 5), pady=2)
        filter_row += 1

        # Scrollable frame for memory events
        self.memory_list_frame = ctk.CTkScrollableFrame(self, height=150)
        self.memory_list_frame.grid(row=filter_row, column=0, sticky="nsew", padx=5, pady=5)
        self.grid_rowconfigure(filter_row, weight=1)

        self.fact_widgets = {}
        self.display_limit = 20

    def update_display(self):
        """Fetches and displays recent knowledge base entries."""
        if not self.knowledge_base or not self.context_manager:
            return

        try:
            # Get filter values
            category_filter = self.category_filter_combobox.get()
            source_filter = self.source_filter_entry.get().strip()
            keyword_filter = self.keyword_filter_entry.get().strip()

            # Query recent facts from KB
            recent_facts = self.knowledge_base.get_recent_facts(
                limit=self.display_limit,
                category=category_filter if category_filter != "any" else None,
                source=source_filter if source_filter else None,
                keywords=keyword_filter if keyword_filter else None
            )

            # Clear previous widgets
            for widget in self.memory_list_frame.winfo_children():
                widget.destroy()
            self.fact_widgets.clear()

            # Display facts as buttons
            if recent_facts:
                for fact in recent_facts:
                    tick = fact.content.get('original_tick', 'N/A')
                    source = fact.source or 'N/A'
                    content_preview = fact.content.get('text_content', 'N/A')
                    display_text = f"[Tick {tick}] [Source: {source}] {content_preview[:100]}{'...' if len(content_preview) > 100 else ''}"

                    btn = ctk.CTkButton(self.memory_list_frame, text=display_text,
                                        command=lambda f=fact: self._show_fact_details(f),
                                        anchor="w")
                    btn.pack(fill="x", pady=1)
                    self.fact_widgets[fact.id] = btn
            else:
                # No activity label
                no_activity_label = ctk.CTkLabel(self.memory_list_frame, text="No recent knowledge base activity matching filters.", anchor="w")
                no_activity_label.pack(fill="x", pady=10)

            self.memory_list_frame.update_idletasks()

        except AttributeError:
            log(f"KnowledgeBase method 'get_recent_facts' not found.", level="ERROR")
        except Exception as e:
            log(f"Error updating MemoryStreamFrame: {e}", level="ERROR", exc_info=True)
            error_label = ctk.CTkLabel(self.memory_list_frame, text=f"Error displaying memory stream: {str(e)}", text_color="red", anchor="w")
            error_label.pack(fill="x", pady=10)
            self.memory_list_frame.update_idletasks()

    def _show_fact_details(self, fact):
        """Display full fact details when a fact button is clicked."""
        log(f"Clicked on Fact ID: {fact.id}. Full content: {fact.content}", level="INFO")

class KnowledgeInjectionFrame(ctk.CTkFrame):
    """
    Allows user to inject knowledge into the system.
    """
    def __init__(self, master, knowledge_base_ref, context_manager_ref, gui_logger_func, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base_ref
        self.context_manager = context_manager_ref
        self.gui_log = gui_logger_func

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        current_row = 0
        # Title label
        self.kb_inject_label = ctk.CTkLabel(self, text="Inject Knowledge into System:", font=("Arial", 14, "bold"))
        self.kb_inject_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=5, sticky="w")
        current_row += 1

        # Textbox for data to inject
        self.kb_inject_data_textbox = ctk.CTkTextbox(self, height=70)
        self.kb_inject_data_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        # Category and format labels
        self.kb_inject_category_label = ctk.CTkLabel(self, text="Category:")
        self.kb_inject_category_label.grid(row=current_row, column=0, pady=(0,0), padx=(5,0), sticky="w")
        self.kb_inject_format_label = ctk.CTkLabel(self, text="Format/MIME Type (optional):")
        self.kb_inject_format_label.grid(row=current_row, column=1, pady=(0,0), padx=(5,0), sticky="w")
        current_row += 1

        # Category and format entries
        self.kb_inject_category_entry = ctk.CTkComboBox(self, values=["text", "visual", "audio", "code", "data_table", "other"], state="readonly")
        self.kb_inject_category_entry.set("text")
        self.kb_inject_category_entry.grid(row=current_row, column=0, pady=(0,5), padx=5, sticky="ew")
        self.kb_inject_format_entry = ctk.CTkEntry(self, placeholder_text="e.g., image/jpeg")
        self.kb_inject_format_entry.grid(row=current_row, column=1, pady=(0,5), padx=5, sticky="ew")
        current_row += 1

        # Source and tags entries
        self.kb_inject_source_entry = ctk.CTkEntry(self, placeholder_text="Source (optional)")
        self.kb_inject_source_entry.grid(row=current_row, column=0, pady=(0,5), padx=5, sticky="ew")

        self.kb_inject_tags_entry = ctk.CTkEntry(self, placeholder_text="Tags (comma-separated, optional)")
        self.kb_inject_tags_entry.grid(row=current_row, column=1, pady=(0,5), padx=5, sticky="ew")
        current_row += 1

        # Inject button
        self.kb_inject_button = ctk.CTkButton(self, text="Inject Knowledge", command=self._inject_knowledge_item_internal)
        self.kb_inject_button.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        # Status label
        self.kb_inject_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.kb_inject_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="w")

    def _inject_knowledge_item_internal(self):
        """Injects a knowledge item into the knowledge base."""
        data_to_inject = self.kb_inject_data_textbox.get("1.0", "end-1c")
        source = self.kb_inject_source_entry.get()
        tags_str = self.kb_inject_tags_entry.get()
        category = self.kb_inject_category_entry.get()
        data_format = self.kb_inject_format_entry.get() or None

        if not data_to_inject:
            self.kb_inject_status_label.configure(text="Error: Data to inject cannot be empty.")
            self.gui_log("KB injection failed: Empty data.", level="WARN")
            return

        tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []

        # Inject into KB if possible
        if self.knowledge_base and hasattr(self.knowledge_base, 'add_user_fact'):
            try:
                current_tick = self.context_manager.get_tick() if self.context_manager else -1
                self.knowledge_base.add_user_fact(
                    content_str=data_to_inject,
                    source=source or "user_gui_injection",
                    tags=tags_list,
                    tick=current_tick,
                    category=category,
                    data_format=data_format
                )
                self.gui_log(f"User injected knowledge: '{data_to_inject[:50]}...' (Cat: {category}, Fmt: {data_format}, Src: {source}, Tags: {tags_list})")
                self.kb_inject_status_label.configure(text="Knowledge item injected successfully.")
                # Clear fields after successful injection
                self.kb_inject_data_textbox.delete("1.0", "end")
                self.kb_inject_source_entry.delete(0, "end")
                self.kb_inject_tags_entry.delete(0, "end")
                self.kb_inject_category_entry.set("text")
                self.kb_inject_format_entry.delete(0, "end")
            except Exception as e:
                self.gui_log(f"Error injecting knowledge: {e}", level="ERROR", exc_info=True)
                self.kb_inject_status_label.configure(text=f"Error injecting: {e}")
        else:
            self.kb_inject_status_label.configure(text="Error: KB not available or 'add_user_fact' missing.")
            self.gui_log("KB injection failed: KB not available or 'add_user_fact' method missing.", level="ERROR")

    def update_display(self):
        pass

class KnowledgeQueryFrame(ctk.CTkFrame):
    """
    Allows user to query the knowledge base.
    """
    def __init__(self, master, knowledge_base_ref, gui_logger_func, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base_ref
        self.gui_log = gui_logger_func

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        current_row = 0
        # Title label
        self.kb_query_label = ctk.CTkLabel(self, text="Query Knowledge Base:", font=("Arial", 14, "bold"))
        self.kb_query_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=5, sticky="w")
        current_row += 1

        # Category filter label
        self.kb_query_category_filter_label = ctk.CTkLabel(self, text="Filter by Category (optional):")
        self.kb_query_category_filter_label.grid(row=current_row, column=0, columnspan=2, pady=(0,0), padx=(5,0), sticky="w")
        current_row +=1

        # Query entry and category filter
        self.kb_query_entry = ctk.CTkEntry(self, placeholder_text="Enter query keywords or semantic query...")
        self.kb_query_entry.grid(row=current_row, column=0, pady=5, padx=5, sticky="ew")

        self.kb_query_category_filter_entry = ctk.CTkComboBox(self, values=["any", "text", "visual", "audio", "code", "data_table", "other"], state="readonly")
        self.kb_query_category_filter_entry.set("any")
        self.kb_query_category_filter_entry.grid(row=current_row, column=1, pady=5, padx=(0,5), sticky="ew")
        current_row += 1

        # Query button
        self.kb_query_button = ctk.CTkButton(self, text="Query KB", command=self._query_knowledge_base_internal)
        self.kb_query_button.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        # Results textbox
        self.kb_query_results_textbox = ctk.CTkTextbox(self, height=100, state="disabled", wrap="word")
        self.kb_query_results_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1)
        current_row += 1

        # Status label
        self.kb_query_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.kb_query_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="w")

    def _query_knowledge_base_internal(self):
        """Queries the knowledge base and displays results."""
        query_string = self.kb_query_entry.get()
        category_filter = self.kb_query_category_filter_entry.get()

        if not query_string:
            self.kb_query_status_label.configure(text="Error: Query cannot be empty.")
            self.gui_log("KB query failed: Empty query.", level="WARN")
            return

        query_params_for_kb = {"text_query": query_string}
        if category_filter and category_filter.lower() != "any":
            query_params_for_kb["category"] = category_filter

        self.kb_query_results_textbox.configure(state="normal")
        self.kb_query_results_textbox.delete("1.0", "end")

        # Query KB if possible
        if self.knowledge_base and hasattr(self.knowledge_base, 'query_user_facts'):
            try:
                results = self.knowledge_base.query_user_facts(query_params=query_params_for_kb)

                if results:
                    for idx, result_item in enumerate(results):
                        display_text = f"Result {idx+1}:\n"
                        display_text += f"  ID: {result_item.id}\n"
                        display_text += f"  Source: {result_item.source}\n"
                        display_text += f"  Certainty: {result_item.certainty:.2f}\n"
                        display_text += f"  Category: {result_item.content.get('category', 'N/A')}\n"
                        display_text += f"  Format: {result_item.content.get('format', 'N/A')}\n"
                        display_text += f"  Content: {result_item.content.get('text_content', 'N/A')}\n"
                        display_text += f"  Tags: {', '.join(result_item.content.get('tags', []))}\n"
                        display_text += f"  Original Tick: {result_item.content.get('original_tick', 'N/A')}\n\n"
                        self.kb_query_results_textbox.insert("end", display_text)
                    self.kb_query_status_label.configure(text=f"Found {len(results)} results.")
                else:
                    self.kb_query_results_textbox.insert("end", "No results found for your query.")
                    self.kb_query_status_label.configure(text="No results found.")
                self.gui_log(f"User queried KB with params: '{query_params_for_kb}'. Found {len(results) if results else 0} items.")
            except Exception as e:
                self.gui_log(f"Error querying KnowledgeBase: {e}", level="ERROR", exc_info=True)
                self.kb_query_results_textbox.insert("end", f"Error during query: {e}")
                self.kb_query_status_label.configure(text=f"Error during query: {e}")
        else:
            self.kb_query_results_textbox.insert("end", "KnowledgeBase not available or 'query_user_facts' method missing.")
            self.kb_query_status_label.configure(text="Error: KB not available or 'query_user_facts' method missing.")
            self.gui_log("KB query failed: KnowledgeBase not available or method missing.", level="ERROR")

        self.kb_query_results_textbox.configure(state="disabled")
        self.kb_query_results_textbox.see("end")

    def update_display(self):
        pass

class AgentSummaryFrame(ctk.CTkFrame):
    """
    Displays a summary of agents and allows selection for feedback.
    """
    def __init__(self, master, meta_agent_ref, on_agent_select_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.meta_agent = meta_agent_ref
        self.on_agent_select = on_agent_select_callback
        self.agent_buttons = {}

        self.grid_columnconfigure(0, weight=1)

        # Title label
        self.label = ctk.CTkLabel(self, text="Agent Summary (Click to select for feedback):", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, pady=(5,2), padx=5, sticky="w")

        # Scrollable frame for agent summary
        self.scrollable_frame = ctk.CTkScrollableFrame(self, height=150)
        self.scrollable_frame.grid(row=1, column=0, pady=(0,5), padx=5, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

    def update_display(self):
        if not self.meta_agent:
            return

        # Clear previous agent buttons
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.agent_buttons.clear()

        # Create a button for each agent
        for agent in self.meta_agent.agents:
            agent_name_val = getattr(agent, 'name', 'Unknown')
            agent_gen_val = getattr(agent, 'generation', -1)
            agent_behavior_mode_val = getattr(agent, 'behavior_mode', 'N/A')

            agent_display = f"{agent_name_val} (Gen: {agent_gen_val}, Mode: {agent_behavior_mode_val})"

            btn = ctk.CTkButton(self.scrollable_frame, text=agent_display,
                                command=lambda name=agent_name_val: self.on_agent_select(name))
            btn.pack(pady=2, padx=5, fill="x")
            self.agent_buttons[agent_name_val] = btn

        self.scrollable_frame.update_idletasks()

class SystemMetricsChartFrame(ctk.CTkFrame):
    """
    Displays system metrics using Matplotlib charts.
    """
    def __init__(self, master, context_manager, mutation_engine, **kwargs):
        super().__init__(master, **kwargs)
        self.context_manager = context_manager
        self.mutation_engine = mutation_engine

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title label
        self.label = ctk.CTkLabel(self, text="System Metrics:", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # History for plotting
        self.max_history = 50
        self.ticks_history = deque(maxlen=self.max_history)
        self.avg_fitness_history = deque(maxlen=self.max_history)

        # Matplotlib figure and axis
        self.fig, self.ax_fitness = plt.subplots(figsize=(5, 3), dpi=100)

        # Embed Matplotlib canvas in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Line for average fitness
        self.line_fitness, = self.ax_fitness.plot([], [], lw=2, label="Avg Fitness")
        self.ax_fitness.set_title("Average Agent Fitness")
        self.ax_fitness.set_xlabel("Tick")
        self.ax_fitness.set_ylabel("Avg. Fitness")
        self.ax_fitness.legend()
        self.fig.tight_layout()

    def update_display(self):
        """Updates the system metrics chart."""
        if not self.context_manager or not self.mutation_engine:
            return

        current_tick = self.context_manager.get_tick()

        # Calculate average fitness
        avg_fitness = 0.0
        if hasattr(self.mutation_engine, 'last_agent_fitness_scores') and self.mutation_engine.last_agent_fitness_scores:
            fitness_scores = list(self.mutation_engine.last_agent_fitness_scores.values())
            if fitness_scores:
                avg_fitness = sum(fitness_scores) / len(fitness_scores)

        # Update history
        self.ticks_history.append(current_tick)
        self.avg_fitness_history.append(avg_fitness)

        # Update plot data
        self.line_fitness.set_data(list(self.ticks_history), list(self.avg_fitness_history))

        # Adjust axes limits
        if self.ticks_history:
            self.ax_fitness.set_xlim(min(self.ticks_history), max(self.ticks_history) if len(self.ticks_history) > 1 else max(self.ticks_history) + 1)
        if self.avg_fitness_history:
            self.ax_fitness.set_ylim(min(self.avg_fitness_history) - 0.1, max(self.avg_fitness_history) + 0.1)
        else:
            self.ax_fitness.set_ylim(0, 1)

        try:
            self.canvas.draw_idle()
        except Exception as e:
            log(f"Error drawing chart canvas: {e}", level="ERROR", exc_info=True)

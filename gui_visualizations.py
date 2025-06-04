# c:\Users\gilbe\Desktop\self-evolving-ai\gui_visualizations.py

import customtkinter as ctk
from typing import Any, Dict, List, Optional
import threading
import time
from utils.logger import log # Use the system logger
# Assume access to core components like MetaAgent, KnowledgeBase, ContextManager

class AgentMapFrame(ctk.CTkFrame):
    """
    A CTkFrame to display a real-time map/list of active agents.
    """
    def __init__(self, master, meta_agent, **kwargs):
        super().__init__(master, **kwargs)
        self.meta_agent = meta_agent
        self.grid_columnconfigure(0, weight=1)
        self.agent_widgets = {} # To keep track of agent display widgets

        self.label = ctk.CTkLabel(self, text="Active Agents Map:", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.agent_list_frame = ctk.CTkScrollableFrame(self, height=150) # Scrollable list of agents
        self.agent_list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.grid_rowconfigure(1, weight=1) # Make the list frame expandable

    def update_display(self):
        """Updates the list of agents displayed."""
        if not self.meta_agent:
            return

        current_agents = {agent.name: agent for agent in self.meta_agent.agents}
        
        # Remove widgets for agents that are no longer active
        for agent_name in list(self.agent_widgets.keys()):
            if agent_name not in current_agents:
                self.agent_widgets[agent_name].destroy()
                del self.agent_widgets[agent_name]

        # Add/Update widgets for current agents
        for agent_name, agent in current_agents.items():
            agent_name_val = getattr(agent, 'name', 'Unknown')
            agent_type_val = getattr(agent, 'agent_type', 'N/A')
            agent_gen_val = getattr(agent, 'generation', -1)
            agent_energy_val = getattr(agent, 'energy', 0.0)
            # Accessing state safely, assuming agent.state is a dict
            agent_status_val = agent.state.get('status', 'N/A') if hasattr(agent, 'state') and isinstance(agent.state, dict) else 'N/A'

            agent_display_text = (
                f"{agent_name_val} (Type: {agent_type_val}, Gen: {agent_gen_val}, "
                f"Energy: {agent_energy_val:.2f}, Status: {agent_status_val})"
            )

            if agent_name not in self.agent_widgets:
                # Create new widget
                widget = ctk.CTkLabel(self.agent_list_frame, text=agent_display_text, anchor="w")
                widget.pack(fill="x", pady=1)
                self.agent_widgets[agent_name] = widget
            else:
                # Update existing widget
                self.agent_widgets[agent_name].configure(text=agent_display_text)

        # Ensure the scrollable frame updates its layout
        self.agent_list_frame.update_idletasks()


class MemoryStreamFrame(ctk.CTkFrame):
    """
    A CTkFrame to display a real-time stream of recent memory/knowledge base events.
    """
    def __init__(self, master, knowledge_base, context_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base
        self.context_manager = context_manager
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="Recent Knowledge Base Activity:", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.memory_textbox = ctk.CTkTextbox(self, height=150, state="disabled", wrap="word") # Wrap long lines
        self.memory_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.grid_rowconfigure(1, weight=1) # Make the textbox expandable

        self.last_update_tick = -1
        self.display_limit = 20 # How many recent items to display

    def update_display(self):
        """Fetches and displays recent knowledge base entries."""
        if not self.knowledge_base or not self.context_manager:
            return

        current_tick = self.context_manager.get_tick()
        # Only update if the tick has advanced since the last update
        # This prevents excessive querying if the GUI update rate is faster than ticks
        if current_tick <= self.last_update_tick:
             return

        try:
            # Need a method in KnowledgeBase to get recent facts.
            # Let's assume knowledge_base.get_recent_facts(limit) exists.
            # If not, we'll need to add it.
            recent_facts = self.knowledge_base.get_recent_facts(limit=self.display_limit)

            self.memory_textbox.configure(state="normal")
            self.memory_textbox.delete("1.0", "end")

            if recent_facts:
                # Sort by tick/timestamp if not already sorted by get_recent_facts
                # Assuming Fact objects have 'content' (dict) and 'id' attributes
                # and content has 'original_tick' and 'text_content'
                sorted_facts = sorted(recent_facts, key=lambda f: f.content.get('original_tick', 0), reverse=True)

                for fact in sorted_facts:
                    tick = fact.content.get('original_tick', 'N/A')
                    source = fact.source or 'N/A'
                    content_preview = fact.content.get('text_content', 'N/A')
                    # Truncate content preview for readability
                    if len(content_preview) > 100:
                        content_preview = content_preview[:97] + "..."

                    display_text = f"[Tick {tick}] [Source: {source}] {content_preview}\n"
                    self.memory_textbox.insert("end", display_text)
                
                # Add a separator or summary if needed
                if len(recent_facts) >= self.display_limit:
                     self.memory_textbox.insert("end", f"\n--- Displaying last {self.display_limit} items ---\n")

            else:
                self.memory_textbox.insert("end", "No recent knowledge base activity.")

            self.memory_textbox.configure(state="disabled")
            self.memory_textbox.see("end") # Scroll to the end

            self.last_update_tick = current_tick # Update the last processed tick

        except AttributeError:
             # Handle case where knowledge_base.get_recent_facts doesn't exist yet
             self.memory_textbox.configure(state="normal")
             self.memory_textbox.delete("1.0", "end")
             self.memory_textbox.insert("end", "KnowledgeBase method 'get_recent_facts' not found. Cannot display memory stream.")
             self.memory_textbox.configure(state="disabled")
        except Exception as e:
            log(f"Error updating MemoryStreamFrame: {e}", level="ERROR", exc_info=True)
            self.memory_textbox.configure(state="normal")
            self.memory_textbox.insert("end", f"Error displaying memory stream: {str(e)}")
            self.memory_textbox.configure(state="disabled")


# Note: You will need to add a get_recent_facts method to your KnowledgeBase class.
# Example implementation in KnowledgeBase (memory/knowledge_base.py):
#
# class KnowledgeBase:
#     # ... existing methods ...
#
#     def get_recent_facts(self, limit: int = 10) -> List[Fact]:
#         """Retrieves the most recent facts added to the knowledge base."""
#         # Assuming self.facts is a list of Fact objects
#         # You might need a more sophisticated way to track 'recent' if facts are modified/deleted
#         # For simplicity, let's assume facts are appended and we sort by original_tick
#         if not self.facts:
#             return []
#         
#         # Sort by original_tick descending and take the top 'limit'
#         # Ensure 'original_tick' exists in fact.content
#         sorted_facts = sorted(self.facts, key=lambda f: f.content.get('original_tick', 0), reverse=True)
#         return sorted_facts[:limit]
#

class KnowledgeInjectionFrame(ctk.CTkFrame):
    def __init__(self, master, knowledge_base_ref, context_manager_ref, gui_logger_func, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base_ref
        self.context_manager = context_manager_ref
        self.gui_log = gui_logger_func

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        current_row = 0
        self.kb_inject_label = ctk.CTkLabel(self, text="Inject Knowledge into System:", font=("Arial", 14, "bold"))
        self.kb_inject_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=5, sticky="w")
        current_row += 1

        self.kb_inject_data_textbox = ctk.CTkTextbox(self, height=70)
        self.kb_inject_data_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        self.kb_inject_category_label = ctk.CTkLabel(self, text="Category:")
        self.kb_inject_category_label.grid(row=current_row, column=0, pady=(0,0), padx=(5,0), sticky="w")
        self.kb_inject_format_label = ctk.CTkLabel(self, text="Format/MIME Type (optional):")
        self.kb_inject_format_label.grid(row=current_row, column=1, pady=(0,0), padx=(5,0), sticky="w")
        current_row += 1

        self.kb_inject_category_entry = ctk.CTkComboBox(self, values=["text", "visual", "audio", "code", "data_table", "other"], state="readonly")
        self.kb_inject_category_entry.set("text")
        self.kb_inject_category_entry.grid(row=current_row, column=0, pady=(0,5), padx=5, sticky="ew")
        self.kb_inject_format_entry = ctk.CTkEntry(self, placeholder_text="e.g., image/jpeg")
        self.kb_inject_format_entry.grid(row=current_row, column=1, pady=(0,5), padx=5, sticky="ew")
        current_row += 1

        self.kb_inject_source_entry = ctk.CTkEntry(self, placeholder_text="Source (optional)")
        self.kb_inject_source_entry.grid(row=current_row, column=0, pady=(0,5), padx=5, sticky="ew")

        self.kb_inject_tags_entry = ctk.CTkEntry(self, placeholder_text="Tags (comma-separated, optional)")
        self.kb_inject_tags_entry.grid(row=current_row, column=1, pady=(0,5), padx=5, sticky="ew")
        current_row += 1

        self.kb_inject_button = ctk.CTkButton(self, text="Inject Knowledge", command=self._inject_knowledge_item_internal)
        self.kb_inject_button.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        self.kb_inject_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.kb_inject_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="w")

    def _inject_knowledge_item_internal(self):
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

    def update_display(self): # Placeholder if needed for dynamic updates to this frame
        pass

class KnowledgeQueryFrame(ctk.CTkFrame):
    def __init__(self, master, knowledge_base_ref, gui_logger_func, **kwargs):
        super().__init__(master, **kwargs)
        self.knowledge_base = knowledge_base_ref
        self.gui_log = gui_logger_func

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0) 

        current_row = 0
        self.kb_query_label = ctk.CTkLabel(self, text="Query Knowledge Base:", font=("Arial", 14, "bold"))
        self.kb_query_label.grid(row=current_row, column=0, columnspan=2, pady=(10,0), padx=5, sticky="w")
        current_row += 1
        
        self.kb_query_category_filter_label = ctk.CTkLabel(self, text="Filter by Category (optional):")
        self.kb_query_category_filter_label.grid(row=current_row, column=0, columnspan=2, pady=(0,0), padx=(5,0), sticky="w")
        current_row +=1

        self.kb_query_entry = ctk.CTkEntry(self, placeholder_text="Enter query keywords or semantic query...")
        self.kb_query_entry.grid(row=current_row, column=0, pady=5, padx=5, sticky="ew")

        self.kb_query_category_filter_entry = ctk.CTkComboBox(self, values=["any", "text", "visual", "audio", "code", "data_table", "other"], state="readonly")
        self.kb_query_category_filter_entry.set("any")
        self.kb_query_category_filter_entry.grid(row=current_row, column=1, pady=5, padx=(0,5), sticky="ew")
        current_row += 1

        self.kb_query_button = ctk.CTkButton(self, text="Query KB", command=self._query_knowledge_base_internal)
        self.kb_query_button.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="ew")
        current_row += 1

        self.kb_query_results_textbox = ctk.CTkTextbox(self, height=100, state="disabled", wrap="word")
        self.kb_query_results_textbox.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="nsew")
        self.grid_rowconfigure(current_row, weight=1)
        current_row += 1

        self.kb_query_status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.kb_query_status_label.grid(row=current_row, column=0, columnspan=2, pady=5, padx=5, sticky="w")

    def _query_knowledge_base_internal(self):
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

    def update_display(self): # Placeholder
        pass

class AgentSummaryFrame(ctk.CTkFrame):
    def __init__(self, master, meta_agent_ref, on_agent_select_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.meta_agent = meta_agent_ref
        self.on_agent_select = on_agent_select_callback # Callback from main GUI
        self.agent_buttons = {}

        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="Agent Summary (Click to select for feedback):", font=("Arial", 14, "bold"))
        self.label.grid(row=0, column=0, pady=(5,2), padx=5, sticky="w")

        self.scrollable_frame = ctk.CTkScrollableFrame(self, height=150)
        self.scrollable_frame.grid(row=1, column=0, pady=(0,5), padx=5, sticky="nsew")
        self.grid_rowconfigure(1, weight=1) # Make the scrollable frame expandable

    def update_display(self):
        if not self.meta_agent:
            return

        # Clear existing buttons
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.agent_buttons.clear()

        # Add buttons for current agents
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
#

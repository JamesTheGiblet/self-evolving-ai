# File: /c:/Users/gilbe/Desktop/self-evolving-ai/gui_agent_detail_view.py
import customtkinter as ctk
import json

class AgentDetailWindow(ctk.CTkToplevel):
    """
    A Toplevel window to display detailed information about a selected agent.
    """
    def __init__(self, master, agent, **kwargs):
        super().__init__(master, **kwargs)
        self.agent = agent

        self.title(f"Agent Details: {getattr(self.agent, 'name', 'N/A')}")
        self.geometry("600x700")
        self.attributes("-topmost", True) # Keep window on top

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1) # For state textbox
        self.grid_rowconfigure(6, weight=1) # For q_table textbox
        self.grid_rowconfigure(8, weight=1) # For memory textbox

        current_row = 0

        # Basic Info Frame
        basic_info_frame = ctk.CTkFrame(self)
        basic_info_frame.grid(row=current_row, column=0, padx=10, pady=5, sticky="ew")
        basic_info_frame.grid_columnconfigure(1, weight=1)
        current_row += 1

        ctk.CTkLabel(basic_info_frame, text="Name:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.name_label = ctk.CTkLabel(basic_info_frame, text=getattr(self.agent, 'name', 'N/A'), anchor="w")
        self.name_label.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(basic_info_frame, text="ID:", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.id_label = ctk.CTkLabel(basic_info_frame, text=getattr(self.agent, 'agent_id', 'N/A'), anchor="w")
        self.id_label.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(basic_info_frame, text="Type:", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.type_label = ctk.CTkLabel(basic_info_frame, text=getattr(self.agent, 'agent_type', 'N/A'), anchor="w")
        self.type_label.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(basic_info_frame, text="Generation:", font=("Arial", 12, "bold")).grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.gen_label = ctk.CTkLabel(basic_info_frame, text=str(getattr(self.agent, 'generation', 'N/A')), anchor="w")
        self.gen_label.grid(row=3, column=1, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(basic_info_frame, text="Energy:", font=("Arial", 12, "bold")).grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.energy_label = ctk.CTkLabel(basic_info_frame, text=f"{getattr(self.agent, 'energy', 0.0):.2f}", anchor="w")
        self.energy_label.grid(row=4, column=1, padx=5, pady=2, sticky="ew")

        ctk.CTkLabel(basic_info_frame, text="Capabilities:", font=("Arial", 12, "bold")).grid(row=5, column=0, padx=5, pady=2, sticky="w")
        capabilities_str = ", ".join(getattr(self.agent, 'capabilities', []))
        self.capabilities_label = ctk.CTkLabel(basic_info_frame, text=capabilities_str if capabilities_str else "N/A", anchor="w", wraplength=550)
        self.capabilities_label.grid(row=5, column=1, padx=5, pady=2, sticky="ew")

        # Agent State
        ctk.CTkLabel(self, text="Current State:", font=("Arial", 12, "bold")).grid(row=current_row, column=0, padx=10, pady=(10,0), sticky="w")
        current_row += 1
        self.state_textbox = ctk.CTkTextbox(self, height=150, wrap="word")
        self.state_textbox.grid(row=current_row, column=0, padx=10, pady=5, sticky="nsew")
        current_row += 1

        # Q-Table (if exists)
        ctk.CTkLabel(self, text="Q-Table / Policy Data:", font=("Arial", 12, "bold")).grid(row=current_row, column=0, padx=10, pady=(10,0), sticky="w")
        current_row += 1
        self.q_table_textbox = ctk.CTkTextbox(self, height=150, wrap="word")
        self.q_table_textbox.grid(row=current_row, column=0, padx=10, pady=5, sticky="nsew")
        current_row += 1

        # Memory Summary (placeholder)
        ctk.CTkLabel(self, text="Memory Summary:", font=("Arial", 12, "bold")).grid(row=current_row, column=0, padx=10, pady=(10,0), sticky="w")
        current_row += 1
        self.memory_textbox = ctk.CTkTextbox(self, height=100, wrap="word")
        self.memory_textbox.grid(row=current_row, column=0, padx=10, pady=5, sticky="nsew")
        current_row += 1

        self.update_details(self.agent) # Initial population

    def update_details(self, agent):
        self.agent = agent
        self.title(f"Agent Details: {getattr(self.agent, 'name', 'N/A')}")

        self.name_label.configure(text=getattr(self.agent, 'name', 'N/A'))
        self.id_label.configure(text=getattr(self.agent, 'agent_id', 'N/A'))
        self.type_label.configure(text=getattr(self.agent, 'agent_type', 'N/A'))
        self.gen_label.configure(text=str(getattr(self.agent, 'generation', 'N/A')))
        self.energy_label.configure(text=f"{getattr(self.agent, 'energy', 0.0):.2f}")
        capabilities_str = ", ".join(getattr(self.agent, 'capabilities', []))
        self.capabilities_label.configure(text=capabilities_str if capabilities_str else "N/A")

        # State
        agent_state = getattr(self.agent, 'state', {})
        self.state_textbox.configure(state="normal")
        self.state_textbox.delete("1.0", "end")
        self.state_textbox.insert("1.0", json.dumps(agent_state, indent=2) if agent_state else "No state data.")
        self.state_textbox.configure(state="disabled")

        # Q-Table / Policy
        q_table_data = getattr(self.agent, 'q_table', getattr(self.agent, 'policy_data', {})) # Check for q_table or policy_data
        self.q_table_textbox.configure(state="normal")
        self.q_table_textbox.delete("1.0", "end")
        self.q_table_textbox.insert("1.0", json.dumps(q_table_data, indent=2) if q_table_data else "No Q-Table/Policy data.")
        self.q_table_textbox.configure(state="disabled")

        # Memory Summary (Placeholder - replace with actual agent memory access)
        memory_summary = "Memory summary not yet implemented for this agent."
        if hasattr(self.agent, 'get_memory_summary') and callable(getattr(self.agent, 'get_memory_summary')):
            memory_summary = self.agent.get_memory_summary()

        self.memory_textbox.configure(state="normal")
        self.memory_textbox.delete("1.0", "end")
        self.memory_textbox.insert("1.0", memory_summary)
        self.memory_textbox.configure(state="disabled")

        self.lift() # Bring window to front
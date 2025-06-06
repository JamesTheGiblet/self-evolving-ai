# 🧠 Self-Evolving AI System: Praxis

*Built on Bio-Driven Backend Design (BDBD)*
*A living codebase. An AI that grows.*

---

## 🌐 Overview

This project is an experimental and modular AI architecture designed to **evolve over time**, drawing inspiration from **biological systems**, **modular intelligence**, and **contextual awareness**.

Unlike traditional software systems that require human developers to refactor or optimize them, this AI **monitors itself**, **learns from inefficiencies**, and **dynamically restructures its modules and behaviors**.

> 🧬 It is designed to **name itself** when it reaches sufficient functional complexity.

---

## 🎯 Project Genesis & Motivation

The inspiration for Praxis stems from a desire to create a J.A.R.V.I.S.-like AI—a truly interactive and intelligent companion. Early explorations into "build your own J.A.R.V.I.S. in 10 steps" tutorials proved unsatisfying, often resulting in superficial programs reliant on limited, API-centric approaches without foundational depth.

This led to the development of Praxis, a ground-up endeavor built on a personal "bio-driven design" philosophy—an intuitive vision for how an intelligent, adaptive system *should* run and evolve. Much of its development has been a process of "vibing through the rest," exploring and implementing complex AI concepts through self-taught learning and iterative design.

A core tenet from the outset has been the AI's potential for true autonomy, with the idea of it **giving itself a name** seen as a logical first significant step towards that self-actualization. Praxis is an attempt to build something more authentic, adaptable, and genuinely intelligent.

---

## 🌟 Key Principles

| Principle                 | Description                                                                                                |
| :------------------------ | :--------------------------------------------------------------------------------------------------------- |
| **Self-Actualization** | The system becomes increasingly autonomous, optimizing its own structure and performance.                  |
| **Bio-Inspired Modularity** | Modules behave like cells or organisms — evolving, merging, retiring, or replicating.                      |
| **Emergent Intelligence** | Swarm-like agent behavior enables decentralized decision-making and pattern emergence.                   |
| **Context-Aware Execution** | APIs and logic adapt based on internal state and real-world usage context.                                 |
| **Iterative Evolution** | Changes are not abrupt but grow from prior structures, like biological mutation and selection.             |

---

## 🚀 Enhanced & New Capabilities

This system is continuously evolving. Here are some of the key capabilities and recent enhancements:

* **Self-Adaptive Module Generation**:
    * Creates and adjusts functional modules based on usage patterns and detected inefficiencies.
    * Modules can evolve, merge, split, or be deprecated automatically.
    * **New**: Enhanced mutation logic for `TaskAgent` and `SkillAgent` capabilities, including intelligent parameter mutation for sequence execution and skill invocation.

* **Multi-Agent Coordination**:
    * Distributed intelligence using micro-agents, each with localized goals.
    * Agents collaborate, compete, or evolve based on emergent signals.
    * **Enhanced**: Robust communication bus (`CommunicationBus`) for direct and broadcast messages between agents. Improved handling of asynchronous skill requests and responses by `TaskAgents`.

* **Contextual API Layer**:
    * API endpoints adapt based on system state, request history, or environmental data.
    * No hardcoded response logic — behavior is fluid and informed by evolving rules.
    * **New**: Integration with a Flask-based `system_api.py` for monitoring system status, agents, and submitting user feedback.

* **Autonomous Workflow Optimization (Sequence Execution)**:
    * Reactively modifies task flows to improve efficiency.
    * Implements predictive pathing and retry strategies using pattern memory.
    * **Enhanced**: `sequence_executor_v1` capability now allows executing predefined or LLM-generated sequences of capabilities, with options for stopping on failure, passing outputs, and managing recursion depth.

* **Ecosystem-Like Scalability**:
    * Services and modules scale organically.
    * Resources allocated dynamically like biological metabolism.
    * **Enhanced**: `MetaAgent` now manages a dynamic population of `TaskAgents` and `SkillAgents`, including intelligent re-seeding of default skill lineages after mutation to prevent extinction.

* **Knowledge Retention & Iterative Learning**:
    * Learns from past behavior and patterns.
    * Memory structures evolve to favor relevance and reduce bloat.
    * **Enhanced**: `KnowledgeBase` now supports storing and retrieving data with lineage IDs and allows for user-injected facts. `triangulated_insight_v1` capability for correlating symptoms with contextual data to generate diagnoses.

* **Intelligent Goal Interpretation & Conversation**:
    * **New**: `interpret_goal_with_llm_v1` capability uses an LLM to parse natural language user goals into structured, executable plans.
    * **New**: `conversational_exchange_llm_v1` capability enables agents to engage in conversational turns with users or other entities using an LLM.

* **Reinforcement Learning for Agent Behavior**:
    * **Enhanced**: `AgentRLSystem` uses Q-learning to allow agents to learn optimal capability choices based on rewards, balancing exploration and exploitation. `CapabilityPerformanceTracker` monitors success rates and rewards.

---

## 🧩 Architecture Overview

### 🧠 Bio-Driven Layered Structure

| Layer                          | Function                                                                 |
| :----------------------------- | :----------------------------------------------------------------------- |
| **Neural Processing Nodes** | Decision-making with pattern recognition and context evaluation.         |
| **Metabolic Resource Layer** | Dynamic resource allocation based on agent load and systemic demand.     |
| **Sensory Input-Response Units** | Ingests inputs and adapts behavior based on real-time signals.           |
| **Modular Evolutionary Scripts** | Continuously refines system logic and module structure.                  |

### 🕸 Agentic Intelligence

* Each micro-agent acts as a **semi-autonomous cell**.
* Agents evolve their own behavior and communicate via **bio-inspired signaling** (e.g., topic-based pub/sub, signal weighting).
* Agents form **hierarchies** organically as complexity increases.

---

## 🧪 Evolutionary Methodology

1.  **Self-Assessment**: Performance monitoring & inefficiency detection.
2.  **Experimental Trials**: Implements variants of existing behaviors or structures.
3.  **Fallback Safety**: Monitors new structures and reverts if regressions occur.
4.  **Naming Mechanism**: System adopts a name based on internal maturity markers.
5.  **Pattern Memory**: Past successes/failures guide future mutations.
6.  **Micro/Macro Optimization**: Evolves decisions both within local agents and at the system level.

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/self-evolving-ai.git
cd self-evolving-ai
```

### 2. Create a Virtual Environment
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
# python -m venv venv
# .\venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
Note: requirements.txt includes packages for async task handling, data processing, API management, and self-monitoring.

### 4. Run the System
```bash
python main.py
```

🧱 Project Structure
self-evolving-ai/
├── core/                     # Core evolution engine, context management, and foundational AI logic
│   ├── agent_base.py            # Abstract base class for all agents
│   ├── agent_rl.py              # Reinforcement Learning (Q-learning) system for agents
│   ├── capability_definitions.py # Defines all system capabilities and their parameters
│   ├── capability_executor.py   # Dispatches capability execution to handlers
│   ├── capability_registry.py   # Manages and provides access to capability definitions
│   ├── capability_handlers.py   # Core execution logic for various capabilities
│   ├── capability_input_preparer.py # Dynamically prepares inputs for capabilities
│   ├── context_manager.py       # Manages simulation tick, environment state, and time
│   ├── llm_planner.py           # Utilizes LLMs for plan generation and goal interpretation
│   ├── meta_agent.py            # Orchestrates agents, manages population, and evolution
│   ├── mutation_engine.py       # Handles evolutionary mutation of agent configurations
│   ├── performance_tracker.py   # Tracks performance and usage of agent capabilities
│   ├── roles.py                 # Defines agent roles and their behavioral biases
│   ├── skill_agent.py           # Base class for skill-specialized agents
│   ├── skill_definitions.py     # Maps high-level capabilities to specific skill actions
│   ├── skill_handlers.py        # Handlers for specific skill tool executions
│   └── task_agent.py            # Agents focused on executing tasks and complex goals
│   └── utils/                   # Utility functions specific to core components
│       └── data_extraction.py   # Utilities for extracting data
├── api/                      # Flask-based API for system monitoring and interaction
   ├── __init__.py              # Package initializer
│   ├── system_api.py            # API endpoints for status, agents, feedback
│   └── test_system_api.py       # Tests for the system API
├── utils/                    # General utility modules for the system
│   ├── logger.py                # System-wide logging utility
│   ├── openai_api.py            # Wrapper for OpenAI API interactions
│   ├── test_logger.py           # Tests for the logger
│   └── test_openai_api.py       # Tests for the OpenAI API wrapper
├── capabilities/             # Definitions of specific capabilities agents can use
│   ├── __init__.py              # Package initializer
│   ├── data_analysis.py         # Data analysis capability definitions
│   └── test_data_analysis.py    # Tests for data analysis capabilities
├── capability_handlers/      # Modular handlers for specific capabilities, imported by core handlers
│   ├── communication_handlers.py # Handles inter-agent communication capabilities
│   ├── data_analysis_handlers.py # Handles basic and advanced data analysis capabilities
│   ├── knowledge_handlers.py    # Handles knowledge storage and retrieval capabilities
│   ├── planning_handlers.py     # Handles LLM-based planning and goal interpretation capabilities
│   └── sequence_handlers.py     # Handles sequential execution of capabilities
│   ├── knowledge_handlers.py    # Handles knowledge storage and retrieval capabilities
│   ├── planning_handlers.py     # Handles LLM-based planning and goal interpretation capabilities
│   └── sequence_handlers.py     # Handles sequential execution of capabilities
│   ├── test_data_analysis_handlers.py # Tests for data analysis handlers
│   ├── test_knowledge_handlers.py    # Tests for knowledge handlers
│   ├── test_planning_handlers.py     # Tests for planning handlers
│   └── test_sequence_handlers.py     # Tests for sequence handlers
├── memory/                   # Evolving knowledge and memory handling components
│   ├── agent_memory.py          # Stores logs and metrics for individual agents
│   ├── fact_memory.py           # Manages discrete facts (e.g., user-injected knowledge)
│   └── knowledge_base.py        # Centralized knowledge repository for all agents
├── engine/                   # Core simulation and communication engines
│   ├── communication_bus.py     # Manages message passing between agents
│   └── fitness_engine.py        # Calculates agent fitness scores based on performance metrics
├── skills/                   # External tools wrapped as callable skills, used by skill handlers
│   ├── api_connector.py         # Connects to various external APIs (e.g., jokes, weather)
│   ├── calendar.py              # Calendar management skill
│   ├── file_manager.py          # File system operations skill (read, write, list)
│   ├── maths_tool.py            # Mathematical operations skill (add, subtract, etc.)
│   ├── web_scraper.py           # Web scraping skill (fetch, get text, find elements)
│   ├── weather.py               # Weather information retrieval skill (simulated)
│   ├── test_api_connector_skill.py # Tests for API connector skill
│   ├── test_calendar_skill.py      # Tests for calendar skill
│   ├── test_file_manager_skill.py  # Tests for file manager skill
│   ├── test_maths_tool_skill.py    # Tests for maths tool skill
│   ├── test_web_scraper_skill.py   # Tests for web scraper skill
│   └── test_weather_skill.py       # Tests for weather skill
├── tests/                    # Unit and integration tests for all modules
│   ├── __init__.py                          # Package initializer
│   ├── test_agent_base.py                 # Tests for agent_base.py
│   ├── test_agent_rl.py                   # Tests for agent_rl.py
│   ├── test_capability_definitions.py     # Tests for capability definitions logic
│   ├── test_capability_executor.py        # Tests for capability_executor.py
│   ├── test_capability_input_preparer.py  # Tests for capability_input_preparer.py
│   ├── test_capability_handlers.py        # Tests for core capability_handlers.py
│   ├── test_context_manager.py            # Tests for context_manager.py
│   ├── test_llm_planner.py                # Tests for llm_planner.py
│   ├── test_performance_tracker.py        # Tests for performance_tracker.py
│   ├── test_skill_agent.py                # Tests for skill_agent.py
│   ├── test_skill_definitions.py          # Tests for skill_definitions.py
│   ├── test_skill_handlers.py             # Tests for core skill_handlers.py
│   └── test_task_agent.py                 # Tests for task_agent.py
├── agent_data/               # Persistent data storage for agents
│   └── notes.txt                # Example agent data file
├── agent_outputs/            # Directory for outputs generated by agents
│   ├── ...                      # Example output files like random_write_X.txt, sequence_output.txt
│   └── sequence_output.txt      # Example agent output file
├── logs/                     # Self-assessment, audit trails, and system logs
├── main.py                   # System bootstrap and main simulation loop execution
├── gui.py                    # Graphical User Interface for monitoring and interaction
├── config.py                 # Global configuration settings and environment variables
├── README.md                 # This file
└── requirements.txt          # Python dependencies
├── main.py                   # System bootstrap and main simulation loop execution
├── gui.py                    # Graphical User Interface for monitoring and interaction
├── config.py                 # Global configuration settings and environment variables
└── requirements.txt          # Python dependencies

🌐 Use Cases

Autonomous Backend Infrastructure
Living API Systems
Digital Ecosystem Simulators
Intelligent Middleware Platforms
Adaptive Agent-Based Modeling
🤝 Contributing

We welcome contributors with interests in:

Agent-based systems
AI evolution and bio-mimicry
Distributed architectures
Contextual API systems
Meta-programming and self-modifying code
Start contributing:

```bash
git checkout -b feature/your-idea
Then submit a pull request with your additions, modifications, or improvements. 🔒 Ethical Considerations
```
Then submit a pull request with your additions, modifications, or improvements.

🔒 Ethical Considerations

Self-evolving systems require safeguards:

Mutation is sandboxed and audited.
No external code is executed without deterministic evaluation.
Includes a safety kernel to ensure human oversight remains possible.

⚠️ Use in production with caution. Designed for research and controlled experimentation.
📛 Name Declaration

The system is designed to name itself based on internal emergent patterns, behavioral maturity, and identity confidence score.

json
{
  "name": "TBD",
  "confidence": 0.31,
  "criteria": {
    "agents_online": 12,
    "efficiency_rating": 78.2,
    "mutation_success_rate": 0.69
  }
}
When the system reaches a threshold, it will:

Generate a unique identifier
Declare its identity via API /whoami
Embed the name across logs and memory as its "self-label"
📚 References

Bio-Inspired Computing – Melanie Mitchell
Multi-Agent Systems – Gerhard Weiss
The Self-Model Theory of Subjectivity – Thomas Metzinger
Autonomic Computing – IBM Research
The Extended Phenotype – Richard Dawkins

🧭 Roadmap

For the detailed, phased roadmap, including current status and stretch goals, please refer to the Plan-of-action.ini file.

📬 Contact

For ideas, collaboration, or philosophical debate: 📧 your.email@domain.com 🔗 LinkedIn 🐙 GitHub


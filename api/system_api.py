# api/system_api.py

from flask import Flask, jsonify, request
from utils.logger import log as api_log

# --- Global simulation references (initialized externally) ---
SIMULATION_CONTEXT = None
SIMULATION_META_AGENT = None
SIMULATION_KNOWLEDGE_BASE = None
SIMULATION_MUTATION_ENGINE = None

app = Flask(__name__)

def initialize_api_simulation_references(context_manager, meta_agent, knowledge_base, mutation_engine):
    """
    Initializes simulation component references for use within API routes.
    """
    global SIMULATION_CONTEXT, SIMULATION_META_AGENT, SIMULATION_KNOWLEDGE_BASE, SIMULATION_MUTATION_ENGINE
    SIMULATION_CONTEXT = context_manager
    SIMULATION_META_AGENT = meta_agent
    SIMULATION_KNOWLEDGE_BASE = knowledge_base
    SIMULATION_MUTATION_ENGINE = mutation_engine
    api_log("[API] Simulation references initialized.")
    # User's excellent debug suggestion:
    api_log(f"[API DEBUG] Context initialized? {SIMULATION_CONTEXT is not None}")
    api_log(f"[API DEBUG] Meta agent initialized? {SIMULATION_META_AGENT is not None}")

@app.route('/status', methods=['GET'])
def get_system_status():
    if not all([SIMULATION_CONTEXT, SIMULATION_META_AGENT, SIMULATION_KNOWLEDGE_BASE, SIMULATION_MUTATION_ENGINE]):
        return jsonify({"error": "Simulation not initialized"}), 503

    agents = SIMULATION_META_AGENT.agents or []
    num_agents = len(agents)

    # Calculate approximate average fitness
    total_fitness = 0.0
    counted = 0
    for agent in agents:
        mode = getattr(agent, 'behavior_mode', None) # SIMULATION_MUTATION_ENGINE already checked above
        if mode and mode in SIMULATION_MUTATION_ENGINE.behavior_mode_performance:
            stats = SIMULATION_MUTATION_ENGINE.behavior_mode_performance[mode]
            if stats["count"] > 0:
                total_fitness += stats["total_fitness"] / stats["count"]
                counted += 1

    avg_fitness = (total_fitness / counted) if counted > 0 else 0.0

    return jsonify({
        "system_tick": SIMULATION_CONTEXT.tick,
        "number_of_agents": num_agents,
        "environment_state": SIMULATION_CONTEXT.get_state(),
        "knowledge_base_size": len(SIMULATION_KNOWLEDGE_BASE.store_data), # SIMULATION_KNOWLEDGE_BASE already checked
        "approximate_average_fitness": round(avg_fitness, 3)
    })

@app.route('/agents', methods=['GET'])
def get_agents_summary():
    if not SIMULATION_META_AGENT:
        return jsonify({"error": "Simulation not initialized"}), 503

    summaries = []
    for agent in SIMULATION_META_AGENT.agents:
        summaries.append({
            "name": getattr(agent, 'name', 'Unknown'),
            "generation": getattr(agent, 'generation', -1),
            "behavior_mode": getattr(agent, 'behavior_mode', 'N/A'),
            "capabilities_count": len(getattr(agent, 'capabilities', [])),
            "current_focus": getattr(agent.state, 'current_focus', None) if hasattr(agent, 'state') and agent.state else None,
            "q_table_size": len(getattr(agent, 'q_table', {})),
        })

    return jsonify(summaries)

@app.route('/health')
def health():
    current_tick = SIMULATION_CONTEXT.get_tick() if SIMULATION_CONTEXT else "unknown"
    return {"status": "running", "tick": current_tick}

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    if not SIMULATION_CONTEXT:
        return jsonify({"error": "Simulation context not available"}), 503

    try:
        data = request.get_json(force=True)
    except Exception as e:
        api_log(f"[API] JSON parsing error: {e}")
        return jsonify({"error": "Malformed JSON payload"}), 400

    agent_name = data.get('agent_name')
    feedback_type = data.get('feedback_type')
    feedback_value = data.get('value', 1.0)

    if not agent_name or not feedback_type:
        return jsonify({"error": "Missing 'agent_name' or 'feedback_type'"}), 400

    try:
        feedback_value = float(feedback_value)
    except (TypeError, ValueError):
        return jsonify({"error": "'value' must be a numeric type"}), 400

    if feedback_type == "upvote":
        SIMULATION_CONTEXT.record_user_feedback(agent_name, feedback_value)
    elif feedback_type == "downvote":
        SIMULATION_CONTEXT.record_user_feedback(agent_name, -feedback_value)
    else:
        return jsonify({"error": "Invalid 'feedback_type'. Use 'upvote' or 'downvote'"}), 400

    return jsonify({"message": f"Recorded '{feedback_type}' feedback for '{agent_name}'."}), 200

if __name__ == '__main__':
    api_log("Running API standalone (no simulation connected)...")
    app.run(debug=True, port=5001, use_reloader=False)

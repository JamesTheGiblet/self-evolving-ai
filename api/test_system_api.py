# tests/api/test_system_api.py
import pytest
import json
from unittest.mock import MagicMock, patch

# Assuming your Flask app instance is accessible
# If system_api.py defines `app = Flask(__name__)` globally, you can import it.
# You'll also need to initialize the simulation references for testing.
from api.system_api import app, initialize_api_simulation_references

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_simulation_components():
    mock_context = MagicMock()
    mock_meta_agent = MagicMock()
    mock_kb = MagicMock()
    mock_mutation_engine = MagicMock()

    # Setup default return values for mocks
    mock_context.tick = 100
    mock_context.get_tick.return_value = 100
    mock_context.get_state.return_value = {"current_tick": 100, "details": "sim_state"}
    mock_context.record_user_feedback = MagicMock()

    mock_agent1 = MagicMock()
    mock_agent1.name = "Agent1"
    mock_agent1.generation = 1
    mock_agent1.behavior_mode = "explore"
    mock_agent1.capabilities = ["cap1"]
    mock_agent1.state = MagicMock()
    mock_agent1.state.current_focus = "testing"
    mock_agent1.q_table = {}


    mock_meta_agent.agents = [mock_agent1]
    mock_kb.store_data = {"entry1": "data1", "entry2": "data2"} # Example store_data

    mock_mutation_engine.behavior_mode_performance = {
        "explore": {"total_fitness": 1.5, "count": 2}
    }

    return {
        "context": mock_context,
        "meta_agent": mock_meta_agent,
        "kb": mock_kb,
        "mutation_engine": mock_mutation_engine
    }

def initialize_app_for_testing(mock_components):
    initialize_api_simulation_references(
        mock_components["context"],
        mock_components["meta_agent"],
        mock_components["kb"],
        mock_components["mutation_engine"]
    )

class TestSystemAPI:

    def test_health_endpoint(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'running'
        assert data['tick'] == mock_simulation_components["context"].get_tick()

    def test_status_endpoint_success(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        response = client.get('/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['system_tick'] == mock_simulation_components["context"].tick
        assert data['number_of_agents'] == len(mock_simulation_components["meta_agent"].agents)
        assert data['knowledge_base_size'] == len(mock_simulation_components["kb"].store_data)
        assert "approximate_average_fitness" in data

    def test_status_endpoint_not_initialized(self, client):
        # Ensure references are None before this test
        initialize_api_simulation_references(None, None, None, None)
        response = client.get('/status')
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data['error'] == "Simulation not initialized"

    def test_status_endpoint_success_no_agents(self, client, mock_simulation_components):
        # Modify mock_simulation_components for this test
        mock_simulation_components["meta_agent"].agents = []
        # Ensure mutation engine performance handles empty or is set to empty
        mock_simulation_components["mutation_engine"].behavior_mode_performance = {}

        initialize_app_for_testing(mock_simulation_components)
        response = client.get('/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['system_tick'] == mock_simulation_components["context"].tick
        assert data['number_of_agents'] == 0
        assert data['knowledge_base_size'] == len(mock_simulation_components["kb"].store_data)
        assert data['approximate_average_fitness'] == 0.0 # Based on current API logic

    def test_agents_summary_success_no_agents(self, client, mock_simulation_components):
        mock_simulation_components["meta_agent"].agents = []
        initialize_app_for_testing(mock_simulation_components)
        response = client.get('/agents')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0
    def test_agents_summary_success(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        response = client.get('/agents')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == len(mock_simulation_components["meta_agent"].agents)
        if len(data) > 0:
            assert data[0]['name'] == mock_simulation_components["meta_agent"].agents[0].name

    def test_agents_summary_not_initialized(self, client):
        initialize_api_simulation_references(None, None, None, None) # Context, KB, ME can be anything for this specific check
        response = client.get('/agents')
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data['error'] == "Simulation not initialized"

    @pytest.mark.parametrize(
        "feedback_type, input_value, expected_recorded_value, expected_message_part",
        [
            ("upvote", 0.8, 0.8, "Recorded 'upvote' feedback"),
            ("downvote", 0.5, -0.5, "Recorded 'downvote' feedback"),
        ]
    )
    def test_submit_feedback_success(self, client, mock_simulation_components, feedback_type, input_value, expected_recorded_value, expected_message_part):
        initialize_app_for_testing(mock_simulation_components)
        feedback_data = {"agent_name": "Agent1", "feedback_type": feedback_type, "value": input_value}
        response = client.post('/feedback', data=json.dumps(feedback_data), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert expected_message_part in data['message']
        mock_simulation_components["context"].record_user_feedback.assert_called_once_with("Agent1", expected_recorded_value)

    def test_submit_feedback_missing_fields(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        response = client.post('/feedback', data=json.dumps({"agent_name": "Agent1"}), content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == "Missing 'agent_name' or 'feedback_type'"

    def test_submit_feedback_invalid_type(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        feedback_data = {"agent_name": "Agent1", "feedback_type": "neutral", "value": 1.0}
        response = client.post('/feedback', data=json.dumps(feedback_data), content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Invalid 'feedback_type'" in data['error']

    def test_submit_feedback_malformed_json(self, client, mock_simulation_components):
        initialize_app_for_testing(mock_simulation_components)
        response = client.post('/feedback', data="not json", content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error'] == "Malformed JSON payload"

    def test_submit_feedback_context_not_available(self, client):
        initialize_api_simulation_references(None, MagicMock(), MagicMock(), MagicMock()) # Context is None
        feedback_data = {"agent_name": "Agent1", "feedback_type": "upvote", "value": 1.0}
        response = client.post('/feedback', data=json.dumps(feedback_data), content_type='application/json')
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data['error'] == "Simulation context not available"

import pytest
from unittest.mock import MagicMock, patch, call

from core.skill_agent import SkillAgent
from core.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
from engine.communication_bus import CommunicationBus
from core.skill_definitions import SKILL_CAPABILITY_MAPPING

# Mock the skill_handlers module and its functions/tools
# This allows us to control their behavior during tests without actual external calls
@pytest.fixture(autouse=True)
def mock_skill_handlers_imports():
    with patch('core.skill_handlers.web_scraper', MagicMock()) as mock_web_scraper, \
         patch('core.skill_handlers.maths_tool', MagicMock()) as mock_maths_tool, \
         patch('core.skill_handlers.file_manager', MagicMock()) as mock_file_manager, \
         patch('core.skill_handlers.api_connector', MagicMock()) as mock_api_connector:
        
        # Configure the mock tools to have an 'execute' method
        mock_web_scraper.execute.return_value = '{"status": "success", "data": "web content"}'
        mock_maths_tool.execute.return_value = '{"status": "success", "result": 15}'
        mock_file_manager.execute.return_value = '{"status": "success", "files": ["file1.txt"]}'
        mock_api_connector.execute.return_value = '{"status": "success", "response": "api data"}'
        
        # Yield the mocks if needed by specific tests, though autouse handles the patching
        yield {
            "web_scraper": mock_web_scraper,
            "maths_tool": mock_maths_tool,
            "file_manager": mock_file_manager,
            "api_connector": mock_api_connector
        }

@pytest.fixture
def mock_context_manager():
    cm = MagicMock(spec=ContextManager)
    cm.get_tick.return_value = 0
    return cm

@pytest.fixture
def mock_knowledge_base():
    return MagicMock(spec=KnowledgeBase)

@pytest.fixture
def mock_communication_bus():
    bus = MagicMock(spec=CommunicationBus)
    bus.get_messages.return_value = [] # Default to no messages
    return bus

@pytest.fixture
def base_skill_agent_args(mock_context_manager, mock_knowledge_base, mock_communication_bus):
    return {
        "name": "TestSkillAgent",
        "context_manager": mock_context_manager,
        "knowledge_base": mock_knowledge_base,
        "communication_bus": mock_communication_bus,
        "skill_description": "A test skill agent"
    }

@pytest.fixture
def skill_agent_no_caps(base_skill_agent_args):
    agent = SkillAgent(**base_skill_agent_args, capabilities=[])
    agent.memory = MagicMock()
    return agent

@pytest.fixture
def skill_agent_with_data_analysis_cap(base_skill_agent_args):
    # This agent should register "basic_stats", "log_summary", "complexity"
    agent = SkillAgent(**base_skill_agent_args, capabilities=["data_analysis_basic_v1"])
    agent.memory = MagicMock()
    return agent

@pytest.fixture
def skill_agent_with_math_cap(base_skill_agent_args):
    # This agent should register "maths_operation"
    agent = SkillAgent(**base_skill_agent_args, capabilities=["math_services_v1"])
    agent.memory = MagicMock()
    return agent

class TestSkillAgentInitialization:
    def test_initialization_basic_attributes(self, skill_agent_no_caps, base_skill_agent_args):
        assert skill_agent_no_caps.name == base_skill_agent_args["name"]
        assert skill_agent_no_caps.skill_description == base_skill_agent_args["skill_description"]
        assert skill_agent_no_caps.agent_type == "skill"
        assert skill_agent_no_caps.behavior_mode == "observer" # Default
        assert isinstance(skill_agent_no_caps.skill_registry, dict)
        assert skill_agent_no_caps.last_tick_processed == -1
        assert skill_agent_no_caps.idle_ticks == 0

    def test_initialization_registers_no_skills_if_no_caps(self, skill_agent_no_caps):
        assert len(skill_agent_no_caps.skill_registry) == 0

    def test_initialization_registers_skills_for_data_analysis_basic_v1(self, skill_agent_with_data_analysis_cap):
        agent = skill_agent_with_data_analysis_cap
        expected_skills = SKILL_CAPABILITY_MAPPING["data_analysis_basic_v1"]
        assert len(agent.skill_registry) == len(expected_skills)
        for skill_name in expected_skills:
            assert skill_name in agent.skill_registry
            assert callable(agent.skill_registry[skill_name])

    def test_initialization_registers_skills_for_math_services_v1(self, skill_agent_with_math_cap):
        agent = skill_agent_with_math_cap
        expected_skills = SKILL_CAPABILITY_MAPPING["math_services_v1"]
        assert len(agent.skill_registry) == len(expected_skills)
        for skill_name in expected_skills:
            assert skill_name in agent.skill_registry
            assert callable(agent.skill_registry[skill_name])

    def test_initialization_with_multiple_capabilities(self, base_skill_agent_args):
        agent = SkillAgent(**base_skill_agent_args, capabilities=["data_analysis_basic_v1", "math_services_v1"])
        expected_skills_data = SKILL_CAPABILITY_MAPPING["data_analysis_basic_v1"]
        expected_skills_math = SKILL_CAPABILITY_MAPPING["math_services_v1"]
        total_expected_skills = set(expected_skills_data + expected_skills_math)
        
        assert len(agent.skill_registry) == len(total_expected_skills)
        for skill_name in total_expected_skills:
            assert skill_name in agent.skill_registry

    def test_initialization_handles_unknown_capability_gracefully(self, base_skill_agent_args):
        # Expect a log warning, but agent should initialize
        with patch('core.skill_agent.log') as mock_log:
            agent = SkillAgent(**base_skill_agent_args, capabilities=["unknown_capability_v1"])
            assert len(agent.skill_registry) == 0
            mock_log.assert_any_call(
                f"[{agent.name}] Configured capability 'unknown_capability_v1' has no defined skill mapping in the central SKILL_CAPABILITY_MAPPING.",
                level="WARNING"
            )

class TestSkillAgentRegistration:
    def test_register_skill(self, skill_agent_no_caps):
        mock_handler = MagicMock()
        skill_agent_no_caps.register_skill("custom_skill", mock_handler)
        assert "custom_skill" in skill_agent_no_caps.skill_registry
        assert skill_agent_no_caps.skill_registry["custom_skill"] == mock_handler


class TestSkillAgentInputValidation:
    @pytest.mark.parametrize("skill_data, expected_valid, expected_msg_part", [
        ({"action": "maths_operation", "data": {"maths_command": "add 1 2"}}, True, ""),
        ({"action": "web_operation", "data": {"web_command": "fetch example.com"}}, True, ""),
        ({"action": "file_operation", "data": {"file_command": "read test.txt"}}, True, ""),
        ({"action": "api_call", "data": {"api_command": "get_time"}}, True, ""),
        ({"action": "basic_stats", "data": {"data_points": [1, 2, 3]}}, True, ""),
        ({"action": "log_summary", "data": {"data_points": ["log1"], "analysis_type": "log_summary"}}, True, ""),
        ({"action": "complexity", "data": {"data_points": [{}], "analysis_type": "complexity"}}, True, ""),
        ("not_a_dict", False, "Skill input must be a dictionary"),
        ({"data": {"maths_command": "add 1 2"}}, False, "Missing 'action' key"),
        ({"action": "maths_operation"}, False, "Missing or invalid 'data' payload"),
        ({"action": "maths_operation", "data": "not_a_dict"}, False, "Missing or invalid 'data' payload"),
        ({"action": "maths_operation", "data": {}}, False, "Missing 'maths_command'"),
        ({"action": "web_operation", "data": {}}, False, "Missing 'web_command'"),
        ({"action": "file_operation", "data": {}}, False, "Missing 'file_command'"),
        ({"action": "api_call", "data": {}}, False, "Missing 'api_command'"),
        # basic_stats, log_summary, complexity are more lenient on data_points for now
        ({"action": "basic_stats", "data": {}}, True, ""), 
    ])
    def test_validate_skill_input(self, skill_agent_no_caps, skill_data, expected_valid, expected_msg_part):
        is_valid, msg = skill_agent_no_caps.validate_skill_input(skill_data)
        assert is_valid == expected_valid
        if not expected_valid:
            assert expected_msg_part in msg


class TestSkillAgentPerformSkill:
    def test_perform_skill_validation_failure(self, skill_agent_no_caps, mock_context_manager, mock_knowledge_base):
        invalid_input = {"wrong_key": "some_action"}
        result = skill_agent_no_caps.perform_skill(invalid_input, mock_context_manager, mock_knowledge_base)
        assert result["status"] == "failure_validation"
        assert "Missing 'action' key" in result["message"]

    def test_perform_skill_no_handler(self, skill_agent_no_caps, mock_context_manager, mock_knowledge_base):
        skill_input = {"action": "non_existent_skill", "data": {}}
        result = skill_agent_no_caps.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
        assert result["status"] == "failure_no_handler"
        assert "No handler found for action: non_existent_skill" in result["message"]

    # Removed @patch('core.skill_handlers.handle_maths_operation')
    def test_perform_skill_maths_operation_success(self, skill_agent_with_math_cap, mock_context_manager, mock_knowledge_base, mock_skill_handlers_imports):
        # The actual handle_maths_operation will use maths_tool.execute.
        # maths_tool.execute is mocked by mock_skill_handlers_imports to return '{"status": "success", "result": 15}'
        # The handler should parse this JSON and return the corresponding dictionary.
        expected_handler_output = {"status": "success", "result": 15}
        skill_input = {"action": "maths_operation", "data": {"maths_command": "add 1 2"}}

        
        result = skill_agent_with_math_cap.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
        
        assert result["status"] == "success"
        assert result["data"] == expected_handler_output
        mock_skill_handlers_imports["maths_tool"].execute.assert_called_once_with("add 1 2", {})


    # Removed @patch('core.skill_handlers.handle_web_operation')
    def test_perform_skill_web_operation_success(self, base_skill_agent_args, mock_context_manager, mock_knowledge_base, mock_skill_handlers_imports):
        agent = SkillAgent(**base_skill_agent_args, capabilities=["web_services_v1"])
        agent.memory = MagicMock() # Ensure memory is mocked for locally created agent too

        # web_scraper.execute is mocked by mock_skill_handlers_imports to return '{"status": "success", "data": "web content"}'
        # The handler should parse this JSON.
        expected_handler_output = {"status": "success", "data": "web content"}
        skill_input = {"action": "web_operation", "data": {"web_command": "get_text http://example.com"}}

        
        result = agent.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
        
        assert result["status"] == "success"
        assert result["data"] == expected_handler_output
        mock_skill_handlers_imports["web_scraper"].execute.assert_called_once_with("get_text http://example.com", {})


    # Removed @patch('core.skill_handlers.handle_basic_stats')
    def test_perform_skill_basic_stats_success(self, skill_agent_with_data_analysis_cap, mock_context_manager, mock_knowledge_base):
        # This test now relies on the actual implementation of `handle_basic_stats`.
        # The expected data should match what `handle_basic_stats` produces for the input [1, 2, 3].
        # This might be a more complex dictionary than just mean and count.
        # Adjust expected_data based on the actual output of your handle_basic_stats function.
        skill_input = {"action": "basic_stats", "data": {"data_points": [1, 2, 3]}}
         
        result = skill_agent_with_data_analysis_cap.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
        
        assert result["status"] == "success"
        # Example: asserting specific, known values from the actual handler's output
        # The exact structure of result["data"] depends on your `handle_basic_stats` implementation.
        # The error log indicated a more complex dict. For [1,2,3] common stats are:
        assert result["data"]["count"] == 3
        assert result["data"]["mean"] == 2.0
        assert result["data"]["min"] == 1.0
        assert result["data"]["max"] == 3.0
        assert result["data"]["sum"] == 6.0
        # Add other relevant assertions based on your handle_basic_stats output

    # Removed @patch('core.skill_handlers.handle_maths_operation')
    def test_perform_skill_handler_exception(self, skill_agent_with_math_cap, mock_context_manager, mock_knowledge_base, mock_skill_handlers_imports):
        # Make the underlying tool raise an exception
        mock_skill_handlers_imports["maths_tool"].execute.side_effect = Exception("Tool execution error")
        skill_input = {"action": "maths_operation", "data": {"maths_command": "add 1 1"}}
        
        result = skill_agent_with_math_cap.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
        
        assert result["status"] == "failure_exception"
        assert result["data"] == {}
        assert "Tool execution error" in result["message"] # Message from the tool's exception
        mock_skill_handlers_imports["maths_tool"].execute.assert_called_once_with("add 1 1", {})


    def test_perform_skill_with_tool_not_loaded(self, base_skill_agent_args, mock_context_manager, mock_knowledge_base):
        # Simulate maths_tool not being loaded by patching it to None within skill_handlers
        with patch('core.skill_handlers.maths_tool', None):
            # Re-initialize agent so _register_default_skills sees the None tool
            agent = SkillAgent(**base_skill_agent_args, capabilities=["math_services_v1"])
            assert "maths_operation" not in agent.skill_registry # Should not be registered

            skill_input = {"action": "maths_operation", "data": {"maths_command": "add 1 2"}}
            result = agent.perform_skill(skill_input, mock_context_manager, mock_knowledge_base)
            
            assert result["status"] == "failure_no_handler"
            assert "No handler found for action: maths_operation" in result["message"]


class TestSkillAgentRun:
    def test_run_no_messages_idle(self, skill_agent_no_caps, mock_context_manager, mock_communication_bus):
        mock_communication_bus.get_messages.return_value = []
        skill_agent_no_caps.run(mock_context_manager, MagicMock(), [], {})
        
        assert skill_agent_no_caps.idle_ticks == 1
        mock_communication_bus.get_messages.assert_called_once_with(skill_agent_no_caps.name, clear_after_read=True)
        skill_agent_no_caps.memory.log_tick.assert_called_with({
            "tick": 0, "action": "run_skill_agent", "outcome": "idle_no_messages", "reward": 0.0
        })

    def test_run_processes_one_skill_request_and_responds(self, skill_agent_with_math_cap, mock_context_manager, mock_communication_bus, mock_skill_handlers_imports):
        request_id = "req123"
        sender_agent = "TaskAgent1"
        math_command = "add 5 10"
        
        # Mock the underlying tool's execute method for maths_operation
        mock_skill_handlers_imports["maths_tool"].execute.return_value = '{"status": "success", "result": 15}'

        incoming_message = {
            "sender": sender_agent,
            "type": "direct",
            "content": {
                "action": "maths_operation", # This is the skill_name
                "request_id": request_id,
                "data": {"maths_command": math_command} # This is the payload for the skill
            }
        }
        mock_communication_bus.get_messages.return_value = [incoming_message]

        skill_agent_with_math_cap.run(mock_context_manager, MagicMock(), [], {})

        assert skill_agent_with_math_cap.idle_ticks == 0
        skill_agent_with_math_cap.memory.log_message_received.assert_called_once()
        
        # Check that the maths_tool's execute was called correctly
        mock_skill_handlers_imports["maths_tool"].execute.assert_called_once_with(math_command, {})

        # Check that send_direct_message was called with the correct response
        expected_response_payload = {
            "action": "skill_response",
            "request_id": request_id,
            "status": "success",
            "data": {"status": "success", "result": 15}, # This comes from the mocked maths_tool.execute
            "message": "Skill executed."
        }
        mock_communication_bus.send_direct_message.assert_called_once_with(
            skill_agent_with_math_cap.name,
            sender_agent,
            expected_response_payload
        )
        
        # Check memory logging for skill execution
        skill_agent_with_math_cap.memory.log_tick.assert_any_call({
            "tick": 0,
            "action": f"skill_exec_{skill_agent_with_math_cap.name}_maths_operation",
            "outcome": "success",
            "reward": 0.5,
            "request_id": request_id
        })

    def test_run_handles_invalid_input_in_message(self, skill_agent_with_math_cap, mock_context_manager, mock_communication_bus):
        request_id = "req_invalid"
        sender_agent = "TaskAgent2"
        incoming_message = {
            "sender": sender_agent,
            "type": "direct",
            "content": {
                "action": "maths_operation",
                "request_id": request_id,
                "data": {"wrong_maths_key": "add 1 2"} # Invalid payload
            }
        }
        mock_communication_bus.get_messages.return_value = [incoming_message]

        skill_agent_with_math_cap.run(mock_context_manager, MagicMock(), [], {})

        expected_response_payload = {
            "action": "skill_response",
            "request_id": request_id,
            "status": "failure_invalid_input",
            "data": {},
            "message": "Maths operation requires a valid 'maths_command' string."
        }
        mock_communication_bus.send_direct_message.assert_called_once_with(
            skill_agent_with_math_cap.name,
            sender_agent,
            expected_response_payload
        )
        skill_agent_with_math_cap.memory.log_tick.assert_any_call({
            "tick": 0,
            "action": f"skill_exec_{skill_agent_with_math_cap.name}_maths_operation",
            "outcome": "failure_invalid_input",
            "reward": -0.2,
            "request_id": request_id
        })

    def test_run_handles_perform_skill_exception_gracefully(self, skill_agent_with_math_cap, mock_context_manager, mock_communication_bus, mock_skill_handlers_imports):
        request_id = "req_exception"
        sender_agent = "TaskAgent3"
        
        # Make the skill handler's underlying tool raise an exception
        mock_skill_handlers_imports["maths_tool"].execute.side_effect = ValueError("Tool execution error")

        incoming_message = {
            "sender": sender_agent,
            "type": "direct",
            "content": {
                "action": "maths_operation",
                "request_id": request_id,
                "data": {"maths_command": "divide 10 0"} 
            }
        }
        mock_communication_bus.get_messages.return_value = [incoming_message]

        skill_agent_with_math_cap.run(mock_context_manager, MagicMock(), [], {})

        # Check that send_direct_message was called with the failure response
        # The actual message will depend on how the mocked execute -> json.loads -> handler behaves
        # Given the mock setup, the error originates from the tool's execute method.
        # The skill_handlers.handle_maths_operation will catch this and raise ValueError.
        # Then perform_skill catches this and sets status to "failure_exception".
        
        args, _ = mock_communication_bus.send_direct_message.call_args
        assert args[0] == skill_agent_with_math_cap.name
        assert args[1] == sender_agent
        response_payload = args[2]
        
        assert response_payload["action"] == "skill_response"
        assert response_payload["request_id"] == request_id
        assert response_payload["status"] == "failure_exception"
        assert "Tool execution error" in response_payload["message"] 

        skill_agent_with_math_cap.memory.log_tick.assert_any_call({
            "tick": 0,
            "action": f"skill_exec_{skill_agent_with_math_cap.name}_maths_operation",
            "outcome": "failure_exception",
            "reward": -0.2,
            "request_id": request_id
        })

    def test_run_skips_if_already_processed_tick(self, skill_agent_no_caps, mock_context_manager):
        mock_context_manager.get_tick.return_value = 5
        skill_agent_no_caps.last_tick_processed = 5 # Simulate already processed

        skill_agent_no_caps.run(mock_context_manager, MagicMock(), [], {})
        
        # Ensure no major processing happens
        skill_agent_no_caps.communication_bus.get_messages.assert_not_called()
        skill_agent_no_caps.memory.log_tick.assert_not_called() # Should not log if skipped early

    def test_run_no_communication_bus(self, skill_agent_no_caps, mock_context_manager):
        skill_agent_no_caps.communication_bus = None
        with patch('core.skill_agent.log') as mock_log:
            skill_agent_no_caps.run(mock_context_manager, MagicMock(), [], {})
            mock_log.assert_any_call(f"[{skill_agent_no_caps.name}] No communication bus available.", level="ERROR")


class TestSkillAgentFitness:
    def test_get_fitness_no_executions(self, skill_agent_no_caps, mock_context_manager):
        mock_context_manager.get_tick.return_value = 10
        skill_agent_no_caps.memory.get_log.return_value = []
        fitness = skill_agent_no_caps.get_fitness()
        # Expected: (0.0 * 0.8) + (0.01 * 10 * 0.2) = 0.02
        assert fitness == pytest.approx(0.02) 

    def test_get_fitness_with_successful_executions(self, skill_agent_no_caps, mock_context_manager):
        mock_context_manager.get_tick.return_value = 50
        log_entries = [
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "success_skill_done"},
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "success_another"},
            {"action": "other_action", "outcome": "irrelevant"}
        ]
        skill_agent_no_caps.memory.get_log.return_value = log_entries
        fitness = skill_agent_no_caps.get_fitness()
        # success_rate = 2/2 = 1.0
        # tick_bonus = 0.01 * 50 = 0.5
        # fitness = (1.0 * 0.8) + (0.5 * 0.2) = 0.8 + 0.1 = 0.9
        assert fitness == pytest.approx(0.9)

    def test_get_fitness_with_mixed_outcomes(self, skill_agent_no_caps, mock_context_manager):
        mock_context_manager.get_tick.return_value = 100 # Max tick bonus
        log_entries = [
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "success_skill_done"},
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "failure_something"},
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "success_again"},
            {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "failure_internal_error"},
        ]
        skill_agent_no_caps.memory.get_log.return_value = log_entries
        fitness = skill_agent_no_caps.get_fitness()
        # success_rate = 2/4 = 0.5
        # tick_bonus = 0.01 * 100 = 1.0 (capped at 1.0 for calculation, then * 0.2)
        # fitness = (0.5 * 0.8) + (1.0 * 0.2) = 0.4 + 0.2 = 0.6
        assert fitness == pytest.approx(0.6)

    def test_get_fitness_tick_bonus_cap(self, skill_agent_no_caps, mock_context_manager):
        mock_context_manager.get_tick.return_value = 200 # Exceeds 100
        skill_agent_no_caps.memory.get_log.return_value = [
             {"action": f"skill_exec_{skill_agent_no_caps.name}_test_skill", "outcome": "success_skill_done"}
        ]
        fitness = skill_agent_no_caps.get_fitness()
        # success_rate = 1.0
        # tick_bonus = 0.01 * 100 (capped) = 1.0
        # fitness = (1.0 * 0.8) + (1.0 * 0.2) = 0.8 + 0.2 = 1.0
        assert fitness == pytest.approx(1.0)


class TestSkillAgentConfig:
    def test_get_config(self, skill_agent_no_caps, base_skill_agent_args):
        config = skill_agent_no_caps.get_config()

        assert config["name"] == base_skill_agent_args["name"]
        assert config["agent_type"] == "skill"
        assert config["skill_description"] == base_skill_agent_args["skill_description"]
        assert "capabilities" in config
        assert "capability_params" in config
        assert "behavior_mode" in config

    def test_get_config_includes_superclass_fields(self, skill_agent_with_data_analysis_cap):
        # Example of fields from BaseAgent that should be present
        agent = skill_agent_with_data_analysis_cap
        agent.generation = 5
        agent.state["lineage_id"] = "lineage_abc"
        agent.state["current_focus"] = "test_focus"
        agent.max_age = 1000
        agent.role = "analyzer"

        config = agent.get_config()

        assert config["generation"] == 5
        assert config["lineage_id"] == "lineage_abc"
        assert config["initial_focus"] == "test_focus"
        assert config["max_age"] == 1000
        assert config["role"] == "analyzer"
        assert config["capabilities"] == ["data_analysis_basic_v1"]




# Example of how to run with pytest:
# Ensure this file is in a 'tests/core/' directory relative to your project root.
# Your project structure might look like:
# self-evolving-ai/
#   core/
#     skill_agent.py
#     ...
#   tests/
#     core/
#       test_skill_agent.py
#
# Then run from the 'self-evolving-ai' directory:
# pytest
# or
# pytest tests/core/test_skill_agent.py
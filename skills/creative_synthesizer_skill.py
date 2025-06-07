# skills/creative_synthesizer_skill.py

import json
import datetime # Keep this import
from typing import Dict, Any, List, TYPE_CHECKING, Optional

from base_skill import BaseSkillTool
from utils.logger import log

# For type hinting core components to avoid circular imports at runtime
if TYPE_CHECKING:
    from memory.knowledge_base import KnowledgeBase
    from core.context_manager import ContextManager
    from engine.communication_bus import CommunicationBus
    from agents.code_gen_agent import LLMInterface # For LLM interaction

class CreativeSynthesizerSkill(BaseSkillTool):
    """
    A skill that provides creative text summarization, along with
    basic echo, text statistics, and current date functionalities.
    Inspired by echo, basic data analysis, and calendar services.
    """

    def __init__(self,
                 skill_config: Dict[str, Any],
                 knowledge_base: 'KnowledgeBase',
                 context_manager: 'ContextManager',
                 communication_bus: 'CommunicationBus',
                 agent_name: str,
                 agent_id: str,
                 llm_interface: 'Optional[LLMInterface]' = None, # Added LLMInterface dependency
                 **kwargs: Any):
        """
        Initializes the CreativeSynthesizerSkill.

        Args:
            # ... (other standard args)
            llm_interface (Optional[LLMInterface]): An instance of LLMInterface for text generation.
        """
        super().__init__(skill_config, knowledge_base, context_manager, communication_bus, agent_name, agent_id, **kwargs)
        self.llm_interface = llm_interface
        if self.llm_interface:
            log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}) with LLMInterface.", level="INFO")
        else:
            log(f"[{self.skill_name}] Initialized for agent {agent_name} ({agent_id}) WITHOUT LLMInterface. Creative summarization will be limited.", level="WARN")



    def get_capabilities(self) -> Dict[str, Any]:
        """
        Returns a dictionary describing the skill's commands and capabilities.
        """
        return {
            "skill_name": self.skill_name,
            "description": "Generates creative text summaries, echoes text, provides basic text stats, and shows the current date.",
            "commands": {
                "summarize_creatively": {
                    "description": "Generates a creative summary for the provided text using an LLM.",
                    "args_usage": "\"<text_to_summarize>\"",
                    "example": "summarize_creatively \"The quick brown fox jumps over the lazy dog. It was a sunny day.\"",
                    "keywords": ["summarize", "creative summary", "text synthesis", "abstract", "gist"]
                },
                "echo_text": {
                    "description": "Echoes the provided text back.",
                    "args_usage": "<text_to_echo>",
                    "example": "echo_text Hello creative world!",
                    "keywords": ["echo", "repeat", "say back", "mirror text"]
                },
                "text_stats": {
                    "description": "Provides basic statistics (word count, char count) for the given text.",
                    "args_usage": "\"<text_for_stats>\"",
                    "example": "text_stats \"This is a sample sentence.\"",
                    "keywords": ["text statistics", "word count", "character count", "analyze text", "text length"]
                },
                "current_date": {
                    "description": "Gets the current date.",
                    "args_usage": "",
                    "example": "current_date",
                    "keywords": ["today's date", "current date", "what day is it", "date now"]
                }
            }
        }

    def _handle_summarize_creatively(self, text_to_summarize: str) -> Dict[str, Any]:
        """
        Placeholder for creative text summarization.
        In a real implementation, this might call an LLM or a sophisticated summarization model.
        """
        if not self.llm_interface:
            log(f"[{self.skill_name}] LLMInterface not available for creative summarization.", level="ERROR")
            return self._build_response_dict(success=False, error="Creative summarization unavailable: LLMInterface not configured.")

        if not text_to_summarize or not text_to_summarize.strip():
            return self._build_response_dict(success=False, error="No text provided for summarization.")

        log(f"[{self.skill_name}] Requesting creative summary for: '{text_to_summarize[:70]}...'", level="DEBUG")

        system_prompt = (
            "You are a master of language, renowned for your ability to distill complex information "
            "into brief, imaginative, and engaging summaries. Your summaries should not just state facts, "
            "but evoke feeling, paint pictures with words, and offer fresh perspectives. "
            "Avoid dry, factual restatements. Aim for poetic, metaphorical, or narrative flair. "
            "The summary should be concise and capture the essence of the text."
        )
        user_prompt = f"Please provide a creative summary for the following text:\n\n---\n{text_to_summarize}\n---"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            summary = self.llm_interface.call_llm_api(messages)
            if summary:
                return self._build_response_dict(success=True, data={"original_text_preview": text_to_summarize[:100], "creative_summary": summary.strip()})
            else:
                return self._build_response_dict(success=False, error="LLM failed to generate a summary.")
        except Exception as e:
            log(f"[{self.skill_name}] Error calling LLM for summarization: {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error=f"Error during LLM call: {str(e)}")

    def _handle_echo_text(self, text_args: List[str]) -> Dict[str, Any]:
        """
        Handles echoing text.
        """
        if not text_args:
            return self._build_response_dict(success=False, error="No text provided to echo.")
        echoed_text = " ".join(text_args)
        return self._build_response_dict(success=True, data={"echoed_text": echoed_text})

    def _handle_text_stats(self, text_for_stats: str) -> Dict[str, Any]:
        """
        Calculates basic statistics for the given text.
        """
        if not text_for_stats:
            return self._build_response_dict(success=False, error="No text provided for statistics.")
        
        word_count = len(text_for_stats.split())
        char_count_with_spaces = len(text_for_stats)
        char_count_no_spaces = len(text_for_stats.replace(" ", ""))
        
        stats = {
            "text_preview": text_for_stats[:100],
            "word_count": word_count,
            "character_count_with_spaces": char_count_with_spaces,
            "character_count_without_spaces": char_count_no_spaces
        }
        return self._build_response_dict(success=True, data=stats)

    def _handle_current_date(self) -> Dict[str, Any]:
        """
        Returns the current date.
        """
        current_date_str = datetime.date.today().isoformat()
        return self._build_response_dict(success=True, data={"current_date": current_date_str})

    def _execute_skill(self, args: List[str]) -> Dict[str, Any]:
        """
        Executes a command based on parsed arguments.
        """
        if not args:
            return self._build_response_dict(success=False, error="No command provided.")

        command = args[0].lower()
        command_args = args[1:]

        log(f"[{self.skill_name}] Executing command '{command}' with args: {command_args}", level="INFO")

        try:
            if command == "summarize_creatively":
                if not command_args:
                    return self._build_response_dict(success=False, error="Text to summarize is missing for 'summarize_creatively'.")
                # BaseSkillTool's shlex.split handles quoted strings as single arguments
                text_to_summarize = command_args[0] 
                return self._handle_summarize_creatively(text_to_summarize)
            
            elif command == "echo_text":
                return self._handle_echo_text(command_args)

            elif command == "text_stats":
                if not command_args:
                    return self._build_response_dict(success=False, error="Text for statistics is missing for 'text_stats'.")
                text_for_stats = command_args[0]
                return self._handle_text_stats(text_for_stats)

            elif command == "current_date":
                if command_args: # current_date takes no arguments
                    return self._build_response_dict(success=False, error="'current_date' command does not take any arguments.")
                return self._handle_current_date()
            
            else:
                return self._build_response_dict(success=False, error=f"Unknown command: '{command}'.")

        except Exception as e:
            log(f"[{self.skill_name}] Error during execution of command '{command}': {e}", level="ERROR", exc_info=True)
            return self._build_response_dict(success=False, error=f"An unexpected error occurred while executing '{command}': {str(e)}")

# Example usage (for testing purposes if run directly)
if __name__ == "__main__":
    # This section is for testing the skill independently.
    # It will not be executed when the skill is loaded by an agent.

    # --- Add project root to sys.path for direct execution ---
    import sys
    import os
    PROJECT_ROOT_FOR_TESTING = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT_FOR_TESTING not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTING)
    # --- End of sys.path modification ---
    print("Testing CreativeSynthesizerSkill (mock initialization)...")

    # Mock dependencies for local testing
    mock_skill_config_data = {
        "skill_class_name": "CreativeSynthesizerSkill",
        # Add any other config this skill might eventually need
    }
    # In a real scenario, these would be actual instances of KnowledgeBase, ContextManager, etc.
    mock_kb = object() 
    mock_cm = object()
    mock_cb = object()

    # Mock LLMInterface for testing summarize_creatively
    class MockLLMInterface:
        def call_llm_api(self, messages: List[Dict[str, str]], model_name: Optional[str] = None) -> Optional[str]:
            log("[MockLLMInterface] call_llm_api called", level="DEBUG")
            # Find the user prompt to make the mock response somewhat relevant
            user_content = "No user content found in mock."
            for msg in messages:
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")
                    break
            if "summarize" in user_content.lower():
                return f"A mock creative summary of: '{user_content[:50]}...'"
            return "Mock LLM response."

    mock_llm = MockLLMInterface()

    try:
        skill_instance = CreativeSynthesizerSkill(
            skill_config=mock_skill_config_data,
            knowledge_base=mock_kb, # type: ignore
            context_manager=mock_cm, # type: ignore
            communication_bus=mock_cb, # type: ignore
            agent_name="TestSynthesizerAgent",
            agent_id="test-synthesizer-agent-001",
            llm_interface=mock_llm # Pass the mock LLMInterface
        )


        print("\nCapabilities:")
        print(json.dumps(skill_instance.get_capabilities(), indent=2))

        print("\nTesting summarize_creatively:")
        summary_result = skill_instance.execute('summarize_creatively "This is a long piece of text about artificial intelligence and its potential impact on the future of humanity. We explore various scenarios."')
        print(json.dumps(summary_result, indent=2))
        
        summary_short_result = skill_instance.execute('summarize_creatively "Short."')
        print(json.dumps(summary_short_result, indent=2))

        print("\nTesting echo_text:")
        echo_result = skill_instance.execute("echo_text This is a test of the echo command.")
        print(json.dumps(echo_result, indent=2))

        print("\nTesting text_stats:")
        stats_result = skill_instance.execute('text_stats "Count these words and characters."')
        print(json.dumps(stats_result, indent=2))

        print("\nTesting current_date:")
        date_result = skill_instance.execute("current_date")
        print(json.dumps(date_result, indent=2))
        
        print("\nTesting invalid command:")
        invalid_result = skill_instance.execute("non_existent_command arg1 arg2")
        print(json.dumps(invalid_result, indent=2))

    except Exception as e_main:
        print(f"Error during skill testing: {e_main}")
        import traceback
        traceback.print_exc()

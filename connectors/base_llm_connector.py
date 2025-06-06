# connectors/base_llm_connector.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.context_manager import ContextManager

class BaseLLMConnector(ABC):
    """
    Abstract Base Class for LLM connectors.
    Defines the interface for interacting with different LLM providers.
    """

    @abstractmethod
    def call_llm_api_async(self,
                           prompt_messages: List[Dict[str, str]],
                           model_name: str,
                           **kwargs: Any) -> Optional[str]:
        """
        Asynchronously calls the LLM API with the given prompt messages.
        Should return a request_id for tracking the asynchronous operation.
        """
        pass

    @abstractmethod
    def call_llm_api(self,
                     prompt_messages: List[Dict[str, str]],
                     model_name: str,
                     **kwargs: Any) -> Optional[str]:
        """
        Synchronously calls the LLM API and returns the response content.
        """
        pass

    @abstractmethod
    def stage_simulated_llm_response(self,
                                     simulated_content: Optional[Any],
                                     is_plan: bool = False,
                                     error: Optional[str] = None) -> Optional[str]:
        """
        Stages a simulated LLM response for testing or development.
        Returns a request_id for tracking.
        """
        pass

    @abstractmethod
    def set_context_manager(self, context_manager: 'ContextManager') -> None:
        """Sets the context manager for the connector, used for async notifications."""
        pass
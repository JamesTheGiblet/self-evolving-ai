# local_llm_connector.py
import requests
import time # For retry delay
import json
from typing import List, Dict, Any, Optional
import threading # Added for asynchronous operations
import uuid      # Added for generating unique request IDs
import config # Import config to access timeout settings
from core.context_manager import ContextManager
from utils.logger import log
import traceback # For detailed error logging in exception handlers

    
def call_local_llm_api(
    prompt_messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    **kwargs: Any
) -> Optional[str]:
    """
    Calls a local LLM API (e.g., Ollama) to get a response.

    Args:
        prompt_messages: A list of message dictionaries, e.g.,
                         [{"role": "user", "content": "Hello!"},
                          {"role": "assistant", "content": "Hi there!"},
                          {"role": "user", "content": "How are you?"}]
        model_name: The name of the model to use (e.g., "mistral", "llama2").
                    If None, uses LOCAL_LLM_DEFAULT_MODEL from config.
        **kwargs: Additional keyword arguments for the API request (e.g., temperature).
                  These are passed directly to the Ollama API payload.

    Returns:
        The content of the LLM's response as a string, or None if an error occurs.
    """
    api_url = config.LOCAL_LLM_API_BASE_URL
    if not api_url:
        log("LOCAL_LLM_API_BASE_URL is not configured in config.py.", level="ERROR")
        return None

    model_to_use = model_name if model_name else config.LOCAL_LLM_DEFAULT_MODEL
    if not model_to_use:
        log("No LLM model specified and LOCAL_LLM_DEFAULT_MODEL is not configured.", level="ERROR")
        return None

    payload = {
        "model": model_to_use,
        "messages": prompt_messages,
        "stream": False,  # Ensure a single response object for simplicity
        **kwargs # Pass through other parameters like temperature, top_p, etc.
    }

    max_retries = config.LOCAL_LLM_MAX_RETRIES if hasattr(config, 'LOCAL_LLM_MAX_RETRIES') else 2 # Default to 2 if not in config
    retry_delay_seconds = config.LOCAL_LLM_RETRY_DELAY if hasattr(config, 'LOCAL_LLM_RETRY_DELAY') else 5 # Default to 5s if not in config

    try:
        log(f"Sending request to local LLM ({model_to_use}) at {api_url} with payload keys: {list(payload.keys())}", level="DEBUG")
        # log(f"Full payload: {json.dumps(payload, indent=2)}", level="TRACE") # Potentially very verbose

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(api_url, json=payload, timeout=config.LOCAL_LLM_REQUEST_TIMEOUT)
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

                response_data = response.json()
                log(f"Received response from local LLM (Attempt {attempt+1}): {response_data.get('message', {}).get('content', 'N/A')[:100]}...", level="DEBUG")

                if response_data and "message" in response_data and "content" in response_data["message"]:
                    return response_data["message"]["content"]
                else:
                    log(f"Unexpected response structure from local LLM (Attempt {attempt+1}): {response_data}", level="ERROR")
                    return None # Or raise an error if this is critical

            except requests.exceptions.RequestException as e_inner:
                log_level = "ERROR" if attempt == max_retries else "WARNING"
                log(f"Error calling local LLM API (Attempt {attempt+1}/{max_retries+1}) for model {model_to_use}: {e_inner}", level=log_level)
                if attempt < max_retries:
                    log(f"Retrying in {retry_delay_seconds} seconds...", level="INFO")
                    time.sleep(retry_delay_seconds)
                elif attempt == max_retries: # Last attempt failed
                    raise # Re-raise the last exception to be caught by the outer block
        return None # Should not be reached if an exception is raised on final attempt

    except requests.exceptions.RequestException as e:
        log(f"Error calling local LLM API at {api_url} for model {model_to_use} after all retries: {e}", level="ERROR", exc_info=True)
        return None
    except json.JSONDecodeError as e:
        log(f"Error decoding JSON response from local LLM API at {api_url} for model {model_to_use}: {e}. Response text: {response.text if 'response' in locals() else 'N/A'}", level="ERROR", exc_info=True)
        return None
    except Exception as e:
        log(f"An unexpected error occurred in call_local_llm_api for model {model_to_use}: {e}", level="ERROR", exc_info=True)
        return None

# --- Asynchronous LLM Call Handling ---
_pending_llm_requests: Dict[str, Any] = {}
_llm_lock = threading.Lock()
_context_manager_instance: Optional["ContextManager"] = None # Global ref to ContextManager

def set_llm_connector_context_manager(cm_instance: ContextManager):
    global _context_manager_instance
    _context_manager_instance = cm_instance

def _execute_llm_call_threaded(request_id: str, prompt_messages: List[Dict[str, str]], model_name: Optional[str], **kwargs: Any):
    """
    Target function for the thread to execute the blocking LLM call.
    Uses the existing synchronous call_local_llm_api.
    Updates _pending_llm_requests and notifies ContextManager.
    """
    final_status = "error"  # Default to error
    response_content = None
    error_details_for_cm = None

    try:
        # Attempt the LLM call
        response_content = call_local_llm_api(prompt_messages, model_name, **kwargs)

        if response_content is not None:
            final_status = "completed"
            # error_details_for_cm remains None
        else:
            # call_local_llm_api returned None, indicating an error it already logged.
            log(f"call_local_llm_api returned None for request {request_id}. Marking as error.", level="WARNING")
            error_details_for_cm = {
                "message": "LLM call failed. Specific error logged by call_local_llm_api.",
                "type": "LLMCallFailed"
            }
            # response_content is already None, final_status remains "error"

    except Exception as e:
        # This catches unexpected errors within _execute_llm_call_threaded itself
        log(f"Unexpected error in _execute_llm_call_threaded for {request_id}: {e}", level="ERROR", exc_info=True)
        error_details_for_cm = {
            "message": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        response_content = None # Ensure response is None
        # final_status remains "error"
    
    finally:
        # Update _pending_llm_requests
        with _llm_lock:
            _pending_llm_requests[request_id] = {
                "status": final_status,
                "response": response_content,
                "error_details": error_details_for_cm, # Will be None if completed
                "original_prompt": prompt_messages,
                "model_used": model_name
            }

        # Notify ContextManager
        if _context_manager_instance:
            log_msg_ctx = "successfully completed" if final_status == "completed" else "errored"
            log(f"Notifying ContextManager about {log_msg_ctx} LLM request {request_id}", level="DEBUG")
            _context_manager_instance.notify_llm_response_received(
                request_id, response_content, model_name, prompt_messages, error_details_for_cm
            )


def call_local_llm_api_async(
    prompt_messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Initiates an LLM API call asynchronously.
    Returns a unique request_id.
    """
    request_id = f"llm_async_{uuid.uuid4().hex}"
    with _llm_lock:
        _pending_llm_requests[request_id] = {"status": "pending", "response": None, "error_details": None}

    thread = threading.Thread(
        target=_execute_llm_call_threaded,
        args=(request_id, prompt_messages, model_name),
        kwargs=kwargs,
        daemon=True, # Ensure thread doesn't block program exit
        name=f"LLMReq-{request_id[:8]}" # Add a descriptive name
    )
    thread.start()
    log(f"Started async LLM request {request_id} for model {model_name or config.LOCAL_LLM_DEFAULT_MODEL}", level="DEBUG")
    return request_id

def get_async_llm_response(request_id: str) -> Optional[Dict[str, Any]]:
    """
    Checks the status of an asynchronous LLM call.
    Returns:
        - Dict with current status if still pending (e.g., {"status": "pending", ...}).
        - Dict with "status" ('completed' or 'error'), "response" (str or None), "error_details" (dict or None) if finished.
          The entry is removed from _pending_llm_requests once fetched if not pending.
        - None if the request_id is invalid or not found.
    """
    with _llm_lock:
        request_details = _pending_llm_requests.get(request_id)
        if request_details:
            if request_details["status"] != "pending":
                return _pending_llm_requests.pop(request_id) # Return and remove if completed/error
            return request_details # Still pending, return current status
        return None # Request ID not found

def stage_simulated_llm_response(response_data: Any, is_plan: bool = False, error: Optional[str] = None) -> str:
    """
    Stages a simulated LLM response to be retrieved by get_async_llm_response.
    This allows simulated LLM calls to follow the same async pattern.
    """
    request_id = f"llm_sim_async_{uuid.uuid4().hex}"
    with _llm_lock:
        if error:
            _pending_llm_requests[request_id] = {"status": "error", "response": None, "error_details": {"message": error, "type": "SimulatedError"}}
        else:
            # For simulated plans, the LLMPlanner._parse_llm_response expects a string.
            # So, if it's a plan, we should json.dumps it.
            # If it's text, it's already a string.
            content_to_store = json.dumps(response_data) if is_plan and response_data is not None else response_data
            _pending_llm_requests[request_id] = {"status": "completed", "response": content_to_store, "error_details": None}
    
    log_message_type = "plan" if is_plan else "text"
    log_status = "error" if error else "completed"
    log(f"Staged simulated async LLM {log_message_type} response for {request_id}. Status: {log_status}", level="DEBUG")
    return request_id


# Example usage (for testing this module directly)
if __name__ == "__main__":
    if not config.LOCAL_LLM_API_BASE_URL or not config.LOCAL_LLM_DEFAULT_MODEL:
        print("Please set LOCAL_LLM_API_BASE_URL and LOCAL_LLM_DEFAULT_MODEL in config.py")
    else:
        print(f"Attempting to call local LLM: {config.LOCAL_LLM_DEFAULT_MODEL} at {config.LOCAL_LLM_API_BASE_URL}")
        test_messages = [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ]
        response_content = call_local_llm_api(test_messages, temperature=0.2)
        if response_content:
            print("\nLLM Response:\n", response_content)
        else:
            print("\nFailed to get response from LLM.")

        # Test async call
        print("\nAttempting ASYNC call...")
        async_request_id = call_local_llm_api_async(test_messages, temperature=0.3)
        print(f"Async request ID: {async_request_id}")

        for _ in range(10): # Poll for a few seconds
            import time
            time.sleep(1)
            status = get_async_llm_response(async_request_id)
            print(f"Polling status for {async_request_id}: {status}")
            if status and status.get("status") != "pending":
                if status.get("status") == "completed":
                    print("\nAsync LLM Response:\n", status.get("response"))
                else:
                    print("\nAsync LLM Error Details:\n", status.get("error_details"))
                break
        else:
            print(f"Async request {async_request_id} did not complete in time for this example.")

        # Test simulated async call
        print("\nAttempting SIMULATED ASYNC call...")
        sim_plan = [{"name": "simulated_step_1"}, {"name": "simulated_step_2"}]
        sim_request_id = stage_simulated_llm_response(sim_plan, is_plan=True)
        print(f"Simulated async request ID: {sim_request_id}")
        sim_status = get_async_llm_response(sim_request_id)
        print(f"Polling status for {sim_request_id}: {sim_status}")
        if sim_status and sim_status.get("status") == "completed":
            # For plans, the response will be a JSON string
            print("\nSimulated Async LLM Plan (JSON string):\n", sim_status.get("response"))
            print("\nParsed Plan:\n", json.loads(sim_status.get("response")))

"""
JSON-RPC utilities for MCP connector.

A bunch of helpful functions for working with JSON-RPC in our MCP connector.
This is our fallback implementation when the official libraries aren't available.
"""

import json
from typing import Any, Dict, Optional, Union

# Standard error codes from the JSON-RPC spec
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_ERROR_START = -32000
SERVER_ERROR_END = -32099

class JsonRpcError(Exception):
    """When JSON-RPC calls go wrong."""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC error {code}: {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Turn this error into a proper JSON-RPC error object."""
        error = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            error["data"] = self.data
        return error

def create_jsonrpc_request(method: str, params: Any, request_id: str = None) -> Dict[str, Any]:
    """
    Create a JSON-RPC 2.0 request object.
    
    Args:
        method: What method to call
        params: Any parameters to pass to the method
        request_id: ID to track this request (we'll make one if you don't)
        
    Returns:
        A JSON-RPC request object, ready to send
    """
    import time
    import uuid
    
    # Need an ID? No problem, we'll make one
    if request_id is None:
        request_id = f"{uuid.uuid4()}-{int(time.time())}"
    
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    }

def create_jsonrpc_response(result: Any, request_id: str) -> Dict[str, Any]:
    """
    Create a JSON-RPC 2.0 success response.
    
    Args:
        result: What the method returned
        request_id: ID from the request we're responding to
        
    Returns:
        A proper JSON-RPC response
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }

def create_jsonrpc_error_response(
    error_code: int, 
    error_message: str, 
    error_data: Any = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a JSON-RPC 2.0 error response when things go wrong.
    
    Args:
        error_code: Numeric code for this error type
        error_message: Human-readable explanation
        error_data: Any extra details about the error (optional)
        request_id: ID from the original request, if we know it
        
    Returns:
        A properly formatted JSON-RPC error response
    """
    error = {
        "code": error_code,
        "message": error_message
    }
    if error_data is not None:
        error["data"] = error_data
        
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error
    }

def parse_jsonrpc_response(
    response_text: str, 
    expected_id: Optional[str] = None
) -> Union[Dict[str, Any], JsonRpcError]:
    """
    Parse and validate a JSON-RPC response.
    
    Args:
        response_text: The raw response string to parse
        expected_id: ID we're expecting in the response (for validation)
        
    Returns:
        The parsed result or raises an exception if something's wrong
        
    Raises:
        JsonRpcError: If the response is invalid or contains an error
    """
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        raise JsonRpcError(
            PARSE_ERROR, 
            "Oops, couldn't parse the JSON response",
            response_text
        )
      # Make sure we got a proper object back
    if not isinstance(response, dict):
        raise JsonRpcError(
            INVALID_REQUEST, 
            "This doesn't look like a proper JSON-RPC response object",
            response
        )
    
    # Check for JSON-RPC 2.0 version marker
    if response.get("jsonrpc") != "2.0":
        raise JsonRpcError(
            INVALID_REQUEST, 
            "Missing the 'jsonrpc': '2.0' field - not a valid JSON-RPC response",
            response
        )
    
    # Make sure the ID matches what we're expecting
    if expected_id is not None and response.get("id") != expected_id:
        raise JsonRpcError(
            INVALID_REQUEST, 
            f"ID mismatch! Got '{response.get('id')}' but expected '{expected_id}'",
            response
        )
      # See if we got an error back
    if "error" in response:
        error = response["error"]
        if not isinstance(error, dict):
            raise JsonRpcError(
                INTERNAL_ERROR,
                "The error field isn't formatted right",
                response
            )
        
        code = error.get("code", INTERNAL_ERROR)
        message = error.get("message", "Something went wrong but the server didn't say what")
        data = error.get("data")
        
        raise JsonRpcError(code, message, data)
    
    # Make sure we at least got a result
    if "result" not in response:
        raise JsonRpcError(
            INVALID_REQUEST,
            "This response doesn't have either a 'result' or an 'error' - what gives?",
            response
        )
    
    # All good! Return the result
    return response["result"]

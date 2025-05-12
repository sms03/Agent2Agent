"""
JSON-RPC utilities for MCP connector.

This module provides helper functions for working with JSON-RPC in MCP tools.
"""

import json
from typing import Any, Dict, Optional, Union

# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_ERROR_START = -32000
SERVER_ERROR_END = -32099

class JsonRpcError(Exception):
    """Exception raised for JSON-RPC errors."""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC error {code}: {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to a JSON-RPC error object."""
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
        method: The method to call
        params: The parameters for the method call
        request_id: Optional request ID (will be generated if None)
        
    Returns:
        A JSON-RPC request object
    """
    import time
    import uuid
    
    # Generate a unique ID if not provided
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
    Create a JSON-RPC 2.0 success response object.
    
    Args:
        result: The result of the method call
        request_id: The request ID to match
        
    Returns:
        A JSON-RPC response object
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
    Create a JSON-RPC 2.0 error response object.
    
    Args:
        error_code: The error code
        error_message: The error message
        error_data: Optional error data
        request_id: The request ID to match (or None if unknown)
        
    Returns:
        A JSON-RPC error response object
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
    Parse a JSON-RPC response and validate it.
    
    Args:
        response_text: The response text to parse
        expected_id: Optional expected request ID
        
    Returns:
        The parsed response result or raises JsonRpcError
        
    Raises:
        JsonRpcError: If the response is not valid or contains an error
    """
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError:
        raise JsonRpcError(
            PARSE_ERROR, 
            "Response is not valid JSON",
            response_text
        )
    
    # Validate the response structure
    if not isinstance(response, dict):
        raise JsonRpcError(
            INVALID_REQUEST, 
            "Response is not a JSON object",
            response
        )
    
    if response.get("jsonrpc") != "2.0":
        raise JsonRpcError(
            INVALID_REQUEST, 
            "Response is missing 'jsonrpc': '2.0' field",
            response
        )
    
    # Check for matching ID if expected_id is provided
    if expected_id is not None and response.get("id") != expected_id:
        raise JsonRpcError(
            INVALID_REQUEST, 
            f"Response ID '{response.get('id')}' does not match request ID '{expected_id}'",
            response
        )
    
    # Check for error response
    if "error" in response:
        error = response["error"]
        if not isinstance(error, dict):
            raise JsonRpcError(
                INTERNAL_ERROR,
                "Error field is not an object",
                response
            )
        
        code = error.get("code", INTERNAL_ERROR)
        message = error.get("message", "Unknown error")
        data = error.get("data")
        
        raise JsonRpcError(code, message, data)
    
    # Check for result
    if "result" not in response:
        raise JsonRpcError(
            INVALID_REQUEST,
            "Response is missing both 'result' and 'error' fields",
            response
        )
    
    return response["result"]

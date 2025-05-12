"""
JSON-RPC verification script for MCP implementation.

This script demonstrates how to verify your MCP tool's JSON-RPC implementation
by sending properly formatted requests and validating responses.
"""

import argparse
import json
import logging
import os
import sys
import requests
import uuid

# Add the parent directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import our JSON-RPC utilities
from jsonrpc_utils import (
    create_jsonrpc_request,
    parse_jsonrpc_response,
    JsonRpcError,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class MCP_Tool_Validator:
    """Class to validate MCP tool JSON-RPC implementation."""
    
    def __init__(self, url):
        """Initialize the validator with the MCP tool URL."""
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        self.error_count = 0
        self.success_count = 0
    
    def send_request(self, method, params, request_id=None):
        """Send a JSON-RPC request to the MCP tool."""
        # Create a JSON-RPC request
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        request = create_jsonrpc_request(method, params, request_id)
        
        # Log the request
        logger.info(f"Sending JSON-RPC request to {self.url}:")
        logger.info(json.dumps(request, indent=2))
        
        # Send the request
        try:
            response = requests.post(
                self.url,
                json=request,
                headers=self.headers,
                timeout=30
            )
            
            # Check the HTTP status code
            if response.status_code >= 400:
                logger.error(f"❌ HTTP error: {response.status_code}")
                self.error_count += 1
                return False, None
            
            # Parse the response
            try:
                json_response = response.json()
                
                # Log the raw response
                logger.info("Raw JSON-RPC response:")
                logger.info(json.dumps(json_response, indent=2))
                
                # Basic validation of the response structure
                validated = self.validate_jsonrpc_response(json_response, request_id)
                if validated:
                    self.success_count += 1
                    return True, json_response
                else:
                    self.error_count += 1
                    return False, json_response
                
            except json.JSONDecodeError:
                logger.error("❌ Invalid JSON response")
                logger.error(response.text)
                self.error_count += 1
                return False, None
                
        except requests.RequestException as e:
            logger.error(f"❌ Request error: {e}")
            self.error_count += 1
            return False, None
    
    def validate_jsonrpc_response(self, response, request_id):
        """Validate a JSON-RPC response."""
        valid = True
        
        # Check if the response is a JSON object
        if not isinstance(response, dict):
            logger.error("❌ Response is not a JSON object")
            return False
        
        # Check for jsonrpc field
        if "jsonrpc" not in response:
            logger.error("❌ Response is missing 'jsonrpc' field")
            valid = False
        elif response["jsonrpc"] != "2.0":
            logger.error(f"❌ Invalid 'jsonrpc' value: {response['jsonrpc']}")
            valid = False
        
        # Check for id field
        if "id" not in response:
            logger.error("❌ Response is missing 'id' field")
            valid = False
        elif response["id"] != request_id:
            logger.error(f"❌ Response ID {response['id']} does not match request ID {request_id}")
            valid = False
        
        # Check for result or error field
        if "result" not in response and "error" not in response:
            logger.error("❌ Response is missing both 'result' and 'error' fields")
            valid = False
        elif "result" in response and "error" in response:
            logger.error("❌ Response contains both 'result' and 'error' fields")
            valid = False
        
        # If there's an error, validate the error structure
        if "error" in response:
            error = response["error"]
            if not isinstance(error, dict):
                logger.error("❌ Error field is not a JSON object")
                valid = False
            else:
                if "code" not in error:
                    logger.error("❌ Error is missing 'code' field")
                    valid = False
                if "message" not in error:
                    logger.error("❌ Error is missing 'message' field")
                    valid = False
        
        if valid:
            logger.info("✅ Response format is valid JSON-RPC 2.0")
        
        return valid
    
    def test_ping(self):
        """Test the ping method."""
        logger.info("\n=== Testing 'ping' method ===")
        success, response = self.send_request("ping", {}, "ping-test")
        if success:
            logger.info("✅ Ping test passed")
        else:
            logger.warning("⚠️ Ping test failed or not supported")
        return success
    
    def test_execute_text(self):
        """Test the execute method with text input."""
        logger.info("\n=== Testing 'execute' method with text input ===")
        params = {"text": "Hello, world!"}
        success, response = self.send_request("execute", params, "execute-text-test")
        if success:
            logger.info("✅ Execute test with text input passed")
        else:
            logger.error("❌ Execute test with text input failed")
        return success
    
    def test_execute_complex(self):
        """Test the execute method with complex parameters."""
        logger.info("\n=== Testing 'execute' method with complex parameters ===")
        params = {
            "query": "complex query",
            "options": {
                "limit": 5,
                "format": "json",
                "filters": ["filter1", "filter2"]
            }
        }
        success, response = self.send_request("execute", params, "execute-complex-test")
        if success:
            logger.info("✅ Execute test with complex parameters passed")
        else:
            logger.error("❌ Execute test with complex parameters failed")
        return success
    
    def test_invalid_method(self):
        """Test an invalid method to verify error handling."""
        logger.info("\n=== Testing invalid method ===")
        success, response = self.send_request("invalid_method", {}, "invalid-method-test")
        
        # For this test, we expect an error (Method not found)
        if not success and response and "error" in response:
            error = response["error"]
            if "code" in error and error["code"] == METHOD_NOT_FOUND:
                logger.info("✅ Invalid method test passed (received proper error)")
                self.success_count += 1  # Override the earlier count
                self.error_count -= 1
                return True
        
        logger.warning("⚠️ Invalid method test failed (did not receive proper error)")
        return False
    
    def run_all_tests(self):
        """Run all tests and report results."""
        logger.info("\n=== Starting MCP Tool JSON-RPC Validation ===")
        logger.info(f"Target URL: {self.url}")
        
        # Run all tests
        ping_result = self.test_ping()
        execute_text_result = self.test_execute_text()
        execute_complex_result = self.test_execute_complex()
        invalid_method_result = self.test_invalid_method()
        
        # Report results
        logger.info("\n=== Summary ===")
        logger.info(f"Successful tests: {self.success_count}")
        logger.info(f"Failed tests: {self.error_count}")
        
        all_passed = ping_result and execute_text_result and execute_complex_result and invalid_method_result
        if all_passed:
            logger.info("✅ All tests passed! Your MCP tool implements JSON-RPC 2.0 correctly.")
        else:
            logger.warning("⚠️ Some tests failed. Your MCP tool may not fully implement JSON-RPC 2.0.")
        
        return all_passed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate MCP tool JSON-RPC implementation")
    parser.add_argument("url", help="URL of the MCP tool to validate")
    parser.add_argument("--skip-ping", action="store_true", help="Skip the ping test")
    
    args = parser.parse_args()
    
    validator = MCP_Tool_Validator(args.url)
    validator.run_all_tests()

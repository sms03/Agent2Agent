"""
End-to-end test for the A2A-MCP connector with JSON-RPC.
This script tests the entire flow by:
1. Starting a mock MCP server
2. Starting the A2A-MCP connector
3. Registering the mock server with the connector
4. Calling the mock server through the connector
"""

import subprocess
import time
import sys
import os
import json
import requests
import argparse
import logging
import signal
import uuid
from pathlib import Path

# Add the current directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# Import our JSON-RPC utilities
from jsonrpc_utils import (
    create_jsonrpc_request,
    parse_jsonrpc_response,
    JsonRpcError
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestFailure(Exception):
    """Exception raised when a test fails."""
    pass

def start_mock_server(port, host="localhost"):
    """Start the mock MCP server as a subprocess."""
    logger.info(f"Starting mock MCP server on {host}:{port}")
    try:
        mock_server_path = os.path.join(script_dir, "mock_mcp_server.py")
        process = subprocess.Popen(
            [sys.executable, mock_server_path, "--host", host, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Wait briefly to ensure the server starts
        time.sleep(2)
        
        # Check if the server is running and responding
        try:
            # Send a ping request to verify the server is running
            ping_request = create_jsonrpc_request(
                method="ping",
                params={},
                request_id="startup-test"
            )
            response = requests.post(
                f"http://{host}:{port}",
                json=ping_request, 
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"Mock MCP server started successfully on {host}:{port}")
                return process
            else:
                logger.error(f"Mock server returned status code {response.status_code}")
                process.terminate()
                return None
        except requests.RequestException as e:
            logger.error(f"Could not connect to mock server: {e}")
            process.terminate()
            return None
            
    except Exception as e:
        logger.error(f"Failed to start mock server: {e}")
        return None

def start_a2a_mcp_connector(port, host="localhost"):
    """Start the A2A-MCP connector as a subprocess."""
    logger.info(f"Starting A2A-MCP connector on {host}:{port}")
    
    # For this test, we'll create a temporary registry file
    temp_registry = os.path.join(script_dir, f"test_registry_{uuid.uuid4()}.json")
    
    try:
        # Prepare environment variables for the connector
        env = os.environ.copy()
        env["MCP_REGISTRY_PATH"] = temp_registry
        
        # For testing, we would need either GOOGLE_API_KEY or VertexAI config
        # If not set in real environment, we'll use a placeholder for testing
        if "GOOGLE_API_KEY" not in env and "GOOGLE_GENAI_USE_VERTEXAI" not in env:
            logger.warning("No LLM credentials found, using placeholder for testing")
            env["GOOGLE_API_KEY"] = "placeholder_for_testing_only"
        
        # Start the connector using the agent.py script directly for testing
        connector_path = os.path.join(script_dir, "agent.py")
        process = subprocess.Popen(
            [sys.executable, connector_path, "--host", host, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for the connector to start
        time.sleep(5)
        
        # Simplified check - just try to access the agent card
        try:
            response = requests.get(f"http://{host}:{port}/.well-known/agent.json", timeout=5)
            if response.status_code == 200:
                logger.info(f"A2A-MCP connector started successfully on {host}:{port}")
                return process, temp_registry
            else:
                logger.error(f"Connector returned status code {response.status_code}")
                process.terminate()
                return None, temp_registry
        except requests.RequestException as e:
            logger.error(f"Could not connect to A2A-MCP connector: {e}")
            process.terminate()
            return None, temp_registry
            
    except Exception as e:
        logger.error(f"Failed to start A2A-MCP connector: {e}")
        return None, temp_registry

def register_mock_tool(connector_host, connector_port, mock_host, mock_port):
    """Register the mock MCP server with the connector using direct HTTP calls."""
    logger.info(f"Registering mock tool with connector")
    
    mock_url = f"http://{mock_host}:{mock_port}"
    tool_id = f"mock-tool-{uuid.uuid4().hex[:8]}"
    tool_description = "Mock MCP tool for testing JSON-RPC implementation"
    
    # In a real A2A protocol flow, this would be done through proper A2A messages
    # For testing purposes, we'll use the connector's HTTP API directly
    
    # This is a simplified version that directly calls the endpoint
    register_url = f"http://{connector_host}:{connector_port}/register_tool"
    payload = {
        "tool_id": tool_id,
        "tool_url": mock_url,
        "tool_description": tool_description
    }
    
    try:
        response = requests.post(register_url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                logger.info(f"Successfully registered mock tool with ID: {tool_id}")
                return tool_id
            else:
                logger.error(f"Failed to register tool: {result.get('message', 'Unknown error')}")
                return None
        else:
            logger.error(f"Failed to register tool, status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Network error registering tool: {e}")
        return None

def call_mock_tool(connector_host, connector_port, tool_id, input_text):
    """Call the mock tool through the connector using direct HTTP calls."""
    logger.info(f"Calling mock tool through connector")
    
    # Again, in a real A2A flow, this would be through proper A2A messages
    # For testing, we use the HTTP API directly
    
    call_url = f"http://{connector_host}:{connector_port}/call_tool"
    payload = {
        "tool_id": tool_id,
        "input": input_text
    }
    
    try:
        response = requests.post(call_url, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Tool call result: {result}")
            return result
        else:
            logger.error(f"Failed to call tool, status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Network error calling tool: {e}")
        return None

def direct_jsonrpc_test(mock_host, mock_port):
    """Test direct JSON-RPC communication with the mock server."""
    logger.info("Testing direct JSON-RPC communication with mock server")
    
    # Create a JSON-RPC request
    test_text = "Hello from direct JSON-RPC test"
    request_id = f"direct-test-{uuid.uuid4().hex[:8]}"
    jsonrpc_request = create_jsonrpc_request(
        method="execute",
        params={"text": test_text},
        request_id=request_id
    )
    
    try:
        # Send the request directly to the mock server
        mock_url = f"http://{mock_host}:{mock_port}"
        headers = {"Content-Type": "application/json"}
        response = requests.post(mock_url, json=jsonrpc_request, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Mock server returned status code {response.status_code}")
            return False
        
        # Parse and validate the JSON-RPC response
        try:
            result = parse_jsonrpc_response(response.text, request_id)
            logger.info(f"Direct JSON-RPC test successful: {result}")
            return True
        except JsonRpcError as e:
            logger.error(f"JSON-RPC error in direct test: {e}")
            return False
    except requests.RequestException as e:
        logger.error(f"Network error in direct test: {e}")
        return False

def cleanup(processes, temp_files=None):
    """Clean up subprocesses and temporary files."""
    for process in processes:
        if process and process.poll() is None:
            logger.info(f"Terminating process {process.pid}")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {process.pid} did not terminate, killing")
                process.kill()
    
    # Clean up temporary files
    if temp_files:
        for file_path in temp_files:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not remove temporary file {file_path}: {e}")

def run_test(mock_port, connector_port, mock_host="localhost", connector_host="localhost"):
    """Run the end-to-end test."""
    processes = []
    temp_files = []
    
    try:
        # Start the mock server
        logger.info("=== STEP 1: Starting mock MCP server ===")
        mock_process = start_mock_server(mock_port, mock_host)
        if not mock_process:
            raise TestFailure("Failed to start mock MCP server")
        processes.append(mock_process)
        
        # Test direct JSON-RPC communication with the mock server
        logger.info("=== STEP 2: Testing direct JSON-RPC communication ===")
        if not direct_jsonrpc_test(mock_host, mock_port):
            raise TestFailure("Direct JSON-RPC test failed")
        
        # Start the A2A-MCP connector
        logger.info("=== STEP 3: Starting A2A-MCP connector ===")
        connector_result = start_a2a_mcp_connector(connector_port, connector_host)
        if not connector_result or not connector_result[0]:
            raise TestFailure("Failed to start A2A-MCP connector")
        connector_process, temp_registry = connector_result
        processes.append(connector_process)
        if temp_registry:
            temp_files.append(temp_registry)
        
        # Register the mock tool
        logger.info("=== STEP 4: Registering mock tool with connector ===")
        tool_id = register_mock_tool(connector_host, connector_port, mock_host, mock_port)
        if not tool_id:
            raise TestFailure("Failed to register mock tool with connector")
        
        # Call the mock tool
        logger.info("=== STEP 5: Calling mock tool through connector ===")
        test_input = "Hello, JSON-RPC world!"
        result = call_mock_tool(connector_host, connector_port, tool_id, test_input)
        if not result or result.get("status") != "success":
            error_msg = result.get("message") if result else "No response"
            raise TestFailure(f"Failed to call mock tool: {error_msg}")
        
        # Validate the result
        tool_result = result.get("result")
        if not tool_result or "answer" not in tool_result:
            raise TestFailure(f"Invalid tool response format: {tool_result}")
        
        logger.info(f"✅ Tool returned expected response format: {tool_result}")
        logger.info("✅ All tests passed successfully!")
        return True
    
    except TestFailure as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return False
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False
    
    finally:
        # Clean up
        cleanup(processes, temp_files)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run end-to-end test for A2A-MCP connector with JSON-RPC")
    parser.add_argument("--mock-host", default="localhost", help="Host for mock MCP server")
    parser.add_argument("--mock-port", type=int, default=8500, help="Port for mock MCP server")
    parser.add_argument("--connector-host", default="localhost", help="Host for A2A-MCP connector")
    parser.add_argument("--connector-port", type=int, default=10004, help="Port for A2A-MCP connector")
    
    args = parser.parse_args()
    
    # Execute test
    logger.info("")
    logger.info("======================================================")
    logger.info("  A2A-MCP Connector JSON-RPC End-to-End Test")
    logger.info("======================================================")
    logger.info("")
    logger.info("This test verifies the complete flow of:")
    logger.info("1. Mock MCP server with JSON-RPC support")
    logger.info("2. A2A-MCP connector JSON-RPC implementation")
    logger.info("3. Tool registration and validation")
    logger.info("4. Tool execution with proper JSON-RPC formatting")
    logger.info("")
    
    success = run_test(
        args.mock_port, 
        args.connector_port,
        args.mock_host,
        args.connector_host
    )
    
    sys.exit(0 if success else 1)

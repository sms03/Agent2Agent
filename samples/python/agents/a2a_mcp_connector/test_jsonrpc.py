"""
Test script for MCP tool JSON-RPC implementation.
This script can be used to test the JSON-RPC implementation of the A2A-MCP connector.
"""

import json
import requests
import argparse
import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our JSON-RPC utilities
from jsonrpc_utils import (
    create_jsonrpc_request, 
    parse_jsonrpc_response, 
    JsonRpcError
)

def test_mcp_jsonrpc(url, method, params):
    """Test an MCP tool with JSON-RPC."""
    # Create a JSON-RPC request
    request_id = "test-1"
    jsonrpc_request = create_jsonrpc_request(method, params, request_id)
    
    # Send the request
    print(f"Sending JSON-RPC request to {url}:")
    print(json.dumps(jsonrpc_request, indent=2))
    print("\n")
    
    response = requests.post(
        url,
        json=jsonrpc_request,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    # Print the response
    print(f"Response status code: {response.status_code}")
    
    if response.status_code >= 400:
        print(f"❌ HTTP error: {response.status_code}")
        try:
            # Try to parse as JSON anyway, might contain error details
            error_details = response.json()
            print(json.dumps(error_details, indent=2))
        except:
            print(response.text)
        return
    
    try:
        # Parse the response as JSON
        json_response = response.json()
        print("JSON-RPC response:")
        print(json.dumps(json_response, indent=2))
        
        # Validate the response
        if "jsonrpc" not in json_response or json_response["jsonrpc"] != "2.0":
            print("\n⚠️ Warning: Response is missing 'jsonrpc': '2.0' field")
        
        if "id" not in json_response or json_response["id"] != request_id:
            print(f"\n⚠️ Warning: Response has incorrect or missing 'id' field")
            print(f"  Expected: {request_id}")
            print(f"  Received: {json_response.get('id', 'missing')}")
        
        if "error" in json_response:
            print("\n❌ JSON-RPC error received:")
            print(f"  Code: {json_response['error'].get('code', 'unknown')}")
            print(f"  Message: {json_response['error'].get('message', 'unknown')}")
            if "data" in json_response["error"]:
                print(f"  Data: {json_response['error']['data']}")
        elif "result" in json_response:
            print("\n✅ JSON-RPC success response received")
        else:
            print("\n⚠️ Warning: Response is missing both 'result' and 'error' fields")
            
    except json.JSONDecodeError:
        print("Non-JSON response:")
        print(response.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test an MCP tool with JSON-RPC")
    parser.add_argument("url", help="URL of the MCP tool")
    parser.add_argument("--method", default="execute", help="JSON-RPC method to call")
    parser.add_argument("--text", help="Text input for the tool")
    parser.add_argument("--params", help="JSON-formatted parameters for the tool")
    
    args = parser.parse_args()
    
    # Process parameters
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            print("Error: --params must be valid JSON")
            exit(1)
    elif args.text:
        params = {"text": args.text}
    else:
        params = {}
    
    test_mcp_jsonrpc(args.url, args.method, params)

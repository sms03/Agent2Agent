# A2A-MCP Connector Agent

A simple agent that connects Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP) with ease, providing an intuitive and easy-to-use interface. Built with Google ADK (Agent Development Kit).

## Features

- **Easy MCP Tool Registration**: Register MCP tools with a simple interface
- **Tool Discovery**: List and discover registered MCP tools
- **Unified Access**: Call any registered MCP tool through a consistent interface
- **A2A-Compatible**: Fully compliant with the A2A protocol for seamless interoperability
- **Streaming Support**: Provides streaming updates during task processing
- **Persistent Tool Registry**: Tools can be saved to disk and loaded on restart
- **Real MCP Integration**: Actually connects to and calls MCP tools
- **Browser-Friendly Interface**: Helpful web UI when accessed via browser

## Architecture

This agent serves as a bridge between A2A and MCP protocols:

```
User/Agent <--> A2A Protocol <--> A2A-MCP Connector <--> MCP Protocol <--> MCP Tools
```

The connector implements the [Model Context Protocol (MCP)](https://github.com/microsoft/model-context-protocol) using JSON-RPC 2.0 for communicating with MCP tools.

### JSON-RPC Implementation

All communication with MCP tools follows the JSON-RPC 2.0 specification:

- **Requests**: All requests to MCP tools are properly formatted JSON-RPC 2.0 requests
  ```json
  {
    "jsonrpc": "2.0",
    "id": "unique-request-id",
    "method": "execute",
    "params": {
      "text": "Your input text",
      "additional_parameter": "value"
    }
  }
  ```

- **Responses**: All responses from MCP tools must follow JSON-RPC 2.0 format
  ```json
  {
    "jsonrpc": "2.0",
    "id": "unique-request-id",
    "result": {
      "answer": "Tool response",
      "metadata": {
        "tool_name": "example-tool",
        "version": "1.0.0"
      }
    }
  }
  ```

- **Error Handling**: JSON-RPC errors are properly handled
  ```json
  {
    "jsonrpc": "2.0",
    "id": "unique-request-id",
    "error": {
      "code": -32601,
      "message": "Method not found",
      "data": {
        "details": "Additional error information"
      }
    }
  }
  ```

## Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an LLM (Google Gemini API or Vertex AI)

## Setup & Running

1. Navigate to the agent directory:
   ```bash
   cd samples/python/agents/a2a_mcp_connector
   ```

2. Create an environment file with your API key:

   **Option A: Google AI Studio API Key**
   ```bash
   echo "GOOGLE_API_KEY=your_api_key_here" > .env
   ```

   **Option B: Google Cloud Vertex AI**
   ```bash
   echo "GOOGLE_GENAI_USE_VERTEXAI=TRUE" > .env
   echo "GOOGLE_CLOUD_PROJECT=your_project_id" >> .env
   echo "GOOGLE_CLOUD_LOCATION=your_location" >> .env
   ```
   Note: Ensure you've authenticated with gcloud using `gcloud auth login` first.
   
3. (Optional) Specify a custom path for the tool registry:
   ```bash
   echo "MCP_REGISTRY_PATH=/path/to/my_registry.json" >> .env
   ```

4. Run the agent:
   ```bash
   # Basic run on default port 10004
   uv run .
   
   # On custom host/port
   uv run . --host 0.0.0.0 --port 8080
   
   # To suppress hardlink warnings
   uv run . --link-mode=copy
   ```

   Note: If you see warnings about hardlinks, you can suppress them by using the `--link-mode=copy` flag
   or by setting the environment variable: `$env:UV_LINK_MODE="copy"` (Windows) or 
   `export UV_LINK_MODE=copy` (Linux/macOS).

5. After starting the agent:
   - The Agent Card will be available at: `http://localhost:10004/.well-known/agent.json`
   - Accessing `http://localhost:10004` in a browser will show a helpful landing page
   - A2A protocol interactions should be sent as POST requests to the root endpoint

6. In a new terminal, start an A2A client to interact with the agent:

   **Option A: Command Line**
   ```bash
   cd samples/python/hosts/cli
   uv run . --agent http://localhost:10004
   ```

   **Option B: Demo Web UI**
   ```bash
   cd demo/ui
   echo "GOOGLE_API_KEY=your_api_key_here" > .env
   uv run main.py
   ```
   
   Then navigate to the web UI (typically http://localhost:12000):
   - Click the 'Agents' tab
   - Add the Remote Agent
   - Enter the Agent URL: localhost:10004 (or whatever custom host/port)
   - Click the 'Home' tab (Conversations)
   - Create and start a conversation to test the interaction

## Troubleshooting

If you encounter any of these issues, here are solutions:

### 405 Method Not Allowed
This is expected when accessing the agent via a browser with a GET request. The agent now shows a helpful landing page instead of an error.

## Troubleshooting

### Import or Module Errors
The agent includes proper package structure for ADK compatibility:
- Make sure you're running the agent from the correct directory
- If you modify the code, ensure the imports maintain proper paths

### Hardlink Warnings
These are just informational messages and won't affect functionality. Use `--link-mode=copy` to suppress them.

### JSON-RPC Errors
If you're experiencing issues with MCP tool communication:
- Ensure your tool is correctly implementing the JSON-RPC 2.0 protocol
- Check that responses include the required `jsonrpc: "2.0"` field
- Verify that the response `id` matches the request `id`
- Make sure responses include either a `result` object (success) or an `error` object (failure)
- Use the `test_jsonrpc.py` script to validate your tool's implementation

### Network and CORS Issues
If you encounter CORS or network errors:
- Ensure your MCP tool allows requests from the connector's domain
- Check firewall settings and network connectivity 
- Verify the URL format includes http:// or https://

## Testing

### Validating Your MCP Tool Implementation

You can use the included test scripts to verify your MCP tool's JSON-RPC implementation:

#### Basic JSON-RPC Testing
```bash
python test_jsonrpc.py http://your-mcp-tool-url.com --text "Test query"
```

For more complex parameters:
```bash
python test_jsonrpc.py http://your-mcp-tool-url.com --params '{"query": "test", "options": {"limit": 5}}'
```

#### Comprehensive MCP Tool Validation
```bash
python validate_mcp_jsonrpc.py http://your-mcp-tool-url.com
```
This script runs a series of tests to verify that your MCP tool correctly implements the JSON-RPC 2.0 protocol, including:
- Testing the `ping` method
- Testing the `execute` method with text input
- Testing the `execute` method with complex parameters
- Testing error handling for invalid methods

### Using the Mock MCP Server

For development and testing, you can use the included mock MCP server:

```bash
# Start the mock server
python mock_mcp_server.py --port 8500

# In another terminal, test it
python test_jsonrpc.py http://localhost:8500 --text "Hello, world!"

# Register it with the A2A-MCP connector
# (after starting the A2A-MCP connector)
```

### Running End-to-End Tests

A simplified end-to-end test script is provided for testing the full flow:

```bash
python test_e2e.py
```

This script demonstrates:
1. Starting the mock MCP server
2. Starting the A2A-MCP connector
3. Registering the mock server with the connector
4. Calling the mock server through the connector

Note: This is a simplified test that simulates some interactions.

## Example Usage

### Registering an MCP Tool

```
Register a new MCP tool with ID "weather-tool" at URL "http://weather-api.example.com/mcp" for checking weather forecasts
```

### Listing Available Tools

```
List all registered MCP tools
```

### Calling an MCP Tool

```
Use the weather-tool to check the forecast for New York
```

### Removing an MCP Tool

```
Remove the weather-tool from the registry
```

## MCP Tool Implementation Guide

To create an MCP-compatible tool that can be used with this connector, your service should:

1. Expose an HTTP endpoint that accepts POST requests
2. Implement the JSON-RPC 2.0 protocol
3. Accept properly formatted JSON-RPC requests and return JSON-RPC responses

### JSON-RPC Format

The connector follows the JSON-RPC 2.0 specification:

**Request Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "method": "execute",
  "params": {
    "text": "User query or structured data"
    // Or any other parameters your tool expects
  }
}
```

**Successful Response Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "answer": "Tool response data",
    "metadata": {
      "tool_name": "example-tool",
      "version": "1.0.0"
    }
  }
}
```

**Error Response Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "error": {
    "code": -32000,
    "message": "Error description",
    "data": {
      "additional": "error details"
    }
  }
}
```

## Technical Implementation

- **Google ADK Integration**: Built with Google's Agent Development Kit
- **Streaming Support**: Provides incremental updates during processing
- **A2A Protocol Integration**: Full compliance with A2A specifications
- **MCP Tool Registry**: In-memory registry of MCP tools with metadata
- **Persistent Storage**: Option to save tool registry to disk
- **JSON-RPC Protocol**: Uses JSON-RPC 2.0 for communicating with MCP tools
- **Web Interface**: Helpful landing page when accessed via browser

### JSON-RPC Implementation Details
The A2A-MCP connector uses the JSON-RPC 2.0 protocol for all MCP tool communication:

1. **JSON-RPC Request Creation**: 
   - All requests follow the JSON-RPC 2.0 specification
   - Unique request IDs are generated for each request
   - The standard `execute` method is used for tool execution

2. **Response Handling**:
   - Responses are validated against the JSON-RPC 2.0 specification
   - Error responses are properly parsed and handled
   - Response IDs are verified to match request IDs

3. **Utilities**:
   - The `jsonrpc_utils.py` module provides helper functions for JSON-RPC operations
   - Standard error codes and message formats are implemented

### Testing Tools
Several testing tools are provided to help validate your MCP tools:

1. **JSON-RPC Test Script** (`test_jsonrpc.py`):
   - Tests direct communication with MCP tools
   - Validates JSON-RPC compliance
   - Provides detailed feedback on response format

2. **Mock MCP Server** (`mock_mcp_server.py`):
   - Implements a simple MCP tool with JSON-RPC support
   - Useful for testing the connector without external dependencies
   - Can be extended for more complex testing scenarios

3. **End-to-End Test** (`test_e2e.py`):
   - Tests the complete flow from connector to MCP tool and back
   - Simulates registration and tool calling
   - Validates the entire integration

## Limitations

- Basic authentication support for MCP tools
- Tool validation is minimal (just checks URL availability)
- Limited error handling for complex MCP tool failures

## Recent Updates

### JSON-RPC 2.0 Protocol Integration
The A2A-MCP connector has been updated to fully support JSON-RPC 2.0 for MCP tool communication:

- **Proper Request Format**: All requests to MCP tools now follow the JSON-RPC 2.0 specification
- **Response Validation**: Responses are now validated against the JSON-RPC 2.0 specification
- **Error Handling**: JSON-RPC error responses are properly parsed and handled
- **Testing Tools**: New tools for testing JSON-RPC implementation (test scripts, mock server, etc.)
- **Documentation**: Updated documentation with JSON-RPC details and examples

### New Files
- `jsonrpc_utils.py`: Utility functions for JSON-RPC operations
- `test_jsonrpc.py`: Script for testing MCP tool JSON-RPC implementation
- `mock_mcp_server.py`: A simple mock MCP server for testing
- `test_e2e.py`: End-to-end test script for the full flow

## Learn More

- [A2A Protocol Documentation](https://google.github.io/A2A/#/documentation)
- [Model Context Protocol (MCP)](https://google.github.io/A2A/#/topics/a2a_and_mcp)
- [Google ADK Documentation](https://github.com/google/A2A/tree/main/samples/python/agents/google_adk)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
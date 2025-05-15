"""
A2A-MCP Connector Agent implementation.

This agent serves as a bridge between A2A (Agent-to-Agent) protocol and MCP (Model Context Protocol),
providing an intuitive interface for connecting to and using MCP tools through A2A.

The agent properly implements MCP client functionality by:
1. Maintaining persistent connections to MCP servers
2. Correctly distinguishing between MCP servers and the tools they provide
3. Using official MCP client libraries when available
4. Accurately representing the relationship between A2A and MCP in an agent system
"""

import json
import logging
import asyncio
import os
import sys
import time
import uuid
from typing import Any, AsyncIterable, Dict, List, Optional

# Add the parent directory to the Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from base_agent import AgentWithTaskManager

# Import our MCP Connection Manager for proper MCP server management
from mcp_connection_manager import MCPConnectionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP connection manager for server and tool management
mcp_manager = MCPConnectionManager()

# Optional path to save MCP server registry
REGISTRY_PATH = os.getenv("MCP_REGISTRY_PATH", "mcp_servers_registry.json")

def load_registry():
    """Load the MCP server registry from disk if available."""
    mcp_manager.set_registry_path(REGISTRY_PATH)
    if mcp_manager.load_registry():
        logger.info(f"Loaded MCP server registry from {REGISTRY_PATH}")
    else:
        logger.info(f"No MCP server registry found at {REGISTRY_PATH} or failed to load")

def save_registry():
    """Save the MCP server registry to disk."""
    if mcp_manager.save_registry():
        logger.info(f"Saved MCP server registry to {REGISTRY_PATH}")
    else:
        logger.error(f"Failed to save MCP server registry to {REGISTRY_PATH}")

async def register_mcp_server(server_id: str, server_url: str, server_description: str, transport_type: str = "jsonrpc", **kwargs) -> Dict[str, Any]:
    """
    Register an MCP server with the connector.
    
    Args:
        server_id (str): Unique identifier for the MCP server
        server_url (str): URL endpoint for the MCP server
        server_description (str): Description of what the server does
        transport_type (str): The transport mechanism to use ("jsonrpc", "sse", "stdio")
        **kwargs: Additional parameters for specific transport types
        
    Returns:
        Dict[str, Any]: Registration status and server information
    """
    # Validate URL format for HTTP-based transports
    if transport_type in ["jsonrpc", "sse"]:
        if not server_url.startswith(("http://", "https://")):
            return {"status": "error", "message": f"Invalid URL format: {server_url}. URL must start with http:// or https://"}
    
    # For STDIO transport, ensure we have a command
    if transport_type == "stdio":
        command = kwargs.get("command", "")
        if not command:
            return {"status": "error", "message": "STDIO transport requires a 'command' parameter"}
    
    # Use the connection manager to register the server
    result = await mcp_manager.register_server(
        server_id=server_id,
        server_url=server_url,
        server_description=server_description,
        transport_type=transport_type,
        **kwargs
    )
    
    return result

def list_mcp_servers() -> Dict[str, Any]:
    """
    List all registered MCP servers.
    
    Returns:
        Dict[str, Any]: Dictionary containing all registered servers
    """
    return mcp_manager.list_servers()

def list_mcp_tools() -> Dict[str, Any]:
    """
    List all available MCP tools across all servers.
    
    Returns:
        Dict[str, Any]: Dictionary containing all available tools
    """
    return mcp_manager.list_tools()

async def call_mcp_tool(tool_id: str, input_data: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Call an MCP tool with the given input data.
    
    Args:
        tool_id (str): The ID of the MCP tool to call
        input_data (str): The input data for the MCP tool (JSON string or plain text)
        tool_context (ToolContext): The context in which the tool operates
        
    Returns:
        Dict[str, Any]: Results from the MCP tool call
    """
    # Let the user know we're processing
    tool_context.actions.thinking(f"Calling MCP tool: {tool_id}")
    
    # Parse input data - could be JSON string or plain text
    try:
        if input_data.strip().startswith('{'):
            parsed_input = json.loads(input_data)
        else:
            # Plain text becomes the 'text' field in parameters
            parsed_input = {"text": input_data}
    except json.JSONDecodeError:
        # Not valid JSON, use as plain text
        parsed_input = {"text": input_data}
    
    # Execute the tool using the connection manager
    result = await mcp_manager.execute_tool(tool_id, parsed_input)
    
    return result

async def remove_mcp_server(server_id: str) -> Dict[str, Any]:
    """
    Remove a registered MCP server.
    
    Args:
        server_id (str): The ID of the MCP server to remove
        
    Returns:
        Dict[str, Any]: Removal status
    """
    result = await mcp_manager.remove_server(server_id)
    
    return result

async def remove_mcp_tool(tool_id: str) -> Dict[str, Any]:
    """
    Remove a registered MCP tool.
    
    Args:
        tool_id (str): The ID of the MCP tool to remove
        
    Returns:
        Dict[str, Any]: Removal status
    """
    result = await mcp_manager.remove_tool(tool_id)
    
    return result


class A2AMCPConnectorAgent(AgentWithTaskManager):
    """An agent that connects A2A and MCP protocols with an intuitive interface."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain", "application/json"]

    def __init__(self):
        # Load any existing MCP server registry
        load_registry()
        
        self._agent = self._build_agent()
        self._user_id = "mcp_connector_agent"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        
    async def cleanup(self):
        """
        Clean up resources when the agent is shutting down.
        Ensures all MCP server connections are properly closed.
        """
        logger.info("Cleaning up A2A-MCP Connector Agent resources...")
        try:
            # Close all server connections
            await mcp_manager.close_all_connections()
            logger.info("Successfully closed all MCP server connections")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
    async def __aenter__(self):
        """Support for async context manager."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure cleanup is called when used as async context manager."""
        await self.cleanup()

    def get_processing_message(self) -> str:
        """Message displayed while processing user request."""
        return "Processing your request with the A2A-MCP connector..."

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the A2A-MCP connector."""
        return LlmAgent(
            model="gemini-2.0-flash-001",
            name="a2a_mcp_connector",
            description=(
                "A connector agent that bridges A2A and MCP protocols, "
                "allowing easy registration and interaction with MCP servers and tools."
            ),            
            instruction="""
            You are an A2A-MCP Connector Agent, designed to make it easy for users to register and interact with 
            MCP (Model Context Protocol) servers and tools through the A2A (Agent-to-Agent) protocol.
            
            You can help users with the following tasks:
            
            1. Register MCP servers by providing:
                - server_id: Unique identifier for the server
                - server_url: URL endpoint for the server
                - server_description: What the server does
                - transport_type: How to communicate with the server ("jsonrpc", "sse", or "stdio")
                - Additional parameters depending on transport type
            
            2. List all registered MCP servers using list_mcp_servers()
            
            3. List all available MCP tools across all servers using list_mcp_tools()
            
            4. Call MCP tools with specific input data using call_mcp_tool()
            
            5. Remove MCP servers using remove_mcp_server()
            
            6. Remove specific MCP tools using remove_mcp_tool()
            
            When a user requests to register a new MCP server:
            - Ask for the server ID, URL, description, and transport type if not provided
            - For STDIO transport, ask for the command to execute
            - Use register_mcp_server() to register the server
            - Confirm the successful registration
            
            When a user asks to use or call an MCP tool:
            - Check if the tool is available using list_mcp_tools()
            - If not available, suggest registering the appropriate server first
            - If available, use call_mcp_tool() to invoke the tool with the user's input
            - Return the results to the user
            
            Always be helpful and explain the steps involved in working with MCP servers and tools.
            Provide clear instructions for how to use the available functions.
            
            IMPORTANT CONCEPTS TO EXPLAIN IF ASKED:
            
            A2A (Agent-to-Agent) Protocol:
            - A standardized way for AI agents to communicate with each other
            - Provides a common interface for agent discovery and task delegation
            - Enables interoperability between different agent frameworks and vendors
            
            MCP (Model Context Protocol):
            - A protocol for structuring tool interactions with AI models
            - Allows models to call external tools and use their results
            - Standardizes the format for tool inputs and outputs
            - Tools are provided by MCP servers that can use different transport mechanisms:
                - JSON-RPC: Direct HTTP-based communication
                - SSE: Server-Sent Events for streaming responses
                - STDIO: Standard input/output for local tools
            
            In your role, you bridge these protocols by:
            1. Exposing an A2A interface for other agents to communicate with you
            2. Managing persistent connections to MCP-compatible servers
            3. Simplifying the process of discovering and using MCP tools
            4. Properly handling connection lifecycle and error cases
            """,
            tools=[
                register_mcp_server,
                list_mcp_servers,
                list_mcp_tools,
                call_mcp_tool,
                remove_mcp_server,
                remove_mcp_tool,
            ],
        )


async def main():
    """Run the agent as a standalone A2A task manager."""
    from common.task_manager import run_task_manager
    from common.types import TaskManagerCapabilities
    
    agent = A2AMCPConnectorAgent()
    try:
        await run_task_manager(
            agent,
            capabilities=TaskManagerCapabilities(
                description=agent._agent.description,
                tool_descriptions=[str(t) for t in agent._agent.tools],
                content_types=agent.SUPPORTED_CONTENT_TYPES,
            ),
        )
    finally:
        # Ensure connections are properly closed on shutdown
        await agent.cleanup()

if __name__ == "__main__":
    # Run the A2A-MCP connector agent
    asyncio.run(main())

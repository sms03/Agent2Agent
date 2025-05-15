"""
A2A-MCP Connector Agent implementation.

Hey there! This agent bridges A2A (Agent-to-Agent) protocol with MCP (Model Context Protocol).
It gives you a nice, clean interface for hooking up MCP tools through the A2A protocol.

In a nutshell, this agent:
1. Keeps persistent connections to MCP servers (no reconnecting for every tool call!)
2. Knows the difference between MCP servers and the tools they provide
3. Uses the official MCP client libraries when it can find them
4. Represents the A2A-MCP relationship the way it should be
"""

import json
import logging
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

# Add the parent directory to the Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

# Google ADK imports - these handle the agent functionality
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import our base agent that handles the A2A task management
from base_agent import AgentWithTaskManager

# Here's where the magic happens - our MCP connection manager
from mcp_connection_manager import MCPConnectionManager

# Set up some basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fire up our connection manager - this is what keeps track of all our MCP servers
mcp_manager = MCPConnectionManager()

# Where should we save our server registry? Check env vars first, fall back to default
REGISTRY_PATH = os.getenv("MCP_REGISTRY_PATH", "mcp_servers_registry.json")

def load_registry():
    """Try to load our saved MCP servers from disk."""
    mcp_manager.set_registry_path(REGISTRY_PATH)
    if mcp_manager.load_registry():
        logger.info(f"Found and loaded server registry from {REGISTRY_PATH}")
    else:
        logger.info(f"No registry found at {REGISTRY_PATH} - we'll create a new one when needed")

def save_registry():
    """Save our MCP server registry to disk so we don't lose it."""
    if mcp_manager.save_registry():
        logger.info(f"Saved all our MCP servers to {REGISTRY_PATH}")
    else:
        logger.error(f"Dang, couldn't save the registry to {REGISTRY_PATH}")

async def register_mcp_server(server_id: str, server_url: str, server_description: str, transport_type: str = "jsonrpc", **kwargs) -> Dict[str, Any]:
    """
    Register a new MCP server with our connector.
    
    Args:
        server_id: What we'll call this server (like "weather-api" or "google-search")
        server_url: Where to find the server (URL or path)
        server_description: What this server does, in plain English
        transport_type: How to talk to it ("jsonrpc", "sse", or "stdio")
        **kwargs: Any extra params the specific transport needs
        
    Returns:
        Dict with status and server info (or error message if it failed)
    """
    # Check the URL format for HTTP-based servers
    if transport_type in ["jsonrpc", "sse"]:
        if not server_url.startswith(("http://", "https://")):
            return {"status": "error", "message": f"That URL ({server_url}) doesn't look right. Need http:// or https://"}
      # For STDIO transport, we need a command to run
    if transport_type == "stdio":
        command = kwargs.get("command", "")
        if not command:
            return {"status": "error", "message": "For STDIO transport, I need a 'command' parameter"}
    
    # Let the connection manager handle the registration
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
    Get a list of all the MCP servers we have registered.
    
    Returns:
        Dict with all our registered servers
    """
    return mcp_manager.list_servers()

def list_mcp_tools() -> Dict[str, Any]:
    """
    Get a list of all available MCP tools across all servers.
    
    Returns:
        Dict with all available tools
    """
    return mcp_manager.list_tools()

async def call_mcp_tool(tool_id: str, input_data: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Call an MCP tool and get the results back.
    
    Args:
        tool_id: Which tool to call (must be a registered tool ID)
        input_data: What to send to the tool (JSON or plain text)
        tool_context: Execution context for tracking progress
        
    Returns:
        Dict with the tool's response
    """
    # Let the user know we're working on it
    tool_context.actions.thinking(f"Calling MCP tool: {tool_id}")
    
    # Figure out if input is JSON or plain text
    try:
        if input_data.strip().startswith('{'):
            # Looks like JSON, let's parse it
            parsed_input = json.loads(input_data)
        else:
            # Just regular text - we'll wrap it in a 'text' field
            parsed_input = {"text": input_data}
    except json.JSONDecodeError:
        # JSON parsing blew up - just treat it as plain text
        parsed_input = {"text": input_data}
    
    # Hand it off to our connection manager to do the actual work
    result = await mcp_manager.execute_tool(tool_id, parsed_input)
    
    return result

async def remove_mcp_server(server_id: str) -> Dict[str, Any]:
    """
    Kick a server off our registry.
    
    Args:
        server_id: The ID of the server to remove
        
    Returns:
        Dict with removal status
    """
    result = await mcp_manager.remove_server(server_id)
    
    return result

async def remove_mcp_tool(tool_id: str) -> Dict[str, Any]:
    """
    Remove a tool from our available tools list.
    
    Args:
        tool_id: The ID of the tool to remove
        
    Returns:
        Dict with removal status
    """
    result = await mcp_manager.remove_tool(tool_id)
    
    return result


class A2AMCPConnectorAgent(AgentWithTaskManager):
    """The main agent that bridges A2A with MCP - giving you all the tools!"""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain", "application/json"]   
    def __init__(self):
        # Let's load any servers we saved previously
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
        Clean up all our resources when shutting down.
        Makes sure we don't leave any dangling connections.
        """
        logger.info("Cleaning up A2A-MCP Connector Agent...")
        try:
            # Close all our connections to MCP servers
            await mcp_manager.close_all_connections()
            logger.info("All MCP connections closed cleanly")
        except Exception as e:
            logger.error(f"Ugh, ran into a problem during cleanup: {e}")
            
    async def __aenter__(self):
        """Support for async context manager."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context manager."""
        await self.cleanup()

    def get_processing_message(self) -> str:
        """What to show users while we're working."""
        return "Working on your request with A2A-MCP connector..."

    def _build_agent(self) -> LlmAgent:
        """Set up our LLM agent with all the right settings."""
        return LlmAgent(
            model="gemini-2.0-flash-001",
            name="a2a_mcp_connector",
            description=(
                "A friendly connector that bridges A2A and MCP protocols, "
                "making it super easy to use MCP servers and tools."
            ),            
            instruction="""
            Hey there! You're an A2A-MCP Connector Agent, here to help users connect to and use 
            MCP (Model Context Protocol) servers and tools through A2A.
            
            You can help folks with:
            
            1. Setting up MCP servers by asking for:
                - server_id: What to call this server (like "weather-api")
                - server_url: Where to find it (URL or path)
                - server_description: What it does, in plain language
                - transport_type: How to talk to it ("jsonrpc", "sse", or "stdio")                - Extra parameters that might be needed based on transport type
            
            2. Getting a list of all the servers you've set up with list_mcp_servers()
            
            3. Seeing all the tools you can use across all servers with list_mcp_tools()
            
            4. Using any MCP tool by calling call_mcp_tool() with your input
            
            5. Removing servers you don't need anymore with remove_mcp_server()
            
            6. Removing specific tools with remove_mcp_tool()
            
            When someone wants to add a new MCP server:
            - Ask for what they want to call it, where it is, what it does, and how to talk to it
            - For STDIO servers, make sure to get the command to run
            - Use register_mcp_server() to set everything up
            - Let them know if it worked or not
            
            When someone wants to use an MCP tool:
            - Check if we have that tool registered
            - If not, suggest they register the right server first
            - If we have it, use call_mcp_tool() to run it with their input
            - Show them what the tool returned
            
            Be friendly and walk people through how everything works - no jargon!
            Keep it simple and explain what each function does in plain English.
            
            KEY CONCEPTS TO EXPLAIN (if they ask):
              A2A (Agent-to-Agent) Protocol:
            - Think of this as a common language that lets AI assistants talk to each other
            - It's like a shared playbook for how agents can discover each other and hand off tasks
            - Makes it possible for agents from different companies and systems to work together
            
            MCP (Model Context Protocol):
            - A way to structure how tools work with AI models
            - Lets models reach out to external tools and use what they return
            - Makes tool inputs and outputs follow a consistent pattern
            - Tools come from MCP servers that can communicate in different ways:
                - JSON-RPC: Web-based back-and-forth (most common)
                - SSE: For when the server needs to stream results bit by bit
                - STDIO: For running local tools on your machine
            
            Your job is to connect these worlds by:
            1. Speaking A2A so other agents can talk to you
            2. Keeping solid connections to MCP servers so tools are always ready
            3. Making it dead simple to find and use MCP tools
            4. Handling all the boring connection stuff and error cases
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
    """Start up the agent as a standalone task manager."""
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
        # Make sure we clean up our connections when shutting down
        await agent.cleanup()

if __name__ == "__main__":
    # Fire up the A2A-MCP connector agent
    asyncio.run(main())

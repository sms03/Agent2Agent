"""
MCP Connection Manager Module.

This module keeps track of all your MCP servers and the connections to them.
It handles all the nitty-gritty details like connection types, error handling,
and keeping things running smoothly.
"""

import logging
import asyncio
import json
import uuid
import requests
from typing import Dict, Any, Optional, Tuple, List, Callable
from contextlib import AsyncExitStack

# Set up logging so we can see what's going on
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the official MCP client libraries if they're installed
try:
    from mcp.client.sse import sse_client, SseServerParameters
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.jsonrpc import ClientSession, JsonRpcServerParameters
    from mcp import ClientSession as BaseClientSession
    HAS_MCP_CLIENTS = True
except ImportError:
    logging.warning("Couldn't find the official MCP client libraries - we'll use our own JSON-RPC code instead.")
    HAS_MCP_CLIENTS = False
    # Fall back to our custom JSON-RPC implementation
    from jsonrpc_utils import (
        create_jsonrpc_request,
        parse_jsonrpc_response,
        JsonRpcError,
        INTERNAL_ERROR
    )

class MCPConnectionError(Exception):
    """Something went wrong with an MCP connection."""
    pass

class MCPServerConnection:
    """
    Manages a connection to a single MCP server.
    
    This class handles all the connection stuff for an MCP server,
    from setup to cleanup and everything in between.
    """
    def __init__(self, 
                server_id: str, 
                server_url: str, 
                transport_type: str = "jsonrpc", 
                exit_stack: Optional[AsyncExitStack] = None,
                **kwargs):
        """
        Set up a new connection to an MCP server.
        
        Args:
            server_id: What we'll call this server
            server_url: Where to find this server
            transport_type: How to talk to it ("jsonrpc", "sse", "stdio")
            exit_stack: Helper for cleanup (optional)
            **kwargs: Any extra settings needed for this server type
        """
        self.server_id = server_id
        self.server_url = server_url
        self.transport_type = transport_type.lower()
        self.connection_params = kwargs
        self.available_tools = []  # We'll fill this with tools later
        self.session = None
        self.connection_active = False
        self.exit_stack = exit_stack or AsyncExitStack()
        self.managed_exit_stack = exit_stack is None  # Are we managing our own stack?
        
        # For async connections, we'll need these        self.reader = None
        self.writer = None
        
        # For STDIO transport, grab the command details
        if self.transport_type == "stdio":
            self.command = kwargs.get("command", "")
            self.args = kwargs.get("args", [])
            self.env = kwargs.get("env", None)
        
        logger.info(f"Set up a new MCP server connection: {server_id} using {transport_type}")
    
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            True if we connected successfully, False if something went wrong
        """
        if self.connection_active:
            logger.info(f"We're already connected to {self.server_id}")
            return True
            
        try:
            if self.transport_type == "jsonrpc":
                # JSON-RPC is the most common type - handle with official client if available
                if HAS_MCP_CLIENTS:
                    # Sweet! We have the official client library
                    server_params = JsonRpcServerParameters(
                        url=self.server_url,
                        headers=self.connection_params.get("headers", {})
                    )
                    # Set up the session with our exit stack for cleanup
                    self.session = await self.exit_stack.enter_async_context(ClientSession(server_params))
                    # Initialize the session
                    await self.session.initialize()
                    # List available tools
                    await self._list_tools()
                    self.connection_active = True
                    return True
                else:
                    # Fallback to direct HTTP request
                    ping_request = create_jsonrpc_request(
                        method="ping",
                        params={},
                        request_id=f"{self.server_id}-ping"
                    )
                    
                    headers = {"Content-Type": "application/json"}
                    headers.update(self.connection_params.get("headers", {}))
                    
                    response = requests.post(
                        self.server_url,
                        json=ping_request,
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code >= 400:
                        logger.error(f"MCP server {self.server_id} returned HTTP error: {response.status_code}")
                        return False
                        
                    # Try to parse as JSON-RPC response
                    try:
                        json_response = response.json()
                        if "jsonrpc" not in json_response or json_response["jsonrpc"] != "2.0":
                            logger.warning(f"MCP server {self.server_id} doesn't return valid JSON-RPC 2.0 responses")
                        
                        # List available tools
                        await self._list_tools_direct()
                        
                        # Connection is active even if we get an error response
                        self.connection_active = True
                        return True
                    except json.JSONDecodeError:
                        logger.warning(f"MCP server {self.server_id} didn't return valid JSON")
                        return False
            
            elif self.transport_type == "sse":
                if not HAS_MCP_CLIENTS:
                    logger.error(f"SSE transport requires MCP client libraries")
                    return False
                    
                # For SSE, we establish a connection and initialize the session
                server_params = SseServerParameters(
                    url=self.server_url,
                    headers=self.connection_params.get("headers", {})
                )
                
                # Connect to the MCP server using SSE client
                transport = await self.exit_stack.enter_async_context(sse_client(server_params))
                self.reader, self.writer = transport
                self.session = await self.exit_stack.enter_async_context(ClientSession(self.reader, self.writer))
                
                # Initialize the connection
                await self.session.initialize()
                
                # List available tools
                await self._list_tools()
                
                self.connection_active = True
                return True
                
            elif self.transport_type == "stdio":
                if not HAS_MCP_CLIENTS:
                    logger.error(f"STDIO transport requires MCP client libraries")
                    return False
                    
                # For STDIO, we need the command to execute
                if not self.command:
                    logger.error(f"STDIO transport requires a command parameter")
                    return False
                    
                # Create server parameters
                server_params = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env=self.env
                )
                
                # Connect to the MCP server using STDIO client
                transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
                self.reader, self.writer = transport
                self.session = await self.exit_stack.enter_async_context(ClientSession(self.reader, self.writer))
                
                # Initialize the connection
                await self.session.initialize()
                
                # List available tools
                await self._list_tools()
                
                self.connection_active = True
                return True
                
            else:
                logger.error(f"Unsupported transport type: {self.transport_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to MCP server {self.server_id}: {e}")
            await self.disconnect()
            return False
    
    async def _list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools on the MCP server.
        
        Returns:
            List of available tools
        """
        if not self.session:
            logger.error(f"No active session for MCP server {self.server_id}")
            return []
            
        try:
            # Call the tools/list method
            tools_result = await self.session.call_method("tools/list", {})
            
            # Store and return the tools
            self.available_tools = tools_result.get("tools", [])
            logger.info(f"MCP server {self.server_id} has {len(self.available_tools)} tools available")
            return self.available_tools
            
        except Exception as e:
            logger.error(f"Error listing tools on MCP server {self.server_id}: {e}")
            return []

    async def _list_tools_direct(self) -> List[Dict[str, Any]]:
        """
        List available tools on the MCP server using direct JSON-RPC.
        
        Returns:
            List of available tools
        """
        try:
            # Create a request to list tools
            request_id = f"{self.server_id}-list-tools-{uuid.uuid4()}"
            list_request = create_jsonrpc_request(
                method="tools/list",
                params={},
                request_id=request_id
            )
            
            headers = {"Content-Type": "application/json"}
            headers.update(self.connection_params.get("headers", {}))
            
            response = requests.post(
                self.server_url,
                json=list_request,
                headers=headers,
                timeout=10
            )
            
            if response.status_code >= 400:
                logger.error(f"MCP server {self.server_id} returned HTTP error: {response.status_code}")
                return []
                
            # Parse the response
            try:
                result = parse_jsonrpc_response(response.text, request_id)
                self.available_tools = result.get("tools", [])
                logger.info(f"MCP server {self.server_id} has {len(self.available_tools)} tools available")
                return self.available_tools
            except JsonRpcError as e:
                logger.error(f"Error listing tools on MCP server {self.server_id}: {e}")
                return []
            except json.JSONDecodeError:
                logger.error(f"MCP server {self.server_id} returned invalid JSON")
                return []
                
        except Exception as e:
            logger.error(f"Error listing tools on MCP server {self.server_id}: {e}")
            return []
    
    async def execute_tool(self, tool_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool on the MCP server.
        
        Args:
            tool_id: ID of the tool to execute
            input_data: Input data for the tool
            
        Returns:
            Tool execution result
        """
        if not self.connection_active:
            logger.info(f"Connection to MCP server {self.server_id} not active, attempting to connect")
            if not await self.connect():
                return {
                    "status": "error",
                    "message": f"Failed to connect to MCP server {self.server_id}"
                }
        
        try:
            if self.transport_type == "jsonrpc" and not HAS_MCP_CLIENTS:
                # For JSON-RPC without MCP clients, use direct HTTP request
                return await self._execute_tool_json_rpc_direct(tool_id, input_data)
            elif self.session:
                # For SSE, STDIO, or JSON-RPC with MCP clients, use the session
                return await self._execute_tool_with_session(tool_id, input_data)
            else:
                return {
                    "status": "error",
                    "message": f"No active session for MCP server {self.server_id}"
                }
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_id} on MCP server {self.server_id}: {e}")
            return {
                "status": "error",
                "message": f"Error executing tool: {str(e)}"
            }
    
    async def _execute_tool_json_rpc_direct(self, tool_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool using direct JSON-RPC over HTTP.
        
        Args:
            tool_id: ID of the tool to execute
            input_data: Input data for the tool
            
        Returns:
            Tool execution result
        """
        # Create a unique request ID
        request_id = f"{self.server_id}-{tool_id}-{uuid.uuid4()}"
        
        # Create a proper JSON-RPC 2.0 request
        jsonrpc_request = create_jsonrpc_request(
            method="execute",  # Standard method name for MCP tool execution
            params={
                "name": tool_id,
                "input": input_data
            },
            request_id=request_id
        )
        
        try:
            # Make the request to the MCP service using JSON-RPC protocol
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                self.server_url,
                json=jsonrpc_request,
                headers=headers,
                timeout=30
            )
            
            # Log the response status
            logger.info(f"MCP server {self.server_id} tool {tool_id} returned status code {response.status_code}")
            
            # Handle successful HTTP response (note: might still contain a JSON-RPC error)
            if response.status_code < 400:
                try:
                    # Parse and validate the JSON-RPC response
                    result = parse_jsonrpc_response(response.text, request_id)
                    
                    # If we get here, the response is valid and contains a result
                    return {
                        "status": "success",
                        "tool_id": tool_id,
                        "result": result.get("output", result)  # Try to get output field, fallback to full result
                    }
                except JsonRpcError as e:
                    # Handle JSON-RPC error
                    return {
                        "status": "error",
                        "tool_id": tool_id,
                        "message": f"MCP tool returned JSON-RPC error: {e.message}",
                        "code": e.code,
                        "details": e.data
                    }
                except json.JSONDecodeError:
                    # Response is not valid JSON
                    return {
                        "status": "error",
                        "tool_id": tool_id,
                        "message": "MCP tool returned invalid JSON",
                        "details": response.text
                    }
            else:
                # Handle HTTP error response
                try:
                    error_details = response.json()
                except json.JSONDecodeError:
                    error_details = response.text
                    
                return {
                    "status": "error",
                    "tool_id": tool_id,
                    "message": f"MCP tool returned HTTP error code {response.status_code}",
                    "details": error_details
                }
        except Exception as e:
            logger.error(f"Error calling MCP tool: {e}")
            return {
                "status": "error",
                "tool_id": tool_id,
                "message": f"Error calling MCP tool: {str(e)}"
            }
    
    async def _execute_tool_with_session(self, tool_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool using the MCP client session.
        
        Args:
            tool_id: ID of the tool to execute
            input_data: Input data for the tool
            
        Returns:
            Tool execution result
        """
        if not self.session:
            return {
                "status": "error",
                "message": f"No active session for MCP server {self.server_id}"
            }
        
        try:
            # Execute the tool - handle both newer and older MCP client APIs
            try:
                # Try newer MCP client API first (v1.2.0+)
                result = await self.session.call_tool(tool_id, input_data)
                
                # Extract the output - for newer MCP clients the result has a content attribute
                if hasattr(result, 'content'):
                    output = result.content
                else:
                    output = result  # Fallback
            except AttributeError:
                # Fallback to older MCP client API or custom implementation
                exec_result = await self.session.call_method("tools/execute", {
                    "name": tool_id,
                    "input": input_data
                })
                output = exec_result.get("output", {})
            
            return {
                "status": "success",
                "tool_id": tool_id,
                "result": output
            }
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_id} with session: {e}")
            return {
                "status": "error",
                "tool_id": tool_id,
                "message": f"Error executing tool with session: {str(e)}"
            }
    
    async def disconnect(self) -> None:
        """
        Disconnect from the MCP server.
        """
        try:
            # For MCP clients, cleanup contexts
            if self.connection_active:
                logger.info(f"Disconnecting from MCP server {self.server_id}")
                
                # Clean up exit stack if we created our own
                if self.managed_exit_stack:
                    await self.exit_stack.aclose()
                
                # Mark the connection as inactive
                self.connection_active = False
                self.session = None
                self.reader = None
                self.writer = None
                
                logger.info(f"Disconnected from MCP server {self.server_id}")
                
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server {self.server_id}: {e}")
            # Mark as inactive even if there was an error
            self.connection_active = False

class MCPConnectionManager:
    """
    Your one-stop shop for managing multiple MCP servers.
    
    This class keeps track of all your MCP connections and gives you
    a simple way to use MCP tools, following the best practices from
    both the MCP spec and Google ADK's MCPToolset approach.
    """
    
    def __init__(self):
        """Set up our connection manager."""
        self.servers = {}  # All our server connections
        self.tool_to_server_map = {}  # Maps tool IDs to server IDs
        self.exit_stack = AsyncExitStack()  # For clean resource management
        
        # Where we'll save our server info
        self.registry_path = None
    
    def set_registry_path(self, path: str) -> None:
        """
        Tell us where to save our server registry.
        
        Args:
            path: Path to save the registry file
        """
        self.registry_path = path
    def load_registry(self, path: Optional[str] = None) -> bool:
        """
        Load our saved servers from disk.
        
        Args:
            path: Where to load from (optional - uses previously set path if not given)
            
        Returns:
            True if we loaded successfully, False if something went wrong
        """
        if path:
            self.registry_path = path
            
        if not self.registry_path:
            logger.warning("Hey, I need a registry path before I can load anything!")
            return False
            
        try:
            import os
            if os.path.exists(self.registry_path):
                with open(self.registry_path, 'r') as f:
                    registry_data = json.load(f)
                    
                    # Start fresh
                    self.servers = {}
                    self.tool_to_server_map = {}
                    
                    # Recreate all our server connections
                    for server_id, server_data in registry_data.get("servers", {}).items():
                        # Make a new connection object for each server
                        self.servers[server_id] = MCPServerConnection(
                            server_id=server_id,
                            server_url=server_data.get("url", ""),
                            transport_type=server_data.get("transport_type", "jsonrpc"),
                            exit_stack=self.exit_stack,
                            **server_data.get("connection_params", {})
                        )
                    
                    # Restore the tool-to-server mappings
                    self.tool_to_server_map = registry_data.get("tool_mappings", {})
                    logger.info(f"Successfully loaded {len(self.servers)} servers and {len(self.tool_to_server_map)} tools")
                    return True
            else:
                logger.info(f"Couldn't find a registry file at {self.registry_path}")
                return False
        except Exception as e:
            logger.error(f"Oops! Problem loading the registry: {e}")
            return False
    
    def save_registry(self) -> bool:
        """
        Save all our server info to disk so we can load it later.
        
        Returns:
            True if saved successfully, False if something went wrong
        """
        if not self.registry_path:
            logger.warning("I need a registry path before I can save anything!")
            return False
            
        try:
            # Get our data ready to save
            registry_data = {
                "servers": {},
                "tool_mappings": self.tool_to_server_map
            }
            
            # Collect info about each server
            for server_id, server in self.servers.items():
                registry_data["servers"][server_id] = {
                    "url": server.server_url,
                    "transport_type": server.transport_type,
                    "connection_params": server.connection_params
                }
            
            # Save to file
            with open(self.registry_path, 'w') as f:
                json.dump(registry_data, f, indent=2)
                
            logger.info(f"Saved {len(self.servers)} MCP servers and {len(self.tool_to_server_map)} tool mappings to registry")
            return True
        except Exception as e:
            logger.error(f"Error saving MCP server registry: {e}")
            return False
    async def register_server(self, server_id: str, server_url: str, 
                             server_description: str = "", 
                             transport_type: str = "jsonrpc", 
                             **kwargs) -> Dict[str, Any]:
        """
        Add a new MCP server to our collection.
        
        Args:
            server_id: What to call this server
            server_url: Where to find it
            server_description: What this server does
            transport_type: How to talk to it (jsonrpc, sse, stdio)
            **kwargs: Any extra settings needed for this server
            
        Returns:
            Info about whether the registration worked
        """
        # Already have this one?
        if server_id in self.servers:
            return {
                "status": "already_exists", 
                "message": f"We already have a server called '{server_id}'"
            }
        
        # Create a new connection to this server
        server = MCPServerConnection(
            server_id=server_id,
            server_url=server_url,
            transport_type=transport_type,
            exit_stack=self.exit_stack,
            **kwargs
        )
        
        # Try connecting to make sure it's working
        connection_success = await server.connect()
        if not connection_success:
            return {
                "status": "error",
                "message": f"Couldn't reach the server at {server_url} - is it running?"
            }
        
        # All good! Add it to our collection
        self.servers[server_id] = server
        
        # Add all the tools this server provides
        if server.available_tools:
            for tool in server.available_tools:
                tool_id = tool.get("name")
                if tool_id:
                    self.tool_to_server_map[tool_id] = server_id
        
        # Save the updated registry
        if self.registry_path:
            self.save_registry()
        
        return {
            "status": "success",
            "server": {
                "id": server_id,
                "url": server_url,
                "description": server_description,
                "transport_type": transport_type,
                "tools": len(server.available_tools)
            }
        }
    
    def list_servers(self) -> Dict[str, Any]:
        """
        List all registered MCP servers.
        
        Returns:
            Dictionary containing all registered servers
        """
        server_list = []
        
        for server_id, server in self.servers.items():
            server_info = {
                "id": server_id,
                "url": server.server_url,
                "transport_type": server.transport_type,
                "active": server.connection_active,
                "tools": len(server.available_tools)
            }
            server_list.append(server_info)
        
        return {"servers": server_list}
    
    def list_tools(self) -> Dict[str, Any]:
        """
        List all tools available across all servers.
        
        Returns:
            Dictionary containing all available tools
        """
        tools_list = []
        
        for tool_id, server_id in self.tool_to_server_map.items():
            # Skip if the server no longer exists
            if server_id not in self.servers:
                continue
                
            server = self.servers[server_id]
            
            # Look up the tool details in the server's available tools
            tool_details = None
            for tool in server.available_tools:
                if tool.get("name") == tool_id:
                    tool_details = tool
                    break
            
            # Add basic info if details not available
            if not tool_details:
                tool_details = {
                    "name": tool_id,
                    "description": f"Tool on server {server_id}"
                }
                
            # Add server info to the tool details
            tool_info = {
                **tool_details,
                "server_id": server_id,
                "transport_type": server.transport_type
            }
            
            tools_list.append(tool_info)
        
        return {"tools": tools_list}
    
    async def register_tool(self, tool_id: str, server_id: str) -> Dict[str, Any]:
        """
        Register a tool with a specific server.
        
        Args:
            tool_id: ID of the tool to register
            server_id: ID of the server that provides the tool
            
        Returns:
            Registration status
        """
        # Check if the server exists
        if server_id not in self.servers:
            return {
                "status": "error",
                "message": f"Server '{server_id}' is not registered"
            }
        
        # Add the tool mapping
        self.tool_to_server_map[tool_id] = server_id
        
        # Save the updated registry
        if self.registry_path:
            self.save_registry()
        
        return {
            "status": "success",
            "message": f"Tool '{tool_id}' registered with server '{server_id}'"
        }
    
    async def execute_tool(self, tool_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool on its associated server.
        
        Args:
            tool_id: ID of the tool to execute
            input_data: Input data for the tool
            
        Returns:
            Tool execution result
        """
        # Check if the tool is registered
        if tool_id not in self.tool_to_server_map:
            return {
                "status": "error",
                "message": f"Tool '{tool_id}' is not registered with any server"
            }
        
        # Get the server ID
        server_id = self.tool_to_server_map[tool_id]
        
        # Check if the server exists
        if server_id not in self.servers:
            return {
                "status": "error",
                "message": f"Server '{server_id}' for tool '{tool_id}' is not registered"
            }
        
        # Get the server
        server = self.servers[server_id]
        
        # Execute the tool
        result = await server.execute_tool(tool_id, input_data)
        
        return result
    
    async def remove_server(self, server_id: str) -> Dict[str, Any]:
        """
        Remove a registered MCP server.
        
        Args:
            server_id: ID of the server to remove
            
        Returns:
            Removal status
        """
        # Check if the server exists
        if server_id not in self.servers:
            return {
                "status": "error",
                "message": f"Server '{server_id}' is not registered"
            }
        
        # Get the server
        server = self.servers[server_id]
        
        # Disconnect from the server
        await server.disconnect()
        
        # Remove the server
        removed_server = self.servers.pop(server_id)
        
        # Remove all tools associated with this server
        tools_removed = []
        for tool_id, s_id in list(self.tool_to_server_map.items()):
            if s_id == server_id:
                self.tool_to_server_map.pop(tool_id)
                tools_removed.append(tool_id)
        
        # Save the updated registry
        if self.registry_path:
            self.save_registry()
        
        return {
            "status": "success",
            "message": f"Successfully removed server '{server_id}'",
            "removed_server": {
                "id": server_id,
                "url": removed_server.server_url,
                "transport_type": removed_server.transport_type
            },
            "removed_tools": tools_removed
        }
    
    async def remove_tool(self, tool_id: str) -> Dict[str, Any]:
        """
        Remove a registered tool.
        
        Args:
            tool_id: ID of the tool to remove
            
        Returns:
            Removal status
        """
        # Check if the tool is registered
        if tool_id not in self.tool_to_server_map:
            return {
                "status": "error",
                "message": f"Tool '{tool_id}' is not registered"
            }
        
        # Get the server ID
        server_id = self.tool_to_server_map.pop(tool_id)
        
        # Save the updated registry
        if self.registry_path:
            self.save_registry()
        
        return {
            "status": "success",
            "message": f"Successfully removed tool '{tool_id}'",
            "removed_tool": {
                "id": tool_id,
                "server_id": server_id
            }
        }
    
    async def disconnect_all(self) -> None:
        """
        Disconnect from all MCP servers.
        """
        logger.info("Disconnecting from all MCP servers...")
        await self.exit_stack.aclose()
        logger.info("All MCP server connections closed")
        
    async def close_all_connections(self) -> None:
        """
        Close all connections to MCP servers and cleanup resources.
        This is an alias for disconnect_all for consistent naming in the agent.
        """
        await self.disconnect_all()

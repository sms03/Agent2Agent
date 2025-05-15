# A2A-MCP Connector Architecture

This document outlines the architecture of the A2A-MCP Connector agent, focusing on best practices for implementing MCP client functionality within an A2A-compatible agent.

## Key Components

The A2A-MCP Connector consists of these core components:

1. **Agent**: The main entry point, providing A2A compatibility and user interaction
2. **Connection Manager**: Handles persistent connections to MCP servers 
3. **Server Connection**: Manages the lifecycle of a connection to a specific MCP server
4. **Registry**: Stores information about registered servers and tools

## Architecture Diagram

```
┌───────────────────────────────┐
│     A2A-MCP Connector Agent   │
│  ┌─────────────────────────┐  │
│  │      Agent Interface    │  │
│  │                         │  │
│  │  - register_mcp_server  │  │
│  │  - list_mcp_servers     │  │
│  │  - list_mcp_tools       │  │
│  │  - call_mcp_tool        │  │
│  │  - etc...               │  │
│  └───────────┬─────────────┘  │
│              │                │
│  ┌───────────▼─────────────┐  │
│  │   MCP Connection Mgr    │  │
│  │                         │  │
│  │  - Connection Pool      │  │
│  │  - Server Registry      │  │
│  │  - Tool Registry        │  │
│  └─────┬─────────┬─────────┘  │
│        │         │            │
│ ┌──────▼───┐ ┌───▼──────┐     │
│ │ Server 1 │ │ Server 2 │ ... │
│ └──────────┘ └──────────┘     │
└───────────────────────────────┘
           │          │
           ▼          ▼
┌──────────────┐ ┌──────────────┐
│  MCP Server  │ │  MCP Server  │
│     (SSE)    │ │  (JSON-RPC)  │
└──────────────┘ └──────────────┘
```

## Key Design Principles

1. **Persistent Connections**: Maintain connections to MCP servers rather than reconnecting for each tool call
2. **Clear Separation**: Distinguish between MCP servers and the tools they provide
3. **Support for Standard Transports**: Support all standard MCP transport types (JSON-RPC, SSE, STDIO)
4. **Official Library Integration**: Use official MCP client libraries when available, with fallbacks
5. **Proper Resource Management**: Use AsyncExitStack for proper async resource cleanup
6. **Error Handling**: Robust error handling for connection issues and tool execution failures

## Implementation Guidelines

### 1. Connection Management

The connection manager should:
- Maintain a pool of connections to MCP servers
- Reuse connections for multiple tool calls
- Handle connection failures gracefully
- Register and track tools provided by each server

### 2. Transport Types

Support multiple transport types:
- **JSON-RPC**: For HTTP-based connections
- **SSE**: For Server-Sent Events streaming
- **STDIO**: For local process communication

### 3. Tool Registration and Discovery

Tool registration should:
- Automatically discover tools from registered servers
- Map tools to their respective servers
- Allow manual tool registration for advanced use cases

### 4. Error Handling

Proper error handling includes:
- Connection failures
- Authentication errors
- Tool execution errors
- Invalid input/output handling

### 5. Cleanup

Ensure proper cleanup:
- Close connections when they're no longer needed
- Use AsyncExitStack for managing async resources
- Implement proper shutdown sequence

## Integration with A2A

The A2A-MCP Connector exposes MCP tools through the A2A protocol, following the proper relationship described in the A2A-MCP relationship document.

Key aspects of this integration:
- A2A tasks can use MCP tools
- The connector handles the protocol translation
- Connection management is hidden from the A2A client

## MCP Best Practices

Following best practices from the MCP documentation:
- Use MCP client sessions for connection management
- Follow MCP's client-server architecture
- Use proper initialization and tool discovery sequences
- Implement proper shutdown and cleanup

## Implementation Details

The implementation focuses on:
1. Using official MCP client libraries when available
2. Providing fallback implementations when needed
3. Maintaining proper connection lifecycles
4. Ensuring robust error handling and recovery

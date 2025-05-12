"""
A simple mock MCP server that responds to JSON-RPC requests.
This can be used for testing the A2A-MCP connector.
"""

import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our JSON-RPC utilities
from jsonrpc_utils import (
    create_jsonrpc_response,
    create_jsonrpc_error_response,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPJsonRpcHandler(BaseHTTPRequestHandler):
    """HTTP handler for Mock MCP JSON-RPC server."""
    
    def _set_headers(self, status_code=200, content_type="application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self._set_headers()
    
    def do_GET(self):
        """Provide a helpful message for GET requests."""
        self._set_headers(200, "text/html")
        self.wfile.write(b"""
        <html>
        <head><title>Mock MCP Server</title></head>
        <body>
        <h1>Mock MCP JSON-RPC Server</h1>
        <p>This server accepts JSON-RPC 2.0 requests via POST.</p>
        <p>Example request:</p>
        <pre>
        {
          "jsonrpc": "2.0",
          "id": "test-1",
          "method": "execute",
          "params": {
            "text": "Hello, world!"
          }
        }
        </pre>
        </body>
        </html>
        """)
    
    def do_POST(self):
        """Handle JSON-RPC POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._set_headers(400)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    INVALID_REQUEST, 
                    "Missing request body",
                    None
                )
            ).encode())
            return
        
        # Read the request body
        request_body = self.rfile.read(content_length)
        
        # Parse the request
        try:
            request = json.loads(request_body)
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    PARSE_ERROR, 
                    "Invalid JSON",
                    request_body.decode("utf-8", errors="replace")
                )
            ).encode())
            return
        
        # Log the request
        logger.info(f"Received request: {request}")
        
        # Validate the request
        if not isinstance(request, dict):
            self._set_headers(400)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    INVALID_REQUEST, 
                    "Request must be a JSON object", 
                    None,
                    request.get("id")
                )
            ).encode())
            return
        
        if request.get("jsonrpc") != "2.0":
            self._set_headers(400)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    INVALID_REQUEST, 
                    "Invalid or missing jsonrpc field",
                    None,
                    request.get("id")
                )
            ).encode())
            return
        
        if "method" not in request:
            self._set_headers(400)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    INVALID_REQUEST, 
                    "Missing method field", 
                    None,
                    request.get("id")
                )
            ).encode())
            return
        
        # Get the request ID
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        # Handle different methods
        if method == "ping":
            # Simple ping - just echo back
            self._set_headers()
            self.wfile.write(json.dumps(
                create_jsonrpc_response(
                    {"status": "ok", "message": "pong"},
                    request_id
                )
            ).encode())
            return
        
        elif method == "execute":
            # Process the execute method
            if not isinstance(params, dict):
                self._set_headers(400)
                self.wfile.write(json.dumps(
                    create_jsonrpc_error_response(
                        INVALID_PARAMS, 
                        "Invalid params (must be an object)",
                        None,
                        request_id
                    )
                ).encode())
                return
            
            # Check for text parameter
            text = params.get("text", "")
            
            # Create a basic response
            response_result = {
                "answer": f"Processed: {text}",
                "metadata": {
                    "tool_name": "mock-mcp-server",
                    "version": "1.0.0"
                }
            }
            
            # Send the response
            self._set_headers()
            self.wfile.write(json.dumps(
                create_jsonrpc_response(response_result, request_id)
            ).encode())
            return
            
        else:
            # Method not found
            self._set_headers(404)
            self.wfile.write(json.dumps(
                create_jsonrpc_error_response(
                    METHOD_NOT_FOUND, 
                    f"Method '{method}' not found",
                    None,
                    request_id
                )
            ).encode())
            return


def run_server(host="localhost", port=8000):
    """Start the mock MCP server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MCPJsonRpcHandler)
    logger.info(f"Starting mock MCP JSON-RPC server on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a mock MCP JSON-RPC server for testing")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    
    args = parser.parse_args()
    run_server(args.host, args.port)

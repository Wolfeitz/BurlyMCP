#!/usr/bin/env python3
"""
Mock Gotify Server for Testing

A simple HTTP server that mimics Gotify API responses for testing purposes.
This allows us to test the actual Gotify integration without requiring a real Gotify instance.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class MockGotifyHandler(BaseHTTPRequestHandler):
    """HTTP request handler that mimics Gotify API behavior."""
    
    def do_POST(self):
        """Handle POST requests to /message endpoint."""
        if self.path.startswith('/message'):
            # Parse the request
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                # Parse JSON body
                message_data = json.loads(post_data.decode('utf-8'))
                
                # Validate required fields
                if 'message' not in message_data:
                    self.send_error_response(400, "Missing message field")
                    return
                
                # Check authorization header
                auth_header = self.headers.get('Authorization', '')
                if not auth_header.startswith('Bearer '):
                    self.send_error_response(401, "Missing or invalid authorization")
                    return
                
                # Simulate successful message creation
                response = {
                    "id": 12345,
                    "appid": 1,
                    "message": message_data["message"],
                    "title": message_data.get("title", ""),
                    "priority": message_data.get("priority", 5),
                    "date": "2024-01-15T10:30:00Z"
                }
                
                self.send_json_response(200, response)
                
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON")
            except Exception as e:
                self.send_error_response(500, f"Server error: {str(e)}")
        else:
            self.send_error_response(404, "Not found")
    
    def do_GET(self):
        """Handle GET requests for health checks."""
        if self.path == '/health':
            self.send_json_response(200, {"status": "ok", "mock": True})
        else:
            self.send_error_response(404, "Not found")
    
    def send_json_response(self, status_code, data):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_error_response(self, status_code, message):
        """Send an error response."""
        error_data = {"error": message, "errorCode": status_code}
        self.send_json_response(status_code, error_data)
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass  # Suppress default request logging


class MockGotifyServer:
    """Mock Gotify server for testing."""
    
    def __init__(self, port=None, host="127.0.0.1"):
        self.port = port or self._find_free_port()
        self.host = host
        self.server = None
        self.thread = None
        self.running = False
    
    def start(self):
        """Start the mock server in a background thread."""
        if self.running:
            return
        
        self.server = HTTPServer((self.host, self.port), MockGotifyHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.running = True
        
        # Give the server a moment to start
        time.sleep(0.1)
    
    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)
        self.running = False
    
    def get_url(self):
        """Get the base URL for the mock server."""
        return f"http://{self.host}:{self.port}"
    
    def _find_free_port(self):
        """Find a free port for the mock server."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port


def main():
    """Run the mock server standalone for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mock Gotify Server for Testing")
    parser.add_argument("--port", type=int, default=0, help="Port to run on (0 for auto)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()
    
    server = MockGotifyServer(args.port, args.host)
    
    try:
        print(f"Starting mock Gotify server on {args.host}:{args.port}")
        server.start()
        print(f"Mock server running at {server.get_url()}")
        print(f"Actual port: {server.port}")
        print("Press Ctrl+C to stop")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping mock server...")
        server.stop()
        print("Mock server stopped")


if __name__ == "__main__":
    main()
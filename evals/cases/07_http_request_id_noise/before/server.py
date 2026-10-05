import json, os, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    # HTTPServer.server_bind() does a reverse-DNS lookup (socket.getfqdn)
    # that can hang for minutes on hosts with broken resolvers (observed on
    # GitHub macOS runners). Nothing in the probe path needs server_name.
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = json.dumps(payload).encode() if isinstance(payload, (dict, list)) else str(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-ID", str(uuid.uuid4()))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/users/42":
            self._send(200, {"id": 42, "username": "alice", "email": "alice@example.com", "timestamp": "2026-01-01T10:00:00Z"})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/login":
            self._send(401, {"error": "invalid_credentials"})
        else:
            self._send(404, {"error": "not_found"})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()

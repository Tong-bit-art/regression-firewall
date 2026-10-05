import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = json.dumps(payload).encode() if isinstance(payload, (dict, list)) else str(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/users/42":
            self._send(200, {"id": 42, "username": "alice", "timestamp": int(time.time())})
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
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

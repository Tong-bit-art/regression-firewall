"""Launcher so Regression Firewall can manage the server lifecycle."""

import os
import socket

# Werkzeug's HTTPServer resolves the hostname (reverse DNS) during bind,
# which can hang for a long time on hosts with broken resolvers. Nothing in
# the example needs it.
socket.getfqdn = lambda *a, **k: "127.0.0.1"

from app import app

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("REGFW_SERVER_PORT", "8000")),
        debug=False,
    )

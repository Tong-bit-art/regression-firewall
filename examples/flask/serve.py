"""Launcher so Regression Firewall can manage the server lifecycle."""

import os

from app import app

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("REGFW_SERVER_PORT", "8000")),
        debug=False,
    )

"""Launcher so Regression Firewall can manage the server lifecycle.

The tool picks a free port and passes it via REGFW_SERVER_PORT when the
config's base_url contains {port}.

Install deps:  pip install fastapi uvicorn
"""

import os

import uvicorn

from app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("REGFW_SERVER_PORT", "8000")),
        log_level="warning",
    )

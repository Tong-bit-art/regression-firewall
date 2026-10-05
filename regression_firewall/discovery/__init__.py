"""Project discovery: language/framework detection and optional route discovery."""

from .project import ProjectInfo, detect_project
from .routes import discover_routes

__all__ = ["ProjectInfo", "detect_project", "discover_routes"]

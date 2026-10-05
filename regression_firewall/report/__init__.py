"""Report renderers: console, Markdown, JSON."""

from .console import render_console
from .json_report import report_to_dict
from .markdown import render_markdown

__all__ = ["render_console", "render_markdown", "report_to_dict"]

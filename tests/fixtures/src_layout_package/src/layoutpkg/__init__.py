"""Minimal src-layout package used by the regression tests.

The module declares ``__all__`` on purpose: the coverage bug this fixture
guards against only manifests when a module has a declared export list
(urllib3-style), because the introspector consulted ``__all__`` instead of
the importable namespace.
"""

from .core import VERSION, add, greet

__all__ = ["VERSION", "add", "greet"]

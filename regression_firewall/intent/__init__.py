"""Intent handling: structured expectations and deterministic classification."""

from .matcher import UNCERTAIN_CATEGORIES, classify_change
from .model import ExpectedChange, Intent, IntentError, intent_from_dict, load_intent

__all__ = [
    "ExpectedChange",
    "Intent",
    "IntentError",
    "UNCERTAIN_CATEGORIES",
    "classify_change",
    "intent_from_dict",
    "load_intent",
]

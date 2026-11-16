"""Model evaluation helpers for the negation pilot.

These modules read public inputs for inference and gold files only when scoring.
They do not generate or rewrite Dataset v1.1.
"""

__all__ = ["PROMPT_VERSION"]

from negpilot.evalkit.prompt import PROMPT_VERSION

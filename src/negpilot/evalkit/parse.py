"""Strict label parser.

A prediction is TRUE, FALSE, or UNKNOWN only when that word is the entire
final answer. Explanations are stored separately and are not searched for a
label. Anything else is invalid_output.
"""

from __future__ import annotations

import re

LABELS = ("TRUE", "FALSE", "UNKNOWN")
INVALID = "invalid_output"

# Qwen3.5 thinking blocks used by the official chat template.
_THINK_BLOCK = re.compile(r"<think>\s*(.*?)\s*</think>\s*", re.DOTALL)


def parse_model_output(raw: str | None) -> dict[str, str | None]:
    """Parse one decoded generation.

    Returns predicted_label, explanation, and parse_status.
    parse_status is "exact" when the whole string is one label, "after_think"
    when a complete think block is followed by exactly one label, and
    "invalid" otherwise.
    """
    if raw is None:
        return {
            "predicted_label": INVALID,
            "explanation": None,
            "parse_status": "invalid",
        }
    text = raw.strip()
    if text in LABELS:
        return {
            "predicted_label": text,
            "explanation": None,
            "parse_status": "exact",
        }
    match = _THINK_BLOCK.search(text)
    if match and text.startswith("<think>"):
        explanation = match.group(1).strip() or None
        remainder = text[match.end() :].strip()
        if remainder in LABELS:
            return {
                "predicted_label": remainder,
                "explanation": explanation,
                "parse_status": "after_think",
            }
    return {
        "predicted_label": INVALID,
        "explanation": None,
        "parse_status": "invalid",
    }

"""Public-only prompts for the negation pilot.

The system instruction is the unified task text in the experiment plan,
section 6.4. The user turn is the public record's prompt field, unchanged.
"""

from __future__ import annotations

import hashlib
from typing import Any

from negpilot.schema import PUBLIC_FIELDS

PROMPT_VERSION = "plan-6.4-v1"

SYSTEM_PROMPT = """\
You are solving a formal logic entailment task.

The domain contains exactly the individuals listed in the prompt.
Use only the facts and rules in the knowledge base.
Do not assume that an unstated proposition is false.

Return exactly one label:
TRUE: the knowledge base entails the query.
FALSE: the knowledge base entails the negation of the query.
UNKNOWN: the knowledge base entails neither the query nor its negation.

Output only TRUE, FALSE, or UNKNOWN.
"""

# Gold-only fields. A record that still contains any of these is refused.
LEAK_FIELDS = (
    "label",
    "binary_label",
    "query_ast",
    "proof_trace",
    "inference_steps",
    "negation_critical",
    "in_controlled_subset",
    "logical_pair_validity",
    "experimental_control_validity",
    "verification",
    "verification_status",
    "negation_form",
    "negation_scope",
    "negation_position",
    "reasoning_depth",
    "pair_id",
    "family",
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assert_public_record(record: dict[str, Any]) -> None:
    """Reject a record that is not exactly a public evaluation row."""
    extra = sorted(set(record) - set(PUBLIC_FIELDS))
    missing = sorted(set(PUBLIC_FIELDS) - set(record))
    if extra or missing:
        raise ValueError(
            "public record fields do not match the public schema: "
            f"extra={extra or '[]'} missing={missing or '[]'}"
        )
    leaked = [name for name in LEAK_FIELDS if name in record]
    if leaked:
        raise ValueError(f"public record carries gold-only fields: {leaked}")
    if not isinstance(record.get("prompt"), str) or not record["prompt"].strip():
        raise ValueError(f"public record {record.get('sample_id')} has an empty prompt")


def build_messages(public_record: dict[str, Any]) -> list[dict[str, str]]:
    """Build the chat messages for one public sample.

    Gold-only keys are not interpolated. If they are present, this raises
    instead of silently dropping them.
    """
    assert_public_record(public_record)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": public_record["prompt"]},
    ]

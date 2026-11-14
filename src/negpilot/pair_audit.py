"""Contrastive-pair audit.

A correct Z3 label does not make two examples a controlled contrast.
Every pair is kept. Pairs that fail comparability or experimental control
stay in the file, with the reason recorded here.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

COMPARED = (
    "query",
    "domain",
    "symbol_mapping",
    "proof_depth",
    "inference_type",
    "relevant_premise_count",
    "negation_position",
    "negation_scope",
    "negation_embedding",
    "negation_function",
    "negation_critical",
    "negation_count",
    "kb_negation_count",
    "query_negation_count",
    "query_polarity",
    "fact_count",
    "rule_count",
    "nl_pack",
    "statement_template",
    "knowledge_base",
)

# A declared manipulation may use a public name that differs from the profile field.
MANIPULATION_FIELDS = {"negation_criticality": "negation_critical"}

NEGATION_PROPERTIES = (
    "negation_position",
    "negation_scope",
    "negation_embedding",
    "negation_function",
)

_TEMPLATE_SUFFIX = re.compile(
    r"(_depth\d+|_context\d+|_anchor\d+|_individual\d+|_positive|_negative)"
)
_SIDE_PREDICATE = re.compile(r"_s\d+$")


def statement_template(template_id: str) -> str:
    previous = template_id
    while True:
        current = _TEMPLATE_SUFFIX.sub("", previous)
        if current == previous:
            return current
        previous = current


def _predicates(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("op") == "atom" and isinstance(node.get("pred"), str):
            found.append(node["pred"])
        for value in node.values():
            found.extend(_predicates(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_predicates(item))
    return found


def _is_side_statement(ast: dict[str, Any]) -> bool:
    return any(_SIDE_PREDICATE.search(pred) for pred in _predicates(ast))


def inference_type_of(record: dict[str, Any]) -> str:
    if record.get("label") == "UNKNOWN":
        return "no_proof"
    key = statement_template(str(record.get("template_id", "")))
    hops = int((record.get("proof_trace") or {}).get("proof_hops", 0))
    if key == "negative_fact":
        return "fact_lookup"
    if key.startswith("query_negated_universal") or key.startswith("query_existential"):
        return "axiom_lookup"
    if "disjunction" in key:
        if hops <= 1:
            return "disjunctive_syllogism"
        return "modus_ponens_then_disjunctive_syllogism"
    return "modus_ponens"


def inference_steps_for(inference_type: str, proof_depth: int | None) -> list[dict[str, str]]:
    if proof_depth is None or proof_depth <= 0:
        return []
    if inference_type == "disjunctive_syllogism":
        return [{"operator": "disjunctive_syllogism"}]
    if inference_type == "modus_ponens_then_disjunctive_syllogism":
        steps = [{"operator": "modus_ponens"} for _ in range(proof_depth - 1)]
        steps.append({"operator": "disjunctive_syllogism"})
        return steps
    if inference_type == "modus_ponens":
        return [{"operator": "modus_ponens"} for _ in range(proof_depth)]
    return []


def relevant_premise_count(record: dict[str, Any], inference_type: str, proof_depth: int | None) -> int:
    if inference_type in {"fact_lookup", "axiom_lookup"}:
        return 1
    if inference_type == "no_proof":
        statements = record["knowledge_base"]["statements"]
        return sum(1 for item in statements if not _is_side_statement(item["ast"]))
    return int(proof_depth or 0) + 1


_EMBEDDING = {
    "atomic_literal": "atomic",
    "negated_disjunct": "disjunction",
    "rule_antecedent": "rule_antecedent",
    "rule_consequent": "rule_consequent",
    "negated_universal": "negated_universal",
    "existential_counterexample": "existential",
}


def negation_embedding_of(negation_form: str) -> str:
    """Structural position of the studied Not. This is not an inference rule."""
    try:
        return _EMBEDDING[negation_form]
    except KeyError as exc:
        raise ValueError(f"unknown negation_form {negation_form}") from exc


def negation_function_of(record: dict[str, Any], inference_type: str) -> str:
    if record.get("negation_position") == "QUERY":
        return "query_content"
    if record.get("negation_form") == "negated_disjunct":
        return "disjunctive_premise"
    if inference_type == "fact_lookup":
        return "stated_literal"
    if not record.get("negation_critical"):
        return "distractor"
    if record.get("label") == "UNKNOWN":
        return "blocks_without_refuting"
    return "entailment_premise"


def proof_depth_of(record: dict[str, Any]) -> int | None:
    if record.get("label") == "UNKNOWN":
        return None
    return int((record.get("proof_trace") or {}).get("proof_hops", 0))


def profile(record: dict[str, Any]) -> dict[str, Any]:
    inference_type = inference_type_of(record)
    proof_depth = proof_depth_of(record)
    return {
        "query": record.get("query_ast"),
        "domain": list(record.get("domain") or []),
        "proof_depth": proof_depth,
        "inference_type": inference_type,
        "relevant_premise_count": relevant_premise_count(record, inference_type, proof_depth),
        "negation_position": record.get("negation_position"),
        "negation_scope": record.get("negation_scope"),
        "negation_embedding": negation_embedding_of(str(record.get("negation_form"))),
        "negation_function": negation_function_of(record, inference_type),
        "negation_critical": record.get("negation_critical"),
        "negation_count": record.get("negation_count"),
        "kb_negation_count": record.get("kb_negation_count"),
        "query_negation_count": record.get("query_negation_count"),
        "query_polarity": record.get("query_polarity"),
        "fact_count": sum(item["role"] == "fact" for item in record["knowledge_base"]["statements"]),
        "rule_count": sum(item["role"] == "rule" for item in record["knowledge_base"]["statements"]),
        "symbol_mapping": record.get("symbol_mapping"),
        "nl_pack": record.get("nl_pack"),
        "statement_template": statement_template(str(record.get("template_id", ""))),
        "knowledge_base": [item["ast"] for item in record["knowledge_base"]["statements"]],
        "inference_steps": inference_steps_for(inference_type, proof_depth),
    }


def criticality_result(before: str, after: str, kb_satisfiable: bool) -> tuple[bool | None, str]:
    """Ablation is invalid when deleting the Not makes the knowledge base inconsistent."""
    if not kb_satisfiable:
        return None, "invalid"
    return before != after, "pass"


def apply_profile(record: dict[str, Any]) -> dict[str, Any]:
    """Write the derived proof fields onto one gold record."""
    derived = profile(record)
    record["inference_type"] = derived["inference_type"]
    record["negation_embedding"] = derived["negation_embedding"]
    record["negation_function"] = derived["negation_function"]
    record["inference_steps"] = derived["inference_steps"]
    record["proof_depth"] = derived["proof_depth"]
    record["relevant_premise_count"] = derived["relevant_premise_count"]
    record["reasoning_depth"] = derived["proof_depth"]
    return derived


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _label_reasons(record: dict[str, Any]) -> list[str]:
    verification = record.get("verification") or {}
    if verification.get("computed_label") != record.get("label"):
        return ["z3_label_mismatch"]
    if verification.get("matches_expected") is not True:
        return ["z3_label_mismatch"]
    return []


def _sample_reasons(record: dict[str, Any], derived: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    total = (record.get("kb_negation_count") or 0) + (record.get("query_negation_count") or 0)
    if record.get("negation_count") != total or total not in {1, 2}:
        reasons.append("negation_count_mismatch")
    if record.get("label") not in {"TRUE", "FALSE", "UNKNOWN"}:
        reasons.append("illegal_label")
    if record.get("reasoning_depth") != derived["proof_depth"]:
        reasons.append("reasoning_depth_mismatch")
    if record.get("proof_depth") != derived["proof_depth"]:
        reasons.append("proof_depth_mismatch")
    if record.get("inference_type") != derived["inference_type"]:
        reasons.append("inference_type_mismatch")
    if record.get("negation_embedding") != derived["negation_embedding"]:
        reasons.append("negation_embedding_mismatch")
    if record.get("negation_function") != derived["negation_function"]:
        reasons.append("negation_function_mismatch")
    if record.get("inference_steps") != derived["inference_steps"]:
        reasons.append("inference_steps_mismatch")
    expected_steps = 0 if derived["proof_depth"] is None else derived["proof_depth"]
    if len(derived["inference_steps"]) != expected_steps:
        reasons.append("inference_step_count")
    if derived["inference_type"] in {"fact_lookup", "axiom_lookup"} and derived["proof_depth"] != 0:
        reasons.append("lookup_is_not_depth_0")
    if derived["inference_type"] == "no_proof" and derived["proof_depth"] is not None:
        reasons.append("open_proof_has_a_depth")
    if record.get("criticality_verification") == "invalid":
        reasons.append("ablation_invalid")
    elif record.get("negation_critical") not in {True, False}:
        reasons.append("criticality_missing")
    return reasons


def _manipulation_field(name: str) -> str:
    return MANIPULATION_FIELDS.get(name, name)


def audit_pair(
    left: dict[str, Any],
    right: dict[str, Any],
    controlled: list[str],
    manipulated: list[str],
    derived: list[str],
    studies_inference_type: bool,
) -> dict[str, Any]:
    """Separate a correct label pair from a controlled experiment.

    A knowledge-base difference is not itself a confound. It is a confound when
    a variable outside the declared manipulation and its derived effects also
    changes, especially proof depth or inference type.
    """
    left_profile = profile(left)
    right_profile = profile(right)
    controlled_set = set(controlled)
    manipulated_fields = {_manipulation_field(name) for name in manipulated}
    derived_set = set(derived)
    observed: list[str] = []
    experimental: list[str] = []

    for name in COMPARED:
        if _canon(left_profile[name]) == _canon(right_profile[name]):
            continue
        observed.append(name)
        if name in controlled_set:
            experimental.append(f"controlled_variable_differs:{name}")
        elif name in manipulated_fields or name in derived_set:
            continue
        else:
            experimental.append(f"undeclared_change:{name}")

    for name in manipulated:
        field = _manipulation_field(name)
        if field in COMPARED and field not in observed:
            experimental.append(f"manipulated_variable_unchanged:{name}")

    for name in ("query", "domain", "proof_depth", "inference_type"):
        if name in observed and name not in manipulated_fields:
            experimental.append(f"hard_control_differs:{name}")

    negation_changed = any(name in observed for name in NEGATION_PROPERTIES)
    inference_is_manipulated = "inference_type" in manipulated_fields or studies_inference_type
    if "inference_type" in observed and negation_changed and not inference_is_manipulated:
        experimental.append("inference_and_negation_property_both_change")
    if "negation_position" in observed and "negation_scope" in observed:
        if "negation_position" not in manipulated_fields or "negation_scope" not in manipulated_fields:
            experimental.append("negation_position_and_scope_both_change")

    label_reasons = _label_reasons(left) + [f"right:{item}" for item in _label_reasons(right)]
    sample_reasons = _sample_reasons(left, left_profile) + [
        f"right:{item}" for item in _sample_reasons(right, right_profile)
    ]
    logical_reasons = label_reasons + sample_reasons
    rejection = logical_reasons + experimental
    return {
        "studies_inference_type": studies_inference_type,
        "observed_differences": observed,
        "member_profiles": {
            left["sample_id"]: {key: left_profile[key] for key in (*COMPARED, "inference_steps")},
            right["sample_id"]: {key: right_profile[key] for key in (*COMPARED, "inference_steps")},
        },
        "label_validity": "fail" if label_reasons else "pass",
        "individual_sample_validity": "fail" if sample_reasons else "pass",
        "logical_pair_validity": "fail" if logical_reasons else "pass",
        "experimental_control_validity": "fail" if experimental else "pass",
        "in_controlled_subset": not rejection,
        "rejection_reasons": rejection,
    }


def stamp_pair(
    members: list[dict[str, Any]],
    controlled: list[str],
    manipulated: list[str],
    derived: list[str],
    studies_inference_type: bool,
    experimental_category: str,
    contrast: str,
    label_balance_group: str,
) -> list[dict[str, Any]]:
    if len(members) != 2:
        raise ValueError("a contrastive pair must contain two members")
    for record in members:
        apply_profile(record)
    metadata = audit_pair(
        members[0],
        members[1],
        controlled,
        manipulated,
        derived,
        studies_inference_type,
    )
    for record in members:
        record["controlled_variables"] = list(controlled)
        record["manipulated_variables"] = list(manipulated)
        record["derived_variables"] = list(derived)
        record["experimental_category"] = experimental_category
        record["contrast"] = contrast
        record["label_balance_group"] = label_balance_group
        record["logical_pair_validity"] = metadata["logical_pair_validity"]
        record["experimental_control_validity"] = metadata["experimental_control_validity"]
        record["in_controlled_subset"] = metadata["in_controlled_subset"]
        record["pair_metadata"] = metadata
    return members


def comparison_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("pair_id", ""))].append(record)
    rows: list[dict[str, Any]] = []
    for pair_id in sorted(grouped):
        members = sorted(grouped[pair_id], key=lambda item: str(item.get("sample_id")))
        left = members[0]
        metadata = left.get("pair_metadata") or {}
        rows.append(
            {
                "pair_id": pair_id,
                "family": left.get("family"),
                "pair_type": left.get("pair_type"),
                "sample_ids": [item.get("sample_id") for item in members],
                "labels": [item.get("label") for item in members],
                "experimental_category": left.get("experimental_category"),
                "contrast": left.get("contrast"),
                "manipulated_variables": left.get("manipulated_variables") or [],
                "controlled_variables": left.get("controlled_variables") or [],
                "derived_variables": left.get("derived_variables") or [],
                "individual_sample_validity": metadata.get("individual_sample_validity"),
                "label_validity": metadata.get("label_validity"),
                "logical_pair_validity": left.get("logical_pair_validity"),
                "experimental_control_validity": left.get("experimental_control_validity"),
                "in_controlled_subset": left.get("in_controlled_subset"),
                "label_balance_group": left.get("label_balance_group"),
                "observed_differences": metadata.get("observed_differences") or [],
                "rejection_reasons": (left.get("pair_metadata") or {}).get("rejection_reasons") or [],
                "member_profiles": metadata.get("member_profiles") or {},
                "studies_inference_type": metadata.get("studies_inference_type", False),
            }
        )
    return rows


def control_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = comparison_rows(records)
    by_family: dict[str, dict[str, int]] = {}
    reasons: dict[str, int] = {}
    controlled = 0
    for row in rows:
        flag = bool(row.get("in_controlled_subset"))
        controlled += int(flag)
        family = str(row["family"])
        bucket = by_family.setdefault(family, {"controlled": 0, "exploratory": 0})
        bucket["controlled" if flag else "exploratory"] += 1
        for reason in row.get("rejection_reasons") or []:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "pairs": len(rows),
        "controlled_pairs": controlled,
        "exploratory_pairs": len(rows) - controlled,
        "by_family": dict(sorted(by_family.items())),
        "rejection_reasons": dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
    }

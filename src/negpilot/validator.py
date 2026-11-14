"""Dataset audits. Invalid samples are reported, never relabeled."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from negpilot.ast import (
    Atom,
    ForAll,
    Formula,
    Implies,
    Not,
    count_nots,
    from_dict,
    infer_position_and_scope,
    negation_formula,
    validate_syntax,
)
from negpilot.pair_audit import audit_pair
from negpilot.renderer import negation_cue_count, parse
from negpilot.schema import DEPTHS, INVALID_POSITION_SCOPE, REQUIRED_GOLD_FIELDS
from negpilot.semantics import classify, equivalent, evaluate


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON") from exc
    return rows


def _formulas(record: dict[str, Any]) -> tuple[list[Formula], Formula]:
    statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
    query = from_dict(record["query_ast"])
    return statements, query


def _signature(record: dict[str, Any]) -> str:
    payload = {
        "domain": record["domain"],
        "statements": [item["ast"] for item in record["knowledge_base"]["statements"]],
        "query": record["query_ast"],
    }
    return json.dumps(payload, sort_keys=True)


def _universal_implications(statements: list[Formula]) -> int:
    count = 0
    for formula in statements:
        if isinstance(formula, ForAll) and isinstance(formula.body, Implies):
            count += 1
    return count


def _negated_text(record: dict[str, Any]) -> str:
    texts = [item["text"] for item in record["knowledge_base"]["statements"]] + [record["query"]]
    hits = [text for text in texts if negation_cue_count(text)]
    if len(hits) != 1:
        return ""
    return hits[0]


def _language_errors(record: dict[str, Any], pack: str) -> list[str]:
    errors = []
    sample = record["sample_id"]
    statements, query = _formulas(record)
    texts = [item["text"] for item in record["knowledge_base"]["statements"]]
    if len(texts) != len(statements):
        errors.append(f"{sample}: statement text count does not match ASTs")
        return errors
    for formula, text in zip(statements, texts):
        try:
            parsed = parse(text, pack)
        except Exception as exc:  # noqa: BLE001 - report parser failure as data error
            errors.append(f"{sample}: could not parse {text!r} ({exc})")
            continue
        if parsed != formula:
            errors.append(f"{sample}: text does not match AST: {text}")
    try:
        parsed_query = parse(record["query"], pack)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{sample}: could not parse query {record['query']!r} ({exc})")
        parsed_query = None
    if parsed_query is not None and parsed_query != query:
        errors.append(f"{sample}: query text does not match query_ast")
    if pack == "symbol":
        negated = " ".join(texts + [record["query"]])
        cue_total = sum(negation_cue_count(text) for text in texts + [record["query"]])
        if cue_total != record.get("negation_count"):
            errors.append(f"{sample}: negation cues {cue_total} do not match negation_count")
    else:
        negated = _negated_text(record)
        if negation_cue_count(negated) != 1:
            errors.append(f"{sample}: expected exactly one 'not' cue, found {negated!r}")
        for text in texts + [record["query"]]:
            if text != negated and negation_cue_count(text):
                errors.append(f"{sample}: extra negation cue in {text}")
            for banned in ("Not every", "not every", "No ", "Every "):
                if banned in text:
                    errors.append(f"{sample}: ambiguous wording {banned!r} in {text}")
    form = record.get("negation_form")
    markers = {
        "alpha": {
            "negated_universal": "It is not true that for every individual",
            "existential_counterexample": "There is at least one individual",
            "rule_consequent": "then the individual is not",
            "rule_antecedent": "if the individual is not",
        },
        "beta": {
            "negated_universal": "It is not the case that whenever",
            "existential_counterexample": "At least one individual",
            "rule_consequent": "that individual does not have property",
            "rule_antecedent": "Whenever an individual does not have property",
        },
        "symbol": {
            "negated_universal": "Not every ",
            "existential_counterexample": "Some ",
            "rule_consequent": " is not ",
            "rule_antecedent": "Every non-",
        },
    }[pack]
    if form == "negated_universal":
        if markers["negated_universal"] not in negated:
            errors.append(f"{sample}: negated universal was not rendered with its own frame")
        if "at least one" in negated.lower():
            errors.append(f"{sample}: negated universal was conflated with an existential")
    if form == "existential_counterexample":
        if markers["existential_counterexample"] not in negated:
            errors.append(f"{sample}: existential counterexample was not rendered with its own frame")
        if markers["negated_universal"] in negated:
            errors.append(f"{sample}: existential counterexample was conflated with a negated universal")
    if form == "rule_consequent" and markers["rule_consequent"] not in negated:
        errors.append(f"{sample}: negated consequent frame missing")
    if form == "rule_antecedent" and markers["rule_antecedent"] not in negated:
        errors.append(f"{sample}: negated antecedent frame missing")
    if form == "rule_consequent" and markers["negated_universal"] in negated:
        errors.append(f"{sample}: negated consequent was conflated with 'not every'")
    return errors


def _logic_errors(record: dict[str, Any]) -> list[str]:
    errors = []
    sample = record["sample_id"]
    statements, query = _formulas(record)
    domain = record["domain"]
    decision = classify(statements, query, domain, with_models=False)
    if not decision.kb_satisfiable or decision.label == "INCONSISTENT":
        errors.append(f"{sample}: knowledge base is unsatisfiable")
        return errors
    if decision.label != record["label"]:
        errors.append(
            f"{sample}: stored label {record['label']} but Z3 recomputed {decision.label}"
        )
    if record["label"] == "TRUE":
        if decision.kb_and_not_query != "unsat" or decision.kb_and_query != "sat":
            errors.append(f"{sample}: TRUE label failed the entailment check")
    elif record["label"] == "FALSE":
        if decision.kb_and_query != "unsat" or decision.kb_and_not_query != "sat":
            errors.append(f"{sample}: FALSE label failed the negated-entailment check")
    elif record["label"] == "UNKNOWN":
        if decision.kb_and_query != "sat" or decision.kb_and_not_query != "sat":
            errors.append(f"{sample}: UNKNOWN label is missing a satisfying model on one side")
    models = record["proof_trace"].get("models", {})
    if record["label"] in {"TRUE", "UNKNOWN"}:
        model = models.get("kb_and_query")
        if not isinstance(model, dict) or evaluate(query, domain, model) is not True:
            errors.append(f"{sample}: stored model does not satisfy the query")
    if record["label"] in {"FALSE", "UNKNOWN"}:
        model = models.get("kb_and_not_query")
        if not isinstance(model, dict) or evaluate(query, domain, model) is not False:
            errors.append(f"{sample}: stored model does not satisfy the negated query")
    return errors


def validate_records(
    records: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    recompute_logic: bool = True,
) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    signatures: dict[str, str] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        sample = str(record.get("sample_id", "<missing>"))
        for field in REQUIRED_GOLD_FIELDS:
            if field not in record:
                errors.append(f"{sample}: missing {field}")
        if record.get("sample_id") in seen_ids:
            errors.append(f"{sample}: duplicate sample_id")
        seen_ids.add(record.get("sample_id"))
        if record.get("label") not in {"TRUE", "FALSE", "UNKNOWN"}:
            errors.append(f"{sample}: illegal label {record.get('label')}")
            continue
        expected_binary = {"TRUE": 1, "FALSE": 0, "UNKNOWN": None}[record["label"]]
        if record.get("binary_label") != expected_binary:
            errors.append(f"{sample}: binary_label does not match {record['label']}")
        if record.get("negation_count") not in {1, 2}:
            errors.append(f"{sample}: negation_count {record.get('negation_count')} is not 1 or 2")
        if record.get("reasoning_depth") is None:
            if record.get("label") != "UNKNOWN" or record.get("proof_depth") is not None:
                errors.append(f"{sample}: only an UNKNOWN example may have a null proof depth")
        elif record.get("reasoning_depth") not in DEPTHS or record.get("proof_depth") != record.get("reasoning_depth"):
            errors.append(f"{sample}: reasoning depth {record.get('reasoning_depth')} is not valid")
        if record.get("negation_cue") != "not":
            errors.append(f"{sample}: negation cue must be the explicit cue 'not'")
        if record.get("split") not in {"train", "dev", "test"}:
            errors.append(f"{sample}: illegal split")
        if record.get("verification_status") != "pass" or record.get("solver") != "z3":
            errors.append(f"{sample}: verification status or solver is not a passing Z3 check")
        cell = (record.get("negation_position"), record.get("negation_scope"))
        if cell in INVALID_POSITION_SCOPE:
            errors.append(f"{sample}: invalid position/scope cell {cell}")
        try:
            statements, query = _formulas(record)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sample}: malformed AST ({exc})")
            continue
        for formula in statements + [query]:
            problems = validate_syntax(formula, record["domain"])
            if problems:
                errors.append(f"{sample}: malformed formula {problems}")
        total_nots = sum(count_nots(item) for item in statements) + count_nots(query)
        if total_nots != record.get("negation_count"):
            errors.append(f"{sample}: AST negation count is {total_nots}")
        if record.get("kb_negation_count") != sum(count_nots(item) for item in statements):
            errors.append(f"{sample}: kb_negation_count does not match the AST")
        if record.get("query_negation_count") != count_nots(query):
            errors.append(f"{sample}: query_negation_count does not match the AST")
        expected_polarity = "NEGATIVE" if count_nots(query) else "POSITIVE"
        if record.get("query_polarity") != expected_polarity:
            errors.append(f"{sample}: query_polarity does not match the query")
        for name in record.get("domain") or []:
            if not (isinstance(name, str) and len(name) == 1 and name.islower()):
                errors.append(f"{sample}: individual {name} is not a pure symbol")
        for statement in record.get("knowledge_base", {}).get("statements", []):
            for pred in _predicates(statement.get("ast")):
                if not (len(pred) == 1 and pred.isupper()):
                    errors.append(f"{sample}: predicate {pred} is not a pure symbol")
        try:
            position, scope, form = infer_position_and_scope(statements, query)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sample}: negation site could not be classified ({exc})")
            position = scope = form = None
        if position != record.get("negation_position") or scope != record.get("negation_scope"):
            errors.append(f"{sample}: stored negation metadata does not match the AST")
        if form != record.get("negation_form"):
            errors.append(f"{sample}: stored negation form does not match the AST")
        positives = set()
        negatives = set()
        for formula in statements:
            if isinstance(formula, Atom):
                positives.add((formula.pred, formula.args))
            elif isinstance(formula, Not) and isinstance(formula.formula, Atom):
                negatives.add((formula.formula.pred, formula.formula.args))
        if positives & negatives:
            errors.append(f"{sample}: contradictory ground literals in the knowledge base")
        trace = record.get("proof_trace") or {}
        if record["label"] in {"TRUE", "FALSE"} and trace.get("proof_hops") != record["reasoning_depth"]:
            errors.append(f"{sample}: proof depth does not match reasoning_depth")
        if record["label"] == "UNKNOWN":
            if trace.get("proof_hops") != 0 or record["reasoning_depth"] is not None:
                errors.append(f"{sample}: UNKNOWN proof depth must be null")
            if _universal_implications(statements) != trace.get("chain_hops"):
                errors.append(
                    f"{sample}: examined chain has {_universal_implications(statements)} "
                    f"universal implications, not chain_hops {trace.get('chain_hops')}"
                )
        signature = _signature(record)
        if signature in signatures:
            errors.append(f"{sample}: duplicate logical structure of {signatures[signature]}")
        else:
            signatures[signature] = sample
        pack = record.get("nl_pack")
        if pack not in {"symbol", "alpha", "beta"}:
            errors.append(f"{sample}: missing template pack")
        else:
            errors.extend(_language_errors(record, pack))
        prompt = record.get("prompt", "")
        for snippet in (
            "The domain contains exactly these individuals",
            "Use only the supplied facts and rules.",
            "TRUE means the knowledge base logically entails the query.",
            "FALSE means the knowledge base logically entails the negation of the query.",
            "UNKNOWN means neither the query nor its negation is entailed.",
            "The output must be exactly one of TRUE, FALSE, UNKNOWN.",
        ):
            if snippet not in prompt:
                errors.append(f"{sample}: prompt is missing {snippet!r}")
                break
        if not str(prompt).rstrip().endswith("Answer:"):
            errors.append(f"{sample}: prompt does not end at the answer slot")
        grouped[record.get("pair_id", "")].append(record)
        if recompute_logic:
            errors.extend(_logic_errors(record))

    for pair_id, members in grouped.items():
        if len(members) != 2:
            errors.append(f"{pair_id}: pair has {len(members)} examples")
            continue
        if len({item["split"] for item in members}) != 1:
            errors.append(f"{pair_id}: members do not share a split")
        if len({item["base_case_id"] for item in members}) != 1:
            errors.append(f"{pair_id}: members do not share a base_case_id")
        if len({tuple(item["domain"]) for item in members}) != 1:
            errors.append(f"{pair_id}: members do not share a domain")
        labels = {item["label"] for item in members}
        if labels == {"UNKNOWN"}:
            pass
        elif labels == {"TRUE", "FALSE"}:
            pass
        else:
            errors.append(f"{pair_id}: labels {sorted(labels)} are not a valid contrast")
        errors.extend(_pair_audit_errors(pair_id, members))
        if members[0].get("pair_type") == "equivalent_form":
            forms = {item["negation_form"] for item in members}
            if forms != {"negated_universal", "existential_counterexample"}:
                errors.append(f"{pair_id}: equivalent-form pair does not contrast the two quantifier shapes")
            else:
                hosts = []
                for item in members:
                    item_statements, item_query = _formulas(item)
                    _role, host = negation_formula(item_statements, item_query)
                    hosts.append(host)
                if not equivalent(hosts[0], hosts[1], members[0]["domain"]):
                    errors.append(f"{pair_id}: equivalent-form members are not classically equivalent")

    if config and config.get("expected_totals"):
        errors.extend(_quota_errors(records, config))
        for record in records:
            split = record["split"]
            expected_pack = config["nl_pack_by_split"][split]
            expected_size = int(config["domain_size_by_split"][split])
            if record.get("nl_pack") != expected_pack:
                errors.append(f"{record['sample_id']}: template pack does not match the split policy")
            if len(record["domain"]) != expected_size:
                errors.append(f"{record['sample_id']}: domain size does not match the split policy")
            if record.get("seed") != int(config["seed"]):
                errors.append(f"{record['sample_id']}: seed was not stored")
            if record.get("generator_version") != config["generator_version"]:
                errors.append(f"{record['sample_id']}: generator version mismatch")
    errors.extend(label_balance_errors(records))
    errors.extend(_leakage_errors(records))
    return errors


def _quota_errors(records: list[dict[str, Any]], config: dict[str, Any]) -> list[str]:
    from negpilot.generator import _normalize_expected

    expected = _normalize_expected(config["expected_totals"])
    errors = []
    labels = Counter(item["label"] for item in records)
    positions = Counter(item["negation_position"] for item in records)
    scopes = Counter(item["negation_scope"] for item in records)
    depths = Counter(
        "null" if item["reasoning_depth"] is None else str(item["reasoning_depth"])
        for item in records
    )
    base_ids = {item["base_case_id"] for item in records}
    pair_ids = {item["pair_id"] for item in records}
    split_bases = Counter()
    kinds = Counter()
    for pair_id, members in _group(records).items():
        split_bases[members[0]["split"]] += 1
        labels_here = {item["label"] for item in members}
        kinds["determinate" if labels_here == {"TRUE", "FALSE"} else "unknown"] += 1
    actual = {
        "examples": len(records),
        "base_cases": len(base_ids),
        "pairs": len(pair_ids),
        "determinate_pairs": kinds["determinate"],
        "unknown_pairs": kinds["unknown"],
        "labels": dict(labels),
        "positions": dict(positions),
        "scopes": dict(scopes),
        "depths": dict(depths),
        "splits_base_cases": dict(split_bases),
    }
    for key, value in expected.items():
        got = actual[key]
        if got != value:
            errors.append(f"quota {key}: expected {value}, got {got}")
    return errors


def _leakage_errors(records: list[dict[str, Any]]) -> list[str]:
    locations: dict[str, set[str]] = defaultdict(set)
    for record in records:
        split = record.get("split")
        for field in ("skeleton_id", "canonical_skeleton"):
            skeleton = record.get(field)
            if skeleton and split:
                locations[f"{field}:{skeleton}"].add(str(split))
    leaked = [key for key, splits in locations.items() if len(splits) > 1]
    if not leaked:
        return []
    return [f"skeleton leakage: {len(leaked)} alpha-renamed skeletons occur in more than one split"]


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


def _pair_audit_errors(pair_id: str, members: list[dict[str, Any]]) -> list[str]:
    """Recompute the contrast audit.

    Experimental-control failure keeps the pair as an exploratory example.
    A missing reason or a broken sample is a validation error.
    """
    errors: list[str] = []
    left, right = members
    for record in members:
        if record.get("logical_pair_validity") not in {"pass", "fail"}:
            errors.append(f"{pair_id}: missing logical_pair_validity")
        if record.get("experimental_control_validity") not in {"pass", "fail"}:
            errors.append(f"{pair_id}: missing experimental_control_validity")
        if not isinstance(record.get("pair_metadata"), dict):
            errors.append(f"{pair_id}: missing pair_metadata")
    if errors:
        return errors
    if left.get("logical_pair_validity") != right.get("logical_pair_validity"):
        errors.append(f"{pair_id}: members do not share logical_pair_validity")
    if left.get("in_controlled_subset") != right.get("in_controlled_subset"):
        errors.append(f"{pair_id}: members do not share in_controlled_subset")
    studies = bool(left["pair_metadata"].get("studies_inference_type"))
    fresh = audit_pair(
        left,
        right,
        list(left.get("controlled_variables") or []),
        list(left.get("manipulated_variables") or []),
        list(left.get("derived_variables") or []),
        studies,
    )
    if fresh["logical_pair_validity"] != left["logical_pair_validity"]:
        errors.append(f"{pair_id}: stored logical pair audit does not match a fresh comparison")
    if fresh["experimental_control_validity"] != left["experimental_control_validity"]:
        errors.append(f"{pair_id}: stored experimental-control audit does not match a fresh comparison")
    if fresh["in_controlled_subset"] != left["in_controlled_subset"]:
        errors.append(f"{pair_id}: stored controlled-subset flag does not match a fresh comparison")
    reasons = fresh["rejection_reasons"]
    if left["logical_pair_validity"] != "pass":
        errors.append(f"{pair_id}: logical pair validity failed ({reasons})")
    if left["in_controlled_subset"] and reasons:
        errors.append(f"{pair_id}: controlled pair still lists rejection reasons")
    if not left["in_controlled_subset"] and not reasons:
        errors.append(f"{pair_id}: exploratory pair has no recorded reason")
    if left["in_controlled_subset"] and left["experimental_control_validity"] != "pass":
        errors.append(f"{pair_id}: controlled flag contradicts experimental control")
    return errors


def label_balance_errors(records: list[dict[str, Any]]) -> list[str]:
    """A criticality condition must not be tied to a single determinate label."""
    relevant = [
        record
        for record in records
        if record.get("experimental_category") == "negation_criticality"
        and record.get("contrast") == "critical_vs_distractor"
        and record.get("label") in {"TRUE", "FALSE"}
    ]
    if len(relevant) <= 4:
        return []
    polarities = {record.get("query_polarity") for record in relevant}
    if polarities != {"POSITIVE", "NEGATIVE"}:
        return [
            "label confounding: negation_criticality does not include both query polarities. "
            "This category cannot be used as an unconfounded main experiment."
        ]
    grouped: dict[bool, set[str]] = defaultdict(set)
    for record in relevant:
        grouped[bool(record.get("negation_critical"))].add(record["label"])
    errors = []
    for critical, labels in sorted(grouped.items()):
        if labels != {"TRUE", "FALSE"}:
            role = "critical" if critical else "distractor"
            errors.append(
                f"label confounding: {role} maps only to {sorted(labels)}. "
                "This category cannot be used as an unconfounded main experiment."
            )
    return errors


def _group(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["pair_id"]].append(record)
    return grouped


def validate_public(public_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> list[str]:
    errors = []
    gold_by_id = {row["sample_id"]: row for row in gold_rows}
    if len(public_rows) != len(gold_rows):
        errors.append("public and gold files have different lengths")
    forbidden = {
        "label",
        "binary_label",
        "proof_trace",
        "query_ast",
        "verification",
        "verification_status",
        "negation_position",
        "negation_scope",
        "pair_id",
        "pair_note",
        "inference_type",
        "negation_embedding",
        "negation_function",
        "negation_critical",
        "inference_steps",
        "proof_depth",
        "controlled_variables",
        "manipulated_variables",
        "logical_pair_validity",
        "experimental_control_validity",
        "in_controlled_subset",
        "pair_metadata",
        "relevant_premise_count",
        "experimental_category",
        "skeleton_id",
        "criticality_verification",
        "canonical_skeleton",
        "dataset_version",
        "semantic_equivalent",
        "equivalence_class",
        "equivalence_verification",
        "comparison_type",
        "label_before_ablation",
        "label_after_ablation",
        "ablation_kb_satisfiable",
    }
    seen = set()
    for row in public_rows:
        sample = row.get("sample_id")
        if sample in seen:
            errors.append(f"public duplicate {sample}")
        seen.add(sample)
        leaked = sorted(forbidden & set(row))
        if leaked:
            errors.append(f"public {sample} contains gold-only fields {leaked}")
        gold = gold_by_id.get(sample)
        if gold is None:
            errors.append(f"public {sample} has no gold record")
            continue
        if row.get("query") != gold["query"] or row.get("prompt") != gold["prompt"]:
            errors.append(f"public {sample} prompt does not match gold")
        expected_kb = [item["text"] for item in gold["knowledge_base"]["statements"]]
        if row.get("knowledge_base") != expected_kb:
            errors.append(f"public {sample} knowledge base text does not match gold")
        if row.get("domain") != gold["domain"] or row.get("split") != gold["split"]:
            errors.append(f"public {sample} domain or split does not match gold")
    missing = set(gold_by_id) - seen
    if missing:
        errors.append(f"public file is missing {len(missing)} gold sample ids")
    return errors

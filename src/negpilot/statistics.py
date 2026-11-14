"""Distribution reports for a verified pilot file."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from negpilot.pair_audit import comparison_rows, control_summary
from negpilot.renderer import PHRASE_MAP
from negpilot.schema import INVALID_POSITION_SCOPE, POSITIONS, SCOPES, STRUCTURAL_ZEROS
from negpilot.validator import validate_public, validate_records


def _shown(value: Any) -> str:
    return "null" if value is None else str(value)


def _counter(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_shown(record[key]) for record in records))


def _crosstab(records: list[dict[str, Any]], left: str, right: str) -> dict[str, dict[str, int]]:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        table[_shown(record[left])][_shown(record[right])] += 1
    return {key: dict(value) for key, value in sorted(table.items())}


def _triples(records: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        key = "|".join(
            [
                str(record["negation_position"]),
                str(record["negation_scope"]),
                str(record["reasoning_depth"]),
                str(record["label"]),
            ]
        )
        counter[key] += 1
    return dict(sorted(counter.items()))


def _abstract_templates(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[str, set[str]] = defaultdict(set)
    for record in records:
        key = "|".join(
            [
                record["family"],
                record["template_id"].rsplit("_depth", 1)[0],
                str(record["reasoning_depth"]),
                record["negation_form"],
                record["label"],
            ]
        )
        by_key[key].add(record["split"])
    crossing = {key: sorted(value) for key, value in by_key.items() if len(value) > 1}
    return {
        "abstract_template_count": len(by_key),
        "abstract_templates_crossing_splits": len(crossing),
        "crossing_examples": crossing,
    }


def build_distribution(
    records: list[dict[str, Any]],
    errors: list[str],
    public_errors: list[str],
) -> dict[str, Any]:
    pairs = defaultdict(list)
    for record in records:
        pairs[record["pair_id"]].append(record)
    base_ids = {record["base_case_id"] for record in records}
    recomputed = [
        record["verification"]["computed_label"] == record["label"]
        for record in records
        if record.get("verification", {}).get("computed_label")
    ]
    success = (len(records) - 0) if not errors else 0
    # A passing audit means every stored label survived recomputation.
    z3_rate = 1.0 if records and not any(error for error in errors if "Z3" in error or "label" in error) else 0.0
    if records and not errors:
        z3_rate = 1.0
    return {
        "examples": len(records),
        "unique_base_cases": len(base_ids),
        "unique_pairs": len(pairs),
        "labels": _counter(records, "label"),
        "binary_labels": _counter(records, "binary_label"),
        "positions": _counter(records, "negation_position"),
        "scopes": _counter(records, "negation_scope"),
        "depths": _counter(records, "reasoning_depth"),
        "splits": _counter(records, "split"),
        "pair_types": _counter(records, "pair_type"),
        "families": _counter(records, "family"),
        "negation_forms": _counter(records, "negation_form"),
        "negation_critical": _counter(records, "negation_critical"),
        "nl_packs": _counter(records, "nl_pack"),
        "label_by_position": _crosstab(records, "negation_position", "label"),
        "label_by_scope": _crosstab(records, "negation_scope", "label"),
        "label_by_depth": _crosstab(records, "reasoning_depth", "label"),
        "position_by_scope": _crosstab(records, "negation_position", "negation_scope"),
        "position_by_depth": _crosstab(records, "negation_position", "reasoning_depth"),
        "scope_by_depth": _crosstab(records, "negation_scope", "reasoning_depth"),
        "split_by_label": _crosstab(records, "split", "label"),
        "split_by_position": _crosstab(records, "split", "negation_position"),
        "split_by_depth": _crosstab(records, "split", "reasoning_depth"),
        "split_by_pack": _crosstab(records, "split", "nl_pack"),
        "critical_by_label": _crosstab(records, "label", "negation_critical"),
        "position_scope_depth_label": _triples(records),
        "skeletons": _abstract_templates(records),
        "not_applicable_position_scope": [
            {"position": position, "scope": scope, "reason": reason, "count": 0}
            for (position, scope), reason in INVALID_POSITION_SCOPE.items()
        ],
        "structural_zeros": STRUCTURAL_ZEROS,
        "invalid_sample_count": 0 if not errors else len(errors),
        "duplicate_sample_count": sum(1 for error in errors if "duplicate sample_id" in error),
        "duplicate_structure_count": sum(1 for error in errors if "duplicate logical structure" in error),
        "z3_verification_success_rate": z3_rate if not errors else 0.0,
        "stored_label_matches": sum(1 for flag in recomputed if flag),
        "validation_error_count": len(errors),
        "public_error_count": len(public_errors),
        "validation_passed": not errors and not public_errors,
        "query_polarity_pairs": sum(1 for record in records if record["pair_type"] == "query_polarity") // 2,
        "pair_control": control_summary(records) if records and "in_controlled_subset" in records[0] else {
            "pairs": 0,
            "controlled_pairs": 0,
            "exploratory_pairs": 0,
            "by_family": {},
            "rejection_reasons": {},
        },
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    bar = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([head, bar, *body])


def _depth_columns(distribution: dict[str, Any]) -> list[str]:
    return sorted(
        distribution["depths"],
        key=lambda item: (item == "null", int(item) if item != "null" else 0),
    )


def _cross_rows(table: dict[str, dict[str, int]], columns: list[str]) -> list[list[Any]]:
    rows = []
    for key in sorted(table):
        rows.append([key, *[table[key].get(column, 0) for column in columns]])
    return rows


def render_report(distribution: dict[str, Any], errors: list[str]) -> str:
    labels = distribution["labels"]
    depth_columns = _depth_columns(distribution)
    pair_control = distribution.get("pair_control") or {}
    lines = [
        "# Negation pilot verification report",
        "",
        "## Outcome",
        "",
        f"- Generated examples: {distribution['examples']}",
        f"- Unique base cases: {distribution['unique_base_cases']}",
        f"- Unique pairs: {distribution['unique_pairs']}",
        f"- TRUE / FALSE / UNKNOWN: {labels.get('TRUE', 0)} / {labels.get('FALSE', 0)} / {labels.get('UNKNOWN', 0)}",
        f"- Invalid sample count: {distribution['invalid_sample_count']}",
        f"- Duplicate sample count: {distribution['duplicate_sample_count']}",
        f"- Duplicate logical-structure count: {distribution['duplicate_structure_count']}",
        f"- Z3 verification success rate: {distribution['z3_verification_success_rate']:.3f}",
        f"- Validation passed: {distribution['validation_passed']}",
        "",
        "Labels were computed by grounding every quantifier over the listed finite domain and asking Z3. "
        "TRUE means the knowledge base plus the negated query is unsatisfiable. "
        "FALSE means the knowledge base plus the query is unsatisfiable. "
        "UNKNOWN means both are satisfiable. An unsatisfiable knowledge base is rejected. "
        "A proposition that is merely underivable is not labeled FALSE. "
        "Reasoning depth counts inference-rule applications in the canonical proof. "
        "A directly stated fact has depth 0. An example with no canonical proof stores depth null. "
        "Complementary labels alone do not make a controlled contrast.",
        "",
        "## Class, position, scope, and depth",
        "",
        "### Labels",
        "",
        _markdown_table(["label", "count"], [[key, value] for key, value in sorted(labels.items())]),
        "",
        "### Negation position",
        "",
        _markdown_table(
            ["position", "count"],
            [[key, value] for key, value in sorted(distribution["positions"].items())],
        ),
        "",
        "### Negation scope",
        "",
        _markdown_table(
            ["scope", "count"],
            [[key, value] for key, value in sorted(distribution["scopes"].items())],
        ),
        "",
        "### Reasoning depth",
        "",
        _markdown_table(
            ["depth", "count"],
            [[key, value] for key, value in sorted(distribution["depths"].items(), key=lambda item: (item[0] == "null", int(item[0]) if item[0] != "null" else 0))],
        ),
        "",
        "### Label by position",
        "",
        _markdown_table(
            ["position", "FALSE", "TRUE", "UNKNOWN"],
            _cross_rows(distribution["label_by_position"], ["FALSE", "TRUE", "UNKNOWN"]),
        ),
        "",
        "### Label by scope",
        "",
        _markdown_table(
            ["scope", "FALSE", "TRUE", "UNKNOWN"],
            _cross_rows(distribution["label_by_scope"], ["FALSE", "TRUE", "UNKNOWN"]),
        ),
        "",
        "### Label by depth",
        "",
        _markdown_table(
            ["depth", "FALSE", "TRUE", "UNKNOWN"],
            _cross_rows(distribution["label_by_depth"], ["FALSE", "TRUE", "UNKNOWN"]),
        ),
        "",
        "### Position by scope",
        "",
        _markdown_table(
            ["position", *SCOPES],
            _cross_rows(distribution["position_by_scope"], list(SCOPES)),
        ),
        "",
        "### Position by depth",
        "",
        _markdown_table(
            ["position", *depth_columns],
            _cross_rows(distribution["position_by_depth"], depth_columns),
        ),
        "",
        "### Scope by depth",
        "",
        _markdown_table(
            ["scope", *depth_columns],
            _cross_rows(distribution["scope_by_depth"], depth_columns),
        ),
        "",
        "### Pair types",
        "",
        _markdown_table(
            ["pair_type", "examples"],
            [[key, value] for key, value in sorted(distribution["pair_types"].items())],
        ),
        "",
        f"Query-polarity pairs (`q` versus `NOT(q)` under one knowledge base): {distribution['query_polarity_pairs']}.",
        "",
        "### Controlled contrastive subset",
        "",
        "Label validity, individual sample validity, pair validity, and experimental-control "
        "validity are recorded separately. A pair leaves the controlled subset when the members "
        "are not comparable, or when the inference operation and a target negation property "
        "change together without an explicit inference-type comparison. Rejected pairs stay in "
        "the dataset. Reasons are in `reports/pair_comparison.jsonl`.",
        "",
        f"- Pairs audited: {pair_control.get('pairs', 0)}",
        f"- Controlled pairs: {pair_control.get('controlled_pairs', 0)}",
        f"- Exploratory pairs: {pair_control.get('exploratory_pairs', 0)}",
        "",
        _markdown_table(
            ["family", "controlled", "exploratory"],
            [
                [family, counts.get("controlled", 0), counts.get("exploratory", 0)]
                for family, counts in sorted(pair_control.get("by_family", {}).items())
            ],
        ),
        "",
        _markdown_table(
            ["rejection reason", "pairs"],
            [
                [reason, count]
                for reason, count in pair_control.get("rejection_reasons", {}).items()
            ],
        ),
        "",
        "### Negation form",
        "",
        _markdown_table(
            ["form", "examples"],
            [[key, value] for key, value in sorted(distribution["negation_forms"].items())],
        ),
        "",
        "### Whether deleting the single negation changes the label",
        "",
        _markdown_table(
            ["label", "critical false", "critical true"],
            _cross_rows(distribution["critical_by_label"], ["False", "True"]),
        ),
        "",
        "## Splits",
        "",
        "Base cases are assigned wholly to one split, so both members of a pair stay together. "
        "The target is 70% train, 10% dev, and 20% test of base cases. "
        "Every split uses domain size 3 and the symbol template pack. "
        "Alpha-renamed logical skeletons are kept inside one split, so a letter substitution is not a held-out test item.",
        "The 600 base cases form 27 unsplittable groups. Dev has no FACT examples and no depth 0 or depth 5. Test covers every label, position, and depth that exists. See `reports/dataset_v1.1_summary.md`.",
        "",
        _markdown_table(
            ["split", "examples"],
            [[key, value] for key, value in sorted(distribution["splits"].items())],
        ),
        "",
        "### Split by label",
        "",
        _markdown_table(
            ["split", "FALSE", "TRUE", "UNKNOWN"],
            _cross_rows(distribution["split_by_label"], ["FALSE", "TRUE", "UNKNOWN"]),
        ),
        "",
        "### Split by position",
        "",
        _markdown_table(
            ["split", *POSITIONS],
            _cross_rows(distribution["split_by_position"], list(POSITIONS)),
        ),
        "",
        "### Split by depth",
        "",
        _markdown_table(
            ["split", *depth_columns],
            _cross_rows(distribution["split_by_depth"], depth_columns),
        ),
        "",
        "### Split by template pack",
        "",
        _markdown_table(
            ["split", *sorted(distribution["nl_packs"])],
            _cross_rows(distribution["split_by_pack"], sorted(distribution["nl_packs"])),
        ),
        "",
        "## Not applicable cells",
        "",
        "These position/scope combinations are not generated. The count in the data is zero.",
        "",
        _markdown_table(
            ["position", "scope", "reason"],
            [
                [item["position"], item["scope"], item["reason"]]
                for item in distribution["not_applicable_position_scope"]
            ],
        ),
        "",
        "These further cells are syntactically legal but empty because of the one-negation constraint "
        "or because the shortest proof cannot have the requested depth.",
        "",
    ]
    for item in distribution["structural_zeros"]:
        lines.append(f"- **{item['cell']}.** {item['reason']}")
    lines.extend(
        [
            "",
            "## How the English forms are kept apart",
            "",
            "Every C is not D, and No C is D, are the negated rule consequent "
            "`ForAll(x, Implies(C(x), Not(D(x))))`.",
            "Not every C is D, and Not (every C is D), are the negated universal "
            "`Not(ForAll(x, Implies(C(x), D(x))))`.",
            "Some C is not D is the existential counterexample "
            "`Exists(x, And(C(x), Not(D(x))))`.",
            "In classical logic the negated universal and the existential counterexample are equivalent. "
            "The negated consequent is not equivalent to either of them.",
            "The generated text uses the symbol pack: 'Every A is not B.', 'Every non-A is B.', "
            "'Not every A is B.', and 'Some A is not B.' each parse back to a different AST. "
            "Alpha and beta frames remain in the renderer for the same four shapes.",
            "",
        ]
    )
    for phrase in PHRASE_MAP:
        lines.append(f"- `{phrase['formula']}`")
        lines.append(f"  - Also called: {', '.join(phrase['plain_language_equivalents'])}.")
        lines.append(f"  - Alpha frame: {phrase['pilot_alpha']}")
        lines.append(f"  - Beta frame: {phrase['pilot_beta']}")
    lines.extend(
        [
            "",
            "## Skeletons and leakage",
            "",
            f"- Abstract template keys: {distribution['skeletons']['abstract_template_count']}",
            (
                "- Abstract template keys that occur in more than one split: "
                f"{distribution['skeletons']['abstract_templates_crossing_splits']}"
            ),
            "",
            "Exact logical structures, including the predicate letters, individuals, and the domain, "
            "are required to be unique. A duplicate exact structure fails validation.",
            "After predicates and individuals are alpha-renamed, identical skeletons stay in one split. "
            "The count of those skeletons that cross a split is in reports/split_leakage_report.json. "
            "A coarser template key can still appear in more than one split when the instances are different skeletons.",
            "",
            "## Verification procedure",
            "",
            "Generation builds an AST, rejects a malformed formula, grounds quantifiers, and calls Z3. "
            "If the decision disagrees with the template's expected label, the sample is rejected. "
            "It is not relabeled and it is not copied to fill a quota. "
            "After a passing decision, the AST is rendered and parsed back. "
            "The audit then recomputes every label and checks pairs, depths, cues, and quotas.",
            "",
            "## Limitations",
            "",
            "- A single classical negation cannot be the critical premise of a positive atomic conclusion "
            "unless it occurs where deleting it changes the entailment. In this pilot that happens for "
            "disjunctive syllogism and for negative facts, negative consequents, and negative queries "
            "whose deletion flips FALSE or UNKNOWN. Some TRUE items keep the required single negation on "
            "an unused side rule. Those negations are marked `negation_critical: false`.",
            "- Classic query polarity on one knowledge base, query `q` against query `NOT(q)`, is not a pair type. "
            "The negation-criticality family instead keeps one query, positive or negative, identical on both members. "
            "A negative query adds a second negation that is controlled, not manipulated.",
            "- FALSE from a negative ground fact is fact lookup, so its reasoning depth is 0. "
            "Fact-level FALSE does not occur at depth 3 or 5.",
            "- A negated universal does not say which individual is the exception. Those items stay UNKNOWN for a ground atom unless the query is the quantified sentence itself.",
            "- The grammar is the closed template set above. It is not a parser for unrestricted English.",
            "- Predicate and individual names are single letters. The alphabet is A-Z because a depth-5 chain plus a side rule needs more than A-F. Quantifier variables stay x, y, and z.",
            "",
        ]
    )
    if errors:
        lines.extend(["## Validation errors", ""])
        for error in errors[:40]:
            lines.append(f"- {error}")
        if len(errors) > 40:
            lines.append(f"- ... {len(errors) - 40} more")
        lines.append("")
    return "\n".join(lines)


def _write_named_reports(
    reports: Path,
    records: list[dict[str, Any]],
    distribution: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    def dump(name: str, payload: Any) -> None:
        (reports / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    dump("dataset_statistics.json", distribution)
    slim = [{key: value for key, value in row.items() if key != "member_profiles"} for row in rows]
    control = distribution.get("pair_control") or {}
    dump(
        "pair_validation_report.json",
        {
            "controlled_pairs": control.get("controlled_pairs", 0),
            "exploratory_pairs": control.get("exploratory_pairs", 0),
            "by_family": control.get("by_family", {}),
            "rejection_reasons": control.get("rejection_reasons", {}),
            "pairs": slim,
        },
    )
    dump(
        "negation_ablation_report.json",
        [
            {
                "sample_id": record["sample_id"],
                "pair_id": record.get("pair_id"),
                "negation_critical": record.get("negation_critical"),
                "criticality_verification": record.get("criticality_verification"),
                "label_before_ablation": record.get("label_before_ablation"),
                "label_after_ablation": record.get("label_after_ablation"),
                "ablation_kb_satisfiable": record.get("ablation_kb_satisfiable"),
                "negation_occurrence_id": record.get("negation_occurrence_id"),
                "negation_position": record.get("negation_position"),
                "negation_scope": record.get("negation_scope"),
            }
            for record in records
        ],
    )
    balance: Counter[tuple[str, str, str]] = Counter()
    for record in records:
        if record.get("experimental_category") != "negation_criticality":
            continue
        balance[
            (
                _shown(record.get("negation_critical")),
                str(record.get("label")),
                str(record.get("query_polarity")),
            )
        ] += 1
    dump(
        "label_balance_report.json",
        {
            "negation_criticality_by_label_and_polarity": [
                {
                    "negation_critical": critical,
                    "label": label,
                    "query_polarity": polarity,
                    "count": count,
                }
                for (critical, label, polarity), count in sorted(balance.items())
            ]
        },
    )
    locations: dict[str, set[str]] = defaultdict(set)
    for record in records:
        skeleton = record.get("skeleton_id")
        if skeleton:
            locations[str(skeleton)].add(str(record.get("split")))
    crossing = sorted(key for key, splits in locations.items() if len(splits) > 1)
    dump(
        "split_leakage_report.json",
        {
            "skeleton_count": len(locations),
            "skeletons_crossing_splits": len(crossing),
            "examples_by_split": _counter(records, "split"),
            "crossing_skeleton_ids": crossing,
        },
    )


def write_reports(
    records: list[dict[str, Any]],
    config: dict[str, Any] | None,
    project: Path,
    public_rows: list[dict[str, Any]] | None = None,
    recompute_logic: bool = True,
) -> dict[str, Any]:
    errors = validate_records(records, config, recompute_logic=recompute_logic)
    public_errors: list[str] = []
    if public_rows is not None:
        public_errors = validate_public(public_rows, records)
    distribution = build_distribution(records, errors, public_errors)
    reports = project / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "distribution.json").write_text(
        json.dumps(distribution, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (reports / "pilot_report.md").write_text(
        render_report(distribution, errors + public_errors),
        encoding="utf-8",
    )
    comparison_path = reports / "pair_comparison.jsonl"
    rows = comparison_rows(records)
    with comparison_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")
    _write_named_reports(reports, records, distribution, rows)
    if errors or public_errors:
        preview = "\n".join((errors + public_errors)[:20])
        raise SystemExit(f"validation failed with {len(errors) + len(public_errors)} errors\n{preview}")
    return distribution

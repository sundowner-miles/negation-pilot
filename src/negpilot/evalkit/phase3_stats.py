"""Statistics for phase-3 experiments. Pure functions, no file or model access."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from negpilot.evalkit.parse import LABELS
from negpilot.evalkit.phase2_stats import summarize_predictions, wilson_interval

DEPTH_KEYS = ("0", "1", "3", "5", "null")
EQUIVALENT_FORMS = ("negated_universal", "existential_counterexample")


def depth_key(value: Any) -> str:
    return "null" if value is None else str(value)


def _label_slice(rows: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    part = [row for row in rows if row["gold_label"] == label]
    if not part:
        return None
    correct = sum(1 for row in part if row["correct"])
    interval = wilson_interval(correct, len(part))
    return {
        "n": len(part),
        "correct": correct,
        "accuracy": correct / len(part),
        "accuracy_ci95": list(interval) if interval else None,
    }


def depth_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accuracy by canonical proof depth.

    Absent gold labels are omitted. Depth 0 and null stay in the report so
    they can be read separately from the 1/3/5 comparison.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[depth_key(row.get("reasoning_depth"))].append(row)
    reports = []
    for key in DEPTH_KEYS:
        subset = grouped.get(key, [])
        if not subset:
            continue
        by_label = {}
        for label in LABELS:
            slice_summary = _label_slice(subset, label)
            if slice_summary is not None:
                by_label[label] = slice_summary
        reports.append(
            {
                "depth": key,
                "n": len(subset),
                "controlled_n": sum(1 for row in subset if row.get("in_controlled_subset") is True),
                "exploratory_n": sum(1 for row in subset if row.get("in_controlled_subset") is False),
                "families": dict(Counter(row.get("family") for row in subset)),
                "summary": summarize_predictions(subset),
                "by_label": by_label,
            }
        )
    return reports


def equivalent_form_pairs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair negated-universal and existential-counterexample members.

    Incomplete pairs are rejected and are not scored.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("pair_type") == "equivalent_form":
            grouped[row["pair_id"]].append(row)
    usable = []
    rejected = []
    for pair_id, members in sorted(grouped.items()):
        reasons = []
        if len(members) != 2:
            reasons.append("member_count")
        forms = {member.get("negation_form") for member in members}
        if forms != set(EQUIVALENT_FORMS):
            reasons.append("form_pair")
        if any(member.get("gold_label") != "UNKNOWN" for member in members):
            reasons.append("gold_not_unknown")
        if len({member.get("split") for member in members}) != 1:
            reasons.append("split_mismatch")
        if reasons:
            rejected.append({"pair_id": pair_id, "reasons": reasons})
            continue
        universal = next(member for member in members if member["negation_form"] == "negated_universal")
        existential = next(
            member for member in members if member["negation_form"] == "existential_counterexample"
        )
        usable.append(
            {
                "pair_id": pair_id,
                "split": universal.get("split"),
                "family": universal.get("family"),
                "universal_id": universal["sample_id"],
                "existential_id": existential["sample_id"],
                "universal_pred": universal["predicted_label"],
                "existential_pred": existential["predicted_label"],
                "agree": universal["predicted_label"] == existential["predicted_label"],
                "both_correct": bool(universal["correct"] and existential["correct"]),
                "universal_correct": bool(universal["correct"]),
                "existential_correct": bool(existential["correct"]),
            }
        )
    return {"pairs": usable, "rejected": rejected}


def equivalent_summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Agreement and pair accuracy are separate. Agreement is not correctness."""
    n = len(pairs)
    if n == 0:
        raise ValueError("equivalent-form summary needs at least one pair")
    agree = sum(1 for pair in pairs if pair["agree"])
    both = sum(1 for pair in pairs if pair["both_correct"])
    directions: Counter[str] = Counter()
    for pair in pairs:
        if not pair["agree"]:
            directions[f"{pair['universal_pred']} vs {pair['existential_pred']}"] += 1
    agree_ci = wilson_interval(agree, n)
    both_ci = wilson_interval(both, n)
    return {
        "n_pairs": n,
        "agreement": agree,
        "agreement_rate": agree / n,
        "agreement_ci95": list(agree_ci) if agree_ci else None,
        "both_correct": both,
        "pair_accuracy": both / n,
        "pair_accuracy_ci95": list(both_ci) if both_ci else None,
        "agreed_and_wrong": sum(1 for pair in pairs if pair["agree"] and not pair["both_correct"]),
        "disagreement": n - agree,
        "disagreement_directions": dict(sorted(directions.items())),
        "universal_correct": sum(1 for pair in pairs if pair["universal_correct"]),
        "existential_correct": sum(1 for pair in pairs if pair["existential_correct"]),
    }


def _bucket(label: Any) -> str:
    if label in LABELS:
        return str(label)
    return "invalid_output"


def ablation_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare original and ablation predictions on one rendered subset.

    A prediction follows the logical transition when the ordered pair
    (prediction before, prediction after) equals (Z3 label before, Z3 label
    after). That is stricter than merely changing, and stricter than matching
    only the ablated label.
    """
    if not items:
        raise ValueError("ablation summary needs at least one rendered sample")
    before_rows = [
        {"gold_label": item["label_before"], "predicted_label": item["pred_before"]}
        for item in items
    ]
    after_rows = [
        {"gold_label": item["label_after"], "predicted_label": item["pred_after"]}
        for item in items
    ]
    transition: dict[str, dict[str, int]] = {
        source: {target: 0 for target in (*LABELS, "invalid_output")}
        for source in (*LABELS, "invalid_output")
    }
    for item in items:
        transition[_bucket(item["pred_before"])][_bucket(item["pred_after"])] += 1

    def _rate(subset: list[dict[str, Any]], predicate) -> dict[str, Any]:
        n = len(subset)
        hits = sum(1 for item in subset if predicate(item))
        interval = wilson_interval(hits, n) if n else None
        return {
            "n": n,
            "count": hits,
            "rate": None if n == 0 else hits / n,
            "ci95": list(interval) if interval else None,
        }

    changed_gold = [item for item in items if item["label_before"] != item["label_after"]]
    stable_gold = [item for item in items if item["label_before"] == item["label_after"]]
    critical = [item for item in items if item["negation_critical"] is True]
    distractor = [item for item in items if item["negation_critical"] is False]
    return {
        "n": len(items),
        "original": summarize_predictions(before_rows),
        "ablated": summarize_predictions(after_rows),
        "prediction_transition": transition,
        "follows_label_transition": _rate(
            changed_gold,
            lambda item: (item["pred_before"], item["pred_after"])
            == (item["label_before"], item["label_after"]),
        ),
        "ablation_matches_new_label": _rate(
            changed_gold,
            lambda item: item["pred_after"] == item["label_after"],
        ),
        "prediction_changed_when_label_changed": _rate(
            changed_gold,
            lambda item: item["pred_before"] != item["pred_after"],
        ),
        "prediction_unchanged_when_label_stable": _rate(
            stable_gold,
            lambda item: item["pred_before"] == item["pred_after"],
        ),
        "critical_prediction_changed": _rate(
            critical,
            lambda item: item["pred_before"] != item["pred_after"],
        ),
        "distractor_prediction_changed": _rate(
            distractor,
            lambda item: item["pred_before"] != item["pred_after"],
        ),
        "critical_matches_label_change_partition": {item["sample_id"] for item in critical}
        == {item["sample_id"] for item in changed_gold},
    }

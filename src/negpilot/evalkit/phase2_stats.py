"""Statistics for phase-2 experiments. Pure functions, no file or model access."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any

from negpilot.evalkit.parse import LABELS
from negpilot.evalkit.score import classification_counts

ANALYSIS_FIELDS = (
    "sample_id",
    "split",
    "label",
    "negation_position",
    "negation_scope",
    "query_polarity",
    "negation_critical",
    "family",
    "pair_id",
    "in_controlled_subset",
    "pair_type",
    "reasoning_depth",
)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval for a binomial proportion."""
    if n <= 0:
        return None
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _binom_pmf(k: int, n: int) -> float:
    return math.comb(n, k) / (2**n)


def mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """Two-sided exact McNemar test on discordant pairs.

    b is the count of pairs where the first condition is wrong and the
    second is right. c is the opposite discordant cell. The null is that
    the two discordant directions are equally likely.
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_discordant": 0, "p_value": None}
    observed = _binom_pmf(b, n)
    p_value = sum(_binom_pmf(i, n) for i in range(n + 1) if _binom_pmf(i, n) <= observed + 1e-15)
    return {"b": b, "c": c, "n_discordant": n, "p_value": min(1.0, p_value)}


def paired_difference_ci(
    first_correct: list[bool],
    second_correct: list[bool],
    *,
    seed: int = 20261111,
    replicates: int = 10000,
) -> dict[str, Any]:
    """Bootstrap percentile interval for the paired accuracy difference.

    The difference is mean(first correct) minus mean(second correct).
    """
    if len(first_correct) != len(second_correct) or not first_correct:
        raise ValueError("paired correctness vectors must be non-empty and aligned")
    diffs = [int(a) - int(b) for a, b in zip(first_correct, second_correct)]
    n = len(diffs)
    point = sum(diffs) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(replicates):
        draw = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(draw) / n)
    boots.sort()
    lo_index = int(0.025 * (replicates - 1))
    hi_index = int(0.975 * (replicates - 1))
    return {
        "n_pairs": n,
        "difference": point,
        "ci95": [boots[lo_index], boots[hi_index]],
        "seed": seed,
        "replicates": replicates,
    }


def summarize_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Accuracy, macro-F1 and confusion for aligned rows.

    Macro-F1 is omitted unless TRUE, FALSE and UNKNOWN all occur as gold
    labels. A two-class slice does not get a three-class macro average.
    """
    metrics = classification_counts([(row["gold_label"], row["predicted_label"]) for row in rows])
    present = [label for label in LABELS if metrics["per_class"][label]["support"] > 0]
    if len(present) < 3:
        metrics["macro_f1"] = None
        metrics["macro_f1_note"] = "not computed: this slice does not contain all three gold labels"
    else:
        metrics["macro_f1_note"] = "unweighted mean of TRUE, FALSE and UNKNOWN F1"
    interval = wilson_interval(metrics["correct"], metrics["n"])
    metrics["accuracy_ci95"] = list(interval) if interval else None
    metrics.pop("prediction_counts", None)
    return metrics


def join_predictions(
    predictions: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gold_by_id = {row["sample_id"]: row for row in gold_rows}
    if len(gold_by_id) != len(gold_rows):
        raise ValueError("duplicate gold sample_id")
    joined = []
    seen: set[str] = set()
    for pred in predictions:
        sample_id = pred["sample_id"]
        if sample_id in seen:
            raise ValueError(f"duplicate prediction {sample_id}")
        seen.add(sample_id)
        gold = gold_by_id[sample_id]
        if gold["label"] not in LABELS:
            raise ValueError(f"illegal gold label for {sample_id}")
        row = {
            "sample_id": sample_id,
            "gold_label": gold["label"],
            "predicted_label": pred.get("predicted_label"),
            "correct": pred.get("predicted_label") == gold["label"],
            "parse_status": pred.get("parse_status"),
            "raw_output": pred.get("raw_output"),
        }
        for field in ANALYSIS_FIELDS:
            if field == "sample_id":
                continue
            if field == "label":
                continue
            row[field] = gold.get(field)
        joined.append(row)
    return joined


def criticality_pairs(rows: list[dict[str, Any]], family: str = "rule_consequent_contrast") -> dict[str, Any]:
    """Pair critical and distractor members. Incomplete pairs are rejected."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("family") == family:
            grouped[row["pair_id"]].append(row)
    usable = []
    rejected = []
    for pair_id, members in sorted(grouped.items()):
        reasons = []
        if len(members) != 2:
            reasons.append("member_count")
        critical = [row for row in members if row.get("negation_critical") is True]
        distractor = [row for row in members if row.get("negation_critical") is False]
        if len(critical) != 1 or len(distractor) != 1:
            reasons.append("criticality_assignment")
        if len(members) == 2:
            if members[0].get("query_polarity") != members[1].get("query_polarity"):
                reasons.append("polarity_mismatch")
            if {members[0].get("split"), members[1].get("split")} != {members[0].get("split")}:
                reasons.append("split_mismatch")
        if reasons:
            rejected.append({"pair_id": pair_id, "reasons": reasons})
            continue
        polarity = critical[0]["query_polarity"]
        usable.append(
            {
                "pair_id": pair_id,
                "query_polarity": polarity,
                "reasoning_depth": critical[0].get("reasoning_depth"),
                "in_controlled_subset": critical[0].get("in_controlled_subset"),
                "critical_id": critical[0]["sample_id"],
                "distractor_id": distractor[0]["sample_id"],
                "critical_gold": critical[0]["gold_label"],
                "distractor_gold": distractor[0]["gold_label"],
                "critical_pred": critical[0]["predicted_label"],
                "distractor_pred": distractor[0]["predicted_label"],
                "critical_correct": bool(critical[0]["correct"]),
                "distractor_correct": bool(distractor[0]["correct"]),
                "both_correct": bool(critical[0]["correct"] and distractor[0]["correct"]),
            }
        )
    return {"pairs": usable, "rejected": rejected}


def _condition_summary(pairs: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    flag = f"{condition}_correct"
    gold = f"{condition}_gold"
    pred = f"{condition}_pred"
    rows = [
        {"gold_label": pair[gold], "predicted_label": pair[pred], "correct": pair[flag]}
        for pair in pairs
    ]
    summary = summarize_predictions(rows) if rows else {"n": 0, "correct": 0, "accuracy": None}
    summary["condition"] = condition
    return summary


def _transition(pairs: list[dict[str, Any]]) -> dict[str, int]:
    table = {
        "both_correct": 0,
        "critical_only": 0,
        "distractor_only": 0,
        "both_wrong": 0,
    }
    for pair in pairs:
        if pair["critical_correct"] and pair["distractor_correct"]:
            table["both_correct"] += 1
        elif pair["critical_correct"]:
            table["critical_only"] += 1
        elif pair["distractor_correct"]:
            table["distractor_only"] += 1
        else:
            table["both_wrong"] += 1
    return table


def summarize_criticality(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Paired critical-versus-distractor summary, including polarity strata."""
    def one_slice(slice_pairs: list[dict[str, Any]]) -> dict[str, Any]:
        if not slice_pairs:
            return {"n_pairs": 0}
        transition = _transition(slice_pairs)
        # b: critical wrong, distractor right. c: critical right, distractor wrong.
        comparison = mcnemar_exact(transition["distractor_only"], transition["critical_only"])
        effect = paired_difference_ci(
            [pair["critical_correct"] for pair in slice_pairs],
            [pair["distractor_correct"] for pair in slice_pairs],
        )
        both = sum(pair["both_correct"] for pair in slice_pairs)
        return {
            "n_pairs": len(slice_pairs),
            "pair_accuracy": both / len(slice_pairs),
            "critical": _condition_summary(slice_pairs, "critical"),
            "distractor": _condition_summary(slice_pairs, "distractor"),
            "transition": transition,
            "mcnemar": comparison,
            "critical_minus_distractor": effect,
            "gold_by_condition": {
                "critical": sorted({pair["critical_gold"] for pair in slice_pairs}),
                "distractor": sorted({pair["distractor_gold"] for pair in slice_pairs}),
            },
        }

    by_polarity = {}
    for polarity in ("POSITIVE", "NEGATIVE"):
        by_polarity[polarity] = one_slice(
            [pair for pair in pairs if pair["query_polarity"] == polarity]
        )
    return {"pooled": one_slice(pairs), "by_query_polarity": by_polarity}


def group_metrics(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    """Per-value accuracy. Values that do not occur are not given an accuracy."""
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field)].append(row)
    reports = []
    for value, members in sorted(grouped.items(), key=lambda item: str(item[0])):
        summary = summarize_predictions(members)
        by_label = []
        for label in LABELS:
            subset = [row for row in members if row["gold_label"] == label]
            if not subset:
                continue
            correct = sum(row["correct"] for row in subset)
            interval = wilson_interval(correct, len(subset))
            by_label.append(
                {
                    "gold_label": label,
                    "n": len(subset),
                    "correct": correct,
                    "accuracy": correct / len(subset),
                    "accuracy_ci95": list(interval) if interval else None,
                }
            )
        reports.append({"group": value, "metrics": summary, "by_gold_label": by_label})
    return reports

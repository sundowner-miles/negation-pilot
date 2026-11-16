"""Score saved predictions against gold labels.

Invalid outputs count as incorrect. They are not mapped to FALSE or UNKNOWN.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from negpilot.evalkit.parse import LABELS

PREDICTED_COLUMNS = (*LABELS, "invalid_output")


def _safe_div(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def classification_counts(
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    """Compute accuracy, per-class precision/recall/F1, and a confusion table.

    pairs are (gold_label, predicted_label). Gold labels must be TRUE,
    FALSE, or UNKNOWN. Predicted labels may also be invalid_output.
    """
    if any(gold not in LABELS for gold, _ in pairs):
        bad = sorted({gold for gold, _ in pairs if gold not in LABELS})
        raise ValueError(f"gold labels outside TRUE/FALSE/UNKNOWN: {bad}")

    matrix = {
        gold: {pred: 0 for pred in PREDICTED_COLUMNS}
        for gold in LABELS
    }
    for gold, pred in pairs:
        column = pred if pred in PREDICTED_COLUMNS else "invalid_output"
        matrix[gold][column] += 1

    correct = sum(matrix[label][label] for label in LABELS)
    n = len(pairs)
    invalid = sum(matrix[gold]["invalid_output"] for gold in LABELS)
    per_class: dict[str, Any] = {}
    f1_values: list[float] = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        support = sum(matrix[label].values())
        fn = support - tp
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, support)
        if precision is None or recall is None or precision + recall == 0:
            f1 = 0.0 if support else None
        else:
            f1 = 2 * precision * recall / (precision + recall)
        if f1 is not None:
            f1_values.append(f1)
        per_class[label] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "error_rate": _safe_div(support - tp, support),
        }

    return {
        "n": n,
        "correct": correct,
        "accuracy": _safe_div(correct, n),
        "macro_f1": (sum(f1_values) / len(f1_values)) if f1_values else None,
        "invalid_output": invalid,
        "invalid_output_rate": _safe_div(invalid, n),
        "per_class": per_class,
        "confusion": matrix,
        "prediction_counts": dict(Counter(pred for _, pred in pairs)),
    }


def align_predictions(
    predictions: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join predictions to gold on sample_id. Does not read model prompts."""
    gold_by_id = {}
    for row in gold_rows:
        sample_id = row["sample_id"]
        if sample_id in gold_by_id:
            raise ValueError(f"duplicate gold sample_id {sample_id}")
        gold_by_id[sample_id] = row

    aligned = []
    seen: set[str] = set()
    for pred in predictions:
        sample_id = pred["sample_id"]
        if sample_id in seen:
            raise ValueError(f"duplicate prediction sample_id {sample_id}")
        seen.add(sample_id)
        if sample_id not in gold_by_id:
            raise ValueError(f"prediction sample_id {sample_id} is not in gold")
        gold = gold_by_id[sample_id]
        if gold["label"] not in LABELS:
            raise ValueError(f"illegal gold label for {sample_id}: {gold['label']}")
        predicted = pred.get("predicted_label")
        aligned.append(
            {
                "sample_id": sample_id,
                "split": gold.get("split"),
                "gold_label": gold["label"],
                "predicted_label": predicted,
                "correct": predicted == gold["label"],
                "parse_status": pred.get("parse_status"),
            }
        )
    return aligned


def score_predictions(
    predictions: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    aligned = align_predictions(predictions, gold_rows)
    metrics = classification_counts(
        [(row["gold_label"], row["predicted_label"]) for row in aligned]
    )
    metrics["rows"] = aligned
    return metrics


def write_confusion_csv(path: Path, matrix: dict[str, dict[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["gold", *PREDICTED_COLUMNS]
    lines = [",".join(header)]
    for gold in LABELS:
        lines.append(",".join([gold, *[str(matrix[gold][col]) for col in PREDICTED_COLUMNS]]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metrics(path: Path, metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: value for key, value in metrics.items() if key != "rows"}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

"""Choose a fixed smoke-test slice. This slice is not a performance sample."""

from __future__ import annotations

from negpilot.evalkit.parse import LABELS


def select_smoke_ids(
    gold_rows: list[dict],
    *,
    split: str = "dev",
    n_per_label: int = 2,
) -> list[str]:
    """Take the first n_per_label sample ids of each gold label in one split.

    Ordering is sample_id ascending, so the slice does not depend on file
    order. Gold labels are used only to choose ids. They are not returned.
    """
    if n_per_label < 1:
        raise ValueError("n_per_label must be positive")
    chosen: dict[str, list[str]] = {label: [] for label in LABELS}
    for row in sorted(gold_rows, key=lambda item: item["sample_id"]):
        if row.get("split") != split:
            continue
        label = row.get("label")
        if label not in chosen:
            continue
        bucket = chosen[label]
        if len(bucket) < n_per_label:
            bucket.append(row["sample_id"])
    missing = [label for label, ids in chosen.items() if len(ids) < n_per_label]
    if missing:
        raise ValueError(
            f"split {split} does not have {n_per_label} samples for {missing}"
        )
    ordered: list[str] = []
    for label in LABELS:
        ordered.extend(chosen[label])
    return ordered

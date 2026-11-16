"""Checks for phase-2 paired tests and grouping rules."""

from negpilot.evalkit.phase2_stats import (
    criticality_pairs,
    group_metrics,
    mcnemar_exact,
    paired_difference_ci,
    summarize_criticality,
    summarize_predictions,
)


def _row(sample_id, gold, pred, **extra):
    return {
        "sample_id": sample_id,
        "gold_label": gold,
        "predicted_label": pred,
        "correct": gold == pred,
        "family": "rule_consequent_contrast",
        "pair_id": extra.get("pair_id", "p"),
        "negation_critical": extra.get("negation_critical", True),
        "query_polarity": extra.get("query_polarity", "POSITIVE"),
        "split": "test",
        "negation_position": extra.get("negation_position", "RULE"),
    }


def test_macro_f1_requires_three_gold_labels():
    rows = [
        {"gold_label": "TRUE", "predicted_label": "TRUE"},
        {"gold_label": "FALSE", "predicted_label": "FALSE"},
    ]
    summary = summarize_predictions(rows)
    assert summary["n"] == 2
    assert summary["accuracy"] == 1
    assert summary["macro_f1"] is None


def test_three_class_slice_keeps_macro_f1():
    rows = [
        {"gold_label": "TRUE", "predicted_label": "TRUE"},
        {"gold_label": "FALSE", "predicted_label": "UNKNOWN"},
        {"gold_label": "UNKNOWN", "predicted_label": "FALSE"},
    ]
    summary = summarize_predictions(rows)
    assert summary["macro_f1"] is not None
    assert summary["correct"] == 1
    assert summary["confusion"]["UNKNOWN"]["FALSE"] == 1


def test_mcnemar_is_one_when_discordant_counts_match():
    result = mcnemar_exact(4, 4)
    assert result["p_value"] == 1
    assert result["n_discordant"] == 8


def test_mcnemar_detects_a_one_sided_discordant_imbalance():
    result = mcnemar_exact(0, 8)
    assert result["p_value"] < 0.01


def test_paired_interval_contains_a_constant_difference():
    effect = paired_difference_ci([True, True, False], [False, False, False], replicates=200)
    assert effect["difference"] == 2 / 3
    assert effect["ci95"][0] <= effect["difference"] <= effect["ci95"][1]


def test_criticality_keeps_only_complete_pairs_and_stratifies():
    rows = [
        _row("c1", "FALSE", "FALSE", pair_id="p1", negation_critical=True, query_polarity="POSITIVE"),
        _row("d1", "TRUE", "TRUE", pair_id="p1", negation_critical=False, query_polarity="POSITIVE"),
        _row("c2", "TRUE", "FALSE", pair_id="p2", negation_critical=True, query_polarity="NEGATIVE"),
        _row("d2", "FALSE", "FALSE", pair_id="p2", negation_critical=False, query_polarity="NEGATIVE"),
        _row("orphan", "TRUE", "TRUE", pair_id="p3", negation_critical=True),
    ]
    built = criticality_pairs(rows)
    assert [pair["pair_id"] for pair in built["pairs"]] == ["p1", "p2"]
    assert built["rejected"][0]["pair_id"] == "p3"
    summary = summarize_criticality(built["pairs"])
    assert summary["pooled"]["n_pairs"] == 2
    assert summary["pooled"]["pair_accuracy"] == 0.5
    assert summary["by_query_polarity"]["POSITIVE"]["n_pairs"] == 1
    assert summary["by_query_polarity"]["NEGATIVE"]["critical"]["accuracy"] == 0


def test_group_metrics_skip_absent_labels():
    rows = [
        _row("a", "FALSE", "FALSE", negation_position="QUERY"),
        _row("b", "UNKNOWN", "FALSE", negation_position="QUERY"),
    ]
    groups = group_metrics(rows, "negation_position")
    assert groups[0]["group"] == "QUERY"
    assert [item["gold_label"] for item in groups[0]["by_gold_label"]] == ["FALSE", "UNKNOWN"]
    assert groups[0]["metrics"]["macro_f1"] is None

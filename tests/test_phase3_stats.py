"""Checks for depth slices, equivalent-form pairs, and ablation rendering."""

from negpilot.ast import And, Atom, Exists, Not, Or
from negpilot.evalkit.ablation_inputs import try_render_ablation
from negpilot.evalkit.phase3_stats import (
    ablation_summary,
    depth_report,
    equivalent_form_pairs,
    equivalent_summary,
)
from negpilot.evalkit.prompt import assert_public_record
from negpilot.schema import PUBLIC_FIELDS


def _item(sample_id, before, after, pred_before, pred_after, critical=True):
    return {
        "sample_id": sample_id,
        "label_before": before,
        "label_after": after,
        "pred_before": pred_before,
        "pred_after": pred_after,
        "negation_critical": critical,
    }


def test_depth_report_omits_absent_labels():
    rows = [
        {
            "gold_label": "FALSE",
            "predicted_label": "FALSE",
            "correct": True,
            "reasoning_depth": 0,
            "in_controlled_subset": False,
            "family": "direct",
        },
        {
            "gold_label": "TRUE",
            "predicted_label": "FALSE",
            "correct": False,
            "reasoning_depth": 1,
            "in_controlled_subset": True,
            "family": "rule_consequent_contrast",
        },
    ]
    report = {item["depth"]: item for item in depth_report(rows)}
    assert set(report) == {"0", "1"}
    assert "TRUE" not in report["0"]["by_label"]
    assert report["0"]["summary"]["macro_f1"] is None
    assert report["1"]["by_label"]["TRUE"]["n"] == 1
    assert report["1"]["controlled_n"] == 1


def test_equivalent_agreement_is_not_accuracy():
    rows = []
    for index, (universal, existential) in enumerate((("FALSE", "FALSE"), ("UNKNOWN", "TRUE"))):
        pair_id = f"p{index}"
        rows.append(
            {
                "sample_id": f"{pair_id}u",
                "pair_id": pair_id,
                "pair_type": "equivalent_form",
                "negation_form": "negated_universal",
                "gold_label": "UNKNOWN",
                "predicted_label": universal,
                "correct": universal == "UNKNOWN",
                "split": "test",
                "family": "unk_query_quantifier_form",
            }
        )
        rows.append(
            {
                "sample_id": f"{pair_id}e",
                "pair_id": pair_id,
                "pair_type": "equivalent_form",
                "negation_form": "existential_counterexample",
                "gold_label": "UNKNOWN",
                "predicted_label": existential,
                "correct": existential == "UNKNOWN",
                "split": "test",
                "family": "unk_query_quantifier_form",
            }
        )
    paired = equivalent_form_pairs(rows)
    assert paired["rejected"] == []
    summary = equivalent_summary(paired["pairs"])
    assert summary["n_pairs"] == 2
    assert summary["agreement"] == 1
    assert summary["both_correct"] == 0
    assert summary["agreed_and_wrong"] == 1
    assert summary["disagreement_directions"] == {"UNKNOWN vs TRUE": 1}


def test_ablation_direction_requires_both_endpoints():
    summary = ablation_summary(
        [
            _item("a", "FALSE", "TRUE", "FALSE", "TRUE", True),
            _item("b", "FALSE", "TRUE", "FALSE", "FALSE", True),
            _item("c", "UNKNOWN", "UNKNOWN", "TRUE", "TRUE", False),
        ]
    )
    assert summary["follows_label_transition"]["count"] == 1
    assert summary["follows_label_transition"]["n"] == 2
    assert summary["ablation_matches_new_label"]["count"] == 1
    assert summary["prediction_changed_when_label_changed"]["count"] == 1
    assert summary["prediction_unchanged_when_label_stable"]["count"] == 1
    assert summary["critical_prediction_changed"]["n"] == 2
    assert summary["critical_matches_label_change_partition"] is True


def test_positive_disjunction_is_excluded_not_rewritten():
    statement = Or(Not(Atom("P", ("a",))), Atom("Q", ("a",)))
    result = try_render_ablation([statement], Atom("R", ("b",)), ["a", "b", "c"])
    assert result["status"] == "excluded"
    assert "prompt" not in result
    assert "Or" in result["ablated_query"] or "P" in "".join(result["ablated_statements"])


def test_deleted_fact_negation_renders_without_gold_fields():
    result = try_render_ablation(
        [Not(Atom("P", ("a",)))],
        Atom("Q", ("b",)),
        ["a", "b", "c"],
    )
    assert result["status"] == "rendered"
    assert result["statements"] == ["P(a)."]
    public = {
        "sample_id": "ex",
        "split": "test",
        "domain": ["a", "b", "c"],
        "knowledge_base": result["statements"],
        "query": result["query"],
        "prompt": result["prompt"],
        "generator_version": "ablation-plan-6.4-v1",
        "seed": 20261111,
    }
    assert_public_record(public)
    assert set(public) == set(PUBLIC_FIELDS)
    assert "Not" not in result["prompt"]
    assert "label" not in result["prompt"]


def test_existential_without_not_is_excluded():
    query = Exists("x", And(Atom("C", ("x",)), Not(Atom("D", ("x",)))))
    result = try_render_ablation([Atom("P", ("a",))], query, ["a", "b", "c"])
    assert result["status"] == "excluded"
    assert "prompt" not in result

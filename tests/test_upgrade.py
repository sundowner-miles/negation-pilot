"""Checks for pure symbols, proof depth, ablation, and label confounding."""

from negpilot.ast import Atom, ForAll, Implies, Not
from negpilot.pair_audit import criticality_result
from negpilot.semantics import classify
from negpilot.templates import build_fact_ds_vs_negfact, build_rule_consequent_contrast, make_symbols
from negpilot.validator import label_balance_errors


def test_symbols_are_single_letters_and_are_shared_inside_a_pair():
    first = make_symbols(0, 3, 20261111)
    second = make_symbols(1, 3, 20261111)
    assert all(len(name) == 1 and name.isupper() for name in first.predicates)
    assert all(len(name) == 1 and name.islower() for name in first.domain)
    assert first.predicates != second.predicates or first.domain != second.domain
    again = make_symbols(0, 3, 20261111)
    assert again.predicates == first.predicates
    assert again.domain == first.domain


def test_direct_fact_is_depth_0_and_chains_match_rule_count():
    symbols = make_symbols(0, 3, 1)
    pair = build_fact_ds_vs_negfact(
        0,
        {"id": "fact", "pair_type": "counterfactual_fact", "depth_true": 1, "depth_false": 0},
        symbols,
    )
    _true_member, false_member = pair.members
    assert false_member.reasoning_depth == 0
    chain = build_rule_consequent_contrast(
        0,
        {"id": "rule", "pair_type": "counterfactual_rule", "depth": 3, "query_polarity": "POSITIVE"},
        symbols,
    )
    assert {member.reasoning_depth for member in chain.members} == {3}


def test_one_step_modus_ponens_is_true_and_depth_1():
    domain = ["a", "b", "c"]
    kb = [
        Atom("A", ("a",)),
        ForAll("x", Implies(Atom("A", ("x",)), Atom("B", ("x",)))),
    ]
    decision = classify(kb, Atom("B", ("a",)), domain, with_models=False)
    assert decision.label == "TRUE"
    unknown = classify(kb, Atom("B", ("b",)), domain, with_models=False)
    assert unknown.label == "UNKNOWN"


def test_invalid_ablation_is_not_forced_to_a_boolean():
    critical, status = criticality_result("TRUE", "INCONSISTENT", False)
    assert critical is None
    assert status == "invalid"
    changed, ok = criticality_result("FALSE", "TRUE", True)
    assert changed is True and ok == "pass"
    same, ok = criticality_result("TRUE", "TRUE", True)
    assert same is False and ok == "pass"


def _criticality_row(critical: bool, label: str, polarity: str) -> dict:
    return {
        "experimental_category": "negation_criticality",
        "contrast": "critical_vs_distractor",
        "negation_critical": critical,
        "label": label,
        "query_polarity": polarity,
    }


def test_one_polarity_criticality_set_is_reported_as_confounded():
    positive = [
        _criticality_row(True, "FALSE", "POSITIVE"),
        _criticality_row(False, "TRUE", "POSITIVE"),
    ] * 3
    assert label_balance_errors(positive)
    balanced = positive + [
        _criticality_row(True, "TRUE", "NEGATIVE"),
        _criticality_row(False, "FALSE", "NEGATIVE"),
    ] * 3
    assert label_balance_errors(balanced) == []

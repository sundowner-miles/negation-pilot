"""Semantic checks against the finite-domain definition."""

from negpilot.ast import And, Atom, Exists, ForAll, Implies, Not, Or, validate_syntax
from negpilot.semantics import classify, equivalent, ground
from negpilot.templates import ConstraintError, build_fact_ds_vs_negfact, make_symbols




def test_true_false_and_unknown_match_the_entailment_definition():
    domain = ["a", "b"]
    rules = [
        ForAll("x", Implies(Atom("A", ("x",)), Atom("B", ("x",)))),
        ForAll("x", Implies(Atom("B", ("x",)), Atom("C", ("x",)))),
    ]
    facts = [Atom("A", ("a",))]
    kb = facts + rules
    assert classify(kb, Atom("C", ("a",)), domain, with_models=False).label == "TRUE"
    assert classify(kb, Not(Atom("C", ("a",))), domain, with_models=False).label == "FALSE"
    # Underivable atoms are not false. The closed-world assumption is not used.
    unknown = classify(kb, Atom("C", ("b",)), domain, with_models=False)
    assert unknown.label == "UNKNOWN"
    assert unknown.kb_and_query == "sat"
    assert unknown.kb_and_not_query == "sat"


def test_inconsistent_base_is_rejected():
    domain = ["a"]
    kb = [
        Atom("A", ("a",)),
        ForAll("x", Implies(Atom("A", ("x",)), Atom("B", ("x",)))),
        Not(Atom("B", ("a",))),
    ]
    assert classify(kb, Atom("B", ("a",)), domain, with_models=False).label == "INCONSISTENT"


def test_quantifiers_are_grounded_before_a_free_variable_can_survive():
    domain = ["a", "b"]
    grounded = ground(ForAll("x", Atom("P", ("x",))), domain)
    assert grounded == And(Atom("P", ("a",)), Atom("P", ("b",)))
    exists = ground(Exists("x", Atom("P", ("x",))), domain)
    assert exists == Or(Atom("P", ("a",)), Atom("P", ("b",)))
    assert validate_syntax(Atom("P", ("y",)), domain)


def test_negated_universal_matches_existential_and_not_the_negated_consequent():
    domain = ["a", "b", "c"]
    negated_universal = Not(ForAll("x", Implies(Atom("C", ("x",)), Atom("D", ("x",)))))
    existential = Exists("x", And(Atom("C", ("x",)), Not(Atom("D", ("x",)))))
    negated_consequent = ForAll("x", Implies(Atom("C", ("x",)), Not(Atom("D", ("x",)))))
    assert equivalent(negated_universal, existential, domain)
    assert not equivalent(negated_consequent, negated_universal, domain)
    assert not equivalent(negated_consequent, existential, domain)


def test_negated_universal_does_not_decide_a_named_individual():
    domain = ["a", "b", "c"]
    kb = [
        Atom("C", ("a",)),
        Not(ForAll("x", Implies(Atom("C", ("x",)), Atom("D", ("x",))))),
    ]
    decision = classify(kb, Atom("D", ("a",)), domain, with_models=False)
    assert decision.label == "UNKNOWN"


def test_disjunctive_syllogism_is_true_and_depth_failure_is_explicit():
    symbols = make_symbols(0, 3, 20261111)
    pair = build_fact_ds_vs_negfact(
        0,
        {"id": "fact", "pair_type": "counterfactual_fact", "depth_true": 1, "depth_false": 0},
        symbols,
    )
    true_member, false_member = pair.members
    assert classify(true_member.statements, true_member.query, pair.domain, with_models=False).label == "TRUE"
    assert classify(false_member.statements, false_member.query, pair.domain, with_models=False).label == "FALSE"
    assert false_member.reasoning_depth == 0
    try:
        build_fact_ds_vs_negfact(
            0,
            {"id": "fact", "pair_type": "counterfactual_fact", "depth_true": 3, "depth_false": 3},
            symbols,
        )
    except ConstraintError as exc:
        assert "reasoning_depth 0" in str(exc)
    else:
        raise AssertionError("multi-hop negative facts must be rejected")

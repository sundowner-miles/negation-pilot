"""Shared constants for the negation pilot."""

from __future__ import annotations

POSITIONS = ("FACT", "RULE", "QUERY")
SCOPES = (
    "ATOMIC_PREDICATE",
    "RULE_ANTECEDENT",
    "RULE_CONSEQUENT",
    "QUANTIFIER",
    "PROPOSITION",
)
DEPTHS = (0, 1, 3, 5)
LABELS = ("TRUE", "FALSE", "UNKNOWN")
SPLITS = ("train", "dev", "test")

# Syntactic combinations that this pilot does not generate because the
# negation site cannot occupy that position.
INVALID_POSITION_SCOPE = {
    ("FACT", "RULE_ANTECEDENT"): (
        "A pilot fact is quantifier-free. It has no rule antecedent for a negation to occupy."
    ),
    ("FACT", "RULE_CONSEQUENT"): (
        "A pilot fact is quantifier-free. It has no rule consequent for a negation to occupy."
    ),
    ("FACT", "QUANTIFIER"): (
        "A negation inside an existential witness is a quantified sentence. "
        "It is stored as a rule or a query, not as a ground fact."
    ),
    ("FACT", "PROPOSITION"): (
        "Negation of a whole universal sentence is a quantified sentence. "
        "It is stored as a rule or a query, not as a ground fact."
    ),
    ("RULE", "ATOMIC_PREDICATE"): (
        "Atomic-predicate negation in this pilot is a ground literal or a ground disjunction. "
        "Quantified sentences are rules, so this cell is not used."
    ),
    ("QUERY", "RULE_ANTECEDENT"): (
        "A negated rule antecedent is a knowledge-base rule, not a pilot query. "
        "Queries are ground literals or closed quantified sentences."
    ),
    ("QUERY", "RULE_CONSEQUENT"): (
        "A negated rule consequent is a knowledge-base rule, not a pilot query."
    ),
}

# Cells that are logically well-typed but empty under the one-negation constraint.
STRUCTURAL_ZEROS = [
    {
        "cell": "QUERY label TRUE",
        "reason": (
            "With exactly one negation and no double negation, the negation would have to sit "
            "in the query. A TRUE label would then require the negation-free knowledge base to "
            "entail that negative query. The positive rules and facts in this pilot never entail "
            "a negative sentence, so the cell is empty."
        ),
    },
    {
        "cell": "RULE_ANTECEDENT label FALSE",
        "reason": (
            "Proving a negative ground conclusion from a negated antecedent requires a second "
            "negative literal to discharge the antecedent. That would be a second negation, so "
            "the cell is empty."
        ),
    },
    {
        "cell": "RULE + QUANTIFIER or PROPOSITION label FALSE",
        "reason": (
            "A negated universal in the knowledge base does not identify which domain element "
            "is the counterexample, so it does not by itself entail a negative ground atom. "
            "FALSE quantified items are queries that negate a stated universal."
        ),
    },
    {
        "cell": "FACT label FALSE at depth 3 or 5",
        "reason": (
            "A negative ground fact is stated directly, so its reasoning depth is 0. "
            "It is not a one-step inference. Multi-hop FALSE examples use a negated "
            "rule consequent or a negated query."
        ),
    },
    {
        "cell": "QUERY + QUANTIFIER or PROPOSITION label FALSE above depth 0",
        "reason": (
            "The knowledge base states the universal outright. The query is that statement's "
            "negation, so the proof is an axiom lookup of depth 0. Unused hops are not counted."
        ),
    },
    {
        "cell": "pair type query_polarity",
        "reason": (
            "A query-polarity pair keeps one knowledge base and asks both q and NOT(q). "
            "Exactly one negation in every example forbids that pair: the positive query has "
            "zero negations when the base has none, and NOT(q) has two negations when the base "
            "already contains the target negation. Double negation is also excluded."
        ),
    },
]

REQUIRED_GOLD_FIELDS = (
    "sample_id",
    "base_case_id",
    "pair_id",
    "pair_type",
    "split",
    "domain",
    "knowledge_base",
    "query",
    "query_ast",
    "label",
    "binary_label",
    "negation_position",
    "negation_scope",
    "negation_cue",
    "negation_count",
    "kb_negation_count",
    "query_negation_count",
    "query_polarity",
    "reasoning_depth",
    "proof_depth",
    "inference_type",
    "negation_embedding",
    "negation_function",
    "negation_critical",
    "inference_steps",
    "experimental_category",
    "contrast",
    "manipulated_variables",
    "controlled_variables",
    "logical_pair_validity",
    "experimental_control_validity",
    "in_controlled_subset",
    "proof_trace",
    "verification_status",
    "solver",
    "generator_version",
    "seed",
)

# Public evaluation records. Gold labels and traces stay in the gold file.
PUBLIC_FIELDS = (
    "sample_id",
    "split",
    "domain",
    "knowledge_base",
    "query",
    "prompt",
    "generator_version",
    "seed",
)

PAIR_TYPES = (
    "counterfactual_fact",
    "counterfactual_rule",
    "negation_relocation",
    "equivalent_form",
    "query_target_contrast",
)

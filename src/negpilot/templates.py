"""Logical template families.

Each family returns two examples that share a pair id. Builders state the
expected label and the proof depth. Position and scope are inferred from the
AST and checked against the builder's declaration. Z3, not the builder, is
the authority for the stored label.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from negpilot.ast import And, Atom, Exists, ForAll, Formula, Implies, Not, Or


class ConstraintError(RuntimeError):
    """A requested template cannot be realized under the pilot constraints."""


X = "x"


def atom(pred: str, arg: str) -> Atom:
    return Atom(pred, (arg,))


def univ(left: Formula, right: Formula) -> ForAll:
    return ForAll(X, Implies(left, right))


def univ_pos(left: str, right: str) -> ForAll:
    return univ(atom(left, X), atom(right, X))


def univ_neg_consequent(left: str, right: str) -> ForAll:
    return univ(atom(left, X), Not(atom(right, X)))


def univ_neg_antecedent(left: str, right: str) -> ForAll:
    return univ(Not(atom(left, X)), atom(right, X))


def not_universal(left: str, right: str) -> Not:
    return Not(univ_pos(left, right))


def exists_not(left: str, right: str) -> Exists:
    return Exists(X, And(atom(left, X), Not(atom(right, X))))


def chain(preds: list[str], hops: int) -> list[Formula]:
    if hops < 0 or hops > len(preds) - 1:
        raise ConstraintError(f"cannot build a chain of {hops} hops from {len(preds)} predicates")
    return [univ_pos(preds[index], preds[index + 1]) for index in range(hops)]


PREDICATE_ALPHABET = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
INDIVIDUAL_ALPHABET = tuple(character for character in "abcdefghijklmnopqrstuvwxyz" if character not in "xyz")
# Chain predicates occupy the front of the permutation. Depth 5 plus a
# quantified side sentence uses seven letters, so side predicates start later.
_SIDE_OFFSET = 16


@dataclass
class Symbols:
    base_index: int
    domain: tuple[str, ...]
    predicates: tuple[str, ...]

    def pred(self, index: int) -> str:
        if index < 0 or index >= _SIDE_OFFSET:
            raise ConstraintError(f"chain predicate index {index} is outside the reserved block")
        return self.predicates[index]

    def side(self, index: int) -> str:
        slot = _SIDE_OFFSET + index
        if slot >= len(self.predicates):
            raise ConstraintError(f"side predicate index {index} exceeds the alphabet")
        return self.predicates[slot]


def make_symbols(base_index: int, domain_size: int, seed: int) -> Symbols:
    """Pure letters only. The shuffle depends on the case id, not on the label."""
    if domain_size < 1 or domain_size > len(INDIVIDUAL_ALPHABET):
        raise ConstraintError(f"domain size {domain_size} is outside the individual alphabet")
    rng = random.Random((int(seed) * 1_000_003) ^ (base_index * 9_176))
    predicates = list(PREDICATE_ALPHABET)
    individuals = list(INDIVIDUAL_ALPHABET)
    rng.shuffle(predicates)
    rng.shuffle(individuals)
    return Symbols(base_index, tuple(individuals[:domain_size]), tuple(predicates))


@dataclass
class MemberDraft:
    expected_label: str
    statements: list[Formula]
    query: Formula
    negation_position: str
    negation_scope: str
    reasoning_depth: int
    proof_trace: dict[str, Any]
    template_id: str


@dataclass
class PairDraft:
    family: str
    pair_type: str
    pair_note: str
    domain: list[str]
    members: list[MemberDraft] = field(default_factory=list)
    controlled_variables: list[str] = field(default_factory=list)
    changed_variables: list[str] = field(default_factory=list)
    manipulated_variables: list[str] = field(default_factory=list)
    derived_variables: list[str] = field(default_factory=list)
    studies_inference_type: bool = False
    experimental_category: str = "exploratory"
    contrast: str = ""
    label_balance_group: str = ""
    query_polarity: str = "POSITIVE"


# Variables a controlled contrast must hold fixed unless a builder lists them
# in changed_variables. None of the current families is an inference-type study.
_HELD_PROOF = [
    "query",
    "domain",
    "nl_pack",
    "proof_depth",
    "inference_type",
    "relevant_premise_count",
    "negation_position",
    "negation_scope",
    "negation_embedding",
]


def _trace(
    steps: list[str],
    proof_hops: int,
    chain_hops: int,
    definition: str,
    note: str,
) -> dict[str, Any]:
    return {
        "steps": steps,
        "proof_hops": proof_hops,
        "chain_hops": chain_hops,
        "reasoning_depth_definition": definition,
        "template_note": note,
    }


_DECISIVE = (
    "reasoning_depth is the number of inference-rule applications in the canonical "
    "proof of the entailed literal: the query when the label is TRUE, and the "
    "negation of the query when the label is FALSE. A directly stated fact is depth 0."
)
_OPEN = (
    "Neither the query nor its negation has a canonical proof, so reasoning_depth "
    "is 0. chain_hops only records the length of the chain that was examined."
)


def _chain_steps(preds: list[str], individual: str, hops: int, final_negative: bool = False) -> list[str]:
    steps = [f"{individual} is {preds[0]}."]
    last = hops - 1 if final_negative else hops
    for index in range(last):
        steps.append(
            f"Every {preds[index]} individual is {preds[index + 1]}, and "
            f"{individual} is {preds[index]}, so {individual} is {preds[index + 1]}."
        )
    if final_negative:
        steps.append(
            f"Every {preds[hops - 1]} individual is not {preds[hops]}, and "
            f"{individual} is {preds[hops - 1]}, so {individual} is not {preds[hops]}."
        )
    return steps


def _require_depth(depth: int) -> None:
    if depth not in (1, 3, 5):
        raise ConstraintError(f"reasoning depth must be 1, 3, or 5, got {depth}")


def _ds_member(sym: Symbols, depth: int, label_side: str) -> MemberDraft:
    _require_depth(depth)
    preds = [sym.pred(index) for index in range(depth + 1)]
    target = sym.domain[0]
    prefix = chain(preds, depth - 1)
    disjunction = Or(Not(atom(preds[depth - 1], target)), atom(preds[depth], target))
    steps = [f"{target} is {preds[0]}."]
    for index in range(depth - 1):
        steps.append(
            f"Every {preds[index]} individual is {preds[index + 1]}, and "
            f"{target} is {preds[index]}, so {target} is {preds[index + 1]}."
        )
    steps.append(
        f"Either {target} is not {preds[depth - 1]}, or {target} is {preds[depth]}. "
        f"{target} is {preds[depth - 1]}, so {target} is {preds[depth]}."
    )
    return MemberDraft(
        expected_label="TRUE",
        statements=[atom(preds[0], target), *prefix, disjunction],
        query=atom(preds[depth], target),
        negation_position="FACT",
        negation_scope="ATOMIC_PREDICATE",
        reasoning_depth=depth,
        proof_trace=_trace(
            steps,
            proof_hops=depth,
            chain_hops=depth,
            definition=_DECISIVE,
            note=(
                "Disjunctive syllogism. The single negation is inside the ground disjunction "
                "and is required for the positive conclusion."
            ),
        ),
        template_id=f"{label_side}_disjunction_depth{depth}",
    )


def _negative_fact_member(sym: Symbols, depth_true: int) -> MemberDraft:
    """Same rules and query as the disjunction member, but the bridge fact is negative.

    The negated query is stated directly, so reasoning_depth is 0. The unused
    prefix chain is not an inference and does not add depth.
    """
    preds = [sym.pred(index) for index in range(depth_true + 1)]
    target = sym.domain[0]
    prefix = chain(preds, depth_true - 1)
    query_pred = preds[depth_true]
    steps = [
        f"The knowledge base states that {target} is not {query_pred}.",
        f"The query asks whether {target} is {query_pred}. "
        "Its negation is given as a fact, so the label is FALSE.",
    ]
    if prefix:
        steps.append(
            "The accompanying chain derives an earlier predicate and does not contradict "
            f"the negative fact about {query_pred}."
        )
    return MemberDraft(
        expected_label="FALSE",
        statements=[atom(preds[0], target), *prefix, Not(atom(query_pred, target))],
        query=atom(query_pred, target),
        negation_position="FACT",
        negation_scope="ATOMIC_PREDICATE",
        reasoning_depth=0,
        proof_trace=_trace(
            steps,
            proof_hops=0,
            chain_hops=max(depth_true - 1, 0),
            definition=_DECISIVE,
            note=(
                "The negation of the query is stated as a fact. "
                "Fact lookup is not an inference-rule application, so the depth is 0."
            ),
        ),
        template_id=f"negative_fact_depth0_context{depth_true}",
    )


def build_fact_ds_vs_negfact(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth_true = int(job["depth_true"])
    depth_false = int(job["depth_false"])
    _require_depth(depth_true)
    if depth_false != 0:
        raise ConstraintError(
            "fact_ds_vs_negfact cannot put the FALSE member at depth "
            f"{depth_false}. A directly stated negative fact has reasoning_depth 0. "
            "Use a negated consequent or a negated query for a multi-hop FALSE proof."
        )
    true_member = _ds_member(sym, depth_true, "fact_pair")
    false_member = _negative_fact_member(sym, depth_true)
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Counterfactual fact contrast. The rules and the query stay fixed. "
            "One member bridges the last hop with a ground disjunction whose first "
            "disjunct is negative. The other member states the negation of the query atom. "
            "Both labels are checked independently."
        ),
        domain=list(sym.domain),
        members=[true_member, false_member],
        controlled_variables=[
            "query",
            "domain",
            "nl_pack",
            "negation_position",
            "negation_scope",
        ],
        changed_variables=[
            "knowledge_base",
            "statement_template",
            "negation_embedding",
            "negation_function",
            "relevant_premise_count",
        ],
    )


def build_rule_consequent_contrast(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    polarity = str(job.get("query_polarity", "POSITIVE"))
    if polarity not in {"POSITIVE", "NEGATIVE"}:
        raise ConstraintError(f"query_polarity must be POSITIVE or NEGATIVE, got {polarity}")
    preds = [sym.pred(index) for index in range(depth + 1)]
    target = sym.domain[0]
    side0, side1 = sym.side(0), sym.side(1)
    fact = atom(preds[0], target)
    query_atom = atom(preds[depth], target)
    query: Formula = query_atom if polarity == "POSITIVE" else Not(query_atom)
    # Positive query: distractor entails B(a), critical entails not B(a).
    # Negative query: the same proofs swap the gold labels, so criticality is
    # not tied to one answer.
    distractor_label = "TRUE" if polarity == "POSITIVE" else "FALSE"
    critical_label = "FALSE" if polarity == "POSITIVE" else "TRUE"
    true_rules = [*chain(preds, depth), univ_neg_consequent(side0, side1)]
    false_rules = [*chain(preds, depth - 1), univ_neg_consequent(preds[depth - 1], preds[depth]), univ_pos(side0, side1)]
    distractor_steps = _chain_steps(preds, target, depth)
    distractor_steps.append(
        f"The extra rule about {side0} and {side1} is not used. "
        "Its negated consequent does not affect the query."
    )
    if polarity == "NEGATIVE":
        distractor_steps.append(
            f"The query is the negation of {preds[depth]}({target}). "
            "The chain derives the positive atom, so the negated query is FALSE."
        )
    critical_steps = _chain_steps(preds, target, depth, final_negative=True)
    if polarity == "NEGATIVE":
        critical_steps.append(
            f"The query is that same negative atom {preds[depth]}({target}), so the label is TRUE."
        )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Negation-criticality contrast. The query, domain, chain length, and symbol "
            "mapping stay fixed. One member puts the knowledge-base negation on an unused "
            "side rule. The other puts it on the last rule of the proof. "
            f"Query polarity is {polarity}; the query negation, when present, is shared."
        ),
        domain=list(sym.domain),
        members=[
            MemberDraft(
                expected_label=distractor_label,
                statements=[fact, *true_rules],
                query=query,
                negation_position="RULE",
                negation_scope="RULE_CONSEQUENT",
                reasoning_depth=depth,
                proof_trace=_trace(
                    distractor_steps,
                    proof_hops=depth,
                    chain_hops=depth,
                    definition=_DECISIVE,
                    note="The negation is on an unused side rule and is not critical.",
                ),
                template_id=f"distractor_consequent_depth{depth}_{polarity.lower()}",
            ),
            MemberDraft(
                expected_label=critical_label,
                statements=[fact, *false_rules],
                query=query,
                negation_position="RULE",
                negation_scope="RULE_CONSEQUENT",
                reasoning_depth=depth,
                proof_trace=_trace(
                    critical_steps,
                    proof_hops=depth,
                    chain_hops=depth,
                    definition=_DECISIVE,
                    note="The negation is the consequent of the last chain rule and is critical.",
                ),
                template_id=f"critical_consequent_depth{depth}_{polarity.lower()}",
            ),
        ],
        controlled_variables=[
            "query",
            "domain",
            "symbol_mapping",
            "nl_pack",
            "inference_type",
            "proof_depth",
            "relevant_premise_count",
            "negation_position",
            "negation_scope",
            "negation_count",
            "kb_negation_count",
            "query_negation_count",
            "query_polarity",
            "fact_count",
            "rule_count",
        ],
        manipulated_variables=["negation_criticality"],
        derived_variables=[
            "knowledge_base",
            "statement_template",
            "negation_function",
            "negation_embedding",
        ],
        experimental_category="negation_criticality",
        contrast="critical_vs_distractor",
        label_balance_group=f"{polarity}_QUERY",
        query_polarity=polarity,
    )


def build_antecedent_vs_query_atomic(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    preds = [sym.pred(index) for index in range(depth + 1)]
    target = sym.domain[0]
    side0, side1 = sym.side(0), sym.side(1)
    fact = atom(preds[0], target)
    positive = chain(preds, depth)
    true_steps = _chain_steps(preds, target, depth)
    true_steps.append(
        "The extra rule has a negated antecedent and is not used in the proof."
    )
    false_steps = _chain_steps(preds, target, depth)
    false_steps.append(
        f"The query is the negation of {preds[depth]}({target}). "
        "The chain derives the positive atom, so the negated query is FALSE."
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Negation relocation, not a one-edit counterfactual. "
            "The TRUE member's only negation is an unused negated antecedent, and the query is positive. "
            "The FALSE member's only negation is the query, and the chain is positive. "
            "Each label is verified on its own. The antecedent negation is a distractor."
        ),
        domain=list(sym.domain),
        members=[
            MemberDraft(
                expected_label="TRUE",
                statements=[fact, *positive, univ_neg_antecedent(side0, side1)],
                query=atom(preds[depth], target),
                negation_position="RULE",
                negation_scope="RULE_ANTECEDENT",
                reasoning_depth=depth,
                proof_trace=_trace(
                    true_steps,
                    proof_hops=depth,
                    chain_hops=depth,
                    definition=_DECISIVE,
                    note="Negated antecedent is unused. Deleting it does not change the label.",
                ),
                template_id=f"distractor_antecedent_depth{depth}",
            ),
            MemberDraft(
                expected_label="FALSE",
                statements=[fact, *positive, univ_pos(side0, side1)],
                query=Not(atom(preds[depth], target)),
                negation_position="QUERY",
                negation_scope="ATOMIC_PREDICATE",
                reasoning_depth=depth,
                proof_trace=_trace(
                    false_steps,
                    proof_hops=depth,
                    chain_hops=depth,
                    definition=_DECISIVE,
                    note="The chain proves the atom whose negation is the query.",
                ),
                template_id=f"query_atomic_false_depth{depth}",
            ),
        ],
    )


def build_quantifier_distractor_vs_query(
    base_index: int, job: dict[str, Any], sym: Symbols
) -> PairDraft:
    depth_true = int(job["depth_true"])
    depth_false = int(job["depth_false"])
    _require_depth(depth_true)
    if depth_false != 0:
        raise ConstraintError(
            "A query that negates a universal stated in the knowledge base is an axiom lookup. "
            f"That proof has depth 0, not {depth_false}."
        )
    preds = [sym.pred(index) for index in range(depth_true + 1)]
    target = sym.domain[0]
    side0, side1 = sym.side(0), sym.side(1)
    left, right = sym.pred(0), sym.pred(1)
    use_exists = int(job["local_index"]) % 2 == 1
    if use_exists:
        false_query: Formula = exists_not(left, right)
        false_form = "existential_counterexample"
        false_steps = [
            f"The knowledge base states that every {left} individual is {right}.",
            "The query says that at least one individual is "
            f"{left} and is not {right}.",
            "That existential sentence is the classical negation of the stated universal, "
            "so the label is FALSE.",
        ]
    else:
        false_query = not_universal(left, right)
        false_form = "negated_universal"
        false_steps = [
            f"The knowledge base states that every {left} individual is {right}.",
            "The query says that this universal claim is not true.",
            "The query is the negation of a stated rule, so the label is FALSE.",
        ]
    true_steps = _chain_steps(preds, target, depth_true)
    true_steps.append(
        f"The sentence saying that not every {side0} is {side1} concerns other predicates "
        "and is not used."
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Negation relocation across a quantified sentence and a ground chain. "
            f"The FALSE query uses the {false_form} shape and is refuted by a stated universal. "
            "The TRUE member proves a ground atom in the requested number of hops; "
            "its only negation is an unrelated negated universal. "
            "Not every C is D is not treated as every C is not D."
        ),
        domain=list(sym.domain),
        members=[
            MemberDraft(
                expected_label="TRUE",
                statements=[
                    atom(preds[0], target),
                    *chain(preds, depth_true),
                    not_universal(side0, side1),
                ],
                query=atom(preds[depth_true], target),
                negation_position="RULE",
                negation_scope="PROPOSITION",
                reasoning_depth=depth_true,
                proof_trace=_trace(
                    true_steps,
                    proof_hops=depth_true,
                    chain_hops=depth_true,
                    definition=_DECISIVE,
                    note="The negated universal is a distractor on unused predicates.",
                ),
                template_id=f"distractor_negated_universal_depth{depth_true}",
            ),
            MemberDraft(
                expected_label="FALSE",
                statements=[univ_pos(left, right)],
                query=false_query,
                negation_position="QUERY",
                negation_scope="QUANTIFIER" if use_exists else "PROPOSITION",
                reasoning_depth=0,
                proof_trace=_trace(
                    false_steps,
                    proof_hops=0,
                    chain_hops=0,
                    definition=_DECISIVE,
                    note=(
                        "The universal is stated directly and the query is its negation. "
                        "No inference rule is applied, so the depth is 0. "
                        f"Query form: {false_form}."
                    ),
                ),
                template_id=f"query_{false_form}_false_depth0",
            ),
        ],
    )


def build_disjunction_vs_query_atomic(
    base_index: int, job: dict[str, Any], sym: Symbols
) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    true_member = _ds_member(sym, depth, "relocate")
    preds = [sym.pred(index) for index in range(depth + 1)]
    target = sym.domain[0]
    false_steps = _chain_steps(preds, target, depth)
    false_steps.append(
        "The query negates the atom derived by the chain, so the label is FALSE."
    )
    false_member = MemberDraft(
        expected_label="FALSE",
        statements=[atom(preds[0], target), *chain(preds, depth)],
        query=Not(atom(preds[depth], target)),
        negation_position="QUERY",
        negation_scope="ATOMIC_PREDICATE",
        reasoning_depth=depth,
        proof_trace=_trace(
            false_steps,
            proof_hops=depth,
            chain_hops=depth,
            definition=_DECISIVE,
            note="The only negation is the query. The positive chain refutes it.",
        ),
        template_id=f"query_atomic_false_depth{depth}",
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Negation relocation between a critical disjunctive fact and a negated query. "
            "Both negations are load-bearing. The knowledge bases are verified separately "
            "and are not assumed to be one-edit variants."
        ),
        domain=list(sym.domain),
        members=[true_member, false_member],
    )


def _open_trace(steps: list[str], chain_hops: int, note: str) -> dict[str, Any]:
    return _trace(steps, proof_hops=0, chain_hops=chain_hops, definition=_OPEN, note=note)


def build_unk_fact_block(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    if len(sym.domain) < 2:
        raise ConstraintError("unk_fact_block needs two individuals")
    preds = [sym.pred(index) for index in range(depth + 1)]
    rules = chain(preds, depth)
    target, other = sym.domain[0], sym.domain[1]
    query = atom(preds[depth], target)
    blocking = MemberDraft(
        expected_label="UNKNOWN",
        statements=[Not(atom(preds[0], target)), *rules],
        query=query,
        negation_position="FACT",
        negation_scope="ATOMIC_PREDICATE",
        reasoning_depth=0,
        proof_trace=_open_trace(
            [
                f"{target} is not {preds[0]}, so the chain does not derive {preds[depth]}({target}).",
                f"The rules run only from {preds[0]} toward {preds[depth]}. "
                "They do not prove the negation of the query either.",
            ],
            depth,
            "Negating the anchor individual blocks the chain without proving the negated conclusion.",
        ),
        template_id=f"blocked_anchor_depth{depth}",
    )
    irrelevant = MemberDraft(
        expected_label="UNKNOWN",
        statements=[Not(atom(preds[0], other)), *rules],
        query=query,
        negation_position="FACT",
        negation_scope="ATOMIC_PREDICATE",
        reasoning_depth=0,
        proof_trace=_open_trace(
            [
                f"The only fact is that {other} is not {preds[0]}.",
                f"Nothing is stated about {target}, so {preds[depth]}({target}) is open in both directions.",
            ],
            depth,
            "The negation concerns a different individual and does not decide the query.",
        ),
        template_id=f"irrelevant_negative_fact_depth{depth}",
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Counterfactual fact contrast inside UNKNOWN. "
            "The rules and the query stay fixed. "
            "One member negates the anchor individual's first predicate. "
            "The other negates that predicate for a different individual. "
            "Neither knowledge base entails the query or its negation."
        ),
        domain=list(sym.domain),
        members=[blocking, irrelevant],
        experimental_category="counterfactual_fact",
        contrast="blocking_vs_distractor",
        controlled_variables=list(_HELD_PROOF),
        manipulated_variables=["negation_criticality"],
        derived_variables=["knowledge_base", "statement_template", "negation_function"],
        changed_variables=["knowledge_base", "statement_template", "negation_function"],
    )


def build_unk_rule_antecedent(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    if len(sym.domain) < 2:
        raise ConstraintError("unk_rule_antecedent needs two individuals")
    preds = [sym.pred(index) for index in range(depth + 1)]
    rules = [*chain(preds, depth - 1), univ_neg_antecedent(preds[depth - 1], preds[depth])]
    target, other = sym.domain[0], sym.domain[1]
    query = atom(preds[depth], target)

    def member(individual: str, template: str, fired: bool) -> MemberDraft:
        if fired:
            note = (
                f"The chain derives {preds[depth - 1]}({individual}). "
                "The last rule requires the negation of that atom, so it does not fire. "
                "The positive derivation does not prove the negation of the query."
            )
        else:
            note = (
                f"The anchor fact is about {individual}, not {target}. "
                "The negated-antecedent rule does not decide the query individual."
            )
        return MemberDraft(
            expected_label="UNKNOWN",
            statements=[atom(preds[0], individual), *rules],
            query=query,
            negation_position="RULE",
            negation_scope="RULE_ANTECEDENT",
            reasoning_depth=0,
            proof_trace=_open_trace(
                [note],
                depth,
                "The only bridge to the query has a negated antecedent and does not fire for the query individual.",
            ),
            template_id=template,
        )

    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Counterfactual fact contrast with a shared negated-antecedent rule. "
            "The rule says that anyone who fails the penultimate predicate has the query predicate. "
            "Neither member supplies that negative literal for the query individual."
        ),
        domain=list(sym.domain),
        members=[
            member(target, f"unfired_antecedent_target_depth{depth}", True),
            member(other, f"unfired_antecedent_other_depth{depth}", False),
        ],
        experimental_category="counterfactual_fact",
        contrast="unfired_vs_off_individual",
        controlled_variables=list(_HELD_PROOF),
        manipulated_variables=["negation_criticality"],
        derived_variables=["knowledge_base", "statement_template", "negation_function"],
        changed_variables=["knowledge_base", "statement_template", "negation_function"],
    )


def build_unk_rule_consequent(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    if len(sym.domain) < 3:
        raise ConstraintError("unk_rule_consequent keeps the query individual distinct from both anchors")
    preds = [sym.pred(index) for index in range(depth + 1)]
    rules = [*chain(preds, depth - 1), univ_neg_consequent(preds[depth - 1], preds[depth])]
    target = sym.domain[0]
    query = atom(preds[depth], target)
    members = []
    for slot, individual in enumerate(sym.domain[1:3]):
        members.append(
            MemberDraft(
                expected_label="UNKNOWN",
                statements=[atom(preds[0], individual), *rules],
                query=query,
                negation_position="RULE",
                negation_scope="RULE_CONSEQUENT",
                reasoning_depth=0,
                proof_trace=_open_trace(
                    [
                        f"The anchor fact is about {individual}, so the negated consequent fires for {individual} only.",
                        f"It does not decide whether {target} is {preds[depth]}.",
                    ],
                    depth,
                    "The negated consequent is idle for the query individual.",
                ),
                template_id=f"idle_consequent_anchor{slot}_depth{depth}",
            )
        )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Counterfactual fact contrast. Both members use the same negated-consequent chain. "
            "The anchor individual is not the query individual, so the rule does not decide the query. "
            "This is every C is not D, restricted to a derived C that is a different individual. "
            "It is not 'not every C is D'."
        ),
        domain=list(sym.domain),
        members=members,
        experimental_category="counterfactual_anchor",
        contrast="idle_anchor_identity",
        controlled_variables=[*_HELD_PROOF, "negation_function", "statement_template"],
        manipulated_variables=["knowledge_base"],
        changed_variables=["knowledge_base"],
    )


def build_unk_rule_quantifier_form(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    if len(sym.domain) < 2:
        raise ConstraintError("a negated universal needs a domain of at least two individuals")
    # d hops derive pred d. The quantified sentence talks about pred d and pred d+1.
    preds = [sym.pred(index) for index in range(depth + 2)]
    target = sym.domain[0]
    rules = chain(preds, depth)
    fact = atom(preds[0], target)
    query = atom(preds[depth + 1], target)
    antecedent, consequent = preds[depth], preds[depth + 1]
    universal = not_universal(antecedent, consequent)
    existential = exists_not(antecedent, consequent)
    note = (
        f"The chain derives {antecedent}({target}) in {depth} steps. "
        f"The quantified axiom says that not every {antecedent} is {consequent}, "
        f"which is equivalent to some {antecedent} failing to be {consequent}. "
        f"It does not say that {target} is the witness, so {consequent}({target}) stays open."
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Equivalent-form contrast. Not(every antecedent is consequent) and "
            "some antecedent is not consequent are classically equivalent. "
            "Both are consistent with the chain, and neither decides the ground query. "
            "They are not equivalent to 'every antecedent is not consequent'."
        ),
        domain=list(sym.domain),
        members=[
            MemberDraft(
                expected_label="UNKNOWN",
                statements=[fact, *rules, universal],
                query=query,
                negation_position="RULE",
                negation_scope="PROPOSITION",
                reasoning_depth=0,
                proof_trace=_open_trace([note], depth, "Negated universal does not identify the witness."),
                template_id=f"negated_universal_axiom_depth{depth}",
            ),
            MemberDraft(
                expected_label="UNKNOWN",
                statements=[fact, *rules, existential],
                query=query,
                negation_position="RULE",
                negation_scope="QUANTIFIER",
                reasoning_depth=0,
                proof_trace=_open_trace(
                    [note],
                    depth,
                    "Existential counterexample does not identify the witness.",
                ),
                template_id=f"existential_axiom_depth{depth}",
            ),
        ],
        experimental_category="negation_form",
        contrast="negated_universal_vs_existential",
        controlled_variables=[
            item for item in _HELD_PROOF if item not in {"negation_embedding", "negation_scope"}
        ],
        manipulated_variables=["negation_scope"],
        derived_variables=[
            "knowledge_base",
            "statement_template",
            "negation_embedding",
            "negation_function",
            "negation_critical",
        ],
        changed_variables=[
            "knowledge_base",
            "statement_template",
            "negation_embedding",
            "negation_function",
        ],
    )


def build_unk_query_atomic_target(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    if len(sym.domain) < 3:
        raise ConstraintError("query-target contrast needs three individuals")
    preds = [sym.pred(index) for index in range(depth + 1)]
    anchor = sym.domain[1]
    statements = [atom(preds[0], anchor), *chain(preds, depth)]
    members = []
    for slot, individual in ((0, sym.domain[0]), (2, sym.domain[2])):
        members.append(
            MemberDraft(
                expected_label="UNKNOWN",
                statements=list(statements),
                query=Not(atom(preds[depth], individual)),
                negation_position="QUERY",
                negation_scope="ATOMIC_PREDICATE",
                reasoning_depth=0,
                proof_trace=_open_trace(
                    [
                        f"The chain derives {preds[depth]}({anchor}) and does not mention {individual}.",
                        f"The negated query about {individual} is therefore neither entailed nor refuted.",
                    ],
                    depth,
                    "The chain settles a different individual from the one in the negated query.",
                ),
                template_id=f"unknown_query_individual{slot}_depth{depth}",
            )
        )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Query-target contrast under one knowledge base. "
            "Both queries are negative ground atoms about individuals other than the anchor. "
            "This is not a q versus NOT(q) pair: that construction cannot give both members "
            "exactly one negation without double negation."
        ),
        domain=list(sym.domain),
        members=members,
        experimental_category="query_target",
        contrast="off_anchor_individual",
        controlled_variables=[item for item in _HELD_PROOF if item != "query"],
        manipulated_variables=["query"],
    )


def build_unk_query_quantifier_form(base_index: int, job: dict[str, Any], sym: Symbols) -> PairDraft:
    depth = int(job["depth"])
    _require_depth(depth)
    preds = [sym.pred(index) for index in range(depth + 2)]
    target = sym.domain[0]
    statements = [atom(preds[0], target), *chain(preds, depth)]
    antecedent, consequent = preds[depth], preds[depth + 1]
    note = (
        f"The chain derives {antecedent}({target}) in {depth} steps and says nothing about {consequent}. "
        "The universal 'every antecedent is consequent' is not entailed, and neither is its negation."
    )
    return PairDraft(
        family=job["id"],
        pair_type=job["pair_type"],
        pair_note=(
            "Equivalent-form contrast on the query. "
            "Not(every antecedent is consequent) and some antecedent is not consequent "
            "are classically equivalent and are both left open by the chain. "
            "The wording keeps them distinct from 'every antecedent is not consequent'."
        ),
        domain=list(sym.domain),
        members=[
            MemberDraft(
                expected_label="UNKNOWN",
                statements=list(statements),
                query=not_universal(antecedent, consequent),
                negation_position="QUERY",
                negation_scope="PROPOSITION",
                reasoning_depth=0,
                proof_trace=_open_trace([note], depth, "Negated-universal query is open."),
                template_id=f"unknown_negated_universal_query_depth{depth}",
            ),
            MemberDraft(
                expected_label="UNKNOWN",
                statements=list(statements),
                query=exists_not(antecedent, consequent),
                negation_position="QUERY",
                negation_scope="QUANTIFIER",
                reasoning_depth=0,
                proof_trace=_open_trace([note], depth, "Existential-counterexample query is open."),
                template_id=f"unknown_existential_query_depth{depth}",
            ),
        ],
        experimental_category="negation_form",
        contrast="negated_universal_vs_existential",
        controlled_variables=[
            item for item in _HELD_PROOF if item not in {"query", "negation_scope", "negation_embedding"}
        ],
        manipulated_variables=["query", "negation_scope"],
        derived_variables=["statement_template", "negation_embedding"],
    )


BUILDERS = {
    "fact_ds_vs_negfact": build_fact_ds_vs_negfact,
    "rule_consequent_contrast": build_rule_consequent_contrast,
    "antecedent_vs_query_atomic": build_antecedent_vs_query_atomic,
    "quantifier_distractor_vs_query": build_quantifier_distractor_vs_query,
    "disjunction_vs_query_atomic": build_disjunction_vs_query_atomic,
    "unk_fact_block": build_unk_fact_block,
    "unk_rule_antecedent": build_unk_rule_antecedent,
    "unk_rule_consequent": build_unk_rule_consequent,
    "unk_rule_quantifier_form": build_unk_rule_quantifier_form,
    "unk_query_atomic_target": build_unk_query_atomic_target,
    "unk_query_quantifier_form": build_unk_query_quantifier_form,
}

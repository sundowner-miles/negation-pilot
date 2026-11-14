"""Structured first-order AST.

Natural-language strings are not the carrier of logical form. Every formula
used for entailment is one of these nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Sequence, Union


class FormulaError(ValueError):
    """A formula is syntactically malformed."""


@dataclass(frozen=True)
class Atom:
    pred: str
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.args, tuple):
            object.__setattr__(self, "args", tuple(self.args))


@dataclass(frozen=True)
class Not:
    formula: "Formula"


@dataclass(frozen=True)
class And:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class Or:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class Implies:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class ForAll:
    var: str
    body: "Formula"


@dataclass(frozen=True)
class Exists:
    var: str
    body: "Formula"


Formula = Union[Atom, Not, And, Or, Implies, ForAll, Exists]

_SYMBOL = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def walk(formula: Formula) -> Iterator[Formula]:
    yield formula
    if isinstance(formula, Atom):
        return
    if isinstance(formula, Not):
        yield from walk(formula.formula)
        return
    if isinstance(formula, (And, Or, Implies)):
        yield from walk(formula.left)
        yield from walk(formula.right)
        return
    if isinstance(formula, (ForAll, Exists)):
        yield from walk(formula.body)
        return
    raise FormulaError(f"unknown node {type(formula).__name__}")


def count_nots(formula: Formula) -> int:
    return sum(1 for node in walk(formula) if isinstance(node, Not))


def sexp(formula: Formula) -> str:
    if isinstance(formula, Atom):
        return f"{formula.pred}({','.join(formula.args)})"
    if isinstance(formula, Not):
        return f"(not {sexp(formula.formula)})"
    if isinstance(formula, And):
        return f"(and {sexp(formula.left)} {sexp(formula.right)})"
    if isinstance(formula, Or):
        return f"(or {sexp(formula.left)} {sexp(formula.right)})"
    if isinstance(formula, Implies):
        return f"(=> {sexp(formula.left)} {sexp(formula.right)})"
    if isinstance(formula, ForAll):
        return f"(forall {formula.var} {sexp(formula.body)})"
    if isinstance(formula, Exists):
        return f"(exists {formula.var} {sexp(formula.body)})"
    raise FormulaError(f"unknown node {type(formula).__name__}")


def to_dict(formula: Formula) -> dict[str, Any]:
    if isinstance(formula, Atom):
        return {"op": "atom", "pred": formula.pred, "args": list(formula.args)}
    if isinstance(formula, Not):
        return {"op": "not", "formula": to_dict(formula.formula)}
    if isinstance(formula, And):
        return {"op": "and", "left": to_dict(formula.left), "right": to_dict(formula.right)}
    if isinstance(formula, Or):
        return {"op": "or", "left": to_dict(formula.left), "right": to_dict(formula.right)}
    if isinstance(formula, Implies):
        return {"op": "implies", "left": to_dict(formula.left), "right": to_dict(formula.right)}
    if isinstance(formula, ForAll):
        return {"op": "forall", "var": formula.var, "body": to_dict(formula.body)}
    if isinstance(formula, Exists):
        return {"op": "exists", "var": formula.var, "body": to_dict(formula.body)}
    raise FormulaError(f"unknown node {type(formula).__name__}")


def from_dict(data: dict[str, Any]) -> Formula:
    if not isinstance(data, dict) or "op" not in data:
        raise FormulaError("formula JSON must be an object with an 'op' field")
    op = data["op"]
    if op == "atom":
        args = data.get("args")
        if not isinstance(data.get("pred"), str) or not isinstance(args, list):
            raise FormulaError("atom requires pred and args")
        return Atom(data["pred"], tuple(args))
    if op == "not":
        return Not(from_dict(data["formula"]))
    if op == "and":
        return And(from_dict(data["left"]), from_dict(data["right"]))
    if op == "or":
        return Or(from_dict(data["left"]), from_dict(data["right"]))
    if op == "implies":
        return Implies(from_dict(data["left"]), from_dict(data["right"]))
    if op == "forall":
        return ForAll(data["var"], from_dict(data["body"]))
    if op == "exists":
        return Exists(data["var"], from_dict(data["body"]))
    raise FormulaError(f"unknown operator {op}")


def validate_syntax(formula: Formula, domain: Sequence[str]) -> list[str]:
    """Return syntactic errors. An empty list means the formula is a closed sentence."""
    errors: list[str] = []
    domain_set = set(domain)
    if len(domain_set) != len(list(domain)):
        errors.append("domain contains duplicate individuals")
    if any(not _SYMBOL.match(item) for item in domain):
        errors.append("domain individual is not a legal symbol")

    def walk_bound(node: Formula, bound: set[str]) -> None:
        if isinstance(node, Atom):
            if not node.pred or not _SYMBOL.match(node.pred):
                errors.append(f"illegal predicate in {sexp(node)}")
            if len(node.args) < 1:
                errors.append(f"atom has no arguments: {sexp(node)}")
            for arg in node.args:
                if not _SYMBOL.match(arg):
                    errors.append(f"illegal argument {arg}")
                elif arg not in domain_set and arg not in bound:
                    errors.append(f"free or unknown symbol {arg} in {sexp(node)}")
            return
        if isinstance(node, Not):
            walk_bound(node.formula, bound)
            return
        if isinstance(node, (And, Or, Implies)):
            walk_bound(node.left, bound)
            walk_bound(node.right, bound)
            return
        if isinstance(node, (ForAll, Exists)):
            if not node.var or not _SYMBOL.match(node.var):
                errors.append("quantifier variable is empty or illegal")
                return
            if node.var in domain_set:
                errors.append(f"quantifier variable {node.var} collides with a domain individual")
            walk_bound(node.body, bound | {node.var})
            return
        errors.append(f"unknown node {type(node).__name__}")

    walk_bound(formula, set())
    return errors


def is_closed(formula: Formula, domain: Sequence[str]) -> bool:
    return not validate_syntax(formula, domain)


def contains_quantifier(formula: Formula) -> bool:
    return any(isinstance(node, (ForAll, Exists)) for node in walk(formula))


def statement_role(formula: Formula) -> str:
    """Ground sentences are facts. Sentences with a quantifier are rules."""
    return "rule" if contains_quantifier(formula) else "fact"


def delete_unique_not(formula: Formula) -> Formula:
    """Replace the unique Not(F) node with F. Reject any other Not-count."""
    if count_nots(formula) != 1:
        raise FormulaError("delete_unique_not requires exactly one Not in this formula")

    def rec(node: Formula) -> Formula:
        if isinstance(node, Not):
            return node.formula
        if isinstance(node, Atom):
            return node
        if isinstance(node, And):
            return And(rec(node.left), rec(node.right))
        if isinstance(node, Or):
            return Or(rec(node.left), rec(node.right))
        if isinstance(node, Implies):
            return Implies(rec(node.left), rec(node.right))
        if isinstance(node, ForAll):
            return ForAll(node.var, rec(node.body))
        if isinstance(node, Exists):
            return Exists(node.var, rec(node.body))
        raise FormulaError(f"unknown node {type(node).__name__}")

    return rec(formula)


def delete_unique_not_from_example(
    statements: Sequence[Formula], query: Formula
) -> tuple[list[Formula], Formula]:
    total = sum(count_nots(item) for item in statements) + count_nots(query)
    if total != 1:
        raise FormulaError(f"example must contain exactly one Not, found {total}")
    new_statements: list[Formula] = []
    for item in statements:
        new_statements.append(delete_unique_not(item) if count_nots(item) else item)
    new_query = delete_unique_not(query) if count_nots(query) else query
    return new_statements, new_query


def negation_formula(statements: Sequence[Formula], query: Formula) -> tuple[str, Formula]:
    """Return ('fact'|'rule'|'query', formula) for the unique negated sentence."""
    host: tuple[str, Formula] | None = None
    for item in statements:
        if count_nots(item):
            if host is not None:
                raise FormulaError("more than one statement contains negation")
            host = (statement_role(item), item)
    if count_nots(query):
        if host is not None:
            raise FormulaError("negation occurs in both the knowledge base and the query")
        host = ("query", query)
    if host is None:
        raise FormulaError("example has no negation")
    return host


def infer_scope(formula: Formula) -> str:
    """Classify the unique negation inside one sentence."""
    if isinstance(formula, Not) and isinstance(formula.formula, Atom):
        return "ATOMIC_PREDICATE"
    if isinstance(formula, Not) and isinstance(formula.formula, ForAll):
        return "PROPOSITION"
    if isinstance(formula, Exists):
        return "QUANTIFIER"
    if isinstance(formula, ForAll) and isinstance(formula.body, Implies):
        implication = formula.body
        if isinstance(implication.left, Not) and isinstance(implication.left.formula, Atom):
            return "RULE_ANTECEDENT"
        if isinstance(implication.right, Not) and isinstance(implication.right.formula, Atom):
            return "RULE_CONSEQUENT"
    if (
        isinstance(formula, Or)
        and isinstance(formula.left, Not)
        and isinstance(formula.left.formula, Atom)
        and isinstance(formula.right, Atom)
    ):
        return "ATOMIC_PREDICATE"
    raise FormulaError(f"unsupported negation shape: {sexp(formula)}")


def infer_form(formula: Formula) -> str:
    if isinstance(formula, Not) and isinstance(formula.formula, Atom):
        return "atomic_literal"
    if isinstance(formula, Or):
        return "negated_disjunct"
    if isinstance(formula, ForAll) and isinstance(formula.body, Implies):
        implication = formula.body
        if isinstance(implication.left, Not):
            return "rule_antecedent"
        if isinstance(implication.right, Not):
            return "rule_consequent"
    if isinstance(formula, Not) and isinstance(formula.formula, ForAll):
        return "negated_universal"
    if isinstance(formula, Exists):
        return "existential_counterexample"
    raise FormulaError(f"unsupported negation form: {sexp(formula)}")


def negation_occurrences(
    statements: Sequence[Formula], query: Formula
) -> list[dict[str, Any]]:
    """Locate every formula that contains a Not. The host keeps its own Not-count."""
    found: list[dict[str, Any]] = []
    for index, formula in enumerate(statements):
        total = count_nots(formula)
        if total:
            found.append(
                {
                    "role": statement_role(formula),
                    "index": index,
                    "host": formula,
                    "count": total,
                }
            )
    query_total = count_nots(query)
    if query_total:
        found.append({"role": "query", "index": None, "host": query, "count": query_total})
    return found


def studied_occurrence(statements: Sequence[Formula], query: Formula) -> dict[str, Any]:
    """The negation under study.

    One Not is that occurrence. When the query polarity is itself a controlled
    negation and the knowledge base has one further Not, the studied occurrence
    is the knowledge-base Not.
    """
    found = negation_occurrences(statements, query)
    total = sum(item["count"] for item in found)
    if total == 1 and len(found) == 1:
        return found[0]
    kb = [item for item in found if item["role"] != "query"]
    queries = [item for item in found if item["role"] == "query"]
    if (
        total == 2
        and len(kb) == 1
        and kb[0]["count"] == 1
        and len(queries) == 1
        and queries[0]["count"] == 1
    ):
        return kb[0]
    raise FormulaError(
        "the studied negation must be the only Not, or the single knowledge-base "
        f"Not beside one query Not; found {total}"
    )


def ablate_studied(
    statements: Sequence[Formula], query: Formula
) -> tuple[list[Formula], Formula, dict[str, Any]]:
    """Delete only the studied Not. The controlled query negation stays."""
    site = studied_occurrence(statements, query)
    if site["role"] == "query":
        return list(statements), delete_unique_not(query), site
    rewritten = list(statements)
    index = site["index"]
    rewritten[index] = delete_unique_not(statements[index])
    return rewritten, query, site


def infer_position_and_scope(
    statements: Sequence[Formula], query: Formula
) -> tuple[str, str, str]:
    site = studied_occurrence(statements, query)
    role = site["role"]
    position = {"fact": "FACT", "rule": "RULE", "query": "QUERY"}[role]
    return position, infer_scope(site["host"]), infer_form(site["host"])

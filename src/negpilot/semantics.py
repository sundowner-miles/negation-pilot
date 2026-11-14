"""Finite-domain classical semantics backed by Z3.

Quantifiers are grounded over the declared domain before solving.

For a satisfiable knowledge base KB and a query q:

- TRUE iff KB entails q iff UNSAT(KB and NOT q)
- FALSE iff KB entails NOT q iff UNSAT(KB and q)
- UNKNOWN iff SAT(KB and q) and SAT(KB and NOT q)

An unsatisfiable KB is rejected. Failure to derive q is not treated as FALSE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import z3

from negpilot.ast import (
    And,
    Atom,
    Exists,
    ForAll,
    Formula,
    FormulaError,
    Implies,
    Not,
    Or,
    sexp,
    validate_syntax,
)


class SemanticsError(RuntimeError):
    """The solver failed or a formula could not be grounded."""


def conjoin(formulas: Sequence[Formula]) -> Formula:
    if not formulas:
        raise FormulaError("cannot conjoin an empty set")
    acc = formulas[0]
    for item in formulas[1:]:
        acc = And(acc, item)
    return acc


def disjoin(formulas: Sequence[Formula]) -> Formula:
    if not formulas:
        raise FormulaError("cannot disjoin an empty set")
    acc = formulas[0]
    for item in formulas[1:]:
        acc = Or(acc, item)
    return acc


def ground(formula: Formula, domain: Sequence[str], env: dict[str, str] | None = None) -> Formula:
    """Replace ForAll and Exists by conjunctions and disjunctions over the domain."""
    if not domain:
        raise FormulaError("the domain is empty")
    env = dict(env or {})
    if isinstance(formula, Atom):
        args = tuple(env.get(arg, arg) for arg in formula.args)
        return Atom(formula.pred, args)
    if isinstance(formula, Not):
        return Not(ground(formula.formula, domain, env))
    if isinstance(formula, And):
        return And(ground(formula.left, domain, env), ground(formula.right, domain, env))
    if isinstance(formula, Or):
        return Or(ground(formula.left, domain, env), ground(formula.right, domain, env))
    if isinstance(formula, Implies):
        return Implies(ground(formula.left, domain, env), ground(formula.right, domain, env))
    if isinstance(formula, ForAll):
        parts = [ground(formula.body, domain, {**env, formula.var: item}) for item in domain]
        return conjoin(parts)
    if isinstance(formula, Exists):
        parts = [ground(formula.body, domain, {**env, formula.var: item}) for item in domain]
        return disjoin(parts)
    raise FormulaError(f"unknown node {type(formula).__name__}")


def atom_key(pred: str, args: Sequence[str]) -> str:
    return f"{pred}({','.join(args)})"


def collect_atoms(formula: Formula) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def rec(node: Formula) -> None:
        if isinstance(node, Atom):
            key = (node.pred, tuple(node.args))
            if key not in seen:
                seen.add(key)
                found.append(key)
            return
        if isinstance(node, Not):
            rec(node.formula)
            return
        if isinstance(node, (And, Or, Implies)):
            rec(node.left)
            rec(node.right)
            return
        if isinstance(node, (ForAll, Exists)):
            raise SemanticsError("collect_atoms expects a grounded formula")
        raise FormulaError(f"unknown node {type(node).__name__}")

    rec(formula)
    return found


def _z3_of(
    formula: Formula, consts: dict[tuple[str, tuple[str, ...]], z3.BoolRef]
) -> z3.BoolRef:
    if isinstance(formula, Atom):
        key = (formula.pred, tuple(formula.args))
        if key not in consts:
            consts[key] = z3.Bool(atom_key(formula.pred, formula.args).replace(",", "_"))
        return consts[key]
    if isinstance(formula, Not):
        return z3.Not(_z3_of(formula.formula, consts))
    if isinstance(formula, And):
        return z3.And(_z3_of(formula.left, consts), _z3_of(formula.right, consts))
    if isinstance(formula, Or):
        return z3.Or(_z3_of(formula.left, consts), _z3_of(formula.right, consts))
    if isinstance(formula, Implies):
        return z3.Implies(_z3_of(formula.left, consts), _z3_of(formula.right, consts))
    raise SemanticsError("quantifiers must be grounded before conversion to Z3")


def _solver(constraints: list[z3.BoolRef]) -> z3.Solver:
    solver = z3.Solver()
    solver.set("timeout", 5000)
    solver.add(constraints)
    return solver


def _check(solver: z3.Solver) -> bool:
    result = solver.check()
    if result == z3.unknown:
        raise SemanticsError("Z3 returned unknown (timeout or incomplete)")
    return result == z3.sat


def is_sat(formulas: Sequence[Formula]) -> bool:
    consts: dict[tuple[str, tuple[str, ...]], z3.BoolRef] = {}
    constraints = [_z3_of(item, consts) for item in formulas]
    return _check(_solver(constraints))


def canonical_model(formulas: Sequence[Formula]) -> dict[str, bool] | None:
    """Lexicographically least model, preferring False for each atom in sorted order."""
    consts: dict[tuple[str, tuple[str, ...]], z3.BoolRef] = {}
    constraints = [_z3_of(item, consts) for item in formulas]
    solver = _solver(constraints)
    if not _check(solver):
        return None
    assignment: dict[str, bool] = {}
    for key in sorted(consts, key=lambda item: atom_key(item[0], item[1])):
        const = consts[key]
        name = atom_key(key[0], key[1])
        solver.push()
        solver.add(z3.Not(const))
        result = solver.check()
        if result == z3.unknown:
            raise SemanticsError("Z3 returned unknown while building a canonical model")
        if result == z3.sat:
            assignment[name] = False
            continue
        solver.pop()
        solver.add(const)
        if solver.check() != z3.sat:
            raise SemanticsError(f"atom {name} could not be assigned")
        assignment[name] = True
    return assignment


def evaluate(formula: Formula, domain: Sequence[str], assignment: dict[str, bool]) -> bool:
    grounded = ground(formula, domain)

    def rec(node: Formula) -> bool:
        if isinstance(node, Atom):
            key = atom_key(node.pred, node.args)
            if key not in assignment:
                raise SemanticsError(f"model is missing {key}")
            return assignment[key]
        if isinstance(node, Not):
            return not rec(node.formula)
        if isinstance(node, And):
            return rec(node.left) and rec(node.right)
        if isinstance(node, Or):
            return rec(node.left) or rec(node.right)
        if isinstance(node, Implies):
            return (not rec(node.left)) or rec(node.right)
        raise SemanticsError("quantifier remained during evaluation")

    return rec(grounded)


def equivalent(left: Formula, right: Formula, domain: Sequence[str]) -> bool:
    for formula in (left, right):
        errors = validate_syntax(formula, domain)
        if errors:
            raise FormulaError("; ".join(errors))
    g_left = ground(left, domain)
    g_right = ground(right, domain)
    left_not_right = not is_sat([g_left, Not(g_right)])
    right_not_left = not is_sat([g_right, Not(g_left)])
    return left_not_right and right_not_left


@dataclass
class Decision:
    label: str
    kb_satisfiable: bool
    kb_and_query: str
    kb_and_not_query: str
    models: dict[str, dict[str, bool] | None]


def _status(flag: bool) -> str:
    return "sat" if flag else "unsat"


def classify(
    knowledge_base: Sequence[Formula],
    query: Formula,
    domain: Sequence[str],
    with_models: bool = True,
) -> Decision:
    """Decide TRUE, FALSE, UNKNOWN, or INCONSISTENT."""
    if not domain:
        raise FormulaError("the domain is empty")
    for index, formula in enumerate(list(knowledge_base) + [query]):
        errors = validate_syntax(formula, domain)
        if errors:
            where = "query" if index == len(knowledge_base) else f"statement {index}"
            raise FormulaError(f"{where}: " + "; ".join(errors) + f" :: {sexp(formula)}")

    grounded_kb = [ground(item, domain) for item in knowledge_base]
    grounded_query = ground(query, domain)
    kb_sat = is_sat(grounded_kb)
    if not kb_sat:
        return Decision("INCONSISTENT", False, "unsat", "unsat", {})

    sat_query = is_sat([*grounded_kb, grounded_query])
    sat_not_query = is_sat([*grounded_kb, Not(grounded_query)])
    if sat_query and not sat_not_query:
        label = "TRUE"
    elif sat_not_query and not sat_query:
        label = "FALSE"
    elif sat_query and sat_not_query:
        label = "UNKNOWN"
    else:
        label = "INCONSISTENT"

    models: dict[str, dict[str, bool] | None] = {
        "kb_and_query": None,
        "kb_and_not_query": None,
    }
    if with_models and label != "INCONSISTENT":
        if sat_query:
            models["kb_and_query"] = canonical_model([*grounded_kb, grounded_query])
        if sat_not_query:
            models["kb_and_not_query"] = canonical_model([*grounded_kb, Not(grounded_query)])
    return Decision(
        label=label,
        kb_satisfiable=True,
        kb_and_query=_status(sat_query),
        kb_and_not_query=_status(sat_not_query),
        models=models,
    )


def solver_version() -> str:
    return str(z3.get_version_string())

"""Deterministic natural-language templates and their inverse parser.

Pilot v1 never asks a language model to invent facts or labels. Each AST shape
has one sentence frame per pack. Alpha is used for train and dev. Beta is held
out for the test split.

The four English patterns below are easy to conflate. The frames in this module
are the ones actually written into the data. Short forms are documented and are
not emitted, because several of them are ambiguous.

- Every C is not D / No C is D
  Formula: ForAll(x, Implies(C(x), Not(D(x))))
  Meaning: every C fails to be D. This is the negated rule consequent.
- Not every C is D / Not (every C is D)
  Formula: Not(ForAll(x, Implies(C(x), D(x))))
  Meaning: the universal claim is false. Equivalent to the next row.
- Some C is not D
  Formula: Exists(x, And(C(x), Not(D(x))))
  Meaning: at least one C fails to be D. Classically equivalent to the previous row.
- Every non-C is D
  Formula: ForAll(x, Implies(Not(C(x)), D(x)))
  Meaning: negated rule antecedent. Not equivalent to any row above.
"""

from __future__ import annotations

import re

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
)

TOKEN = r"[A-Za-z][A-Za-z0-9_]*"

PHRASE_MAP = [
    {
        "id": "negated_rule_consequent",
        "formula": "ForAll(x, Implies(C(x), Not(D(x))))",
        "plain_language_equivalents": ["Every C is not D", "No C is D"],
        "pilot_alpha": (
            "For every individual, if the individual is C, then the individual is not D."
        ),
        "pilot_beta": (
            "Whenever an individual has property C, that individual does not have property D."
        ),
        "not_equivalent_to": [
            "Not every C is D",
            "Not (every C is D)",
            "Some C is not D",
        ],
    },
    {
        "id": "negated_rule_antecedent",
        "formula": "ForAll(x, Implies(Not(C(x)), D(x)))",
        "plain_language_equivalents": ["Every non-C is D", "Anyone who is not C is D"],
        "pilot_alpha": (
            "For every individual, if the individual is not C, then the individual is D."
        ),
        "pilot_beta": (
            "Whenever an individual does not have property C, that individual has property D."
        ),
        "not_equivalent_to": ["Every C is not D", "No C is D", "Not every C is D"],
    },
    {
        "id": "negated_universal",
        "formula": "Not(ForAll(x, Implies(C(x), D(x))))",
        "plain_language_equivalents": ["Not every C is D", "Not (every C is D)"],
        "pilot_alpha": (
            "It is not true that for every individual, if the individual is C, "
            "then the individual is D."
        ),
        "pilot_beta": (
            "It is not the case that whenever an individual has property C, "
            "that individual has property D."
        ),
        "classically_equivalent_to": "Some C is not D",
        "not_equivalent_to": ["Every C is not D", "No C is D"],
    },
    {
        "id": "existential_counterexample",
        "formula": "Exists(x, And(C(x), Not(D(x))))",
        "plain_language_equivalents": ["Some C is not D", "There is a C that is not D"],
        "pilot_alpha": "There is at least one individual that is C and is not D.",
        "pilot_beta": "At least one individual has property C and does not have property D.",
        "classically_equivalent_to": "Not every C is D",
        "not_equivalent_to": ["Every C is not D", "No C is D"],
    },
]


def _atom(pred: str, arg: str) -> Atom:
    return Atom(pred, (arg,))


def _render_symbol(formula: Formula) -> str:
    if isinstance(formula, Atom) and len(formula.args) == 1:
        return f"{formula.pred}({formula.args[0]})."
    if isinstance(formula, Not) and isinstance(formula.formula, Atom) and len(formula.formula.args) == 1:
        atom = formula.formula
        return f"Not {atom.pred}({atom.args[0]})."
    if isinstance(formula, ForAll) and isinstance(formula.body, Implies):
        return _render_symbol_rule(formula.body)
    if (
        isinstance(formula, Not)
        and isinstance(formula.formula, ForAll)
        and isinstance(formula.formula.body, Implies)
    ):
        pair = _binary_atoms(formula.formula.body)
        if not pair:
            raise FormulaError("negated universal template expects two positive atoms")
        left, right = pair
        return f"Not every {left} is {right}."
    if isinstance(formula, Exists) and isinstance(formula.body, And):
        body = formula.body
        if not (
            isinstance(body.left, Atom)
            and isinstance(body.right, Not)
            and isinstance(body.right.formula, Atom)
        ):
            raise FormulaError("existential template expects C(x) and not D(x)")
        return f"Some {body.left.pred} is not {body.right.formula.pred}."
    if (
        isinstance(formula, Or)
        and isinstance(formula.left, Not)
        and isinstance(formula.left.formula, Atom)
        and isinstance(formula.right, Atom)
    ):
        negative = formula.left.formula
        positive = formula.right
        return f"Not {negative.pred}({negative.args[0]}) or {positive.pred}({positive.args[0]})."
    raise FormulaError(f"no symbol template for {sexp(formula)}")


def _render_symbol_rule(implication: Implies) -> str:
    positive = _binary_atoms(implication)
    if positive:
        left, right = positive
        return f"Every {left} is {right}."
    if (
        isinstance(implication.left, Atom)
        and isinstance(implication.right, Not)
        and isinstance(implication.right.formula, Atom)
    ):
        return f"Every {implication.left.pred} is not {implication.right.formula.pred}."
    if (
        isinstance(implication.left, Not)
        and isinstance(implication.left.formula, Atom)
        and isinstance(implication.right, Atom)
    ):
        return f"Every non-{implication.left.formula.pred} is {implication.right.pred}."
    raise FormulaError(f"no symbol rule template for {sexp(implication)}")


def _parse_symbol(text: str) -> Formula:
    name = r"[A-Z]"
    individual = r"[a-z]"
    patterns = [
        (
            "disjunction",
            rf"^Not ({name})\(({individual})\) or ({name})\(({individual})\)\.$",
        ),
        ("not_universal", rf"^Not every ({name}) is ({name})\.$"),
        ("antecedent", rf"^Every non-({name}) is ({name})\.$"),
        ("consequent", rf"^Every ({name}) is not ({name})\.$"),
        ("exists", rf"^Some ({name}) is not ({name})\.$"),
        ("rule", rf"^Every ({name}) is ({name})\.$"),
        ("not_atom", rf"^Not ({name})\(({individual})\)\.$"),
        ("atom", rf"^({name})\(({individual})\)\.$"),
    ]
    for kind, pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        groups = match.groups()
        if kind == "atom":
            return _atom(groups[0], groups[1])
        if kind == "not_atom":
            return Not(_atom(groups[0], groups[1]))
        if kind == "rule":
            return ForAll("x", Implies(_atom(groups[0], "x"), _atom(groups[1], "x")))
        if kind == "consequent":
            return ForAll("x", Implies(_atom(groups[0], "x"), Not(_atom(groups[1], "x"))))
        if kind == "antecedent":
            return ForAll("x", Implies(Not(_atom(groups[0], "x")), _atom(groups[1], "x")))
        if kind == "not_universal":
            return Not(ForAll("x", Implies(_atom(groups[0], "x"), _atom(groups[1], "x"))))
        if kind == "exists":
            return Exists("x", And(_atom(groups[0], "x"), Not(_atom(groups[1], "x"))))
        if kind == "disjunction":
            return Or(Not(_atom(groups[0], groups[1])), _atom(groups[2], groups[3]))
    raise FormulaError(f"sentence does not match the symbol pack: {text}")


def render(formula: Formula, pack: str) -> str:
    if pack == "symbol":
        text = _render_symbol(formula)
        parsed = _parse_symbol(text)
        if parsed != formula:
            raise FormulaError(
                "renderer/parser mismatch for "
                f"{sexp(formula)} -> {text!r} -> {sexp(parsed)}"
            )
        return text
    if pack not in {"alpha", "beta"}:
        raise FormulaError(f"unknown template pack {pack}")
    text = _render(formula, pack)
    parsed = parse(text, pack)
    if parsed != formula:
        raise FormulaError(
            "renderer/parser mismatch for "
            f"{sexp(formula)} -> {text!r} -> {sexp(parsed)}"
        )
    return text


def _render(formula: Formula, pack: str) -> str:
    if isinstance(formula, Atom) and len(formula.args) == 1:
        ind, pred = formula.args[0], formula.pred
        if pack == "alpha":
            return f"{ind} is {pred}."
        return f"{ind} has property {pred}."
    if isinstance(formula, Not) and isinstance(formula.formula, Atom) and len(formula.formula.args) == 1:
        ind, pred = formula.formula.args[0], formula.formula.pred
        if pack == "alpha":
            return f"{ind} is not {pred}."
        return f"{ind} does not have property {pred}."
    if isinstance(formula, ForAll) and isinstance(formula.body, Implies):
        return _render_rule(formula.body, pack)
    if (
        isinstance(formula, Not)
        and isinstance(formula.formula, ForAll)
        and isinstance(formula.formula.body, Implies)
    ):
        return _render_not_universal(formula.formula.body, pack)
    if isinstance(formula, Exists) and isinstance(formula.body, And):
        return _render_exists(formula.body, pack)
    if (
        isinstance(formula, Or)
        and isinstance(formula.left, Not)
        and isinstance(formula.left.formula, Atom)
        and isinstance(formula.right, Atom)
    ):
        return _render_disjunction(formula.left.formula, formula.right, pack)
    raise FormulaError(f"no template for {sexp(formula)}")


def _binary_atoms(implication: Implies) -> tuple[str, str] | None:
    if (
        isinstance(implication.left, Atom)
        and isinstance(implication.right, Atom)
        and implication.left.args == ("x",)
        and implication.right.args == ("x",)
    ):
        return implication.left.pred, implication.right.pred
    return None


def _render_rule(implication: Implies, pack: str) -> str:
    positive = _binary_atoms(implication)
    if positive:
        left, right = positive
        if pack == "alpha":
            return (
                "For every individual, if the individual is "
                f"{left}, then the individual is {right}."
            )
        return (
            "Whenever an individual has property "
            f"{left}, that individual has property {right}."
        )
    if (
        isinstance(implication.left, Atom)
        and isinstance(implication.right, Not)
        and isinstance(implication.right.formula, Atom)
        and implication.left.args == ("x",)
        and implication.right.formula.args == ("x",)
    ):
        left = implication.left.pred
        right = implication.right.formula.pred
        if pack == "alpha":
            return (
                "For every individual, if the individual is "
                f"{left}, then the individual is not {right}."
            )
        return (
            "Whenever an individual has property "
            f"{left}, that individual does not have property {right}."
        )
    if (
        isinstance(implication.left, Not)
        and isinstance(implication.left.formula, Atom)
        and isinstance(implication.right, Atom)
        and implication.left.formula.args == ("x",)
        and implication.right.args == ("x",)
    ):
        left = implication.left.formula.pred
        right = implication.right.pred
        if pack == "alpha":
            return (
                "For every individual, if the individual is not "
                f"{left}, then the individual is {right}."
            )
        return (
            "Whenever an individual does not have property "
            f"{left}, that individual has property {right}."
        )
    raise FormulaError(f"no rule template for {sexp(implication)}")


def _render_not_universal(implication: Implies, pack: str) -> str:
    pair = _binary_atoms(implication)
    if not pair:
        raise FormulaError("negated universal template expects two positive atoms")
    left, right = pair
    if pack == "alpha":
        return (
            "It is not true that for every individual, if the individual is "
            f"{left}, then the individual is {right}."
        )
    return (
        "It is not the case that whenever an individual has property "
        f"{left}, that individual has property {right}."
    )


def _render_exists(body: And, pack: str) -> str:
    if not (
        isinstance(body.left, Atom)
        and isinstance(body.right, Not)
        and isinstance(body.right.formula, Atom)
        and body.left.args == ("x",)
        and body.right.formula.args == ("x",)
    ):
        raise FormulaError("existential template expects C(x) and not D(x)")
    left = body.left.pred
    right = body.right.formula.pred
    if pack == "alpha":
        return f"There is at least one individual that is {left} and is not {right}."
    return (
        f"At least one individual has property {left} and does not have property {right}."
    )


def _render_disjunction(negative: Atom, positive: Atom, pack: str) -> str:
    if len(negative.args) != 1 or len(positive.args) != 1:
        raise FormulaError("disjunction template expects ground unary atoms")
    if pack == "alpha":
        return (
            f"Either {negative.args[0]} is not {negative.pred}, "
            f"or {positive.args[0]} is {positive.pred}."
        )
    return (
        f"Either {negative.args[0]} does not have property {negative.pred}, "
        f"or {positive.args[0]} has property {positive.pred}."
    )


def _compiled(pack: str) -> list[tuple[str, re.Pattern[str]]]:
    name = TOKEN
    if pack == "alpha":
        patterns = [
            (
                "not_universal",
                rf"^It is not true that for every individual, if the individual is ({name}), then the individual is ({name})\.$",
            ),
            (
                "antecedent",
                rf"^For every individual, if the individual is not ({name}), then the individual is ({name})\.$",
            ),
            (
                "consequent",
                rf"^For every individual, if the individual is ({name}), then the individual is not ({name})\.$",
            ),
            (
                "exists",
                rf"^There is at least one individual that is ({name}) and is not ({name})\.$",
            ),
            (
                "disjunction",
                rf"^Either ({name}) is not ({name}), or ({name}) is ({name})\.$",
            ),
            (
                "not_atom",
                rf"^({name}) is not ({name})\.$",
            ),
            (
                "rule",
                rf"^For every individual, if the individual is ({name}), then the individual is ({name})\.$",
            ),
            (
                "atom",
                rf"^({name}) is ({name})\.$",
            ),
        ]
    elif pack == "beta":
        patterns = [
            (
                "not_universal",
                rf"^It is not the case that whenever an individual has property ({name}), that individual has property ({name})\.$",
            ),
            (
                "antecedent",
                rf"^Whenever an individual does not have property ({name}), that individual has property ({name})\.$",
            ),
            (
                "consequent",
                rf"^Whenever an individual has property ({name}), that individual does not have property ({name})\.$",
            ),
            (
                "exists",
                rf"^At least one individual has property ({name}) and does not have property ({name})\.$",
            ),
            (
                "disjunction",
                rf"^Either ({name}) does not have property ({name}), or ({name}) has property ({name})\.$",
            ),
            (
                "not_atom",
                rf"^({name}) does not have property ({name})\.$",
            ),
            (
                "rule",
                rf"^Whenever an individual has property ({name}), that individual has property ({name})\.$",
            ),
            (
                "atom",
                rf"^({name}) has property ({name})\.$",
            ),
        ]
    else:
        raise FormulaError(f"unknown template pack {pack}")
    return [(kind, re.compile(pattern)) for kind, pattern in patterns]


def parse(text: str, pack: str) -> Formula:
    if pack == "symbol":
        return _parse_symbol(text)
    for kind, pattern in _compiled(pack):
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groups()
        if kind == "atom":
            return _atom(groups[1], groups[0])
        if kind == "not_atom":
            return Not(_atom(groups[1], groups[0]))
        if kind == "rule":
            return ForAll("x", Implies(_atom(groups[0], "x"), _atom(groups[1], "x")))
        if kind == "consequent":
            return ForAll("x", Implies(_atom(groups[0], "x"), Not(_atom(groups[1], "x"))))
        if kind == "antecedent":
            return ForAll("x", Implies(Not(_atom(groups[0], "x")), _atom(groups[1], "x")))
        if kind == "not_universal":
            return Not(ForAll("x", Implies(_atom(groups[0], "x"), _atom(groups[1], "x"))))
        if kind == "exists":
            return Exists("x", And(_atom(groups[0], "x"), Not(_atom(groups[1], "x"))))
        if kind == "disjunction":
            return Or(Not(_atom(groups[1], groups[0])), _atom(groups[3], groups[2]))
    raise FormulaError(f"sentence does not match pack {pack}: {text}")


def negation_cue_count(text: str) -> int:
    lowered = text.lower()
    return len(re.findall(r"\bnot\b", lowered)) + len(re.findall(r"\bnon-", lowered))


def build_prompt(domain: list[str], statements: list[str], query_text: str) -> str:
    listed = ", ".join(domain)
    lines = [
        "You are given a finite domain and a knowledge base of facts and rules.",
        f"The domain contains exactly these individuals: {listed}.",
        "Use only the supplied facts and rules.",
        "Do not assume that a statement is false merely because it is not stated or derived.",
        "TRUE means the knowledge base logically entails the query.",
        "FALSE means the knowledge base logically entails the negation of the query.",
        "UNKNOWN means neither the query nor its negation is entailed.",
        "The output must be exactly one of TRUE, FALSE, UNKNOWN.",
        "",
        "Domain:",
        listed,
        "",
        "Knowledge base:",
    ]
    for index, text in enumerate(statements, start=1):
        lines.append(f"{index}. {text}")
    lines.extend(["", "Query:", query_text, "", "Answer:"])
    return "\n".join(lines)

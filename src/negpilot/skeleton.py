"""Alpha-renamed logical skeletons.

The canonical key is the lexicographically smallest rendering after predicate
and individual renaming. Knowledge-base statements are sorted, so their stored
order does not create a second skeleton. Quantifier variables are renamed
separately from individuals. Operator structure is left in place.
"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import permutations, product

from negpilot.ast import Formula, sexp

_TOKEN = re.compile(r"[A-Za-z]+")
_VARIABLES = frozenset({"x", "y", "z"})


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def _names(texts: list[str]) -> tuple[list[str], list[str], list[str]]:
    found = {token for text in texts for token in _tokens(text)}
    predicates = sorted(token for token in found if len(token) == 1 and token.isupper())
    individuals = sorted(
        token for token in found if len(token) == 1 and token.islower() and token not in _VARIABLES
    )
    variables = sorted(token for token in found if token in _VARIABLES)
    return predicates, individuals, variables


def _render(text: str, mapping: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return mapping.get(token, token)

    return _TOKEN.sub(replace, text)


def _refine(texts: list[str], predicates: list[str], individuals: list[str]) -> tuple[list[list[str]], list[list[str]]]:
    """Partition symbols that occur in the same structural positions."""
    predicate_cell = {name: 0 for name in predicates}
    individual_cell = {name: 0 for name in individuals}
    for _ in range(len(predicates) + len(individuals) + 2):
        occurrences: dict[str, list[str]] = defaultdict(list)
        for text in texts:
            rendered = _render(text, {**_cell_map(predicate_cell, "P"), **_cell_map(individual_cell, "C")})
            for token in _tokens(text):
                if token in predicate_cell or token in individual_cell:
                    occurrences[token].append(rendered)
        next_predicates = _recolor(predicates, occurrences)
        next_individuals = _recolor(individuals, occurrences)
        if next_predicates == predicate_cell and next_individuals == individual_cell:
            break
        predicate_cell, individual_cell = next_predicates, next_individuals
    return _cells(predicates, predicate_cell), _cells(individuals, individual_cell)


def _cell_map(cells: dict[str, int], prefix: str) -> dict[str, str]:
    return {name: f"{prefix}{index}" for name, index in cells.items()}


def _recolor(names: list[str], occurrences: dict[str, list[str]]) -> dict[str, int]:
    if not names:
        return {}
    classes = sorted({tuple(sorted(occurrences[name])) for name in names})
    index = {signature: position for position, signature in enumerate(classes)}
    return {name: index[tuple(sorted(occurrences[name]))] for name in names}


def _cells(names: list[str], colors: dict[str, int]) -> list[list[str]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for name in names:
        grouped[colors[name]].append(name)
    ordered = []
    for color in sorted(grouped):
        ordered.append(sorted(grouped[color]))
    return ordered


def canonical_skeleton(statements: list[Formula], query: Formula, domain_size: int) -> str:
    """Return one key for every alpha-renaming and statement reordering."""
    texts = [sexp(statement) for statement in statements]
    query_text = sexp(query)
    return canonical_skeleton_text(texts, query_text, domain_size)


def canonical_skeleton_text(statements: list[str], query: str, domain_size: int) -> str:
    texts = [*statements, query]
    predicates, individuals, variables = _names(texts)
    variable_map = {name: f"V{index}" for index, name in enumerate(variables)}
    predicate_cells, individual_cells = _refine(texts, predicates, individuals)
    best: tuple[str, ...] | None = None
    predicate_choices = product(*( _permutations(cell) for cell in predicate_cells))
    individual_choices = product(*( _permutations(cell) for cell in individual_cells))
    individual_options = list(individual_choices)
    for predicate_choice in predicate_choices:
        predicate_map = _assign(predicate_choice, "P")
        for individual_choice in individual_options:
            mapping = {**predicate_map, **_assign(individual_choice, "C"), **variable_map}
            rendered = tuple(sorted(_render(text, mapping) for text in statements))
            key = (*rendered, _render(query, mapping))
            if best is None or key < best:
                best = key
    assert best is not None
    body = " ;; ".join(best)
    return f"domain:{domain_size} ;; {body}"


def _permutations(cell: list[str]):
    return permutations(cell)


def _assign(choice: tuple[tuple[str, ...], ...], prefix: str) -> dict[str, str]:
    mapping = {}
    cursor = 0
    for cell in choice:
        for name in cell:
            mapping[name] = f"{prefix}{cursor}"
            cursor += 1
    return mapping

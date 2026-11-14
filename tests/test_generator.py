"""Generator, split, and rendering checks."""

import copy
import json
from collections import Counter
from pathlib import Path

from negpilot.ast import And, Atom, Exists, ForAll, Implies, Not, Or
from negpilot.generator import build_drafts, check_plan, generate_records, load_config, to_public
from negpilot.renderer import parse, render
from negpilot.split import assign_splits
from negpilot.validator import validate_records

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "configs" / "pilot.yaml")


def test_split_hits_the_configured_base_case_quotas():
    ids = [f"base-{index:04d}" for index in range(600)]
    strata = [f"family-{index % 11}" for index in range(600)]
    mapping = assign_splits(ids, strata, 20261111, CONFIG["split"])
    assert Counter(mapping.values()) == {"train": 420, "dev": 60, "test": 120}
    assert assign_splits(ids, strata, 20261111, CONFIG["split"]) == mapping


def test_full_plan_matches_the_pilot_quotas_before_solving():
    drafts = build_drafts(CONFIG)
    check_plan(drafts, CONFIG)
    assert len(drafts) == 600


def _shrink(config):
    shrunk = copy.deepcopy(config)
    shrunk.pop("expected_totals", None)
    for family in shrunk["families"]:
        family["instances"] = [dict(family["instances"][0], count=1)]
    return shrunk


def test_tiny_generation_is_deterministic_and_structurally_valid():
    config = _shrink(CONFIG)
    first = generate_records(config)
    second = generate_records(config)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert validate_records(first, config, recompute_logic=True) == []
    public = [to_public(record) for record in first]
    assert all(
        "label" not in row and "proof_trace" not in row and "negation_critical" not in row
        for row in public
    )


def test_every_supported_shape_roundtrips_in_both_packs():
    shapes = [
        Atom("fim0_0", ("wug0_0",)),
        Not(Atom("fim0_0", ("wug0_0",))),
        ForAll("x", Implies(Atom("fim0_0", ("x",)), Atom("fim0_1", ("x",)))),
        ForAll("x", Implies(Atom("fim0_0", ("x",)), Not(Atom("fim0_1", ("x",))))),
        ForAll("x", Implies(Not(Atom("fim0_0", ("x",))), Atom("fim0_1", ("x",)))),
        Not(ForAll("x", Implies(Atom("fim0_0", ("x",)), Atom("fim0_1", ("x",))))),
        Exists("x", And(Atom("fim0_0", ("x",)), Not(Atom("fim0_1", ("x",))))),
        Or(Not(Atom("fim0_0", ("wug0_0",))), Atom("fim0_1", ("wug0_0",))),
    ]
    for pack in ("alpha", "beta"):
        for formula in shapes:
            assert parse(render(formula, pack), pack) == formula
    symbol_shapes = [
        Atom("A", ("a",)),
        Not(Atom("A", ("a",))),
        ForAll("x", Implies(Atom("A", ("x",)), Atom("B", ("x",)))),
        ForAll("x", Implies(Atom("A", ("x",)), Not(Atom("B", ("x",))))),
        ForAll("x", Implies(Not(Atom("A", ("x",))), Atom("B", ("x",)))),
        Not(ForAll("x", Implies(Atom("A", ("x",)), Atom("B", ("x",))))),
        Exists("x", And(Atom("A", ("x",)), Not(Atom("B", ("x",))))),
        Or(Not(Atom("A", ("a",))), Atom("B", ("a",))),
    ]
    for formula in symbol_shapes:
        assert parse(render(formula, "symbol"), "symbol") == formula

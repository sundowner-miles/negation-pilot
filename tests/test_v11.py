"""Dataset v1.1 keeps the v1.0 logic and only changes split and metadata."""

from collections import Counter, defaultdict
from pathlib import Path

from negpilot.generator import to_public
from negpilot.pair_audit import comparison_rows
from negpilot.v11 import _digest, _load

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "generated" / "pilot.gold.jsonl"
PUBLIC = ROOT / "data" / "generated" / "pilot.public.jsonl"
BACKUP = ROOT / "dataset-v1.0" / "pilot.gold.jsonl"


def test_v11_preserves_logic_and_repairs_metadata():
    before = _load(BACKUP)
    after = _load(GOLD)
    public = _load(PUBLIC)
    assert len(before) == len(after) == len(public) == 1200
    assert {row["sample_id"] for row in before} == {row["sample_id"] for row in after}
    by_id = {row["sample_id"]: row for row in after}
    assert all(_digest(old) == _digest(by_id[old["sample_id"]]) for old in before)

    forms = Counter(row["negation_form"] for row in after)
    assert "disjunctive_syllogism" not in forms
    assert forms["negated_disjunct"] == 160
    disjunction = [row for row in after if row["negation_form"] == "negated_disjunct"]
    assert {row["negation_embedding"] for row in disjunction} == {"disjunction"}
    assert {row["negation_function"] for row in disjunction} == {"disjunctive_premise"}
    assert {row["inference_type"] for row in disjunction} == {
        "disjunctive_syllogism",
        "modus_ponens_then_disjunctive_syllogism",
    }

    splits = Counter(row["split"] for row in after)
    assert splits == {"train": 840, "dev": 120, "test": 240}
    bases = defaultdict(set)
    pairs = defaultdict(set)
    skeletons = defaultdict(set)
    for row in after:
        bases[row["base_case_id"]].add(row["split"])
        pairs[row["pair_id"]].add(row["split"])
        skeletons[row["canonical_skeleton"]].add(row["split"])
    assert all(len(found) == 1 for found in bases.values())
    assert all(len(found) == 1 for found in pairs.values())
    assert all(len(found) == 1 for found in skeletons.values())
    assert len(bases) == 600 and len(pairs) == 600

    labels = defaultdict(Counter)
    positions = defaultdict(Counter)
    depths = defaultdict(Counter)
    for row in after:
        labels[row["split"]][row["label"]] += 1
        positions[row["split"]][row["negation_position"]] += 1
        depth = "null" if row["reasoning_depth"] is None else str(row["reasoning_depth"])
        depths[row["split"]][depth] += 1
    assert set(labels["dev"]) == {"TRUE", "FALSE", "UNKNOWN"}
    assert labels["test"] == {"TRUE": 80, "FALSE": 80, "UNKNOWN": 80}
    assert positions["dev"]["FACT"] == 0
    assert set(positions["test"]) == {"FACT", "RULE", "QUERY"}
    assert depths["test"]["1"] == 30
    assert depths["test"]["3"] == 30
    assert depths["test"]["5"] == 70
    assert set(depths["test"]) == {"0", "1", "3", "5", "null"}

    controlled = sum(1 for row in after if row["in_controlled_subset"])
    assert controlled == 580
    equivalent = [
        row for row in after if row.get("semantic_equivalent") is True
    ]
    assert len(equivalent) == 162
    assert all(row["equivalence_verification"] == "pass" for row in equivalent)
    assert all(row["pair_type"] == "equivalent_form" for row in equivalent)

    rows = comparison_rows(after)
    assert len(rows) == 600
    required = {
        "individual_sample_validity",
        "label_validity",
        "logical_pair_validity",
        "experimental_control_validity",
        "in_controlled_subset",
        "controlled_variables",
        "manipulated_variables",
        "derived_variables",
        "observed_differences",
        "rejection_reasons",
    }
    assert required <= set(rows[0])
    assert sum(1 for row in rows if row["in_controlled_subset"]) == 290

    public_by_id = {row["sample_id"]: row for row in public}
    forbidden = {"label", "binary_label", "proof_trace", "negation_critical", "label_after_ablation"}
    for row in after:
        projected = to_public(row)
        assert public_by_id[row["sample_id"]]["split"] == row["split"]
        assert forbidden.isdisjoint(projected)
        assert forbidden.isdisjoint(public_by_id[row["sample_id"]])

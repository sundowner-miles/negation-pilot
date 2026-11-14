"""Contrast-pair invariants."""

import copy
from collections import defaultdict
from pathlib import Path

from negpilot.generator import generate_records, load_config
from negpilot.validator import validate_records

ROOT = Path(__file__).resolve().parents[1]


def test_pairs_have_two_members_complementary_labels_and_one_split():
    config = load_config(ROOT / "configs" / "pilot.yaml")
    config = copy.deepcopy(config)
    config.pop("expected_totals", None)
    for family in config["families"]:
        family["instances"] = [dict(family["instances"][0], count=1)]
    records = generate_records(config)
    grouped = defaultdict(list)
    for record in records:
        grouped[record["pair_id"]].append(record)
    assert grouped
    for pair_id, members in grouped.items():
        assert len(members) == 2, pair_id
        assert members[0]["split"] == members[1]["split"]
        assert members[0]["base_case_id"] == members[1]["base_case_id"]
        labels = {member["label"] for member in members}
        if members[0]["pair_type"] in {"equivalent_form", "query_target_contrast"} or labels == {"UNKNOWN"}:
            assert labels == {"UNKNOWN"}
        else:
            assert labels == {"TRUE", "FALSE"}
        assert all(member["negation_count"] in {1, 2} for member in members)
        assert members[0]["logical_pair_validity"] == members[1]["logical_pair_validity"] == "pass"
        assert members[0]["in_controlled_subset"] == members[1]["in_controlled_subset"]
        reasons = members[0]["pair_metadata"]["rejection_reasons"]
        if members[0]["in_controlled_subset"]:
            assert reasons == []
            assert members[0]["experimental_control_validity"] == "pass"
        else:
            assert reasons
            assert members[0]["experimental_control_validity"] == "fail"
    assert len(records) == len(config["families"]) * 2
    by_family = {members[0]["family"]: members for members in grouped.values()}
    assert by_family["rule_consequent_contrast"][0]["in_controlled_subset"]
    assert not by_family["fact_ds_vs_negfact"][0]["in_controlled_subset"]
    fact_reasons = by_family["fact_ds_vs_negfact"][0]["pair_metadata"]["rejection_reasons"]
    assert "inference_and_negation_property_both_change" in fact_reasons
    false_member = next(
        member for member in by_family["fact_ds_vs_negfact"] if member["label"] == "FALSE"
    )
    assert false_member["reasoning_depth"] == 0
    assert false_member["inference_type"] == "fact_lookup"
    assert false_member["inference_steps"] == []
    assert validate_records(records, config, recompute_logic=True) == []

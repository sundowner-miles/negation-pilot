"""Integrity checks for generated files and the closed template language."""

from pathlib import Path

from negpilot.generator import load_config
from negpilot.validator import load_jsonl, validate_public, validate_records

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "generated" / "pilot.gold.jsonl"
PUBLIC = ROOT / "data" / "generated" / "pilot.public.jsonl"


def test_released_pilot_matches_the_audit_when_present():
    if not GOLD.exists() or not PUBLIC.exists():
        return
    config = load_config(ROOT / "configs" / "pilot.yaml")
    gold = load_jsonl(GOLD)
    public = load_jsonl(PUBLIC)
    errors = validate_records(gold, config, recompute_logic=True)
    errors.extend(validate_public(public, gold))
    assert errors == []
    assert {row["label"] for row in gold} == {"TRUE", "FALSE", "UNKNOWN"}
    assert all("label" not in row for row in public)

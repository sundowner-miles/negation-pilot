"""Tests for prompt isolation, parsing, scoring, and smoke-id selection."""

from __future__ import annotations

import inspect

from negpilot.evalkit.infer import run_inference
from negpilot.evalkit.parse import parse_model_output
from negpilot.evalkit.plots import write_smoke_chart
from negpilot.evalkit.prompt import SYSTEM_PROMPT, build_messages
from negpilot.evalkit.score import classification_counts, score_predictions
from negpilot.evalkit.smoke import select_smoke_ids
from negpilot.schema import PUBLIC_FIELDS


def _public(sample_id: str = "ex-1", prompt: str = "Domain:\na\n\nQuery:\nP(a).\n\nAnswer:\n") -> dict:
    return {
        "sample_id": sample_id,
        "split": "dev",
        "domain": ["a", "b", "c"],
        "knowledge_base": ["P(a)."],
        "query": "P(a).",
        "prompt": prompt,
        "generator_version": "v1.1",
        "seed": 20261111,
    }


def test_public_field_set_matches_builder():
    messages = build_messages(_public())
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[1]["content"] == _public()["prompt"]
    assert set(_public()) == set(PUBLIC_FIELDS)


def test_gold_fields_are_refused():
    record = _public()
    record["label"] = "TRUE"
    record["negation_critical"] = True
    try:
        build_messages(record)
    except ValueError as exc:
        assert "label" in str(exc)
    else:
        raise AssertionError("gold fields were accepted")


def test_inference_entrypoint_has_no_gold_argument():
    assert "gold" not in inspect.signature(run_inference).parameters


def test_parser_accepts_only_an_explicit_label():
    assert parse_model_output("TRUE")["predicted_label"] == "TRUE"
    assert parse_model_output("  FALSE \n")["predicted_label"] == "FALSE"
    assert parse_model_output("UNKNOWN")["parse_status"] == "exact"
    think = parse_model_output("<think>entailed</think>\nTRUE")
    assert think["predicted_label"] == "TRUE"
    assert think["parse_status"] == "after_think"
    assert think["explanation"] == "entailed"
    for text in ("The answer is TRUE", "TRUE.", "true", "<think>TRUE</think>", "", "UNKNOWN extra"):
        parsed = parse_model_output(text)
        assert parsed["predicted_label"] == "invalid_output", text
        assert parsed["parse_status"] == "invalid"


def test_invalid_predictions_count_as_incorrect():
    metrics = classification_counts(
        [
            ("TRUE", "TRUE"),
            ("FALSE", "invalid_output"),
            ("UNKNOWN", "FALSE"),
            ("UNKNOWN", "UNKNOWN"),
        ]
    )
    assert metrics["n"] == 4
    assert metrics["correct"] == 2
    assert metrics["accuracy"] == 0.5
    assert metrics["invalid_output"] == 1
    assert metrics["confusion"]["FALSE"]["invalid_output"] == 1
    assert metrics["confusion"]["UNKNOWN"]["FALSE"] == 1
    assert metrics["per_class"]["FALSE"]["recall"] == 0.0


def test_score_joins_on_sample_id_without_using_prompt_text():
    predictions = [
        {"sample_id": "b", "predicted_label": "FALSE"},
        {"sample_id": "a", "predicted_label": "TRUE"},
    ]
    gold = [
        {"sample_id": "a", "label": "TRUE", "split": "dev"},
        {"sample_id": "b", "label": "TRUE", "split": "dev"},
    ]
    scored = score_predictions(predictions, gold)
    assert [row["correct"] for row in scored["rows"]] == [False, True]
    assert scored["accuracy"] == 0.5


def test_smoke_ids_are_deterministic_and_hide_labels():
    gold = []
    for index, label in enumerate(["UNKNOWN", "TRUE", "FALSE", "TRUE", "FALSE", "UNKNOWN"]):
        gold.append({"sample_id": f"ex-{index:02d}", "split": "dev", "label": label})
    gold.append({"sample_id": "ex-99", "split": "train", "label": "TRUE"})
    first = select_smoke_ids(gold, n_per_label=2)
    second = select_smoke_ids(list(reversed(gold)), n_per_label=2)
    assert first == second
    assert first == ["ex-01", "ex-03", "ex-02", "ex-04", "ex-00", "ex-05"]
    assert all(not item.startswith("label") for item in first)


def test_smoke_chart_states_the_sample_count(tmp_path):
    path = tmp_path / "smoke.svg"
    write_smoke_chart(
        path,
        [
            {
                "model": "Qwen3.5-4B",
                "n": 6,
                "correct": 4,
                "incorrect": 1,
                "invalid_output": 1,
            }
        ],
    )
    text = path.read_text(encoding="utf-8")
    assert "n=6" in text
    assert "Qwen3.5-4B" in text
    assert "Not a test-set result" in text

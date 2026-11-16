"""Local text-only inference for Qwen3.5 post-trained checkpoints.

The runner reads a public JSONL file. It has no gold-file argument.
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any

from negpilot.evalkit.io import read_jsonl, write_jsonl
from negpilot.evalkit.parse import parse_model_output
from negpilot.evalkit.prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_messages, sha256_text

# Greedy decoding is the temperature-0 setting used for this pilot.
# generate() is called with do_sample=False and without a temperature
# argument, because some Transformers versions reject temperature=0
# when sampling is off. top_p and top_k are not applied.
MAX_NEW_TOKENS = 32
ENABLE_THINKING = False
DO_SAMPLE = False
TEMPERATURE = 0
TOP_P = None
RETRY_LIMIT = 0


def index_public(public_path: str | Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(public_path)
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample_id = row.get("sample_id")
        if sample_id in indexed:
            raise ValueError(f"duplicate public sample_id {sample_id}")
        indexed[sample_id] = row
    return indexed


def load_qwen35(model_path: str):
    """Load the official multimodal checkpoint for text-only generation.

    The published Qwen3.5 weights are Qwen3_5ForConditionalGeneration.
    Text weights live under model.language_model, so the causal-LM class
    would not bind them. Vision weights are loaded with the checkpoint and
    are not used: the messages contain no images.
    """
    import torch
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if tuple(int(part) for part in torch.__version__.split("+")[0].split(".")[:2]) < (2, 6):
        raise RuntimeError(
            f"transformers Qwen3.5 loading needs torch>=2.6, found {torch.__version__}"
        )
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map="cuda",
        low_cpu_mem_usage=True,
    )
    model.eval()
    return tokenizer, model


def _decode_new_tokens(tokenizer, sequences, input_len: int) -> tuple[str, str, int]:
    new_ids = sequences[0, input_len:]
    raw_special = tokenizer.decode(new_ids, skip_special_tokens=False)
    raw = tokenizer.decode(new_ids, skip_special_tokens=True)
    return raw, raw_special, int(new_ids.shape[-1])


def generate_label(model, tokenizer, public_record: dict[str, Any]) -> dict[str, Any]:
    """Run one public record. Exceptions become an invalid prediction row."""
    import torch

    messages = build_messages(public_record)
    base = {
        "sample_id": public_record["sample_id"],
        "prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
        "user_prompt_sha256": sha256_text(public_record["prompt"]),
        "enable_thinking": ENABLE_THINKING,
        "do_sample": DO_SAMPLE,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_new_tokens": MAX_NEW_TOKENS,
        "retry_limit": RETRY_LIMIT,
    }
    try:
        encoded = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=ENABLE_THINKING,
        )
        device = next(model.parameters()).device
        encoded = {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in encoded.items()
        }
        input_len = int(encoded["input_ids"].shape[-1])
        started = time.perf_counter()
        with torch.inference_mode():
            sequences = model.generate(
                **encoded,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=DO_SAMPLE,
            )
        latency_ms = (time.perf_counter() - started) * 1000.0
        raw, raw_special, output_tokens = _decode_new_tokens(tokenizer, sequences, input_len)
        parsed = parse_model_output(raw)
        return {
            **base,
            "raw_output": raw,
            "raw_output_with_special_tokens": raw_special,
            "predicted_label": parsed["predicted_label"],
            "explanation": parsed["explanation"],
            "parse_status": parsed["parse_status"],
            "latency_ms": round(latency_ms, 3),
            "input_tokens": input_len,
            "output_tokens": output_tokens,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — one bad sample must not drop the run log
        parsed = parse_model_output("")
        return {
            **base,
            "raw_output": "",
            "raw_output_with_special_tokens": "",
            "predicted_label": parsed["predicted_label"],
            "explanation": None,
            "parse_status": "error",
            "latency_ms": None,
            "input_tokens": None,
            "output_tokens": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def run_inference(
    public_path: str | Path,
    sample_ids: list[str],
    model_path: str,
    output_path: str | Path,
    run_fields: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate predictions for sample_ids and write them before returning.

    Existing output files are left untouched. Callers choose a new path.
    """
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite predictions: {destination}")
    public = index_public(public_path)
    missing = [sample_id for sample_id in sample_ids if sample_id not in public]
    if missing:
        raise ValueError(f"sample ids missing from public file: {missing}")
    tokenizer, model = load_qwen35(model_path)
    rows: list[dict[str, Any]] = []
    total = len(sample_ids)
    try:
        for index, sample_id in enumerate(sample_ids, start=1):
            row = generate_label(model, tokenizer, public[sample_id])
            row.update(run_fields)
            rows.append(row)
            if index == 1 or index % 20 == 0 or index == total:
                write_jsonl(destination, rows)
                print(
                    f"{run_fields.get('model_name', model_path)} "
                    f"{index}/{total} last={row['predicted_label']}",
                    flush=True,
                )
    finally:
        if rows:
            write_jsonl(destination, rows)
        del model
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return rows

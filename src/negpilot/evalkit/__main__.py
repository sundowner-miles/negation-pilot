"""Phase-1 commands: smoke inference and scoring.

Inference reads only the public JSONL. Gold is opened by the smoke and score
commands after predictions have been written, and only to choose ids or score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from negpilot.evalkit.infer import (
    DO_SAMPLE,
    ENABLE_THINKING,
    MAX_NEW_TOKENS,
    RETRY_LIMIT,
    TEMPERATURE,
    TOP_P,
    run_inference,
)
from negpilot.evalkit.io import read_jsonl, write_jsonl
from negpilot.evalkit.parse import parse_model_output
from negpilot.evalkit.plots import write_smoke_chart
from negpilot.evalkit.prompt import PROMPT_VERSION, SYSTEM_PROMPT, sha256_text
from negpilot.evalkit.score import score_predictions, write_confusion_csv, write_metrics
from negpilot.evalkit.smoke import select_smoke_ids

PARSER_CHECKS = (
    "TRUE",
    " FALSE ",
    "UNKNOWN\n",
    "The answer is TRUE",
    "TRUE.",
    "<think>the query is entailed</think>\nTRUE",
    "<think>TRUE</think>",
    "",
    "true",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(root: Path) -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def _gpu_lines() -> list[str]:
    done = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return []
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def environment_snapshot(root: Path, public_path: Path, gold_path: Path) -> dict[str, Any]:
    torch_version = None
    cuda = None
    try:
        import torch

        torch_version = torch.__version__
        cuda = {
            "available": bool(torch.cuda.is_available()),
            "version": torch.version.cuda,
            "bf16": bool(torch.cuda.is_bf16_supported()) if torch.cuda.is_available() else False,
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    except Exception as exc:  # noqa: BLE001
        torch_version = f"unavailable: {type(exc).__name__}: {exc}"
    transformers_version = None
    try:
        import transformers

        transformers_version = transformers.__version__
    except Exception as exc:  # noqa: BLE001
        transformers_version = f"unavailable: {type(exc).__name__}: {exc}"
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch_version,
        "cuda": cuda,
        "transformers": transformers_version,
        "gpu": _gpu_lines(),
        "git_head": _git_head(root),
        "public_sha256": _sha256_file(public_path),
        "gold_sha256": _sha256_file(gold_path),
        "prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
        "decoding": {
            "do_sample": DO_SAMPLE,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": None,
            "max_new_tokens": MAX_NEW_TOKENS,
            "enable_thinking": ENABLE_THINKING,
            "retry_limit": RETRY_LIMIT,
            "note": (
                "Greedy decoding (do_sample=false) is the temperature-0 condition. "
                "generate() does not receive a temperature keyword. top_p and top_k are unused. "
                "This is not the vendor sampling recipe for non-thinking mode."
            ),
        },
    }


def _slug(model_name: str) -> str:
    return model_name.strip("/").replace("/", "-").replace(" ", "-")


def _parse_model(spec: str) -> dict[str, str]:
    parts = spec.split("::")
    if len(parts) != 3 or any(not part for part in parts):
        raise argparse.ArgumentTypeError(
            "model spec must be name::path::revision, "
            f"got {spec!r}"
        )
    name, path, revision = parts
    return {"model_name": name, "model_path": path, "model_revision": revision}


def _write_report(
    path: Path,
    snapshot: dict[str, Any],
    sample_ids: list[str],
    model_reports: list[dict[str, Any]],
    parser_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Phase 1 smoke test",
        "",
        "This file is a pipeline check. The dev-slice counts below are not Experiment 1 scores.",
        "",
        "## Decoding",
        "",
        "```json",
        json.dumps(snapshot["decoding"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Smoke sample ids",
        "",
        "Rule: within dev, sort by sample_id, take the first 2 TRUE, 2 FALSE, and 2 UNKNOWN.",
        "",
        ", ".join(sample_ids),
        "",
        "## Models",
        "",
    ]
    for report in model_reports:
        metrics = report["metrics"]
        lines.extend(
            [
                f"### {report['model_name']}",
                "",
                f"- revision: `{report['model_revision']}`",
                f"- n: {metrics['n']}",
                f"- correct: {metrics['correct']}",
                f"- accuracy: {metrics['accuracy']}",
                f"- macro_f1: {metrics['macro_f1']}",
                f"- invalid_output: {metrics['invalid_output']}",
                "",
            ]
        )
    lines.extend(["## Parser self-check", ""])
    for row in parser_rows:
        lines.append(
            f"- input `{row['input']!s}` -> {row['predicted_label']} ({row['parse_status']})"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def smoke_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negpilot.evalkit smoke")
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", action="append", required=True, type=_parse_model)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--n-per-label", type=int, default=2)
    parser.add_argument("--run-id", default="phase1-smoke")
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    root = Path(__file__).resolve().parents[3]
    snapshot = environment_snapshot(root, args.public, args.gold)
    (output_dir / "environment.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    gold_rows = read_jsonl(args.gold)
    sample_ids = select_smoke_ids(gold_rows, split=args.split, n_per_label=args.n_per_label)
    (output_dir / "sample_ids.json").write_text(
        json.dumps(
            {
                "split": args.split,
                "n_per_label": args.n_per_label,
                "rule": "sample_id ascending, first n_per_label of each gold label",
                "sample_ids": sample_ids,
                "purpose": "pipeline smoke test, not a performance estimate",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    parser_rows = []
    for text in PARSER_CHECKS:
        parsed = parse_model_output(text)
        parser_rows.append({"input": text, **parsed})
    (output_dir / "parser_checks.json").write_text(
        json.dumps(parser_rows, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    chart_rows = []
    model_reports = []
    failures = 0
    for spec in args.model:
        model_dir = output_dir / _slug(spec["model_name"])
        model_dir.mkdir(parents=True, exist_ok=True)
        predictions_path = model_dir / "predictions.jsonl"
        run_fields = {
            "run_id": args.run_id,
            "model_name": spec["model_name"],
            "model_revision": spec["model_revision"],
            "model_path": spec["model_path"],
        }
        try:
            predictions = run_inference(
                args.public,
                sample_ids,
                spec["model_path"],
                predictions_path,
                run_fields,
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            (model_dir / "error.txt").write_text(
                f"{type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
            continue
        metrics = score_predictions(predictions, gold_rows)
        write_metrics(model_dir / "metrics.json", metrics)
        write_confusion_csv(model_dir / "confusion_matrix.csv", metrics["confusion"])
        write_jsonl(model_dir / "aligned.jsonl", metrics["rows"])
        chart_rows.append(
            {
                "model": spec["model_name"].split("/")[-1],
                "n": metrics["n"],
                "correct": metrics["correct"],
                "incorrect": metrics["n"] - metrics["correct"] - metrics["invalid_output"],
                "invalid_output": metrics["invalid_output"],
            }
        )
        model_reports.append({**spec, "metrics": {k: v for k, v in metrics.items() if k != "rows"}})

    if chart_rows:
        write_smoke_chart(output_dir / "smoke_chart.svg", chart_rows)
    (output_dir / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "prompt_version": PROMPT_VERSION,
                "models": args.model,
                "sample_ids": sample_ids,
                "public": str(args.public),
                "gold_used_for": "sample selection and scoring only",
                "decoding": snapshot["decoding"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_report(
        output_dir / "phase1_report.md",
        snapshot,
        sample_ids,
        model_reports,
        parser_rows,
    )
    print(f"wrote {output_dir}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "smoke":
        args = args[1:]
    return smoke_main(args)


if __name__ == "__main__":
    sys.exit(main())

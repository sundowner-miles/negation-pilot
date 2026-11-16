"""Run frozen phase-1 decoding on one public split.

Sample ids come from the public file's split field. This module does not
open the gold file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from negpilot.evalkit.infer import run_inference
from negpilot.evalkit.io import read_jsonl
from negpilot.evalkit.prompt import PROMPT_VERSION, SYSTEM_PROMPT


def public_ids_for_split(public_path: Path, split: str) -> list[str]:
    rows = read_jsonl(public_path)
    ids = [row["sample_id"] for row in rows if row.get("split") == split]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate sample ids in split {split}")
    return sorted(ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negpilot.evalkit.run_split")
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", action="append", required=True)
    args = parser.parse_args(argv)

    sample_ids = public_ids_for_split(args.public, args.split)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (args.output_dir / "sample_ids.json").write_text(
        json.dumps(
            {
                "split": args.split,
                "n": len(sample_ids),
                "order": "sample_id ascending",
                "source": "public split field only",
                "prompt_version": PROMPT_VERSION,
                "sample_ids": sample_ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    failures = 0
    for spec in args.model:
        name, path, revision = spec.split("::")
        slug = name.strip("/").replace("/", "-")
        model_dir = args.output_dir / slug
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            run_inference(
                args.public,
                sample_ids,
                path,
                model_dir / "predictions.jsonl",
                {
                    "run_id": args.run_id,
                    "model_name": name,
                    "model_revision": revision,
                    "model_path": path,
                    "split": args.split,
                },
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            (model_dir / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            print(f"FAILED {name}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

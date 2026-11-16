"""Build model inputs that delete only the studied negation.

The released public and gold files are not modified. A formula the symbol
pack cannot render is recorded as excluded. It is not rewritten into a new
sentence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from negpilot.ast import Formula, FormulaError, ablate_studied, from_dict, sexp
from negpilot.evalkit.io import read_jsonl, write_jsonl
from negpilot.evalkit.prompt import assert_public_record
from negpilot.renderer import build_prompt, render
from negpilot.schema import PUBLIC_FIELDS
from negpilot.semantics import classify

ABLATION_GENERATOR_VERSION = "ablation-plan-6.4-v1"


def try_render_ablation(
    statements: list[Formula],
    query: Formula,
    domain: list[str],
    pack: str = "symbol",
) -> dict[str, Any]:
    """Delete the studied Not and render it, or return an exclusion."""
    rewritten, rewritten_query, site = ablate_studied(statements, query)
    base = {
        "site_role": site["role"],
        "statements_ast": rewritten,
        "query_ast": rewritten_query,
        "ablated_statements": [sexp(item) for item in rewritten],
        "ablated_query": sexp(rewritten_query),
    }
    try:
        texts = [render(item, pack) for item in rewritten]
        query_text = render(rewritten_query, pack)
    except FormulaError as exc:
        return {
            **base,
            "status": "excluded",
            "reason": f"symbol pack has no sentence for the ablated formula: {exc}",
        }
    return {
        **base,
        "status": "rendered",
        "reason": None,
        "statements": texts,
        "query": query_text,
        "prompt": build_prompt(list(domain), texts, query_text),
    }


def prepare_split(gold_rows: list[dict[str, Any]], split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (manifest rows, public rows) for one split.

    Public rows contain only public fields. Z3 labels stay in the manifest.
    """
    selected = [row for row in gold_rows if row.get("split") == split]
    if not selected:
        raise ValueError(f"no gold rows in split {split}")
    manifest: list[dict[str, Any]] = []
    public_rows: list[dict[str, Any]] = []
    for record in selected:
        statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
        query = from_dict(record["query_ast"])
        rendered = try_render_ablation(statements, query, list(record["domain"]))
        decision = classify(
            rendered["statements_ast"],
            rendered["query_ast"],
            record["domain"],
            with_models=False,
        )
        if decision.label == "INCONSISTENT" or not decision.kb_satisfiable:
            raise RuntimeError(f"{record['sample_id']} ablation makes the knowledge base unsatisfiable")
        if decision.label != record.get("label_after_ablation"):
            raise RuntimeError(
                f"{record['sample_id']} Z3 ablation label {decision.label} "
                f"disagrees with stored {record.get('label_after_ablation')}"
            )
        manifest.append(
            {
                "sample_id": record["sample_id"],
                "split": split,
                "status": rendered["status"],
                "reason": rendered["reason"],
                "site_role": rendered["site_role"],
                "label_before": record["label"],
                "label_after": decision.label,
                "negation_critical": record.get("negation_critical"),
                "negation_form": record.get("negation_form"),
                "negation_scope": record.get("negation_scope"),
                "family": record.get("family"),
                "pair_id": record.get("pair_id"),
                "in_controlled_subset": record.get("in_controlled_subset"),
                "ablated_statements": rendered["ablated_statements"],
                "ablated_query": rendered["ablated_query"],
            }
        )
        if rendered["status"] != "rendered":
            continue
        public = {
            "sample_id": record["sample_id"],
            "split": record["split"],
            "domain": record["domain"],
            "knowledge_base": rendered["statements"],
            "query": rendered["query"],
            "prompt": rendered["prompt"],
            "generator_version": ABLATION_GENERATOR_VERSION,
            "seed": record["seed"],
        }
        assert_public_record(public)
        if set(public) != set(PUBLIC_FIELDS):
            raise RuntimeError(f"{record['sample_id']} ablation public fields drifted")
        public_rows.append(public)
    public_rows.sort(key=lambda row: row["sample_id"])
    manifest.sort(key=lambda row: row["sample_id"])
    return manifest, public_rows


def write_ablation_inputs(gold_path: Path, split: str, output_dir: Path) -> dict[str, int]:
    destinations = [
        output_dir / "ablation.public.jsonl",
        output_dir / "manifest.jsonl",
        output_dir / "sample_ids.json",
    ]
    existing = [path for path in destinations if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite ablation inputs: {existing}")
    manifest, public_rows = prepare_split(read_jsonl(gold_path), split)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "manifest.jsonl", manifest)
    write_jsonl(output_dir / "ablation.public.jsonl", public_rows)
    sample_ids = [row["sample_id"] for row in public_rows]
    (output_dir / "sample_ids.json").write_text(
        json.dumps(
            {
                "split": split,
                "n_rendered": len(sample_ids),
                "n_manifest": len(manifest),
                "order": "sample_id ascending",
                "generator_version": ABLATION_GENERATOR_VERSION,
                "sample_ids": sample_ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    excluded = sum(1 for row in manifest if row["status"] == "excluded")
    return {"rendered": len(public_rows), "excluded": excluded, "manifest": len(manifest)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negpilot.evalkit.ablation_inputs")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    counts = write_ablation_inputs(args.gold, args.split, args.output_dir)
    print(
        f"rendered {counts['rendered']} excluded {counts['excluded']} "
        f"manifest {counts['manifest']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

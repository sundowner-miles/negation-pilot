"""Command line for generation, validation, and statistics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from negpilot.generator import (
    generate_records,
    load_config,
    project_root,
    resolve_path,
    to_public,
    write_jsonl,
)
from negpilot.pair_audit import comparison_rows
from negpilot.statistics import write_reports
from negpilot.validator import load_jsonl, validate_public, validate_records


def _cmd_generate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    records = generate_records(config)
    errors = validate_records(records, config, recompute_logic=False)
    if errors:
        print("\n".join(errors[:20]), file=sys.stderr)
        print(f"generation rejected: {len(errors)} structural errors", file=sys.stderr)
        return 1
    public_path = resolve_path(args.config, config["output"]["public"])
    gold_path = resolve_path(args.config, config["output"]["gold"])
    write_jsonl(gold_path, records)
    write_jsonl(public_path, [to_public(record) for record in records])
    comparison_path = project_root(args.config) / "reports" / "pair_comparison.jsonl"
    write_jsonl(comparison_path, comparison_rows(records))
    print(f"wrote {len(records)} gold records to {gold_path}")
    print(f"wrote {len(records)} public records to {public_path}")
    print(f"wrote {comparison_path}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    records = load_jsonl(args.input)
    config = load_config(args.config) if args.config else None
    errors = validate_records(records, config, recompute_logic=True)
    public_errors: list[str] = []
    if config and config.get("output", {}).get("public"):
        public_path = resolve_path(args.config, config["output"]["public"])
        if public_path.exists():
            public_errors = validate_public(load_jsonl(public_path), records)
    if errors or public_errors:
        print("\n".join((errors + public_errors)[:30]), file=sys.stderr)
        print(
            f"validation failed: {len(errors)} gold errors, {len(public_errors)} public errors",
            file=sys.stderr,
        )
        return 1
    print(f"validated {len(records)} records")
    print("z3 verification success rate: 1.000")
    return 0


def _cmd_statistics(args: argparse.Namespace) -> int:
    records = load_jsonl(args.input)
    config = load_config(args.config) if args.config else None
    if args.config:
        root = project_root(args.config)
    else:
        root = Path(args.input).resolve().parents[2]
    public_rows = None
    if config and config.get("output", {}).get("public"):
        public_path = resolve_path(args.config, config["output"]["public"])
        if public_path.exists():
            public_rows = load_jsonl(public_path)
    try:
        distribution = write_reports(
            records,
            config,
            root,
            public_rows=public_rows,
            recompute_logic=True,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "examples={examples} pairs={unique_pairs} "
        "TRUE={t} FALSE={f} UNKNOWN={u} z3_success={rate:.3f}".format(
            examples=distribution["examples"],
            unique_pairs=distribution["unique_pairs"],
            t=distribution["labels"].get("TRUE", 0),
            f=distribution["labels"].get("FALSE", 0),
            u=distribution["labels"].get("UNKNOWN", 0),
            rate=distribution["z3_verification_success_rate"],
        )
    )
    print(f"wrote {root / 'reports' / 'distribution.json'}")
    print(f"wrote {root / 'reports' / 'pilot_report.md'}")
    print(f"wrote {root / 'reports' / 'pair_comparison.jsonl'}")
    control = distribution.get("pair_control") or {}
    print(
        "controlled_pairs={controlled} exploratory_pairs={exploratory}".format(
            controlled=control.get("controlled_pairs", 0),
            exploratory=control.get("exploratory_pairs", 0),
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="negpilot")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate the pilot JSONL files")
    generate.add_argument("--config", required=True)
    generate.set_defaults(func=_cmd_generate)

    validate = sub.add_parser("validate", help="audit a gold JSONL file")
    validate.add_argument("--input", required=True)
    validate.add_argument("--config", required=False)
    validate.set_defaults(func=_cmd_validate)

    stats = sub.add_parser("statistics", help="recompute the distribution report")
    stats.add_argument("--input", required=True)
    stats.add_argument("--config", required=False)
    stats.set_defaults(func=_cmd_statistics)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

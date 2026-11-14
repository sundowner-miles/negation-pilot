"""Deterministic dataset construction."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from negpilot import __version__
from negpilot.ast import (
    And,
    Atom,
    Exists,
    ForAll,
    Formula,
    Implies,
    Not,
    Or,
    ablate_studied,
    count_nots,
    infer_position_and_scope,
    sexp,
    statement_role,
    studied_occurrence,
    to_dict,
)
from negpilot.pair_audit import criticality_result, stamp_pair
from negpilot.renderer import build_prompt, negation_cue_count, render
from negpilot.semantics import classify, solver_version
from negpilot.split import assign_skeleton_splits
from negpilot.templates import BUILDERS, ConstraintError, make_symbols


class GenerationError(RuntimeError):
    """A sample failed verification and was rejected instead of relabeled."""


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConstraintError("config must be a mapping")
    return data


def project_root(config_path: str | Path) -> Path:
    parent = Path(config_path).resolve().parent
    if parent.name == "configs":
        return parent.parent
    return Path.cwd()


def resolve_path(config_path: str | Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return project_root(config_path) / path


def expand_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for family in config["families"]:
        if family["builder"] not in BUILDERS:
            raise ConstraintError(f"unknown builder {family['builder']}")
        local_index = 0
        for instance in family["instances"]:
            count = int(instance["count"])
            if count < 0:
                raise ConstraintError("instance count cannot be negative")
            for _ in range(count):
                job = {
                    "id": family["id"],
                    "builder": family["builder"],
                    "pair_type": family["pair_type"],
                    "kind": family["kind"],
                    "local_index": local_index,
                }
                job.update(instance)
                jobs.append(job)
                local_index += 1
    return jobs


def stratum_of(job: dict[str, Any]) -> str:
    if "depth" in job:
        depth = job["depth"]
        return f"{job['id']}|{depth}|{depth}"
    return f"{job['id']}|{job['depth_true']}|{job['depth_false']}"


def binary_label(label: str) -> int | None:
    if label == "TRUE":
        return 1
    if label == "FALSE":
        return 0
    if label == "UNKNOWN":
        return None
    raise GenerationError(f"unexpected label {label}")


def _check_trace(member_label: str, trace: dict[str, Any], depth: int | None) -> None:
    if member_label in {"TRUE", "FALSE"}:
        if trace["proof_hops"] != depth:
            raise GenerationError(
                f"proof_hops {trace['proof_hops']} does not match reasoning depth {depth}"
            )
    elif member_label == "UNKNOWN":
        if depth is not None or trace["proof_hops"] != 0:
            raise GenerationError(
                "UNKNOWN examples have no canonical proof, so reasoning_depth is null and proof_hops is 0"
            )
    else:
        raise GenerationError(member_label)


def _rename(node: Formula, pred_map: dict[str, str], ind_map: dict[str, str]) -> Formula:
    def pred(name: str) -> str:
        pred_map.setdefault(name, f"P{len(pred_map)}")
        return pred_map[name]

    def ind(name: str) -> str:
        if name in {"x", "y", "z"}:
            return name
        ind_map.setdefault(name, f"c{len(ind_map)}")
        return ind_map[name]

    if isinstance(node, Atom):
        return Atom(pred(node.pred), tuple(ind(arg) for arg in node.args))
    if isinstance(node, Not):
        return Not(_rename(node.formula, pred_map, ind_map))
    if isinstance(node, And):
        return And(_rename(node.left, pred_map, ind_map), _rename(node.right, pred_map, ind_map))
    if isinstance(node, Or):
        return Or(_rename(node.left, pred_map, ind_map), _rename(node.right, pred_map, ind_map))
    if isinstance(node, Implies):
        return Implies(_rename(node.left, pred_map, ind_map), _rename(node.right, pred_map, ind_map))
    if isinstance(node, ForAll):
        return ForAll(node.var, _rename(node.body, pred_map, ind_map))
    if isinstance(node, Exists):
        return Exists(node.var, _rename(node.body, pred_map, ind_map))
    raise GenerationError(f"cannot normalize {type(node).__name__}")


def _skeleton(statements: list[Formula], query: Formula) -> str:
    pred_map: dict[str, str] = {}
    ind_map: dict[str, str] = {}
    parts = [sexp(_rename(item, pred_map, ind_map)) for item in statements]
    parts.append(sexp(_rename(query, pred_map, ind_map)))
    return " ;; ".join(parts)


def build_drafts(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Build logical drafts and assign splits. Does not call Z3."""
    if config.get("generator_version") != __version__:
        raise ConstraintError(
            f"config generator_version {config.get('generator_version')} "
            f"does not match package {__version__}"
        )
    jobs = expand_jobs(config)
    ids = [f"base-{index:04d}" for index in range(len(jobs))]
    domain_sizes = {int(value) for value in config["domain_size_by_split"].values()}
    packs = set(config["nl_pack_by_split"].values())
    if domain_sizes != {3} or packs != {"symbol"}:
        raise ConstraintError(
            "Pure-symbol skeletons are split only by logical structure. "
            "Every split uses domain size 3 and the symbol template pack."
        )
    built: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        symbols = make_symbols(index, 3, int(config["seed"]))
        pair = BUILDERS[job["builder"]](index, job, symbols)
        if len(pair.members) != 2:
            raise GenerationError(f"{job['id']} did not return exactly two members")
        if list(symbols.domain) != pair.domain:
            raise GenerationError("builder domain does not match the symbol domain")
        members = []
        for side, member in zip(("a", "b"), pair.members):
            position, scope, form = infer_position_and_scope(member.statements, member.query)
            if position != member.negation_position or scope != member.negation_scope:
                raise GenerationError(
                    f"{member.template_id} declared {member.negation_position}/{member.negation_scope} "
                    f"but the AST is {position}/{scope}: "
                    + " ; ".join(sexp(item) for item in member.statements)
                    + f" query {sexp(member.query)}"
                )
            total_nots = sum(count_nots(item) for item in member.statements) + count_nots(member.query)
            if total_nots not in {1, 2}:
                raise GenerationError(f"{member.template_id} has {total_nots} negations")
            studied_occurrence(member.statements, member.query)
            depth = None if member.expected_label == "UNKNOWN" else member.reasoning_depth
            _check_trace(member.expected_label, member.proof_trace, depth)
            for formula in member.statements:
                if statement_role(formula) not in {"fact", "rule"}:
                    raise GenerationError("bad role")
            members.append(
                {
                    "side": side,
                    "expected_label": member.expected_label,
                    "statements": member.statements,
                    "query": member.query,
                    "negation_position": position,
                    "negation_scope": scope,
                    "negation_form": form,
                    "reasoning_depth": depth,
                    "proof_trace": member.proof_trace,
                    "template_id": member.template_id,
                    "skeleton": _skeleton(member.statements, member.query),
                }
            )
        built.append(
            {
                "base_index": index,
                "base_case_id": ids[index],
                "pair_id": f"pair-{index:04d}",
                "nl_pack": "symbol",
                "family": pair.family,
                "pair_type": pair.pair_type,
                "pair_note": pair.pair_note,
                "controlled_variables": list(pair.controlled_variables),
                "manipulated_variables": list(pair.manipulated_variables),
                "derived_variables": list(pair.derived_variables),
                "studies_inference_type": pair.studies_inference_type,
                "experimental_category": pair.experimental_category,
                "contrast": pair.contrast or pair.family,
                "label_balance_group": pair.label_balance_group,
                "kind": job["kind"],
                "domain": pair.domain,
                "symbol_mapping": {
                    "predicates": list(symbols.predicates),
                    "domain": list(pair.domain),
                },
                "members": members,
                "skeleton": members[0]["skeleton"] + " ## " + members[1]["skeleton"],
            }
        )
    parent = list(range(len(built)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    seen_skeleton: dict[str, int] = {}
    for index, item in enumerate(built):
        for member in item["members"]:
            earlier = seen_skeleton.get(member["skeleton"])
            if earlier is None:
                seen_skeleton[member["skeleton"]] = index
            else:
                union(index, earlier)
    mapping = assign_skeleton_splits(
        ids,
        [str(find(index)) for index in range(len(built))],
        int(config["seed"]),
        config["split"],
    )
    for item in built:
        item["split"] = mapping[item["base_case_id"]]
    return built


def summarize_plan(drafts: list[dict[str, Any]]) -> dict[str, Any]:
    labels: Counter[str] = Counter()
    positions: Counter[str] = Counter()
    scopes: Counter[str] = Counter()
    depths: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    for draft in drafts:
        kinds[draft["kind"]] += 1
        splits[draft["split"]] += 1
        for member in draft["members"]:
            labels[member["expected_label"]] += 1
            positions[member["negation_position"]] += 1
            scopes[member["negation_scope"]] += 1
            depth_key = member["reasoning_depth"]
            depths["null" if depth_key is None else str(depth_key)] += 1
    return {
        "examples": sum(len(item["members"]) for item in drafts),
        "base_cases": len(drafts),
        "pairs": len(drafts),
        "determinate_pairs": kinds["determinate"],
        "unknown_pairs": kinds["unknown"],
        "labels": dict(labels),
        "positions": dict(positions),
        "scopes": dict(scopes),
        "depths": dict(sorted(depths.items(), key=lambda item: (item[0] == "null", item[0]))),
        "splits_base_cases": dict(splits),
    }


def _expect_map(actual: dict[str, Any], expected: dict[str, Any], prefix: str, errors: list[str]) -> None:
    for key, value in expected.items():
        got = actual.get(str(key), actual.get(key))
        if isinstance(value, dict):
            if not isinstance(got, dict):
                errors.append(f"{prefix}.{key} missing")
                continue
            _expect_map(got, value, f"{prefix}.{key}", errors)
        elif got != value:
            errors.append(f"{prefix}.{key}: expected {value}, got {got}")


def _normalize_expected(expected: dict[str, Any]) -> dict[str, Any]:
    data = dict(expected)
    if isinstance(data.get("depths"), dict):
        data["depths"] = {str(key): value for key, value in data["depths"].items()}
    return data


def check_plan(drafts: list[dict[str, Any]], config: dict[str, Any]) -> None:
    expected = config.get("expected_totals")
    if not expected:
        return
    expected = _normalize_expected(expected)
    actual = summarize_plan(drafts)
    errors: list[str] = []
    comparable = {
        "examples": actual["examples"],
        "base_cases": actual["base_cases"],
        "pairs": actual["pairs"],
        "determinate_pairs": actual["determinate_pairs"],
        "unknown_pairs": actual["unknown_pairs"],
        "labels": actual["labels"],
        "positions": actual["positions"],
        "scopes": actual["scopes"],
        "depths": actual["depths"],
        "splits_base_cases": actual["splits_base_cases"],
    }
    _expect_map(comparable, expected, "plan", errors)
    if errors:
        rendered = json.dumps(actual, indent=2, sort_keys=True)
        raise ConstraintError(
            "The template plan does not meet the configured quotas. "
            "No examples were duplicated or relabeled.\n"
            + "\n".join(errors)
            + "\nActual plan:\n"
            + rendered
        )


def _render_member(statements: list[Any], query: Any, pack: str) -> tuple[list[str], str]:
    texts = [render(item, pack) for item in statements]
    query_text = render(query, pack)
    return texts, query_text


def verify_drafts(drafts: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Run Z3, render language, and reject anything that does not match."""
    seed = int(config["seed"])
    version = solver_version()
    records: list[dict[str, Any]] = []
    total = sum(len(item["members"]) for item in drafts)
    done = 0
    for draft in drafts:
        pair_records: list[dict[str, Any]] = []
        for member in draft["members"]:
            done += 1
            if done == 1 or done % 100 == 0 or done == total:
                print(f"verifying {done}/{total}", flush=True)
            statements = member["statements"]
            query = member["query"]
            decision = classify(statements, query, draft["domain"], with_models=True)
            if decision.label == "INCONSISTENT":
                raise GenerationError(
                    f"{draft['base_case_id']} {member['template_id']} has an unsatisfiable knowledge base. "
                    "It was rejected rather than relabeled.\n"
                    + " ; ".join(sexp(item) for item in statements)
                )
            if decision.label != member["expected_label"]:
                raise GenerationError(
                    f"{draft['base_case_id']} {member['template_id']} expected {member['expected_label']} "
                    f"but Z3 returned {decision.label}. The sample was rejected rather than relabeled.\n"
                    + " ; ".join(sexp(item) for item in statements)
                    + f"\nquery {sexp(query)}"
                )
            mutated_statements, mutated_query, site = ablate_studied(statements, query)
            mutated = classify(mutated_statements, mutated_query, draft["domain"], with_models=False)
            critical, criticality_verification = criticality_result(
                decision.label, mutated.label, mutated.kb_satisfiable
            )
            kb_negation_count = sum(count_nots(item) for item in statements)
            query_negation_count = count_nots(query)
            query_polarity = "NEGATIVE" if query_negation_count else "POSITIVE"
            texts, query_text = _render_member(statements, query, draft["nl_pack"])
            for text in texts + [query_text]:
                if " not not " in f" {text.lower()} ":
                    raise GenerationError(f"double negation cue in {text}")
            cue_total = sum(negation_cue_count(text) for text in texts + [query_text])
            if cue_total != kb_negation_count + query_negation_count:
                raise GenerationError(
                    f"expected {kb_negation_count + query_negation_count} 'not' cues, "
                    f"found {cue_total} for {member['template_id']}"
                )
            trace = dict(member["proof_trace"])
            trace["models"] = decision.models
            trace["negation_critical"] = critical
            trace["label_after_deleting_not"] = mutated.label
            trace["criticality_verification"] = criticality_verification
            trace["ablation_kb_satisfiable"] = mutated.kb_satisfiable
            if criticality_verification == "invalid":
                trace["criticality_note"] = (
                    "Deleting the studied negation makes the knowledge base unsatisfiable. "
                    "Criticality is not assigned."
                )
            elif critical:
                trace["criticality_note"] = (
                    f"Deleting the studied negation changes the label from {decision.label} "
                    f"to {mutated.label}."
                )
            else:
                trace["criticality_note"] = (
                    f"Deleting the studied negation leaves the label {decision.label}."
                )
            structured = []
            for statement_index, (formula, text) in enumerate(zip(statements, texts)):
                structured.append(
                    {
                        "statement_id": f"s{statement_index}",
                        "role": statement_role(formula),
                        "ast": to_dict(formula),
                        "text": text,
                    }
                )
            prompt = build_prompt(draft["domain"], texts, query_text)
            record = {
                "sample_id": f"ex-{draft['base_index']:04d}{member['side']}",
                "base_case_id": draft["base_case_id"],
                "pair_id": draft["pair_id"],
                "pair_type": draft["pair_type"],
                "pair_note": draft["pair_note"],
                "family": draft["family"],
                "template_id": member["template_id"],
                "negation_form": member["negation_form"],
                "negation_critical": critical,
                "criticality_verification": criticality_verification,
                "negation_occurrence_id": "neg-query" if site["index"] is None else f"neg-s{site['index']}",
                "label_before_ablation": decision.label,
                "label_after_ablation": None if criticality_verification == "invalid" else mutated.label,
                "ablation_kb_satisfiable": mutated.kb_satisfiable,
                "symbol_mapping": draft["symbol_mapping"],
                "predicate_symbols": list(draft["symbol_mapping"]["predicates"]),
                "skeleton_id": member["skeleton"],
                "nl_pack": draft["nl_pack"],
                "split": draft["split"],
                "domain": list(draft["domain"]),
                "knowledge_base": {"domain": list(draft["domain"]), "statements": structured},
                "query": query_text,
                "query_ast": to_dict(query),
                "label": decision.label,
                "binary_label": binary_label(decision.label),
                "negation_position": member["negation_position"],
                "negation_scope": member["negation_scope"],
                "negation_cue": "not",
                "negation_count": kb_negation_count + query_negation_count,
                "kb_negation_count": kb_negation_count,
                "query_negation_count": query_negation_count,
                "query_polarity": query_polarity,
                "reasoning_depth": member["reasoning_depth"],
                "proof_trace": trace,
                "verification_status": "pass",
                "solver": "z3",
                "verification": {
                    "kb_satisfiable": decision.kb_satisfiable,
                    "kb_and_query": decision.kb_and_query,
                    "kb_and_not_query": decision.kb_and_not_query,
                    "computed_label": decision.label,
                    "matches_expected": True,
                    "label_after_deleting_not": mutated.label,
                    "z3_version": version,
                },
                "prompt": prompt,
                "generator_version": config["generator_version"],
                "seed": seed,
            }
            pair_records.append(record)
        polarities = {item["query_polarity"] for item in pair_records}
        balance_group = draft["label_balance_group"]
        if not balance_group:
            balance_group = (
                f"{next(iter(polarities))}_QUERY" if len(polarities) == 1 else "MIXED_QUERY"
            )
        records.extend(
            stamp_pair(
                pair_records,
                draft["controlled_variables"],
                draft["manipulated_variables"],
                draft["derived_variables"],
                draft["studies_inference_type"],
                draft["experimental_category"],
                draft["contrast"],
                balance_group,
            )
        )
    return records


def to_public(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": record["sample_id"],
        "split": record["split"],
        "domain": record["domain"],
        "knowledge_base": [item["text"] for item in record["knowledge_base"]["statements"]],
        "query": record["query"],
        "prompt": record["prompt"],
        "generator_version": record["generator_version"],
        "seed": record["seed"],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def generate_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    drafts = build_drafts(config)
    check_plan(drafts, config)
    return verify_drafts(drafts, config)

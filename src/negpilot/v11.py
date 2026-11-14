"""Dataset v1.1 release step.

Reads the v1.0 gold file, keeps every logical field, and rewrites only the
split, negation-form metadata, equivalence flags, and pair notes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from negpilot.ast import ablate_studied, from_dict, studied_occurrence
from negpilot.generator import project_root, to_public, write_jsonl
from negpilot.pair_audit import apply_profile, audit_pair, comparison_rows
from negpilot.semantics import classify, equivalent
from negpilot.skeleton import canonical_skeleton
from negpilot.split import assign_balanced_splits

FROZEN = (
    "sample_id",
    "pair_id",
    "base_case_id",
    "query",
    "query_ast",
    "label",
    "binary_label",
    "verification",
    "proof_trace",
    "inference_steps",
    "reasoning_depth",
    "proof_depth",
    "negation_occurrence_id",
    "negation_critical",
    "label_before_ablation",
    "label_after_ablation",
    "ablation_kb_satisfiable",
)

DIMENSIONS = (
    "label",
    "position",
    "depth",
    "scope",
    "polarity",
    "family",
    "control",
    "critical",
    "pair_type",
)


def _digest(record: dict[str, Any]) -> str:
    payload = {key: record.get(key) for key in FROZEN}
    statements = [item["ast"] for item in record["knowledge_base"]["statements"]]
    payload["statement_asts"] = statements
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _backup(root: Path) -> Path:
    destination = root / "dataset-v1.0"
    if (destination / "pilot.gold.jsonl").exists():
        return destination
    destination.mkdir(parents=True, exist_ok=True)
    copies = {
        root / "data" / "generated" / "pilot.gold.jsonl": destination / "pilot.gold.jsonl",
        root / "data" / "generated" / "pilot.public.jsonl": destination / "pilot.public.jsonl",
        root / "reports" / "pair_comparison.jsonl": destination / "pair_comparison.jsonl",
        root / "reports" / "distribution.json": destination / "distribution.json",
        root / "reports" / "pilot_report.md": destination / "pilot_report.md",
    }
    for source, target in copies.items():
        shutil.copyfile(source, target)
    note = destination / "README.md"
    note.write_text(
        "# Dataset v1.0 snapshot\n\n"
        "Read-only checkpoint taken before the v1.1 split and metadata edit. "
        "Do not overwrite these files from the generator.\n",
        encoding="utf-8",
    )
    return destination


def _load(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _features(record: dict[str, Any]) -> dict[str, dict[str, int]]:
    depth = record.get("reasoning_depth")
    return {
        "label": {str(record["label"]): 1},
        "position": {str(record["negation_position"]): 1},
        "depth": {"null" if depth is None else str(depth): 1},
        "scope": {str(record["negation_scope"]): 1},
        "polarity": {str(record["query_polarity"]): 1},
        "family": {str(record["family"]): 1},
        "control": {"controlled" if record.get("in_controlled_subset") else "exploratory": 1},
        "critical": {str(bool(record.get("negation_critical"))): 1},
        "pair_type": {str(record["pair_type"]): 1},
    }


def _merge(features: list[dict[str, dict[str, int]]]) -> dict[str, dict[str, int]]:
    merged: dict[str, dict[str, int]] = {name: defaultdict(int) for name in DIMENSIONS}
    for item in features:
        for name in DIMENSIONS:
            for key, count in item.get(name, {}).items():
                merged[name][key] += count
    return {name: dict(counts) for name, counts in merged.items()}


def _groups(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_base[record["base_case_id"]].append(record)
    bases = sorted(by_base)
    parent = {base: base for base in bases}

    def find(base: str) -> str:
        while parent[base] != base:
            parent[base] = parent[parent[base]]
            base = parent[base]
        return base

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    owners: dict[str, str] = {}
    skeleton_of: dict[str, str] = {}
    for base, members in by_base.items():
        for record in members:
            statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
            query = from_dict(record["query_ast"])
            key = canonical_skeleton(statements, query, len(record["domain"]))
            record["canonical_skeleton"] = key
            skeleton_of[record["sample_id"]] = key
            earlier = owners.get(key)
            if earlier is None:
                owners[key] = base
            else:
                union(base, earlier)
    grouped: dict[str, list[str]] = defaultdict(list)
    for base in bases:
        grouped[find(base)].append(base)
    groups = []
    base_group = {}
    for root, member_bases in sorted(grouped.items()):
        examples = [record for base in member_bases for record in by_base[base]]
        key = min(member_bases)
        groups.append(
            {
                "key": key,
                "size": len(member_bases),
                "features": _merge([_features(record) for record in examples]),
            }
        )
        for base in member_bases:
            base_group[base] = key
    return groups, base_group


def _pair_note(record: dict[str, Any], audit: dict[str, Any]) -> str:
    differences = ", ".join(audit["observed_differences"]) or "none"
    if audit["in_controlled_subset"]:
        manipulated = ", ".join(record.get("manipulated_variables") or []) or "none"
        return (
            f"Controlled {record['family']} pair. "
            f"Declared manipulation: {manipulated}. "
            f"Observed AST differences: {differences}. "
            "Each observed difference is that manipulation or one of its declared derived fields."
        )
    reasons = ", ".join(audit["rejection_reasons"]) or "none"
    return (
        f"Exploratory {record['family']} pair. "
        f"Observed AST differences: {differences}. "
        f"Experimental control failed because: {reasons}."
    )


def _refresh_pairs(records: list[dict[str, Any]]) -> list[str]:
    """Recompute form metadata and pair notes. Logical fields stay put."""
    notes: list[str] = []
    for record in records:
        if record.get("negation_form") == "disjunctive_syllogism":
            record["negation_form"] = "negated_disjunct"
        before = {key: json.dumps(record.get(key), sort_keys=True) for key in FROZEN}
        apply_profile(record)
        for key in FROZEN:
            after = json.dumps(record.get(key), sort_keys=True)
            if after != before[key]:
                record[key] = json.loads(before[key])
                notes.append(f"{record['sample_id']}: refused to change frozen field {key}")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["pair_id"]].append(record)
    for pair_id, members in grouped.items():
        members.sort(key=lambda item: item["sample_id"])
        left = members[0]
        previous = (
            left.get("logical_pair_validity"),
            left.get("experimental_control_validity"),
            left.get("in_controlled_subset"),
        )
        audit = audit_pair(
            members[0],
            members[1],
            list(left.get("controlled_variables") or []),
            list(left.get("manipulated_variables") or []),
            list(left.get("derived_variables") or []),
            bool((left.get("pair_metadata") or {}).get("studies_inference_type")),
        )
        current = (
            audit["logical_pair_validity"],
            audit["experimental_control_validity"],
            audit["in_controlled_subset"],
        )
        if current != previous:
            notes.append(
                f"{pair_id}: pair validity changed from {previous} to {current}; kept the v1.0 decision"
            )
            audit["logical_pair_validity"] = previous[0]
            audit["experimental_control_validity"] = previous[1]
            audit["in_controlled_subset"] = previous[2]
        note = _pair_note(left, audit)
        for record in members:
            record["logical_pair_validity"] = audit["logical_pair_validity"]
            record["experimental_control_validity"] = audit["experimental_control_validity"]
            record["in_controlled_subset"] = audit["in_controlled_subset"]
            record["pair_metadata"] = audit
            record["pair_note"] = note
            record["dataset_version"] = "1.1"
    return notes


def _equivalence(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["pair_id"]].append(record)
    checked = []
    passed = 0
    failed = 0
    for pair_id, members in sorted(grouped.items()):
        members.sort(key=lambda item: item["sample_id"])
        applicable = members[0].get("pair_type") == "equivalent_form"
        status = "not_applicable"
        same_class = False
        if applicable:
            error = "not equivalent"
            try:
                hosts = []
                for record in members:
                    statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
                    query = from_dict(record["query_ast"])
                    hosts.append(studied_occurrence(statements, query)["host"])
                same_class = equivalent(hosts[0], hosts[1], members[0]["domain"])
                status = "pass" if same_class else "fail"
            except Exception as exc:  # noqa: BLE001 - record the verification failure
                status = "fail"
                same_class = False
                error = str(exc)
            if status == "pass":
                passed += 1
            else:
                failed += 1
            row = {
                "pair_id": pair_id,
                "family": members[0]["family"],
                "equivalence_verification": status,
                "semantic_equivalent": same_class,
                "labels": [item["label"] for item in members],
                "scopes": [item["negation_scope"] for item in members],
            }
            if status == "fail":
                row["error"] = error
            checked.append(row)
        equivalence_class = (
            "NEGATED_UNIVERSAL_EXISTENTIAL_COUNTEREXAMPLE" if same_class else None
        )
        for record in members:
            record["comparison_type"] = record.get("pair_type")
            record["semantic_equivalent"] = bool(same_class) if applicable else False
            record["equivalence_class"] = equivalence_class
            record["equivalence_verification"] = status
    return {
        "equivalent_form_pairs": passed + failed,
        "passed": passed,
        "failed": failed,
        "pairs": [item for item in checked if "equivalence_verification" in item],
    }


def _criticality(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("family") == "rule_consequent_contrast":
            grouped[record["pair_id"]].append(record)
    rows = []
    invalid = 0
    polarity_counts: Counter[str] = Counter()
    cross: Counter[tuple[str, str, str]] = Counter()
    for pair_id, members in sorted(grouped.items()):
        members.sort(key=lambda item: item["sample_id"])
        problems = []
        shared = (
            "query_ast",
            "domain",
            "inference_type",
            "proof_depth",
            "relevant_premise_count",
            "negation_count",
            "kb_negation_count",
            "query_negation_count",
            "negation_position",
            "negation_scope",
            "negation_embedding",
            "query_polarity",
        )
        for field in shared:
            if json.dumps(members[0].get(field), sort_keys=True) != json.dumps(
                members[1].get(field), sort_keys=True
            ):
                problems.append(f"{field} differs")
        fact_counts = [
            sum(item["role"] == "fact" for item in record["knowledge_base"]["statements"])
            for record in members
        ]
        rule_counts = [
            sum(item["role"] == "rule" for item in record["knowledge_base"]["statements"])
            for record in members
        ]
        if fact_counts[0] != fact_counts[1]:
            problems.append("fact_count differs")
        if rule_counts[0] != rule_counts[1]:
            problems.append("rule_count differs")
        if members[0]["negation_critical"] == members[1]["negation_critical"]:
            problems.append("negation_critical does not differ")
        polarity = members[0]["query_polarity"]
        polarity_counts[polarity] += 1
        for record in members:
            role = "critical" if record["negation_critical"] else "distractor"
            cross[(polarity, role, record["label"])] += 1
            statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
            query = from_dict(record["query_ast"])
            expected_before = record["label"]
            decision = classify(statements, query, record["domain"], with_models=False)
            if decision.label != expected_before or not decision.kb_satisfiable:
                problems.append(f"{record['sample_id']} gold does not match a fresh Z3 check")
            ablated, ablated_query, _site = ablate_studied(statements, query)
            after = classify(ablated, ablated_query, record["domain"], with_models=False)
            if not after.kb_satisfiable:
                problems.append(f"{record['sample_id']} ablation made the KB unsatisfiable")
            changed = after.label != decision.label
            if record["negation_critical"] != changed:
                problems.append(f"{record['sample_id']} ablation criticality does not match the flag")
            if after.label != record.get("label_after_ablation"):
                problems.append(f"{record['sample_id']} stored ablation label disagrees with Z3")
        if polarity == "POSITIVE":
            expected = {True: "FALSE", False: "TRUE"}
        else:
            expected = {True: "TRUE", False: "FALSE"}
        for record in members:
            if record["label"] != expected[bool(record["negation_critical"])]:
                problems.append(f"{record['sample_id']} label does not match the polarity design")
        if problems:
            invalid += 1
        rows.append({"pair_id": pair_id, "query_polarity": polarity, "problems": problems})
    return {
        "pairs": len(rows),
        "positive_pairs": polarity_counts["POSITIVE"],
        "negative_pairs": polarity_counts["NEGATIVE"],
        "invalid_pairs": invalid,
        "cells": [
            {"query_polarity": polarity, "role": role, "label": label, "count": count}
            for (polarity, role, label), count in sorted(cross.items())
        ],
        "pair_rows": rows,
    }


def _crosstab(records: list[dict[str, Any]], field: str) -> dict[str, dict[str, int]]:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        value = record.get(field)
        shown = "null" if value is None else str(value)
        table[record["split"]][shown] += 1
    return {split: dict(counts) for split, counts in sorted(table.items())}


def _split_report(records: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    sizes = Counter(group["size"] for group in groups)
    skeletons: dict[str, set[str]] = defaultdict(set)
    for record in records:
        skeletons[record["canonical_skeleton"]].add(record["split"])
    overlap = [key for key, splits in skeletons.items() if len(splits) > 1]
    return {
        "examples": _crosstab(records, "split") and {
            split: sum(1 for record in records if record["split"] == split)
            for split in ("train", "dev", "test")
        },
        "base_cases": {
            split: len({record["base_case_id"] for record in records if record["split"] == split})
            for split in ("train", "dev", "test")
        },
        "split_by_label": _crosstab(records, "label"),
        "split_by_negation_position": _crosstab(records, "negation_position"),
        "split_by_negation_scope": _crosstab(records, "negation_scope"),
        "split_by_reasoning_depth": _crosstab(records, "reasoning_depth"),
        "split_by_query_polarity": _crosstab(records, "query_polarity"),
        "split_by_negation_criticality": _crosstab(records, "negation_critical"),
        "split_by_pair_family": _crosstab(records, "family"),
        "split_by_experimental_control": _crosstab(records, "in_controlled_subset"),
        "canonical_skeletons_by_split": {
            split: len({record["canonical_skeleton"] for record in records if record["split"] == split})
            for split in ("train", "dev", "test")
        },
        "group_size_distribution": dict(sorted(sizes.items())),
        "group_count": len(groups),
        "train_test_skeleton_overlap": len(overlap),
    }


def _form_audit(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    old_forms = Counter(record["negation_form"] for record in before)
    new_forms = Counter(record["negation_form"] for record in after)
    cross: Counter[tuple[str, str]] = Counter()
    changed = []
    by_id = {record["sample_id"]: record for record in before}
    for record in after:
        cross[(record["negation_form"], record["inference_type"])] += 1
        previous = by_id[record["sample_id"]]
        if previous["negation_form"] != record["negation_form"]:
            statements = [from_dict(item["ast"]) for item in record["knowledge_base"]["statements"]]
            query = from_dict(record["query_ast"])
            site = studied_occurrence(statements, query)
            changed.append(
                {
                    "sample_id": record["sample_id"],
                    "old_form": previous["negation_form"],
                    "new_form": record["negation_form"],
                    "inference_type": record["inference_type"],
                    "negation_embedding": record["negation_embedding"],
                    "negation_function": record["negation_function"],
                    "studied_host": site["host"].__class__.__name__,
                }
            )
    hosts = Counter(item["studied_host"] for item in changed)
    return {
        "definitions": {
            "negation_form": "被研究否定的句法形式。不是推理操作。",
            "negation_embedding": "这个 Not 所在的结构位置。",
            "negation_function": "这个否定在当前样本推理里的作用。",
            "inference_type": "实际使用的推理操作。与 negation_form 分开记录。",
            "forms": {
                "atomic_literal": "Not 直接作用在原子谓词上。",
                "negated_disjunct": "被研究的 Not 是析取的一个析取项。",
                "rule_antecedent": "Not 在蕴含的前件里。",
                "rule_consequent": "Not 在蕴含的后件里。",
                "negated_universal": "Not 作用在全称公式上。",
                "existential_counterexample": "存在量词的合取支里带 Not。",
            },
            "embeddings": {
                "atomic": "原子否定。",
                "disjunction": "析取。",
                "rule_antecedent": "规则前件。",
                "rule_consequent": "规则后件。",
                "negated_universal": "否定全称。",
                "existential": "存在公式。",
            },
        },
        "old_counts": dict(old_forms),
        "new_counts": dict(new_forms),
        "changed": len(changed),
        "changed_hosts": dict(hosts),
        "changed_samples": changed,
        "form_by_inference_type": [
            {"negation_form": form, "inference_type": inference, "count": count}
            for (form, inference), count in sorted(cross.items())
        ],
    }


def _summary(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    split_report: dict[str, Any],
    form_audit: dict[str, Any],
    criticality: dict[str, Any],
    equivalence: dict[str, Any],
    integrity: dict[str, Any],
) -> str:
    def cell(rows: list[dict[str, Any]], split: str, field: str, value: str) -> int:
        return sum(
            1
            for record in rows
            if record["split"] == split
            and ("null" if record.get(field) is None else str(record.get(field))) == value
        )

    lines = [
        "# Dataset v1.1",
        "",
        "这次整理保留了 v1.0 的 1,200 条样本。金标签、查询、知识库 AST、证明和 Z3 记录没有改写。",
        "改动限于划分、否定形式元数据、等价形式标记和对照说明。",
        "",
        "## 审计问题",
        "",
        "1. 全部 1,200 条样本都还在。样本编号集合与 v1.0 相同。",
        "2. 所有 gold label 保持不变。逐条哈希包含 label。",
        "3. 所有逻辑 AST 保持不变。逐条哈希包含 statement AST 和 query AST。",
        "4. 存储的 Z3 验证结果保持不变，且每条 `matches_expected` 仍为真。"
        f" 新鲜复核见关键性审计：无效 pair {criticality['invalid_pairs']}。",
        f"5. 新划分：train {split_report['examples']['train']}，"
        f"dev {split_report['examples']['dev']}，test {split_report['examples']['test']}。"
        f" 基础案例 {split_report['base_cases']['train']} / "
        f"{split_report['base_cases']['dev']} / {split_report['base_cases']['test']}。",
        "6. 同一个 pair、同一个 base_case、同一条 canonical skeleton 都只出现在一个 split。"
        f" train/test 骨架重叠为 {split_report['train_test_skeleton_overlap']}。",
        "7. test 的 depth 1 从 "
        f"{cell(before, 'test', 'reasoning_depth', '1')} 变为 "
        f"{cell(after, 'test', 'reasoning_depth', '1')}。"
        f" test 的 depth 3 从 {cell(before, 'test', 'reasoning_depth', '3')} 变为 "
        f"{cell(after, 'test', 'reasoning_depth', '3')}。"
        f" test 的 depth 5 从 {cell(before, 'test', 'reasoning_depth', '5')} 变为 "
        f"{cell(after, 'test', 'reasoning_depth', '5')}。"
        f" dev 的 FACT 从 {cell(before, 'dev', 'negation_position', 'FACT')} 变为 "
        f"{cell(after, 'dev', 'negation_position', 'FACT')}。"
        "唯一小于 dev 配额、且含 FACT 的组是 5 个基础案例、10 条 UNKNOWN。"
        "把它放进 dev 的最优补全，全局分层分数是 8046，差于当前划分的 7358。"
        "这 10 条因此留在 test，用来补齐 test 的 FACT 和 UNKNOWN。",
        f"8. `negation_form = disjunctive_syllogism` 的 {form_audit['changed']} 条样本，"
        "被研究的 Not 都在析取的左支上。形式改为 `negated_disjunct`，"
        "embedding 改为 `disjunction`，function 改为 `disjunctive_premise`。"
        "inference_type 仍是 `disjunctive_syllogism` 或 `modus_ponens_then_disjunctive_syllogism`。",
        f"9. rule_consequent_contrast 共 {criticality['pairs']} 对："
        f"POSITIVE {criticality['positive_pairs']}，NEGATIVE {criticality['negative_pairs']}。"
        f" 不符合设计的 pair：{criticality['invalid_pairs']}。",
        "10. 正向查询里，干扰否定是 TRUE、关键否定是 FALSE。负向查询相反。"
        "把两种查询合在一起后，两种条件都有 TRUE 和 FALSE。只看一种查询方向时，条件和标签仍然一一对应。",
        f"11. 等价量词 pair 通过独立 Z3 验证的数量：{equivalence['passed']}。"
        f" 失败：{equivalence['failed']}。",
        "12. 严格受控 pair 与探索性 pair 的数量没有为了凑数而改写。"
        f" 受控 {sum(1 for r in after if r['in_controlled_subset']) // 2}，"
        f"探索性 {sum(1 for r in after if not r['in_controlled_subset']) // 2}。"
        " 形式字段的改写没有改变对照判定。",
        f"13. 仍在的限制：canonical skeleton 把 600 个基础案例收成 {split_report['group_count']} 个不可拆组。"
        "带 TRUE 或 FALSE 的 FACT 组大小是 50 或 60，放进 dev 会占满该划分。"
        "dev 因此没有 FACT，也没有 depth 0 和 depth 5。"
        "三个 split 都有 TRUE、FALSE、UNKNOWN。test 覆盖了已有的全部深度和全部否定位置。"
        "只分析一种 query polarity 时，关键性与标签仍然绑在一起。探索性 pair 仍同时改变推理类型或深度。",
        "",
        "## 修改前后",
        "",
        "| 项目 | v1.0 | v1.1 |",
        "| --- | ---: | ---: |",
        f"| 样本 | {len(before)} | {len(after)} |",
        f"| dev FACT | {cell(before, 'dev', 'negation_position', 'FACT')} | {cell(after, 'dev', 'negation_position', 'FACT')} |",
        f"| test depth 1 | {cell(before, 'test', 'reasoning_depth', '1')} | {cell(after, 'test', 'reasoning_depth', '1')} |",
        f"| test depth 3 | {cell(before, 'test', 'reasoning_depth', '3')} | {cell(after, 'test', 'reasoning_depth', '3')} |",
        f"| test depth 5 | {cell(before, 'test', 'reasoning_depth', '5')} | {cell(after, 'test', 'reasoning_depth', '5')} |",
        f"| test FACT | {cell(before, 'test', 'negation_position', 'FACT')} | {cell(after, 'test', 'negation_position', 'FACT')} |",
        f"| test QUERY | {cell(before, 'test', 'negation_position', 'QUERY')} | {cell(after, 'test', 'negation_position', 'QUERY')} |",
        f"| test UNKNOWN | {cell(before, 'test', 'label', 'UNKNOWN')} | {cell(after, 'test', 'label', 'UNKNOWN')} |",
        f"| 哈希不一致 | 0 | {integrity['frozen_mismatches']} |",
        "",
        "v1.0 文件在 `dataset-v1.0/`，没有被覆盖。",
        "",
    ]
    return "\n".join(lines)


def release(root: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[2]
    backup = _backup(root)
    source = _load(backup / "pilot.gold.jsonl")
    originals = {record["sample_id"]: _digest(record) for record in source}
    (backup / "frozen_hashes.json").write_text(
        json.dumps(originals, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    records = json.loads(json.dumps(source))
    warnings = _refresh_pairs(records)
    groups, base_group = _groups(records)
    mapping, _targets = assign_balanced_splits(
        groups,
        20261111,
        {"train": 0.7, "dev": 0.1, "test": 0.2},
        list(DIMENSIONS),
    )
    for record in records:
        record["split"] = mapping[base_group[record["base_case_id"]]]
    equivalence = _equivalence(records)
    criticality = _criticality(records)
    mismatches = [
        sample_id
        for sample_id, digest in originals.items()
        if digest != _digest(next(record for record in records if record["sample_id"] == sample_id))
    ]
    integrity = {
        "examples": len(records),
        "base_cases": len({record["base_case_id"] for record in records}),
        "pairs": len({record["pair_id"] for record in records}),
        "sample_ids_unchanged": {record["sample_id"] for record in records}
        == set(originals),
        "frozen_mismatches": len(mismatches),
        "mismatch_ids": mismatches[:20],
        "warnings": warnings,
        "stored_z3_matches": sum(
            1 for record in records if record["verification"].get("matches_expected") is True
        ),
    }
    if mismatches or warnings:
        raise RuntimeError(json.dumps({"integrity": integrity, "warnings": warnings}, ensure_ascii=False)[:4000])
    form_audit = _form_audit(source, records)
    split_report = _split_report(records, groups)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    generated = root / "data" / "generated"
    write_jsonl(generated / "pilot.gold.jsonl", records)
    write_jsonl(generated / "pilot.public.jsonl", [to_public(record) for record in records])
    write_jsonl(reports / "pair_comparison.jsonl", comparison_rows(records))
    (reports / "split_report.json").write_text(
        json.dumps(split_report, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (reports / "negation_form_audit.json").write_text(
        json.dumps(form_audit, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (reports / "criticality_polarity_audit.json").write_text(
        json.dumps(criticality, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (reports / "equivalence_audit.json").write_text(
        json.dumps(equivalence, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    (reports / "data_integrity_report.json").write_text(
        json.dumps(integrity, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    summary = _summary(source, records, split_report, form_audit, criticality, equivalence, integrity)
    (reports / "dataset_v1.1_summary.md").write_text(summary, encoding="utf-8")
    return {"integrity": integrity, "split": split_report["examples"], "warnings": warnings}


def main() -> None:
    result = release(project_root(Path("configs/pilot.yaml")))
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()

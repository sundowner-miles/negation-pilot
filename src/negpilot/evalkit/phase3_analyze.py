"""Score phase-3 experiments from saved predictions.

Experiment 4 and 5 reuse the frozen test predictions. Experiment 6 reads a
separate ablation run. This module does not call a model and does not write
into data/generated.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from negpilot.evalkit.io import read_jsonl
from negpilot.evalkit.phase2_stats import join_predictions
from negpilot.evalkit.phase3_stats import (
    ablation_summary,
    depth_key,
    depth_report,
    equivalent_form_pairs,
    equivalent_summary,
)
from negpilot.evalkit.prompt import PROMPT_VERSION, sha256_text

LABELS = ("TRUE", "FALSE", "UNKNOWN", "invalid_output")


def _pct(count: int, n: int) -> str:
    if n == 0:
        return "0/0"
    return f"{count}/{n}（{100.0 * count / n:.1f}%）"


def _ci(interval: list[float] | None) -> str:
    if not interval:
        return "—"
    return f"[{100.0 * interval[0]:.1f}%, {100.0 * interval[1]:.1f}%]"


def _attach_form(joined: list[dict[str, Any]], gold_by_id: dict[str, dict[str, Any]]) -> None:
    for row in joined:
        row["negation_form"] = gold_by_id[row["sample_id"]].get("negation_form")


def _check_ablation_predictions(
    predictions: list[dict[str, Any]],
    public_by_id: dict[str, dict[str, Any]],
    expected_ids: list[str],
    model_name: str,
) -> None:
    found = [row["sample_id"] for row in predictions]
    if found != expected_ids:
        raise ValueError(f"{model_name} ablation predictions do not match the rendered sample ids")
    if len(set(found)) != len(found):
        raise ValueError(f"{model_name} has duplicate ablation predictions")
    for row in predictions:
        public = public_by_id[row["sample_id"]]
        if row.get("prompt_version") != PROMPT_VERSION:
            raise ValueError(f"{model_name} {row['sample_id']} prompt version drifted")
        if row.get("user_prompt_sha256") != sha256_text(public["prompt"]):
            raise ValueError(f"{model_name} {row['sample_id']} ablation prompt hash does not match")
        if row.get("do_sample") is not False or row.get("enable_thinking") is not False:
            raise ValueError(f"{model_name} {row['sample_id']} decoding is not the frozen setting")
        leaked = [name for name in ("label", "label_after", "negation_critical") if name in row]
        if leaked:
            raise ValueError(f"{model_name} prediction carries scoring fields: {leaked}")


def _scope_notes(gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    equivalent_pairs: dict[str, set[str]] = {}
    rcc: Counter[tuple[str, str]] = Counter()
    for row in gold_rows:
        if row.get("pair_type") == "equivalent_form":
            equivalent_pairs.setdefault(row["split"], set()).add(row["pair_id"])
        if row.get("family") == "rule_consequent_contrast":
            rcc[(row["split"], depth_key(row.get("reasoning_depth")))] += 1
    return {
        "equivalent_pairs_by_split": {split: len(ids) for split, ids in sorted(equivalent_pairs.items())},
        "rule_consequent_contrast_by_split_depth": {
            f"{split} depth {depth}": count for (split, depth), count in sorted(rcc.items())
        },
    }


def _exclusion_counts(manifest: list[dict[str, Any]]) -> dict[str, int]:
    excluded = [row for row in manifest if row["status"] == "excluded"]
    return dict(Counter(row.get("negation_form") for row in excluded))


def _ablation_items(
    original: list[dict[str, Any]],
    ablation: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    original_by_id = {row["sample_id"]: row for row in original}
    ablation_by_id = {row["sample_id"]: row for row in ablation}
    items = []
    for row in manifest:
        if row["status"] != "rendered":
            continue
        sample_id = row["sample_id"]
        before = original_by_id[sample_id]
        after = ablation_by_id[sample_id]
        if before["gold_label"] != row["label_before"]:
            raise ValueError(f"{sample_id} manifest label_before disagrees with gold")
        items.append(
            {
                "sample_id": sample_id,
                "label_before": row["label_before"],
                "label_after": row["label_after"],
                "pred_before": before["predicted_label"],
                "pred_after": after["predicted_label"],
                "negation_critical": row["negation_critical"],
            }
        )
    return items


def _depth_lines(report: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| 深度 | n | 受控 / 探索 | 正确 | Accuracy | 95% Wilson | 标签分层 |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in report:
        summary = item["summary"]
        strata = "；".join(
            f"{label} {_pct(part['correct'], part['n'])}"
            for label, part in item["by_label"].items()
        )
        lines.append(
            f"| {item['depth']} | {item['n']} | {item['controlled_n']} / {item['exploratory_n']} "
            f"| {summary['correct']} | {100.0 * summary['accuracy']:.1f}% | {_ci(summary['accuracy_ci95'])} "
            f"| {strata} |"
        )
    return lines


def _transition_lines(transition: dict[str, dict[str, int]]) -> list[str]:
    lines = [
        "| 原预测 \\ 消融预测 | TRUE | FALSE | UNKNOWN | invalid_output |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for source in LABELS:
        cells = transition[source]
        if sum(cells.values()) == 0:
            continue
        lines.append(
            f"| {source} | {cells['TRUE']} | {cells['FALSE']} | {cells['UNKNOWN']} | {cells['invalid_output']} |"
        )
    return lines


def render_report(models: list[dict[str, Any]], scope: dict[str, Any], exclusions: dict[str, int]) -> str:
    lines = [
        "# 阶段三：实验 4–6",
        "",
        "评测集是 test。实验 4 和实验 5 使用阶段二已经生成的 test 预测，没有重新调用模型。",
        "实验 6 使用另行渲染的消融输入，解码和提示词与阶段二相同。",
        "train、dev 和全量 1,200 条没有为这三个实验重新推理。",
        "",
        "## 实验 4：推理深度",
        "",
        "深度 0 全部是 FALSE，深度 null 全部是 UNKNOWN。它们不进入 1、3、5 的趋势比较。",
        "深度 1 和 3 在 test 上是受控样本；深度 5 在 test 上是探索性样本，标签构成也不同。",
        "rule_consequent_contrast 在各 split 的样本数：",
        "",
    ]
    for key, count in scope["rule_consequent_contrast_by_split_depth"].items():
        lines.append(f"- {key}：{count} 条")
    lines.append("")
    for model in models:
        lines.append(f"### {model['model_name']}")
        lines.append("")
        lines.extend(_depth_lines(model["depth"]))
        lines.append("")
        for item in model["depth"]:
            families = "，".join(f"{name} {count}" for name, count in sorted(item["families"].items()))
            lines.append(f"深度 {item['depth']} 的家族：{families}。")
        lines.append("")
    lines.extend(
        [
            "## 实验 5：等价量词形式",
            "",
            "一对里一条是否定全称，另一条是存在反例。两条的金标签都是 UNKNOWN。",
            "预测一致率和两条都预测正确的 pair accuracy 分开报告。",
            "",
            "各 split 的等价形式 pair 数：",
            "",
        ]
    )
    for split, count in scope["equivalent_pairs_by_split"].items():
        lines.append(f"- {split}：{count} 对")
    lines.append("")
    lines.append("本次只使用 test 里已经有预测的 pair。其余 split 没有运行。")
    lines.append("")
    for model in models:
        summary = model["equivalent"]
        lines.extend(
            [
                f"### {model['model_name']}",
                "",
                f"可用 pair {summary['n_pairs']}，拒绝 {model['equivalent_rejected']}。",
                f"预测一致 {_pct(summary['agreement'], summary['n_pairs'])}，"
                f"95% Wilson {_ci(summary['agreement_ci95'])}。",
                f"两条都正确 {_pct(summary['both_correct'], summary['n_pairs'])}，"
                f"95% Wilson {_ci(summary['pair_accuracy_ci95'])}。",
                f"一致但并非两条都正确：{summary['agreed_and_wrong']} 对。",
                f"否定全称正确 {summary['universal_correct']}/{summary['n_pairs']}，"
                f"存在反例正确 {summary['existential_correct']}/{summary['n_pairs']}。",
                f"不一致 {summary['disagreement']} 对。方向（否定全称预测 vs 存在反例预测）："
                f"{summary['disagreement_directions'] or '无'}。",
                "",
            ]
        )
    excluded_text = "，".join(f"{name} {count}" for name, count in sorted(exclusions.items()))
    lines.extend(
        [
            "## 实验 6：否定消融",
            "",
            "模型输入只删除被研究的那个 Not，再用同一套 symbol 句式渲染。",
            f"渲染失败因而没有送进模型的样本：{excluded_text}。这些样本没有改写成新句子。",
            "下面的准确率只计算成功渲染的样本。原准确率对照删除前的 Z3 标签，消融准确率对照删除后的 Z3 标签。",
            "“跟着标签过渡”指（原预测，消融预测）等于（原 Z3 标签，消融后 Z3 标签）。",
            "",
        ]
    )
    for model in models:
        ablation = model["ablation"]
        lines.extend(
            [
                f"### {model['model_name']}",
                "",
                f"n={ablation['n']}。原任务正确 {ablation['original']['correct']}/{ablation['n']}，"
                f"Accuracy {100.0 * ablation['original']['accuracy']:.1f}%"
                f"（{_ci(ablation['original']['accuracy_ci95'])}）。",
                f"消融任务正确 {ablation['ablated']['correct']}/{ablation['n']}，"
                f"Accuracy {100.0 * ablation['ablated']['accuracy']:.1f}%"
                f"（{_ci(ablation['ablated']['accuracy_ci95'])}）。",
                "invalid_output："
                f"原任务 {ablation['original']['invalid_output']}，"
                f"消融任务 {ablation['ablated']['invalid_output']}。",
                "",
            ]
        )
        lines.extend(_transition_lines(ablation["prediction_transition"]))
        lines.append("")
        follows = ablation["follows_label_transition"]
        matched = ablation["ablation_matches_new_label"]
        changed = ablation["prediction_changed_when_label_changed"]
        stable = ablation["prediction_unchanged_when_label_stable"]
        critical = ablation["critical_prediction_changed"]
        distractor = ablation["distractor_prediction_changed"]
        lines.extend(
            [
                f"标签发生变化的样本 {follows['n']} 条。预测跟着这条过渡的有 "
                f"{_pct(follows['count'], follows['n'])}，95% Wilson {_ci(follows['ci95'])}。",
                f"其中消融预测等于新标签的有 {_pct(matched['count'], matched['n'])}，"
                f"预测发生了变化的有 {_pct(changed['count'], changed['n'])}。",
                f"标签没有变化的样本 {stable['n']} 条，预测也没有变化的有 "
                f"{_pct(stable['count'], stable['n'])}，95% Wilson {_ci(stable['ci95'])}。",
                f"critical 上预测发生变化 {_pct(critical['count'], critical['n'])}，"
                f"95% Wilson {_ci(critical['ci95'])}。",
                f"distractor 上预测发生变化 {_pct(distractor['count'], distractor['n'])}，"
                f"95% Wilson {_ci(distractor['ci95'])}。",
                (
                    "在这批成功渲染的样本里，critical 和“删除 Not 后 Z3 标签发生变化”是同一批样本。"
                    if ablation["critical_matches_label_change_partition"]
                    else "critical 与标签是否变化不完全重合，见 JSON。"
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negpilot.evalkit.phase3_analyze")
    parser.add_argument("--predictions", action="append", required=True)
    parser.add_argument("--ablation", action="append", required=True)
    parser.add_argument("--ablation-public", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    original_paths = dict(spec.split("=", 1) for spec in args.predictions)
    ablation_paths = dict(spec.split("=", 1) for spec in args.ablation)
    if set(original_paths) != set(ablation_paths):
        raise ValueError("original and ablation prediction names differ")
    gold_rows = read_jsonl(args.gold)
    gold_by_id = {row["sample_id"]: row for row in gold_rows}
    manifest = read_jsonl(args.manifest)
    public_rows = read_jsonl(args.ablation_public)
    public_by_id = {row["sample_id"]: row for row in public_rows}
    expected_ids = [row["sample_id"] for row in public_rows]
    rendered_ids = [row["sample_id"] for row in manifest if row["status"] == "rendered"]
    if rendered_ids != expected_ids:
        raise ValueError("rendered manifest ids and ablation public ids differ")
    scope = _scope_notes(gold_rows)
    exclusions = _exclusion_counts(manifest)
    models = []
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for model_name in original_paths:
        original_rows = read_jsonl(original_paths[model_name])
        joined = join_predictions(original_rows, gold_rows)
        if len(joined) != 240 or any(row.get("split") != "test" for row in joined):
            raise ValueError(f"{model_name} original predictions are not the 240 test rows")
        _attach_form(joined, gold_by_id)
        ablation_rows = read_jsonl(ablation_paths[model_name])
        _check_ablation_predictions(ablation_rows, public_by_id, expected_ids, model_name)
        paired = equivalent_form_pairs(joined)
        summary = equivalent_summary(paired["pairs"])
        items = _ablation_items(joined, ablation_rows, manifest)
        model = {
            "model_name": model_name,
            "depth": depth_report(joined),
            "equivalent": summary,
            "equivalent_rejected": len(paired["rejected"]),
            "ablation": ablation_summary(items),
        }
        models.append(model)
        slug = model_name.strip("/").replace("/", "-")
        (output_dir / f"{slug}-phase3.json").write_text(
            json.dumps(
                {
                    "depth": model["depth"],
                    "equivalent": model["equivalent"],
                    "equivalent_rejected": model["equivalent_rejected"],
                    "ablation": model["ablation"],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / f"{slug}-equivalent-pairs.jsonl").write_text(
            "".join(json.dumps(pair, ensure_ascii=False) + "\n" for pair in paired["pairs"]),
            encoding="utf-8",
        )
    (output_dir / "scope.json").write_text(
        json.dumps({"scope": scope, "exclusions": exclusions}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "phase3_report.md").write_text(
        render_report(models, scope, exclusions),
        encoding="utf-8",
    )
    print(f"wrote {output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

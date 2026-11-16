"""Write phase-2 tables, charts and the test-set report from saved predictions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from negpilot.evalkit.io import read_jsonl
from negpilot.evalkit.phase2_stats import (
    criticality_pairs,
    group_metrics,
    join_predictions,
    summarize_criticality,
    summarize_predictions,
)
from negpilot.evalkit.score import write_confusion_csv


def _expected_groups() -> tuple[tuple[str, ...], tuple[str, ...]]:
    from negpilot.schema import POSITIONS, SCOPES

    return POSITIONS, SCOPES


def _pct(value: float | None) -> str:
    if value is None:
        return "未计算"
    return f"{100 * value:.1f}%"


def _ci(interval: list[float] | None) -> str:
    if not interval:
        return "未计算"
    return f"[{100 * interval[0]:.1f}%, {100 * interval[1]:.1f}%]"


def _num(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "未计算"
    return f"{value:.{digits}f}"


def analyze_joined(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positions, scopes = _expected_groups()
    observed_positions = {row["negation_position"] for row in rows}
    observed_scopes = {row["negation_scope"] for row in rows}
    label_position = Counter((row["negation_position"], row["gold_label"]) for row in rows)
    absent_cells = [
        {"negation_position": position, "gold_label": label}
        for position in positions
        for label in ("TRUE", "FALSE", "UNKNOWN")
        if label_position[(position, label)] == 0
    ]
    built = criticality_pairs(rows)
    return {
        "n": len(rows),
        "experiment_1": summarize_predictions(rows),
        "experiment_2": {
            "family": "rule_consequent_contrast",
            "rejected_pairs": built["rejected"],
            **summarize_criticality(built["pairs"]),
            "pairs": built["pairs"],
        },
        "experiment_3": {
            "by_position": group_metrics(rows, "negation_position"),
            "by_scope": group_metrics(rows, "negation_scope"),
            "controlled_by_position": group_metrics(
                [row for row in rows if row.get("in_controlled_subset") is True],
                "negation_position",
            ),
            "exploratory_by_position": group_metrics(
                [row for row in rows if row.get("in_controlled_subset") is False],
                "negation_position",
            ),
            "positions_absent_from_split": [item for item in positions if item not in observed_positions],
            "scopes_absent_from_split": [item for item in scopes if item not in observed_scopes],
            "position_label_cells_with_zero_samples": absent_cells,
        },
        "distribution": {
            "label": dict(Counter(row["gold_label"] for row in rows)),
            "negation_position": dict(Counter(row["negation_position"] for row in rows)),
            "negation_scope": dict(Counter(row["negation_scope"] for row in rows)),
            "in_controlled_subset": {
                "controlled": sum(row.get("in_controlled_subset") is True for row in rows),
                "exploratory": sum(row.get("in_controlled_subset") is False for row in rows),
            },
        },
    }


def error_rows(rows: list[dict[str, Any]], public_by_id: dict[str, dict[str, Any]], model_name: str) -> list[dict[str, Any]]:
    errors = []
    for row in rows:
        if row["correct"]:
            continue
        public = public_by_id[row["sample_id"]]
        errors.append(
            {
                "model_name": model_name,
                "sample_id": row["sample_id"],
                "pair_id": row.get("pair_id"),
                "gold_label": row["gold_label"],
                "predicted_label": row["predicted_label"],
                "parse_status": row.get("parse_status"),
                "negation_position": row.get("negation_position"),
                "negation_scope": row.get("negation_scope"),
                "family": row.get("family"),
                "in_controlled_subset": row.get("in_controlled_subset"),
                "query_polarity": row.get("query_polarity"),
                "negation_critical": row.get("negation_critical"),
                "reasoning_depth": row.get("reasoning_depth"),
                "raw_output": row.get("raw_output"),
                "prompt": public["prompt"],
            }
        )
    return errors


def confusion_counts(summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        gold: {
            "TRUE": summary["confusion"][gold]["TRUE"],
            "FALSE": summary["confusion"][gold]["FALSE"],
            "UNKNOWN": summary["confusion"][gold]["UNKNOWN"],
            "invalid_output": summary["confusion"][gold]["invalid_output"],
        }
        for gold in ("TRUE", "FALSE", "UNKNOWN")
    }


def write_confusion_svg(path: Path, title: str, matrix: dict[str, dict[str, int]], n: int) -> None:
    columns = ("TRUE", "FALSE", "UNKNOWN", "invalid_output")
    rows = ("TRUE", "FALSE", "UNKNOWN")
    cell = 72
    left, top = 110, 70
    width = left + cell * len(columns) + 40
    height = top + cell * len(rows) + 50
    peak = max(matrix[gold][pred] for gold in rows for pred in columns) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="16" y="28" font-family="sans-serif" font-size="16" fill="#1c1c1c">{title}</text>',
        f'<text x="16" y="48" font-family="sans-serif" font-size="12" fill="#444">Counts of test samples. n={n}. Rows are gold labels.</text>',
    ]
    for index, pred in enumerate(columns):
        x = left + index * cell + cell / 2
        parts.append(
            f'<text x="{x}" y="{top - 8}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#222">{pred}</text>'
        )
    for r_index, gold in enumerate(rows):
        y = top + r_index * cell
        parts.append(
            f'<text x="{left - 10}" y="{y + cell / 2}" text-anchor="end" font-family="sans-serif" font-size="12" fill="#222">{gold}</text>'
        )
        for c_index, pred in enumerate(columns):
            value = matrix[gold][pred]
            shade = 255 - int(180 * value / peak)
            fill = f"rgb({shade},{shade},{shade})"
            ink = "#111" if shade > 140 else "#f7f7f7"
            x = left + c_index * cell
            parts.append(f'<rect x="{x}" y="{y}" width="{cell - 4}" height="{cell - 4}" fill="{fill}" stroke="#ddd"/>')
            parts.append(
                f'<text x="{x + (cell - 4) / 2}" y="{y + cell / 2}" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{ink}">{value}</text>'
            )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_grouped_bar_svg(
    path: Path,
    title: str,
    caption: str,
    categories: list[str],
    series: list[dict[str, Any]],
    y_label: str,
    y_max: float,
) -> None:
    width = 760
    height = 420
    left, top, chart_w, chart_h = 64, 72, 640, 250
    baseline = top + chart_h
    group_w = chart_w / max(len(categories), 1)
    bar_w = min(28, group_w / (len(series) + 1))
    colors = ("#2f6f4e", "#3d5a80", "#8a5a12", "#8d3b3b")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="24" y="28" font-family="sans-serif" font-size="16" fill="#1c1c1c">{title}</text>',
        f'<text x="24" y="48" font-family="sans-serif" font-size="12" fill="#444">{caption}</text>',
        f'<line x1="{left}" y1="{baseline}" x2="{left + chart_w}" y2="{baseline}" stroke="#222"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{baseline}" stroke="#222"/>',
        f'<text x="16" y="{top + 12}" font-family="sans-serif" font-size="11" fill="#333">{y_label}</text>',
    ]
    for g_index, category in enumerate(categories):
        origin = left + g_index * group_w + 12
        for s_index, item in enumerate(series):
            value = float(item["data"][g_index])
            bar_h = 0 if y_max == 0 else chart_h * value / y_max
            x = origin + s_index * (bar_w + 6)
            y = baseline - bar_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{colors[s_index % len(colors)]}"/>'
            )
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#222">{value:.0f}</text>'
            )
        parts.append(
            f'<text x="{left + g_index * group_w + group_w / 2:.1f}" y="{baseline + 20}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#222">{category}</text>'
        )
    legend_y = baseline + 48
    for s_index, item in enumerate(series):
        x = 64 + s_index * 180
        parts.append(f'<rect x="{x}" y="{legend_y}" width="12" height="12" fill="{colors[s_index % len(colors)]}"/>')
        parts.append(
            f'<text x="{x + 18}" y="{legend_y + 11}" font-family="sans-serif" font-size="12" fill="#222">{item["name"]}</text>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _metric_line(summary: dict[str, Any]) -> str:
    per = summary["per_class"]
    return (
        f"n={summary['n']}，正确 {summary['correct']}，"
        f"Accuracy {_pct(summary['accuracy'])}（95% Wilson {_ci(summary.get('accuracy_ci95'))}），"
        f"Macro-F1 {_num(summary.get('macro_f1'))}，"
        f"invalid {summary['invalid_output']}。"
        f" TRUE F1 {_num(per['TRUE']['f1'])}，"
        f"FALSE F1 {_num(per['FALSE']['f1'])}，"
        f"UNKNOWN F1 {_num(per['UNKNOWN']['f1'])}。"
    )


def _class_table(summary: dict[str, Any]) -> list[str]:
    lines = ["| 标签 | n | Precision | Recall | F1 |", "| --- | ---: | ---: | ---: | ---: |"]
    for label in ("TRUE", "FALSE", "UNKNOWN"):
        item = summary["per_class"][label]
        lines.append(
            f"| {label} | {item['support']} | {_num(item['precision'])} | {_num(item['recall'])} | {_num(item['f1'])} |"
        )
    return lines


def _group_table(groups: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for group in groups:
        metrics = group["metrics"]
        lines.append(
            f"| {group['group']} | {metrics['n']} | {metrics['correct']} | {_pct(metrics['accuracy'])} | {_ci(metrics.get('accuracy_ci95'))} | {_num(metrics.get('macro_f1'))} |"
        )
    return lines


def _label_lines(groups: list[dict[str, Any]]) -> list[str]:
    lines = ["| 组 | 金标签 | n | 正确 | Accuracy |", "| --- | --- | ---: | ---: | ---: |"]
    for group in groups:
        for item in group["by_gold_label"]:
            lines.append(
                f"| {group['group']} | {item['gold_label']} | {item['n']} | {item['correct']} | {_pct(item['accuracy'])} |"
            )
    return lines


def render_report(model_reports: list[dict[str, Any]]) -> str:
    lines = [
        "# 阶段二：test 集上的实验 1–3",
        "",
        "这是独立 test 的 240 条。dev 和 train 没有参与这次评分。全量 1,200 条没有运行。",
        "提示词版本是 plan-6.4-v1，两个模型都使用贪心解码，思考模式关闭。",
        "实验 3 的分组准确率是描述性结果。探索性对照同时改变了多个因素，不能单独当成位置或辖域的因果效应。",
        "",
        "## 实验 1：三分类",
        "",
    ]
    for report in model_reports:
        summary = report["analysis"]["experiment_1"]
        lines.append(f"### {report['model_name']}")
        lines.append("")
        lines.append(_metric_line(summary))
        lines.append("")
        lines.extend(_class_table(summary))
        lines.append("")
        lines.append("| 金标签 \\ 预测 | TRUE | FALSE | UNKNOWN | invalid_output |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for gold in ("TRUE", "FALSE", "UNKNOWN"):
            cells = summary["confusion"][gold]
            lines.append(
                f"| {gold} | {cells['TRUE']} | {cells['FALSE']} | {cells['UNKNOWN']} | {cells['invalid_output']} |"
            )
        lines.append("")
        unknown_as_false = summary["confusion"]["UNKNOWN"]["FALSE"]
        false_as_unknown = summary["confusion"]["FALSE"]["UNKNOWN"]
        lines.append(
            f"UNKNOWN 被判成 FALSE：{unknown_as_false} / {summary['per_class']['UNKNOWN']['support']}。"
            f" FALSE 被判成 UNKNOWN：{false_as_unknown} / {summary['per_class']['FALSE']['support']}。"
        )
        lines.append("")
    lines.extend(["## 实验 2：否定关键性", ""])
    lines.append(
        "只使用 test 中的 `rule_consequent_contrast`。全部 90 对里还有 60 对在 train 或 dev，这次没有运行。"
    )
    lines.append(
        "正向查询里 distractor 的金标签是 TRUE、critical 是 FALSE；负向查询相反。只看一种极性时，条件和标签绑在一起。"
    )
    lines.append("")
    for report in model_reports:
        exp2 = report["analysis"]["experiment_2"]
        lines.append(f"### {report['model_name']}")
        lines.append("")
        pooled = exp2["pooled"]
        lines.append(
            f"对数 {pooled['n_pairs']}。pair accuracy（两条都对）{_pct(pooled['pair_accuracy'])}。"
            f" critical Accuracy {_pct(pooled['critical']['accuracy'])}，"
            f"distractor Accuracy {_pct(pooled['distractor']['accuracy'])}。"
        )
        effect = pooled["critical_minus_distractor"]
        mcnemar = pooled["mcnemar"]
        lines.append(
            f"critical 减 distractor 的准确率差是 {_pct(effect['difference'])}，"
            f"自助法 95% 区间 {_ci(effect['ci95'])}（{effect['replicates']} 次，种子 {effect['seed']}）。"
            f" McNemar 精确检验：discordant {mcnemar['n_discordant']} "
            f"（critical 错而 distractor 对 {mcnemar['b']}，相反 {mcnemar['c']}），"
            f"双侧 p={_num(mcnemar['p_value'], 4)}。"
        )
        lines.append("")
        lines.append("| 极性 | 对数 | critical Accuracy | distractor Accuracy | pair accuracy | 准确率差 | 95% 区间 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
        for polarity in ("POSITIVE", "NEGATIVE"):
            item = exp2["by_query_polarity"][polarity]
            diff = item["critical_minus_distractor"]
            lines.append(
                f"| {polarity} | {item['n_pairs']} | {_pct(item['critical']['accuracy'])} | "
                f"{_pct(item['distractor']['accuracy'])} | {_pct(item['pair_accuracy'])} | "
                f"{_pct(diff['difference'])} | {_ci(diff['ci95'])} |"
            )
        lines.append("")
        lines.append(
            f"被拒绝的不完整 pair：{len(exp2['rejected_pairs'])}。"
        )
        lines.append("")
    lines.extend(["## 实验 3：位置与辖域", ""])
    lines.append("下面每个格子都带样本数。某个位置没有出现的金标签不写成准确率 0。")
    lines.append("")
    for report in model_reports:
        exp3 = report["analysis"]["experiment_3"]
        lines.append(f"### {report['model_name']}：位置")
        lines.append("")
        lines.extend(_group_table(exp3["by_position"]))
        lines.append("")
        lines.extend(_label_lines(exp3["by_position"]))
        lines.append("")
        lines.append(f"### {report['model_name']}：辖域")
        lines.append("")
        lines.extend(_group_table(exp3["by_scope"]))
        lines.append("")
        lines.extend(_label_lines(exp3["by_scope"]))
        lines.append("")
        lines.append("受控对照与探索性对照分开：")
        lines.append("")
        lines.append("受控")
        lines.append("")
        lines.extend(_group_table(exp3["controlled_by_position"]))
        lines.append("")
        lines.append("探索性")
        lines.append("")
        lines.extend(_group_table(exp3["exploratory_by_position"]))
        lines.append("")
    first = model_reports[0]["analysis"]["experiment_3"]
    lines.append(
        "本 split 中没有样本的位置："
        + (", ".join(first["positions_absent_from_split"]) or "无")
        + "。没有样本的辖域："
        + (", ".join(first["scopes_absent_from_split"]) or "无")
        + "。"
    )
    lines.append(
        "位置×金标签样本数为 0 的格子："
        + ", ".join(
            f"{item['negation_position']}×{item['gold_label']}"
            for item in first["position_label_cells_with_zero_samples"]
        )
        + "。"
    )
    lines.append("")
    lines.append("这些空格子是当前 test 划分里没有生成的组合，不是模型在该格上得分为 0。")
    lines.append("")
    return "\n".join(lines) + "\n"


def _strip_pairs(analysis: dict[str, Any]) -> dict[str, Any]:
    """Drop per-pair rows from the JSON summary. The pair file is stored separately."""
    copied = json.loads(json.dumps(analysis))
    copied["experiment_2"].pop("pairs", None)
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="negpilot.evalkit.phase2_analyze")
    parser.add_argument("--predictions", action="append", required=True)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    gold_rows = read_jsonl(args.gold)
    public_rows = read_jsonl(args.public)
    public_by_id = {row["sample_id"]: row for row in public_rows}
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(exist_ok=True)
    model_reports = []
    all_errors = []
    position_categories = []
    position_series: dict[str, list[float]] = {}
    crit_categories = ["pooled", "POSITIVE", "NEGATIVE"]
    crit_series: dict[str, dict[str, list[float]]] = {}

    for spec in args.predictions:
        model_name, path = spec.split("=", 1)
        predictions = read_jsonl(path)
        joined = join_predictions(predictions, gold_rows)
        if any(row.get("split") != "test" for row in joined):
            raise ValueError(f"{model_name} predictions are not all test samples")
        analysis = analyze_joined(joined)
        slug = model_name.strip("/").replace("/", "-")
        write_confusion_csv(output_dir / f"{slug}-confusion.csv", analysis["experiment_1"]["confusion"])
        matrix = confusion_counts(analysis["experiment_1"])
        write_confusion_svg(
            chart_dir / f"{slug}-confusion.svg",
            f"{model_name} test confusion counts",
            matrix,
            analysis["n"],
        )
        errors = error_rows(joined, public_by_id, model_name)
        all_errors.extend(errors)
        (output_dir / f"{slug}-analysis.json").write_text(
            json.dumps(_strip_pairs(analysis), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / f"{slug}-pairs.jsonl").write_text(
            "".join(json.dumps(pair, ensure_ascii=False) + "\n" for pair in analysis["experiment_2"]["pairs"]),
            encoding="utf-8",
        )
        model_reports.append({"model_name": model_name, "analysis": analysis, "n_errors": len(errors)})
        short = model_name.split("/")[-1]
        groups = {item["group"]: item for item in analysis["experiment_3"]["by_position"]}
        if not position_categories:
            position_categories = [f"{name} (n={groups[name]['metrics']['n']})" for name in ("FACT", "RULE", "QUERY") if name in groups]
        position_series[short] = [
            100 * groups[name]["metrics"]["accuracy"]
            for name in ("FACT", "RULE", "QUERY")
            if name in groups
        ]
        exp2 = analysis["experiment_2"]
        crit_series[short] = {
            "critical": [
                100 * exp2["pooled"]["critical"]["accuracy"],
                100 * exp2["by_query_polarity"]["POSITIVE"]["critical"]["accuracy"],
                100 * exp2["by_query_polarity"]["NEGATIVE"]["critical"]["accuracy"],
            ],
            "distractor": [
                100 * exp2["pooled"]["distractor"]["accuracy"],
                100 * exp2["by_query_polarity"]["POSITIVE"]["distractor"]["accuracy"],
                100 * exp2["by_query_polarity"]["NEGATIVE"]["distractor"]["accuracy"],
            ],
        }

    (output_dir / "errors.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_errors),
        encoding="utf-8",
    )
    distribution = model_reports[0]["analysis"]["distribution"]
    label_order = [label for label in ("TRUE", "FALSE", "UNKNOWN") if label in distribution["label"]]
    write_grouped_bar_svg(
        chart_dir / "test-label-counts.svg",
        "Gold label counts on the evaluated test split",
        "Source: test samples scored in this run. This is the label base rate, not model accuracy.",
        label_order,
        [{"name": "samples", "data": [float(distribution["label"][key]) for key in label_order]}],
        "Samples",
        max(distribution["label"].values()),
    )
    write_grouped_bar_svg(
        chart_dir / "position-accuracy.svg",
        "Test accuracy by negation position",
        "Percent correct. Category labels include n. Overall accuracy mixes different gold-label compositions.",
        position_categories,
        [{"name": name, "data": values} for name, values in position_series.items()],
        "Accuracy (%)",
        100,
    )
    pair_n = model_reports[0]["analysis"]["experiment_2"]["pooled"]["n_pairs"]
    pos_n = model_reports[0]["analysis"]["experiment_2"]["by_query_polarity"]["POSITIVE"]["n_pairs"]
    neg_n = model_reports[0]["analysis"]["experiment_2"]["by_query_polarity"]["NEGATIVE"]["n_pairs"]
    write_grouped_bar_svg(
        chart_dir / "criticality-accuracy.svg",
        "Critical versus distractor accuracy on test pairs",
        f"Percent correct. Pooled n={pair_n} pairs; POSITIVE n={pos_n}; NEGATIVE n={neg_n}.",
        [f"pooled (n={pair_n})", f"POSITIVE (n={pos_n})", f"NEGATIVE (n={neg_n})"],
        [
            {"name": f"{model} {condition}", "data": crit_series[model][condition]}
            for model in crit_series
            for condition in ("critical", "distractor")
        ],
        "Accuracy (%)",
        100,
    )
    (output_dir / "phase2_report.md").write_text(render_report(model_reports), encoding="utf-8")
    print(f"wrote {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

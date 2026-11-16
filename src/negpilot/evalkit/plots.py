"""Write a small SVG check chart for the smoke test. No extra dependencies."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


def write_smoke_chart(path: str | Path, rows: list[dict]) -> None:
    """Grouped bars of correct, incorrect, and invalid counts.

    Each row needs model, n, correct, incorrect, and invalid_output.
    The chart states that the counts are a pipeline check.
    """
    if not rows:
        raise ValueError("smoke chart needs at least one model row")
    width = 760
    height = 420
    left = 64
    top = 72
    chart_w = 640
    chart_h = 250
    max_n = max(int(row["n"]) for row in rows)
    group_w = chart_w / len(rows)
    bar_w = min(36, group_w / 5)
    colors = {"correct": "#2f6f4e", "incorrect": "#8a5a12", "invalid_output": "#8d3b3b"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="32" y="32" font-family="sans-serif" font-size="18" fill="#1c1c1c">Smoke-test label outcomes by model</text>',
        f'<text x="32" y="54" font-family="sans-serif" font-size="12" fill="#444">Pipeline check on the fixed dev slice. Not a test-set result. n per model is labeled under the axis.</text>',
    ]
    baseline = top + chart_h
    parts.append(
        f'<line x1="{left}" y1="{baseline}" x2="{left + chart_w}" y2="{baseline}" stroke="#222"/>'
    )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{baseline}" stroke="#222"/>')
    parts.append(
        f'<text x="16" y="{top + chart_h / 2}" font-family="sans-serif" font-size="12" fill="#333" transform="rotate(-90 16 {top + chart_h / 2})">Samples</text>'
    )
    for index, row in enumerate(rows):
        origin = left + index * group_w + group_w / 2 - 1.5 * bar_w - 8
        for offset, key in enumerate(("correct", "incorrect", "invalid_output")):
            value = int(row[key])
            bar_h = 0 if max_n == 0 else chart_h * value / max_n
            x = origin + offset * (bar_w + 8)
            y = baseline - bar_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{colors[key]}"/>'
            )
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#222">{value}</text>'
            )
        label = escape(str(row["model"]))
        parts.append(
            f'<text x="{left + index * group_w + group_w / 2:.1f}" y="{baseline + 22}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#222">{label}</text>'
        )
        parts.append(
            f'<text x="{left + index * group_w + group_w / 2:.1f}" y="{baseline + 40}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#444">n={int(row["n"])}</text>'
        )
    legend_x = left
    legend_y = baseline + 68
    for offset, (key, color) in enumerate(colors.items()):
        x = legend_x + offset * 180
        parts.append(f'<rect x="{x}" y="{legend_y}" width="12" height="12" fill="{color}"/>')
        parts.append(
            f'<text x="{x + 18}" y="{legend_y + 11}" font-family="sans-serif" font-size="12" fill="#222">{key}</text>'
        )
    parts.append("</svg>")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")

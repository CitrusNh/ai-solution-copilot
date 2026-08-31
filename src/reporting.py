"""Create portable sales-analysis reports and local feedback records."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.retrieve import SearchResult
from src.solution_card import SolutionCard


def build_markdown_report(
    card: SolutionCard,
    results: list[SearchResult],
) -> str:
    """Render one analysis card as a shareable Markdown document."""

    lines = [
        "# AI 企业研究与售前方案助手分析报告",
        "",
        "## 客户需求",
        "",
        card.request_summary,
        "",
        f"**结论状态：{card.confidence}**",
        "",
        "## 匹配能力",
        "",
    ]
    if card.matched_capabilities:
        for item in card.matched_capabilities:
            lines.extend(
                [f"- {item.text}", f"  - 来源：{item.source} · {item.heading}"]
            )
    else:
        lines.append("当前资料中没有可确认的产品能力。")

    lines.extend(["", "## 限制与风险", ""])
    if card.constraints_and_risks:
        for item in card.constraints_and_risks:
            lines.extend(
                [f"- {item.text}", f"  - 来源：{item.source} · {item.heading}"]
            )
    else:
        lines.append("当前检索片段中没有明确写出的限制；这不代表不存在限制。")

    lines.extend(["", "## 建议继续询问客户", ""])
    lines.extend(
        f"{index}. {question}"
        for index, question in enumerate(card.open_questions, start=1)
    )
    lines.extend(["", "## 售前回复草稿", "", card.reply_draft])
    lines.extend(["", "## 检索证据", ""])
    for rank, result in enumerate(results, start=1):
        lines.extend(
            [
                f"### {rank}. {result.heading}",
                "",
                f"来源：{result.source} · 匹配分数：{result.score:.3f}",
                "",
                result.content,
                "",
            ]
        )
    lines.extend(
        [
            "---",
            "本报告由本地规则版本生成，关键结论应由售前或产品负责人复核。",
            "",
        ]
    )
    return "\n".join(lines)


def append_feedback(
    path: Path,
    *,
    query: str,
    confidence: str,
    rating: str,
    note: str,
) -> None:
    """Append one non-sensitive usability record to a local CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["created_at", "query", "confidence", "rating", "note"],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "query": query,
                "confidence": confidence,
                "rating": rating,
                "note": note.strip(),
            }
        )


def count_feedback(path: Path) -> int:
    """Count valid feedback rows without loading them into the application UI."""

    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))

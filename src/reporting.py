"""Create portable sales-analysis reports and local feedback records."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.retrieve import SearchResult
from src.solution_card import SolutionCard

if TYPE_CHECKING:
    from src.llm_analysis import LLMAnalysis
    from src.web_search import WebSearchResult


def build_markdown_report(
    card: SolutionCard,
    results: list[SearchResult],
    *,
    ai_analysis: "LLMAnalysis | None" = None,
    web_results: "list[WebSearchResult] | None" = None,
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
    if ai_analysis is not None:
        lines.extend(
            [
                "## AI 增强分析",
                "",
                ai_analysis.analysis_summary,
                "",
                "### AI 售前回复草稿",
                "",
                ai_analysis.customer_reply_draft,
                "",
                f"模型：{ai_analysis.model}",
                f"Token：输入 {ai_analysis.prompt_tokens}，输出 {ai_analysis.completion_tokens}",
                "",
            ]
        )
        if ai_analysis.risks:
            lines.extend(["### AI 补充风险", ""])
            lines.extend(f"- {item}" for item in ai_analysis.risks)
            lines.append("")
        if ai_analysis.follow_up_questions:
            lines.extend(["### AI 建议追问", ""])
            lines.extend(
                f"{index}. {item}"
                for index, item in enumerate(
                    ai_analysis.follow_up_questions, start=1
                )
            )
            lines.append("")
    if web_results:
        lines.extend(
            [
                "## 互联网公开资料",
                "",
                "> 互联网资料只用于补充背景，不能证明本产品支持某项能力。",
                "",
            ]
        )
        for index, item in enumerate(web_results, start=1):
            lines.extend(
                [
                    f"### W{index}. {item.title}",
                    "",
                    item.url,
                    "",
                    item.snippet,
                    "",
                ]
            )
    lines.extend(
        [
            "---",
            "本报告保留本地规则安全基线；AI 内容属于辅助草稿，关键结论应由售前或产品负责人复核。",
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

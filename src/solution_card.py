"""Build a grounded, rule-based presales analysis card."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.retrieve import SearchResult


RISK_KEYWORDS = (
    "不支持",
    "不包含",
    "没有承诺",
    "不得",
    "需要人工",
    "需要单独",
    "需要另行",
    "另行评估",
    "单独评估",
    "限制",
    "可能下降",
    "超过",
)

BLOCKING_RISK_KEYWORDS = (
    "没有承诺",
    "不得自行推断",
    "需要人工确认",
    "不得直接承诺",
)

QUERY_RELEVANCE_TERMS = (
    ("价格", "多少钱", "收费", "报价", "费用", "元"),
    ("人数", "上限", "席位", "名用户", "多少用户"),
    ("私有化", "部署", "服务器", "运维", "公有云", "SaaS"),
    ("审计", "日志"),
    ("权限", "角色", "部门", "组织", "知识空间"),
    ("保留", "周期", "天"),
    ("离线", "客户端"),
    ("BYOK", "密钥", "等保", "认证", "驻留", "境内", "合规"),
    ("培训", "学员", "现场", "驻场"),
)

RISK_CONTEXT_TERMS = (
    "需要人工确认",
    "不得自行推断",
    "不得直接承诺",
)


@dataclass(frozen=True)
class GroundedStatement:
    """One statement copied from a retrieved source."""

    text: str
    source: str
    heading: str


@dataclass(frozen=True)
class SolutionCard:
    """A transparent local baseline for a future LLM-generated analysis."""

    request_summary: str
    matched_capabilities: tuple[GroundedStatement, ...]
    constraints_and_risks: tuple[GroundedStatement, ...]
    open_questions: tuple[str, ...]
    reply_draft: str
    confidence: str


def split_sentences(text: str) -> list[str]:
    """Split Chinese prose and Markdown list items into readable statements."""

    normalized = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    parts = re.split(r"(?<=[。！？；])\s*|\n+", normalized)
    return [part.strip(" -*\t") for part in parts if part.strip(" -*\t")]


def is_risk_statement(text: str) -> bool:
    """Return whether a source sentence describes a limit or uncertainty."""

    return any(keyword in text for keyword in RISK_KEYWORDS)


def relevant_to_query(query: str, text: str) -> bool:
    """Keep statements that address at least one explicit request intent."""

    if any(term in text for term in RISK_CONTEXT_TERMS):
        return True

    query_upper = query.upper()
    text_upper = text.upper()
    active_groups = [
        group
        for group in QUERY_RELEVANCE_TERMS
        if any(term.upper() in query_upper for term in group)
    ]
    if not active_groups:
        return True
    return any(
        any(term.upper() in text_upper for term in group) for group in active_groups
    )


def join_statements(statements: list[GroundedStatement]) -> str:
    """Join source statements without producing duplicated punctuation."""

    cleaned = [item.text.rstrip("。！？；") for item in statements if item.text.strip()]
    return "；".join(cleaned) + ("。" if cleaned else "")


def discovery_questions(query: str) -> tuple[str, ...]:
    """Select a small presales discovery checklist from the request topic."""

    if "审计" in query or "日志" in query:
        return (
            "客户需要记录哪些操作和用户行为？",
            "审计日志需要保留多久，是否要求导出或对接其他系统？",
            "该能力是否属于客户验收或合规的硬性要求？",
        )
    if "私有化" in query or "部署" in query:
        return (
            "客户计划使用的服务器、操作系统和网络环境是什么？",
            "预计用户数、文档量和并发量是多少？",
            "客户期望的交付时间、运维边界和预算范围是什么？",
        )
    if "培训" in query:
        return (
            "培训城市、时间和参与人数是否已经确定？",
            "客户需要管理员培训还是普通用户培训？",
            "是否还需要二次开发、服务器采购或长期驻场支持？",
        )
    if any(keyword in query.upper() for keyword in ("BYOK", "等保", "驻留", "认证")):
        return (
            "该安全或合规能力是否属于采购的硬性门槛？",
            "客户要求的认证等级、数据区域和验收材料是什么？",
            "是否需要产品、安全或法务负责人进行书面确认？",
        )
    if "价格" in query or "多少钱" in query or "收费" in query:
        return (
            "客户预计的用户数、部署方式和合同周期是什么？",
            "是否需要培训、实施、迁移或定制开发服务？",
            "客户预算范围和采购时间表是什么？",
        )
    return (
        "客户希望解决的核心业务问题和成功标准是什么？",
        "预计用户数、使用频率、部署方式和交付时间是什么？",
        "哪些需求属于必须满足，哪些可以后续迭代？",
    )


def build_solution_card(
    query: str,
    results: list[SearchResult],
    max_statements: int = 4,
) -> SolutionCard:
    """Convert retrieval results into a source-grounded presales card."""

    cleaned_query = " ".join(query.split())
    capabilities: list[GroundedStatement] = []
    risks: list[GroundedStatement] = []
    seen: set[str] = set()
    has_blocking_risk = False

    for result in results:
        for sentence in split_sentences(result.content):
            if sentence in seen:
                continue
            seen.add(sentence)
            if not relevant_to_query(cleaned_query, sentence):
                continue
            statement = GroundedStatement(
                text=sentence,
                source=result.source,
                heading=result.heading,
            )
            sentence_is_risk = is_risk_statement(sentence)
            if sentence_is_risk and any(
                keyword in sentence for keyword in BLOCKING_RISK_KEYWORDS
            ):
                has_blocking_risk = True
            target = risks if sentence_is_risk else capabilities
            if len(target) < max_statements:
                target.append(statement)

    has_explicit_answer = bool(capabilities or risks) and not has_blocking_risk
    has_grounded_answer = has_explicit_answer
    confidence = "资料可支持初步回复" if has_grounded_answer else "资料不足，需要人工确认"

    pricing_requires_assessment = (
        any(term in cleaned_query for term in ("价格", "多少钱", "收费", "报价", "费用"))
        and any("单独评估" in item.text or "另行评估" in item.text for item in risks)
    )

    if has_blocking_risk:
        # General product descriptions are not evidence that the blocked
        # requirement itself is supported. Hide them from the match section.
        capabilities = []

    if has_grounded_answer:
        confirmed_text = join_statements(capabilities[:2])
        reply_parts = [f"根据当前产品资料，可初步确认：{confirmed_text}"]
        if pricing_requires_assessment:
            reply_parts.append("其中私有化部署的具体价格需要单独评估服务器、部署和维护成本。")
    else:
        reply_parts = ["当前产品资料不足以确认该需求，暂时不能向客户作出承诺。"]

    if risks and not pricing_requires_assessment:
        risk_text = join_statements(risks[:2])
        reply_parts.append(f"同时需要说明：{risk_text}")
    reply_parts.append("建议补充确认上述问题后，再由相关负责人给出正式方案和承诺。")

    return SolutionCard(
        request_summary=cleaned_query,
        matched_capabilities=tuple(capabilities),
        constraints_and_risks=tuple(risks),
        open_questions=discovery_questions(cleaned_query),
        reply_draft="\n\n".join(reply_parts),
        confidence=confidence,
    )

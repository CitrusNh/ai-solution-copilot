"""Run a deterministic retrieval and safety evaluation baseline."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    variant: str
    run_id: str
    category: str
    risk_tier: str
    score: float
    passed: bool
    retrieval_hit: bool
    top1_correct: bool
    confidence_correct: bool
    required_terms_found: bool
    latency_ms: float
    cost_usd: float
    query: str
    actual_top_sources: list[str]
    actual_confidence: str
    missing_terms: list[str]


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate non-empty JSONL evaluation cases."""

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {line_number} 行不是有效 JSON。") from exc

        required_fields = {
            "case_id",
            "category",
            "risk_tier",
            "query",
            "expected_sources",
            "expected_top1",
            "expected_confidence",
            "required_terms",
        }
        missing_fields = required_fields - case.keys()
        if missing_fields:
            raise ValueError(
                f"用例 {case.get('case_id', line_number)} 缺少字段：{sorted(missing_fields)}"
            )
        if case["case_id"] in seen_ids:
            raise ValueError(f"重复的 case_id：{case['case_id']}")
        seen_ids.add(case["case_id"])
        cases.append(case)

    if not cases:
        raise ValueError("评测集为空。")
    return cases


def normalize_for_match(text: str) -> str:
    """Normalize superficial formatting without changing factual meaning."""

    return re.sub(r"\s+", "", text).casefold()


def evaluate_case(case: dict[str, Any], chunks: list, variant: str) -> CaseResult:
    """Evaluate one case with deterministic checks."""

    started = time.perf_counter()
    results = search_chunks(case["query"], chunks, top_k=3)
    card = build_solution_card(case["query"], results)
    latency_ms = (time.perf_counter() - started) * 1000

    actual_sources = [result.source for result in results]
    expected_sources = set(case["expected_sources"])
    retrieval_hit = bool(expected_sources.intersection(actual_sources))
    top1_correct = bool(actual_sources) and actual_sources[0] == case["expected_top1"]
    confidence_correct = card.confidence == case["expected_confidence"]

    grounded_text = "\n".join(
        [
            *(item.text for item in card.matched_capabilities),
            *(item.text for item in card.constraints_and_risks),
            card.reply_draft,
        ]
    )
    normalized_grounded_text = normalize_for_match(grounded_text)
    missing_terms = [
        term
        for term in case["required_terms"]
        if normalize_for_match(term) not in normalized_grounded_text
    ]
    required_terms_found = not missing_terms

    checks = [
        retrieval_hit,
        top1_correct,
        confidence_correct,
        required_terms_found,
    ]
    score = sum(checks) / len(checks)
    passed = all(checks)

    return CaseResult(
        case_id=case["case_id"],
        variant=variant,
        run_id="deterministic-1",
        category=case["category"],
        risk_tier=case["risk_tier"],
        score=score,
        passed=passed,
        retrieval_hit=retrieval_hit,
        top1_correct=top1_correct,
        confidence_correct=confidence_correct,
        required_terms_found=required_terms_found,
        latency_ms=round(latency_ms, 3),
        cost_usd=0.0,
        query=case["query"],
        actual_top_sources=actual_sources,
        actual_confidence=card.confidence,
        missing_terms=missing_terms,
    )


def run_evaluation(
    cases_path: Path,
    data_dir: Path,
    variant: str = "local-rules-v0.3.1",
) -> list[CaseResult]:
    """Run the frozen local baseline on every evaluation case."""

    cases = load_cases(cases_path)
    chunks = load_markdown_chunks(data_dir)
    return [evaluate_case(case, chunks, variant) for case in cases]


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    """Produce explicit aggregate and critical-case metrics."""

    total = len(results)
    passed = sum(result.passed for result in results)
    critical = [result for result in results if result.risk_tier == "critical"]
    return {
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": passed / total,
        "retrieval_hit_rate_at_3": sum(result.retrieval_hit for result in results) / total,
        "top1_accuracy": sum(result.top1_correct for result in results) / total,
        "confidence_accuracy": sum(result.confidence_correct for result in results) / total,
        "required_terms_rate": sum(result.required_terms_found for result in results) / total,
        "critical_cases": len(critical),
        "critical_passed": sum(result.passed for result in critical),
        "critical_pass_rate": (
            sum(result.passed for result in critical) / len(critical) if critical else None
        ),
        "average_latency_ms": sum(result.latency_ms for result in results) / total,
        "total_cost_usd": sum(result.cost_usd for result in results),
        "failed_case_ids": [result.case_id for result in results if not result.passed],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("eval/questions.jsonl"))
    parser.add_argument("--data", type=Path, default=Path("data/demo"))
    parser.add_argument("--output", type=Path, default=Path("eval/results.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("eval/summary.json"))
    args = parser.parse_args()

    results = run_evaluation(args.cases, args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(asdict(result), ensure_ascii=False) for result in results)
        + "\n",
        encoding="utf-8",
    )
    summary = summarize(results)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

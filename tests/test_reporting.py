from pathlib import Path

from src.reporting import append_feedback, build_markdown_report, count_feedback
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card


DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def test_markdown_report_contains_answer_and_citations():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("最多支持多少用户？", chunks)
    card = build_solution_card("最多支持多少用户？", results)

    report = build_markdown_report(card, results)

    assert "# AI 企业研究与售前方案助手分析报告" in report
    assert "500 名用户" in report
    assert "pricing_and_limits.md" in report
    assert "售前回复草稿" in report


def test_feedback_is_appended_locally(tmp_path: Path):
    feedback_path = tmp_path / "feedback.csv"

    append_feedback(
        feedback_path,
        query="是否支持 BYOK？",
        confidence="资料不足，需要人工确认",
        rating="有用",
        note="没有乱承诺",
    )
    append_feedback(
        feedback_path,
        query="最多支持多少用户？",
        confidence="资料可支持初步回复",
        rating="部分有用",
        note="",
    )

    content = feedback_path.read_text(encoding="utf-8-sig")
    assert count_feedback(feedback_path) == 2
    assert "没有乱承诺" in content
    assert "OPENAI_API_KEY" not in content

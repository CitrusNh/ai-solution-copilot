from pathlib import Path
from types import SimpleNamespace

from src.reporting import append_feedback, build_markdown_report, count_feedback
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card
from src.web_search import WebSearchResult


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


def test_markdown_report_keeps_ai_and_web_sources_separate():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("最多支持多少用户？", chunks)
    card = build_solution_card("最多支持多少用户？", results)
    ai_analysis = SimpleNamespace(
        analysis_summary="专业版最多 500 名用户。[D1]",
        customer_reply_draft="根据内部资料，最多 500 名用户。[D1]",
        risks=("超过上限需要升级。[D1]",),
        follow_up_questions=("客户预计多少账号？[D1]",),
        model="fake-chat",
        prompt_tokens=100,
        completion_tokens=50,
    )
    web_results = [
        WebSearchResult("行业资料", "https://example.com", "公开行业背景")
    ]

    report = build_markdown_report(
        card,
        results,
        ai_analysis=ai_analysis,
        web_results=web_results,
    )

    assert "## AI 增强分析" in report
    assert "## 互联网公开资料" in report
    assert "不能证明本产品支持某项能力" in report
    assert "AI 内容属于辅助草稿" in report

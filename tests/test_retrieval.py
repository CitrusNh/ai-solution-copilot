from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.retrieve import load_markdown_chunks, search_chunks


DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def test_demo_documents_are_loaded():
    chunks = load_markdown_chunks(DATA_DIR)

    assert len(chunks) >= 8
    assert {chunk.source for chunk in chunks} == {
        "pricing_and_limits.md",
        "product_overview.md",
        "security_faq.md",
    }


def test_price_query_finds_pricing_document_first():
    chunks = load_markdown_chunks(DATA_DIR)

    results = search_chunks("专业版每月多少钱？", chunks)

    assert results
    assert results[0].source == "pricing_and_limits.md"


def test_audit_query_finds_security_faq_first():
    chunks = load_markdown_chunks(DATA_DIR)

    results = search_chunks("是否支持审计日志？", chunks)

    assert results
    assert results[0].source == "security_faq.md"


def test_empty_query_returns_no_results():
    chunks = load_markdown_chunks(DATA_DIR)

    assert search_chunks("   ", chunks) == []


def test_streamlit_search_flow_shows_a_source():
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))
    app.run(timeout=15)

    app.text_input[0].set_value("是否支持审计日志？")
    app.button[0].click()
    app.run(timeout=15)

    assert not app.exception
    assert any(
        "security_faq.md" in caption.value for caption in app.caption
    )

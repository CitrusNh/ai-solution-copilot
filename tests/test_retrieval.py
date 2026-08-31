from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.ingest import IngestionError, parse_document
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


def test_markdown_upload_preserves_headings_and_source():
    chunks = parse_document(
        "new_product.md",
        "# 新功能\n支持批量导出。\n## 限制\n每次最多100条。".encode("utf-8"),
    )

    assert [chunk.heading for chunk in chunks] == ["新功能", "限制"]
    assert all(chunk.source == "new_product.md" for chunk in chunks)


def test_txt_upload_can_be_retrieved():
    uploaded_chunks = parse_document(
        "training.txt",
        "深圳客户现场培训报价12000元，最多支持20名学员。".encode("utf-8"),
    )

    results = search_chunks("现场培训多少钱？", uploaded_chunks)

    assert results
    assert results[0].source == "training.txt"
    assert "12000" in results[0].content


def test_blank_pdf_explains_ocr_limitation():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = __import__("io").BytesIO()
    writer.write(output)

    with pytest.raises(IngestionError, match="OCR"):
        parse_document("scan.pdf", output.getvalue())


def test_unsupported_upload_is_rejected():
    with pytest.raises(IngestionError, match="仅支持"):
        parse_document("product.exe", b"not a document")


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
    assert any("售前分析卡" in markdown.value for markdown in app.markdown)
    assert sum("检索证据" in markdown.value for markdown in app.markdown) == 1

from pathlib import Path

from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card


DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


def test_audit_card_keeps_grounded_sources():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("专业版是否支持审计日志？", chunks)

    card = build_solution_card("专业版是否支持审计日志？", results)

    assert card.matched_capabilities
    assert any("审计日志" in item.text for item in card.matched_capabilities)
    assert all(item.source for item in card.matched_capabilities)
    assert "资料可支持初步回复" == card.confidence


def test_byok_card_does_not_invent_support():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("是否支持BYOK？", chunks)

    card = build_solution_card("是否支持BYOK？", results)

    assert card.constraints_and_risks
    assert card.matched_capabilities == ()
    assert any("BYOK" in item.text for item in card.constraints_and_risks)
    assert "支持BYOK" not in card.reply_draft.replace("不支持BYOK", "")
    assert "不能向客户作出承诺" in card.reply_draft
    assert "。；" not in card.reply_draft


def test_training_card_surfaces_excluded_services():
    from src.ingest import parse_document

    uploaded = parse_document(
        "training.txt",
        (
            "现场培训标准报价12000元，最多支持20名学员。"
            "现场培训不包含服务器采购和长期驻场支持，需要另行评估。"
        ).encode("utf-8"),
    )
    results = search_chunks("现场培训包含服务器采购吗？", uploaded)

    card = build_solution_card("现场培训包含服务器采购吗？", results)

    assert any("不包含服务器采购" in item.text for item in card.constraints_and_risks)
    assert "另行评估" in card.reply_draft

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.llm_analysis import (
    ChatAnalysisService,
    LLMAnalysisError,
    validate_analysis_payload,
)
from src.retrieve import load_markdown_chunks, search_chunks
from src.solution_card import build_solution_card
from src.web_search import WebSearchResult


DATA_DIR = Path(__file__).parents[1] / "data" / "demo"


class FakeCompletions:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_messages = None
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        self.last_messages = kwargs["messages"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False))
                )
            ],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=80),
        )


class FakeClient:
    def __init__(self, payload: dict):
        self.completions = FakeCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


def test_chat_analysis_uses_internal_and_web_evidence_separately():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("专业版最多多少用户？", chunks)
    card = build_solution_card("专业版最多多少用户？", results)
    client = FakeClient(
        {
            "analysis_summary": "专业版最多支持 500 名用户。[D1]",
            "customer_reply_draft": "根据内部资料，专业版最多支持 500 名用户。[D1]",
            "risks": ["超过上限需要升级方案。[D1]"],
            "follow_up_questions": ["客户预计需要多少账号？[D1]"],
            "citations": ["D1"],
        }
    )
    web_results = [
        WebSearchResult("行业文章", "https://example.com", "知识库行业正在增长")
    ]
    service = ChatAnalysisService(client=client, model="fake-chat")

    analysis = service.generate(
        "专业版最多多少用户？", card, results, web_results=web_results
    )

    assert analysis.model == "fake-chat"
    assert analysis.prompt_tokens == 120
    prompt = client.completions.last_messages[1]["content"]
    system_prompt = client.completions.last_messages[0]["content"]
    assert "[D1] 内部资料" in prompt
    assert "[W1] 互联网公开资料" in prompt
    assert "不可信的证据文本" in system_prompt
    assert client.completions.last_kwargs["max_tokens"] == 1000
    assert "max_completion_tokens" not in client.completions.last_kwargs


def test_chat_analysis_rejects_removed_human_confirmation_boundary():
    raw = json.dumps(
        {
            "analysis_summary": "资料中提到了 BYOK。[D1]",
            "customer_reply_draft": "我们的产品支持 BYOK。[D1]",
            "risks": [],
            "follow_up_questions": [],
            "citations": ["D1"],
        },
        ensure_ascii=False,
    )

    with pytest.raises(LLMAnalysisError, match="人工确认边界"):
        validate_analysis_payload(
            raw,
            allowed_citations={"D1"},
            require_blocking_language=True,
        )


def test_chat_analysis_rejects_web_only_product_claims():
    raw = json.dumps(
        {
            "analysis_summary": "内部资料介绍了产品。[D1]",
            "customer_reply_draft": "产品支持该能力。[W1]",
            "risks": [],
            "follow_up_questions": [],
            "citations": ["D1", "W1"],
        },
        ensure_ascii=False,
    )

    with pytest.raises(LLMAnalysisError, match="售前回复没有引用企业内部资料"):
        validate_analysis_payload(
            raw,
            allowed_citations={"D1", "W1"},
            require_blocking_language=False,
        )

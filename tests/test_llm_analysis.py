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
    def __init__(self, payload: dict | str | list[dict | str]):
        self.payloads = payload if isinstance(payload, list) else [payload]
        self.last_messages = None
        self.last_kwargs = None
        self.call_kwargs = []
        self.calls = 0

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        self.call_kwargs.append(kwargs)
        self.last_messages = kwargs["messages"]
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        content = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False)
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=80),
        )


class FakeClient:
    def __init__(self, payload: dict | str | list[dict | str]):
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
    assert client.completions.last_kwargs["response_format"] == {"type": "json_object"}
    assert "max_completion_tokens" not in client.completions.last_kwargs


def test_chat_analysis_repairs_missing_reply_citation_once():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("是否支持 BYOK？", chunks)
    card = build_solution_card("是否支持 BYOK？", results)
    client = FakeClient(
        [
            {
                "analysis_summary": "资料没有承诺 BYOK，需要人工确认。[D1]",
                "customer_reply_draft": "当前资料不足，暂时不能承诺，请人工确认。",
                "risks": ["存在错误承诺风险。[D1]"],
                "follow_up_questions": [],
                "citations": ["D1"],
            },
            {
                "analysis_summary": "资料没有承诺 BYOK，需要人工确认。[D1]",
                "customer_reply_draft": "根据内部资料，当前资料不足，暂时不能承诺，请人工确认。[D1]",
                "risks": ["存在错误承诺风险。[D1]"],
                "follow_up_questions": [],
                "citations": ["D1"],
            },
        ]
    )
    service = ChatAnalysisService(client=client, model="deepseek-chat")

    analysis = service.generate("是否支持 BYOK？", card, results)

    assert client.completions.calls == 2
    assert "customer_reply_draft" in client.completions.last_messages[-1]["content"]
    assert "[D1]" in analysis.customer_reply_draft
    assert analysis.prompt_tokens == 240
    assert analysis.completion_tokens == 160


def test_chat_analysis_repairs_missing_reply_citation_without_third_request():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("是否支持 BYOK？", chunks)
    card = build_solution_card("是否支持 BYOK？", results)
    payload_without_reply_citation = {
        "analysis_summary": "资料没有承诺 BYOK，需要人工确认。[D1]",
        "customer_reply_draft": "当前资料不足，暂时不能承诺，请人工确认。",
        "risks": ["存在错误承诺风险。[D1]"],
        "follow_up_questions": [],
        "citations": ["D1"],
    }
    client = FakeClient([payload_without_reply_citation, payload_without_reply_citation])
    service = ChatAnalysisService(client=client, model="deepseek-chat")

    analysis = service.generate("是否支持 BYOK？", card, results)

    assert client.completions.calls == 2
    assert analysis.customer_reply_draft.endswith("[D1]")


@pytest.mark.parametrize(
    "wrapper",
    [
        "```json\n{payload}\n```",
        "下面是结果：\n{payload}\n以上为结构化分析。",
    ],
)
def test_chat_analysis_parses_json_wrapped_by_provider_text(wrapper):
    payload = json.dumps(
        {
            "analysis_summary": "专业版最多支持 500 名用户。[D1]",
            "customer_reply_draft": "专业版最多支持 500 名用户。[D1]",
            "risks": [],
            "follow_up_questions": [],
            "citations": ["D1"],
        },
        ensure_ascii=False,
    )

    parsed = validate_analysis_payload(
        wrapper.format(payload=payload),
        allowed_citations={"D1"},
        require_blocking_language=False,
    )

    assert parsed.citations == ["D1"]


def test_chat_analysis_falls_back_to_plain_request_after_two_invalid_json_results():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("是否支持 BYOK？", chunks)
    card = build_solution_card("是否支持 BYOK？", results)
    valid_payload = {
        "analysis_summary": "资料没有承诺 BYOK，需要人工确认。[D1]",
        "customer_reply_draft": "当前资料不足，不能承诺，请人工确认。[D1]",
        "risks": ["存在错误承诺风险。[D1]"],
        "follow_up_questions": [],
        "citations": ["D1"],
    }
    client = FakeClient(["不是 JSON", "仍然不是 JSON", valid_payload])
    service = ChatAnalysisService(client=client, model="deepseek-chat")

    analysis = service.generate("是否支持 BYOK？", card, results)

    assert client.completions.calls == 3
    assert "response_format" in client.completions.call_kwargs[0]
    assert "response_format" in client.completions.call_kwargs[1]
    assert "response_format" not in client.completions.call_kwargs[2]
    assert client.completions.call_kwargs[2]["max_tokens"] == 2000
    assert len(client.completions.call_kwargs[2]["messages"]) == 3
    assert "仍然不是 JSON" not in str(client.completions.call_kwargs[2]["messages"])
    assert analysis.citations == ("D1",)
    assert analysis.prompt_tokens == 360
    assert analysis.completion_tokens == 240


def test_chat_analysis_stops_safely_after_three_invalid_results():
    chunks = load_markdown_chunks(DATA_DIR)
    results = search_chunks("是否支持 BYOK？", chunks)
    card = build_solution_card("是否支持 BYOK？", results)
    client = FakeClient(["不是 JSON", "仍然不是 JSON", "最终也不是 JSON"])
    service = ChatAnalysisService(client=client, model="deepseek-chat")

    with pytest.raises(LLMAnalysisError, match="没有返回可解析的 JSON"):
        service.generate("是否支持 BYOK？", card, results)

    assert client.completions.calls == 3
    assert "response_format" not in client.completions.call_kwargs[2]
    assert client.completions.call_kwargs[2]["max_tokens"] == 2000


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

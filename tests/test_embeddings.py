from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.embeddings import EmbeddingBudgetExceeded, OpenAIEmbeddingService
from src.retrieve import DocumentChunk
from src.semantic_retrieve import HybridRetriever


@dataclass
class FakeEmbeddingItem:
    embedding: list[float]


class FakeEmbeddingsEndpoint:
    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = mapping
        self.calls = 0

    def create(self, *, model: str, input: list[str], dimensions: int):
        self.calls += 1
        vectors = [self.mapping[text] for text in input]
        return SimpleNamespace(
            data=[FakeEmbeddingItem(vector) for vector in vectors],
            usage=SimpleNamespace(prompt_tokens=sum(len(text) for text in input)),
            model=model,
        )


class FakeClient:
    def __init__(self, mapping: dict[str, list[float]]):
        self.embeddings = FakeEmbeddingsEndpoint(mapping)


def test_embedding_cache_avoids_a_second_api_call(tmp_path: Path):
    client = FakeClient({"价格": [1.0, 0.0]})
    service = OpenAIEmbeddingService(
        client=client,
        dimensions=2,
        cache_path=tmp_path / "cache.json",
    )

    assert service.embed_texts(["价格"]) == [[1.0, 0.0]]
    assert service.embed_texts(["价格"]) == [[1.0, 0.0]]
    assert client.embeddings.calls == 1
    assert service.usage.cache_hits == 1


def test_budget_is_checked_before_api_call(tmp_path: Path):
    client = FakeClient({"很长的测试文本": [1.0, 0.0]})
    service = OpenAIEmbeddingService(
        client=client,
        dimensions=2,
        budget_cny=0.000000001,
        cache_path=tmp_path / "cache.json",
    )

    with pytest.raises(EmbeddingBudgetExceeded):
        service.embed_texts(["很长的测试文本"])
    assert client.embeddings.calls == 0


def test_semantic_and_hybrid_retrieval_can_fix_price_ranking(tmp_path: Path):
    chunks = [
        DocumentChunk("security.md", "审计", "专业版支持审计日志。"),
        DocumentChunk("pricing.md", "价格", "专业版8999元，最多500名用户。"),
    ]
    document_texts = [f"{chunk.heading}\n{chunk.content}" for chunk in chunks]
    query = "专业版价格和用户上限是多少？"
    mapping = {
        document_texts[0]: [0.0, 1.0],
        document_texts[1]: [1.0, 0.0],
        query: [1.0, 0.0],
    }
    service = OpenAIEmbeddingService(
        client=FakeClient(mapping),
        dimensions=2,
        cache_path=tmp_path / "cache.json",
    )
    retriever = HybridRetriever(chunks, service)

    assert retriever.search_semantic(query)[0].source == "pricing.md"
    assert retriever.search_hybrid(query)[0].source == "pricing.md"


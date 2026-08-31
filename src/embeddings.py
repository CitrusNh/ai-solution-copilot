"""Budgeted OpenAI-compatible embedding client with a local disk cache."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 512
USD_PER_MILLION_TOKENS = 0.02
CONSERVATIVE_CNY_PER_USD = 7.5


class EmbeddingError(RuntimeError):
    """A safe, actionable embedding integration error."""


class EmbeddingBudgetExceeded(EmbeddingError):
    """Raised before a request that could exceed the authorized budget."""


@dataclass
class EmbeddingUsage:
    """Usage generated in the current process, excluding cache hits."""

    prompt_tokens: int = 0
    api_calls: int = 0
    cache_hits: int = 0

    @property
    def cost_usd(self) -> float:
        return self.prompt_tokens * USD_PER_MILLION_TOKENS / 1_000_000

    @property
    def cost_cny(self) -> float:
        return self.cost_usd * CONSERVATIVE_CNY_PER_USD


class EmbeddingCache:
    """A small JSON cache keyed by model, dimensions and exact text hash."""

    def __init__(self, path: Path | None):
        self.path = path
        self.entries: dict[str, list[float]] = {}
        if path and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.entries = raw
            except (json.JSONDecodeError, OSError):
                self.entries = {}

    @staticmethod
    def key(model: str, dimensions: int, text: str) -> str:
        payload = json.dumps(
            {"model": model, "dimensions": dimensions, "text": text},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get(self, model: str, dimensions: int, text: str) -> list[float] | None:
        return self.entries.get(self.key(model, dimensions, text))

    def set(self, model: str, dimensions: int, text: str, vector: list[float]) -> None:
        self.entries[self.key(model, dimensions, text)] = vector

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.entries, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def conservative_token_estimate(texts: list[str]) -> int:
    """Overestimate short Chinese/English inputs for a budget preflight."""

    return sum(max(1, len(text) * 2) for text in texts)


def estimated_cost_cny(texts: list[str]) -> float:
    """Estimate cost with a deliberately conservative token count."""

    tokens = conservative_token_estimate(texts)
    return tokens * USD_PER_MILLION_TOKENS / 1_000_000 * CONSERVATIVE_CNY_PER_USD


class OpenAIEmbeddingService:
    """Create embeddings through an OpenAI-compatible API with safeguards."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        budget_cny: float = 1.0,
        cache_path: Path | None = Path("data/cache/embeddings.json"),
    ):
        if dimensions <= 0:
            raise ValueError("Embedding dimensions 必须大于0。")
        if budget_cny <= 0:
            raise ValueError("Embedding预算必须大于0元。")

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if client is None and not resolved_key:
            raise EmbeddingError("未找到 OPENAI_API_KEY。")

        if client is None:
            client_kwargs: dict[str, Any] = {
                "api_key": resolved_key,
                "timeout": 20.0,
                "max_retries": 2,
            }
            resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL")
            if resolved_base_url:
                client_kwargs["base_url"] = resolved_base_url
            client = OpenAI(**client_kwargs)

        self.client = client
        self.model = model
        self.dimensions = dimensions
        self.budget_cny = budget_cny
        self.cache = EmbeddingCache(cache_path)
        self.usage = EmbeddingUsage()

    def _check_budget(self, missing_texts: list[str]) -> None:
        projected = self.usage.cost_cny + estimated_cost_cny(missing_texts)
        if projected > self.budget_cny:
            raise EmbeddingBudgetExceeded(
                f"预计累计费用约 {projected:.4f} 元，超过 {self.budget_cny:.2f} 元预算。"
            )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return vectors in input order, using cached results when possible."""

        if not texts:
            return []

        resolved: list[list[float] | None] = []
        missing_texts: list[str] = []
        missing_positions: list[int] = []
        for position, text in enumerate(texts):
            cached = self.cache.get(self.model, self.dimensions, text)
            if cached is None:
                resolved.append(None)
                missing_texts.append(text)
                missing_positions.append(position)
            else:
                resolved.append(cached)
                self.usage.cache_hits += 1

        if missing_texts:
            self._check_budget(missing_texts)
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=missing_texts,
                    dimensions=self.dimensions,
                )
            except OpenAIError as exc:
                raise EmbeddingError(
                    "Embedding API调用失败。请检查网络、OPENAI_BASE_URL、账户权限或额度。"
                ) from exc
            except Exception as exc:
                raise EmbeddingError("Embedding API连接失败。") from exc

            vectors = [list(item.embedding) for item in response.data]
            if len(vectors) != len(missing_texts):
                raise EmbeddingError("Embedding API返回的向量数量与输入不一致。")

            usage = getattr(response, "usage", None)
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            self.usage.prompt_tokens += prompt_tokens
            self.usage.api_calls += 1
            if self.usage.cost_cny > self.budget_cny:
                raise EmbeddingBudgetExceeded("API返回的实际Token用量超过授权预算。")

            for position, text, vector in zip(missing_positions, missing_texts, vectors):
                resolved[position] = vector
                self.cache.set(self.model, self.dimensions, text, vector)
            self.cache.save()

        return [vector for vector in resolved if vector is not None]


"""Semantic and hybrid retrieval built on cached embedding vectors."""

from __future__ import annotations

import numpy as np

from src.embeddings import OpenAIEmbeddingService
from src.retrieve import (
    DocumentChunk,
    SearchResult,
    rank_chunks,
    score_keyword_chunks,
)


def searchable_text(chunk: DocumentChunk) -> str:
    return f"{chunk.heading}\n{chunk.content}"


def cosine_scores(query_vector: list[float], document_vectors: list[list[float]]) -> list[float]:
    """Return cosine similarity scores in document order."""

    if not document_vectors:
        return []
    documents = np.asarray(document_vectors, dtype=float)
    query = np.asarray(query_vector, dtype=float)
    document_norms = np.linalg.norm(documents, axis=1)
    query_norm = np.linalg.norm(query)
    denominator = document_norms * query_norm
    denominator[denominator == 0] = 1.0
    return [float(value) for value in (documents @ query / denominator)]


def reciprocal_rank_scores(scores: list[float], constant: int = 60) -> list[float]:
    """Convert arbitrary scores into stable reciprocal-rank contributions."""

    ranked = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
    output = [0.0] * len(scores)
    for rank, index in enumerate(ranked, start=1):
        output[index] = 1.0 / (constant + rank)
    return output


class HybridRetriever:
    """Reuse document embeddings and offer semantic or hybrid ranking."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        embedding_service: OpenAIEmbeddingService,
        semantic_weight: float = 0.65,
    ):
        if not 0 <= semantic_weight <= 1:
            raise ValueError("semantic_weight 必须在0和1之间。")
        self.chunks = chunks
        self.embedding_service = embedding_service
        self.semantic_weight = semantic_weight
        self.document_vectors = embedding_service.embed_texts(
            [searchable_text(chunk) for chunk in chunks]
        )

    def semantic_scores(self, query: str) -> list[float]:
        query_vector = self.embedding_service.embed_texts([query])[0]
        return cosine_scores(query_vector, self.document_vectors)

    def search_semantic(self, query: str, top_k: int = 3) -> list[SearchResult]:
        return rank_chunks(self.chunks, self.semantic_scores(query), top_k=top_k)

    def search_hybrid(self, query: str, top_k: int = 3) -> list[SearchResult]:
        keyword = reciprocal_rank_scores(score_keyword_chunks(query, self.chunks))
        semantic = reciprocal_rank_scores(self.semantic_scores(query))
        hybrid = [
            (1 - self.semantic_weight) * keyword_score
            + self.semantic_weight * semantic_score
            for keyword_score, semantic_score in zip(keyword, semantic)
        ]
        return rank_chunks(self.chunks, hybrid, top_k=top_k)


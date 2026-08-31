"""Local, interpretable retrieval baseline for Markdown product documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


INTENT_TERMS = {
    "pricing": ("价格", "多少钱", "收费", "报价", "费用"),
    "users": ("用户", "人数", "上限", "席位"),
    "deployment": ("部署", "私有化", "SaaS", "公有云"),
    "audit": ("审计", "日志"),
    "permissions": ("权限", "角色", "部门", "组织"),
    "retention": ("保留", "周期", "多久"),
    "offline": ("离线", "客户端"),
    "compliance": ("BYOK", "等保", "认证", "驻留", "境内", "密钥"),
}

INTENT_BOOST = 0.12


@dataclass(frozen=True)
class DocumentChunk:
    """A searchable section from one source document."""

    source: str
    heading: str
    content: str


@dataclass(frozen=True)
class SearchResult:
    """One ranked retrieval result."""

    source: str
    heading: str
    content: str
    score: float


def split_markdown_text(text: str, source: str) -> list[DocumentChunk]:
    """Split Markdown text by headings while preserving source metadata."""

    chunks: list[DocumentChunk] = []
    heading = "文档开头"
    lines: list[str] = []

    def save_chunk() -> None:
        content = "\n".join(lines).strip()
        if content:
            chunks.append(
                DocumentChunk(
                    source=source,
                    heading=heading,
                    content=content,
                )
            )

    for line in text.splitlines():
        if line.startswith("#"):
            save_chunk()
            heading = line.lstrip("#").strip() or "未命名章节"
            lines = []
        else:
            lines.append(line)

    save_chunk()
    return chunks


def split_markdown(path: Path) -> list[DocumentChunk]:
    """Load and split one UTF-8 Markdown file."""

    text = path.read_text(encoding="utf-8")
    return split_markdown_text(text, path.name)


def load_markdown_chunks(data_dir: Path) -> list[DocumentChunk]:
    """Load every Markdown document below a directory in stable order."""

    chunks: list[DocumentChunk] = []
    for path in sorted(data_dir.glob("*.md")):
        chunks.extend(split_markdown(path))
    return chunks


def search_chunks(
    query: str,
    chunks: list[DocumentChunk],
    top_k: int = 3,
) -> list[SearchResult]:
    """Rank chunks using character n-gram TF-IDF cosine similarity.

    Character n-grams work as a transparent Chinese keyword-search baseline
    without requiring a tokenizer or a paid embedding API.
    """

    scores = score_keyword_chunks(query, chunks)
    return rank_chunks(chunks, scores, top_k=top_k)


def score_keyword_chunks(
    query: str,
    chunks: list[DocumentChunk],
) -> list[float]:
    """Return character n-gram TF-IDF scores in original chunk order."""

    cleaned_query = query.strip()
    if not cleaned_query or not chunks:
        return [0.0] * len(chunks)

    searchable_texts = [f"{chunk.heading}\n{chunk.content}" for chunk in chunks]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3))
    matrix = vectorizer.fit_transform([*searchable_texts, cleaned_query])
    base_scores = [
        float(score) for score in cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    ]

    # A small, interpretable intent boost fixes short Chinese questions where
    # generic words such as “专业版” otherwise outweigh the actual request for
    # price, user limits, deployment, or compliance evidence.
    query_upper = cleaned_query.upper()
    active_intents = {
        intent
        for intent, terms in INTENT_TERMS.items()
        if any(term.upper() in query_upper for term in terms)
    }
    if not active_intents:
        return base_scores

    scores: list[float] = []
    for chunk, base_score in zip(chunks, base_scores):
        chunk_upper = f"{chunk.heading}\n{chunk.content}".upper()
        matched_intents = sum(
            any(term.upper() in chunk_upper for term in INTENT_TERMS[intent])
            for intent in active_intents
        )
        scores.append(base_score + matched_intents * INTENT_BOOST)
    return scores


def rank_chunks(
    chunks: list[DocumentChunk],
    scores: list[float],
    top_k: int = 3,
) -> list[SearchResult]:
    """Convert aligned numeric scores into ranked search results."""

    if top_k <= 0 or not chunks:
        return []
    if len(chunks) != len(scores):
        raise ValueError("chunks 与 scores 数量必须一致。")

    ranked_indices = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
    results: list[SearchResult] = []
    for index in ranked_indices:
        score = float(scores[index])
        if score <= 0:
            continue
        chunk = chunks[int(index)]
        results.append(
            SearchResult(
                source=chunk.source,
                heading=chunk.heading,
                content=chunk.content,
                score=score,
            )
        )
        if len(results) == top_k:
            break

    return results

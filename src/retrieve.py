"""Local, interpretable retrieval baseline for Markdown product documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


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


def split_markdown(path: Path) -> list[DocumentChunk]:
    """Split one Markdown file by headings while preserving source metadata."""

    text = path.read_text(encoding="utf-8")
    chunks: list[DocumentChunk] = []
    heading = "文档开头"
    lines: list[str] = []

    def save_chunk() -> None:
        content = "\n".join(lines).strip()
        if content:
            chunks.append(
                DocumentChunk(
                    source=path.name,
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

    cleaned_query = query.strip()
    if not cleaned_query or not chunks or top_k <= 0:
        return []

    searchable_texts = [
        f"{chunk.heading}\n{chunk.content}" for chunk in chunks
    ]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3))
    matrix = vectorizer.fit_transform([*searchable_texts, cleaned_query])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()

    ranked_indices = scores.argsort()[::-1]
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


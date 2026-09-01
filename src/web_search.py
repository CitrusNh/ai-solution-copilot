"""Public web search with traceable sources and safe failure handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


MAX_QUERY_CHARS = 300
MAX_RESULTS = 6


class WebSearchError(RuntimeError):
    """A user-facing error raised when public web search is unavailable."""


@dataclass(frozen=True)
class WebSearchResult:
    """One public search result kept separate from internal product evidence."""

    title: str
    url: str
    snippet: str


def _is_public_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def search_web(
    query: str,
    *,
    max_results: int = 4,
    client: Any | None = None,
) -> list[WebSearchResult]:
    """Search the public web without uploading internal product documents."""

    cleaned_query = " ".join(query.split())
    if not cleaned_query:
        return []
    if len(cleaned_query) > MAX_QUERY_CHARS:
        raise WebSearchError(f"联网搜索问题不能超过 {MAX_QUERY_CHARS} 个字符。")
    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_results 必须在 1 到 {MAX_RESULTS} 之间。")

    if client is None:
        try:
            from ddgs import DDGS

            client = DDGS(timeout=10)
        except Exception as exc:
            raise WebSearchError("联网搜索组件初始化失败。") from exc

    try:
        raw_results = client.text(cleaned_query, max_results=max_results)
    except Exception as exc:
        raise WebSearchError("联网搜索暂时不可用，请稍后重试。") from exc

    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results or []:
        url = str(item.get("href") or item.get("url") or "").strip()
        if not _is_public_http_url(url) or url in seen_urls:
            continue
        title = " ".join(str(item.get("title") or "未命名网页").split())
        snippet = " ".join(
            str(item.get("body") or item.get("snippet") or "").split()
        )
        if not snippet:
            continue
        results.append(WebSearchResult(title=title, url=url, snippet=snippet))
        seen_urls.add(url)
        if len(results) == max_results:
            break
    return results

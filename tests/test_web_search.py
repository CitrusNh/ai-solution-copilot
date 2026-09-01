from src.web_search import WebSearchError, search_web


class FakeSearchClient:
    def __init__(self, results=None, error: Exception | None = None):
        self.results = results or []
        self.error = error

    def text(self, query: str, *, max_results: int):
        if self.error:
            raise self.error
        assert query
        return self.results[:max_results]


def test_web_search_filters_invalid_and_duplicate_urls():
    client = FakeSearchClient(
        [
            {"title": "官方说明", "href": "https://example.com/a", "body": "公开资料"},
            {"title": "重复", "href": "https://example.com/a", "body": "重复资料"},
            {"title": "本地", "href": "file:///tmp/a", "body": "不应展示"},
        ]
    )

    results = search_web("企业知识库", client=client)

    assert len(results) == 1
    assert results[0].title == "官方说明"
    assert results[0].url == "https://example.com/a"


def test_web_search_wraps_provider_errors():
    client = FakeSearchClient(error=RuntimeError("provider down"))

    try:
        search_web("企业知识库", client=client)
    except WebSearchError as exc:
        assert "暂时不可用" in str(exc)
    else:
        raise AssertionError("WebSearchError was not raised")

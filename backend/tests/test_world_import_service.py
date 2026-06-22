from types import SimpleNamespace

from app.services.world_import_service import WorldImportService


def test_wikipedia_403_is_reported_as_partial(monkeypatch) -> None:
    service = WorldImportService()
    errors: list[str] = []
    failures: list[dict] = []

    class Response:
        status_code = 403

        def json(self):
            raise ValueError("no json")

    client = SimpleNamespace(get=lambda *_args, **_kwargs: Response())

    payload = service._wikipedia_summary(client, "示例", "Q1", errors, failures)

    assert payload is None
    assert errors
    assert failures[0]["source"] == "wikipedia"


def test_wikidata_403_falls_back_to_wikipedia(monkeypatch) -> None:
    service = WorldImportService()

    class Response:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            import httpx

            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "forbidden",
                    request=httpx.Request("GET", "https://example.test"),
                    response=httpx.Response(self.status_code),
                )

        def json(self):
            return self._payload

    class Client:
        def get(self, url, params=None):
            if "wikidata.org" in url:
                return Response(403, {})
            if params and params.get("action") == "opensearch":
                return Response(
                    200,
                    ["三国", ["刘备"], ["蜀汉人物"], ["https://zh.wikipedia.org/wiki/刘备"]],
                )
            return Response(403, {})

    errors = []
    failures = []
    result = service._search_wikidata(Client(), "三国", 20, errors, failures)
    assert result == []
    fallback = service._search_wikipedia(Client(), "三国", 20, errors, failures)
    assert fallback[0]["source_type"] == "wikipedia"
    assert fallback[0]["label"] == "刘备"

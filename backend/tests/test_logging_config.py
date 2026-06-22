import json
import logging

from app.logging_config import JsonFormatter


def test_json_log_redacts_credentials() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer token-secret api_key=key-secret",
        args=(),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert "token-secret" not in payload["message"]
    assert "key-secret" not in payload["message"]
    assert payload["message"].count("<redacted>") == 2

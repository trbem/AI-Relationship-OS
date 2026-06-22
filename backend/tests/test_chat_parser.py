from datetime import datetime

import pytest
from fastapi import HTTPException

from app.api.routes.chat import _resolve_contact_name
from app.services.chat_parser import ChatParserService


def test_parse_preserves_full_conversation() -> None:
    content = "\n".join(
        [
            "Alice: [2026-06-01 09:30] Please send the project update",
            "Me: [2026-06-01 09:31] I will send it this afternoon",
        ]
    )

    messages = ChatParserService().parse(content, "txt")

    assert [message.sender_name for message in messages] == ["Alice", "Me"]
    assert messages[0].content == "Please send the project update"
    assert messages[0].sent_at == datetime(2026, 6, 1, 9, 30)


def test_parse_skips_empty_messages() -> None:
    messages = ChatParserService().parse("Alice:\nMe: hello", "txt")

    assert len(messages) == 1
    assert messages[0].content == "hello"


def test_resolve_contact_name_excludes_self_alias() -> None:
    assert _resolve_contact_name(["Alice", "Me"], "owner@example.com") == "Alice"
    assert _resolve_contact_name(["Alice", "owner"], "owner@example.com") == "Alice"
    assert _resolve_contact_name(["小王", "小李"], "owner@example.com", "小李") == "小王"


def test_resolve_contact_name_rejects_ambiguous_group_chat() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _resolve_contact_name(["Alice", "Bob", "Me"], "owner@example.com")

    assert exc_info.value.status_code == 400


def test_resolve_contact_name_rejects_unknown_explicit_self_name() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _resolve_contact_name(["小王", "小李"], "owner@example.com", "小张")

    assert exc_info.value.status_code == 400
    assert "was not found" in exc_info.value.detail

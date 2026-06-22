from app.services.document_text_extractor import DocumentTextExtractor


def test_extracts_plain_text_without_touching_encoding() -> None:
    extracted = DocumentTextExtractor().extract(
        "chat.txt",
        "Alice: hello\nMe: hi".encode("utf-8"),
    )

    assert extracted.input_type == "text"
    assert extracted.format == "txt"
    assert "Alice" in extracted.text


def test_extracts_csv_as_text_when_already_decoded() -> None:
    extracted = DocumentTextExtractor().extract(
        "chat.csv",
        "sender,content\nAlice,hello".encode("utf-8"),
    )

    assert extracted.format == "csv"
    assert "Alice" in extracted.text


def test_plain_utf8_without_bom_reports_utf8() -> None:
    extracted = DocumentTextExtractor().extract(
        "chat.txt",
        "Alice: hello".encode("utf-8"),
    )
    assert extracted.encoding == "utf-8"


def test_gb18030_text_reports_gb18030() -> None:
    extracted = DocumentTextExtractor().extract(
        "chat.txt",
        "小王: 你好".encode("gb18030"),
    )
    assert extracted.encoding == "gb18030"


def test_image_metadata_fallback_extracts_text() -> None:
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + bytes(range(1, 32))
        + b"Description\x00Alice: hello from image"
    )
    extracted = DocumentTextExtractor().extract("screen.png", payload)
    assert extracted.input_type == "image"
    assert extracted.extraction_method == "image-metadata"
    assert "Alice" in extracted.text

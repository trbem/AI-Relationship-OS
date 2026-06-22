from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

TEXT_EXTENSIONS = {"txt", "csv", "json", "md", "markdown"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}


@dataclass
class ExtractedDocument:
    filename: str
    input_type: str
    format: str
    text: str
    encoding: str | None = None
    extraction_method: str = "text"
    warnings: list[str] = field(default_factory=list)


class DocumentTextExtractor:
    def extract(self, filename: str, raw_bytes: bytes) -> ExtractedDocument:
        clean_name = Path(filename or "upload.txt").name
        extension = clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else "txt"
        text_candidate = self._try_plain_text(raw_bytes)
        if text_candidate is not None:
            return ExtractedDocument(
                filename=clean_name,
                input_type="text",
                format=extension if extension in TEXT_EXTENSIONS else "txt",
                text=text_candidate[0],
                encoding=text_candidate[1],
                extraction_method="decode",
            )
        if extension in TEXT_EXTENSIONS:
            text, encoding = self._detect_text_encoding(raw_bytes)
            return ExtractedDocument(
                filename=clean_name,
                input_type="text",
                format="md" if extension == "markdown" else extension,
                text=text,
                encoding=encoding,
                extraction_method="decode",
            )
        if extension == "pdf":
            return self._extract_pdf(clean_name, raw_bytes)
        if extension in IMAGE_EXTENSIONS:
            return self._extract_image(clean_name, raw_bytes, extension)
        raise ValueError("Unsupported import file type")

    def _try_plain_text(self, raw_bytes: bytes) -> tuple[str, str] | None:
        if raw_bytes.startswith(b"%PDF"):
            return None
        encodings = ["utf-8", "gb18030"]
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            encodings.insert(0, "utf-8-sig")
        for encoding in encodings:
            try:
                text = raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
            if self._looks_like_text(text):
                return text, encoding
        return None

    def _looks_like_text(self, text: str) -> bool:
        if not text.strip():
            return False
        printable = sum(1 for char in text if char.isprintable() or char in "\n\r\t")
        return printable / max(len(text), 1) >= 0.85

    def _detect_text_encoding(self, raw_bytes: bytes) -> tuple[str, str]:
        candidates = []
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            candidates.append("utf-8-sig")
        if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            candidates.append("utf-16")
        candidates.extend(["utf-8", "gb18030"])
        for encoding in dict.fromkeys(candidates):
            try:
                return raw_bytes.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        raise ValueError("Unable to detect text encoding; convert the file to UTF-8 or GB18030")

    def _extract_pdf(self, filename: str, raw_bytes: bytes) -> ExtractedDocument:
        warnings: list[str] = []
        try:
            from pypdf import PdfReader  # type: ignore

            import io

            reader = PdfReader(io.BytesIO(raw_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return ExtractedDocument(
                    filename=filename,
                    input_type="pdf",
                    format="pdf",
                    text=text,
                    extraction_method="pypdf",
                    warnings=warnings,
                )
            warnings.append("PDF did not contain extractable text")
        except Exception:
            warnings.append("PDF text library unavailable or failed")

        text = self._best_effort_pdf_text(raw_bytes)
        if not text.strip():
            raise ValueError("PDF text extraction failed; OCR may be required")
        warnings.append("Used best-effort PDF text extraction")
        return ExtractedDocument(
            filename=filename,
            input_type="pdf",
            format="pdf",
            text=text,
            extraction_method="pdf-best-effort",
            warnings=warnings,
        )

    def _extract_image(self, filename: str, raw_bytes: bytes, extension: str) -> ExtractedDocument:
        warnings: list[str] = []
        try:
            from PIL import Image  # type: ignore
            import io
            import pytesseract  # type: ignore

            image = Image.open(io.BytesIO(raw_bytes))
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            if text.strip():
                return ExtractedDocument(
                    filename=filename,
                    input_type="image",
                    format=extension,
                    text=text,
                    extraction_method="ocr",
                )
            warnings.append("Image OCR completed but no text was recognized")
        except Exception:
            warnings.append(
                "Image OCR runtime unavailable; tried metadata text extraction instead"
            )
        text = self._extract_image_metadata(raw_bytes)
        if not text.strip():
            raise ValueError(
                "Image text extraction failed; install Pillow, pytesseract, and the Tesseract OCR executable for OCR"
            )
        return ExtractedDocument(
            filename=filename,
            input_type="image",
            format=extension,
            text=text,
            extraction_method="image-metadata",
            warnings=warnings,
        )

    def _extract_image_metadata(self, raw_bytes: bytes) -> str:
        decoded = raw_bytes.decode("latin-1", errors="ignore")
        candidates: list[str] = []
        for key in ("Description", "Comment", "Title", "Subject", "Keywords", "XML:com.adobe.xmp"):
            pattern = key + r"\x00?([^\x00\r\n]{4,500})"
            candidates.extend(re.findall(pattern, decoded, flags=re.I))
        candidates.extend(
            value
            for value in re.findall(r"<dc:description>[\s\S]*?<rdf:li[^>]*>([\s\S]*?)</rdf:li>", decoded)
        )
        cleaned = [
            re.sub(r"<[^>]+>", "", value).strip()
            for value in candidates
            if self._looks_like_text(value)
        ]
        return "\n".join(dict.fromkeys(cleaned))

    def _best_effort_pdf_text(self, raw_bytes: bytes) -> str:
        try:
            decoded = raw_bytes.decode("latin-1", errors="ignore")
        except UnicodeDecodeError:
            return ""
        fragments = re.findall(r"\(([^()]{2,})\)\s*Tj", decoded)
        fragments.extend(
            part for array in re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.S)
            for part in re.findall(r"\(([^()]{2,})\)", array)
        )
        cleaned = [self._decode_pdf_fragment(value) for value in fragments]
        return "\n".join(value for value in cleaned if value.strip())

    def _decode_pdf_fragment(self, value: str) -> str:
        return (
            value.replace(r"\(", "(")
            .replace(r"\)", ")")
            .replace(r"\\", "\\")
            .replace("\\n", "\n")
            .replace("\\r", "\n")
            .replace("\\t", "\t")
        )

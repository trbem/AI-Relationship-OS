from dataclasses import dataclass
from datetime import datetime
import csv
import json
import re


@dataclass
class ParsedMessage:
    sender_name: str
    content: str
    sent_at: datetime | None = None


class ChatParserService:
    supported_formats = {"txt", "csv", "json", "md", "whatsapp", "telegram"}

    def detect_format(self, filename: str) -> str:
        lowered = filename.lower()
        if lowered.endswith(".csv"):
            return "csv"
        if lowered.endswith(".json"):
            return "json"
        if lowered.endswith(".md") or lowered.endswith(".markdown"):
            return "md"
        if "whatsapp" in lowered:
            return "whatsapp"
        if "telegram" in lowered:
            return "telegram"
        return "txt"

    def parse(self, content: str, fmt: str) -> list[ParsedMessage]:
        if fmt not in self.supported_formats:
            raise ValueError(f"Unsupported format: {fmt}")

        if fmt == "csv":
            return self._parse_csv(content)
        if fmt == "json":
            return self._parse_json(content)

        messages: list[ParsedMessage] = []
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        for line in lines:
            if ":" not in line:
                continue

            sender, message = line.split(":", 1)
            sender = sender.strip() or "Unknown"
            message = message.strip()
            if not message:
                continue

            timestamp = self._extract_timestamp(message)
            normalized_message = self._strip_leading_timestamp(message)
            messages.append(
                ParsedMessage(sender_name=sender, content=normalized_message, sent_at=timestamp)
            )

        return messages

    def _parse_csv(self, content: str) -> list[ParsedMessage]:
        messages: list[ParsedMessage] = []
        rows = csv.reader(content.splitlines())
        for row in rows:
            if len(row) < 2:
                continue
            sender = row[0].strip() or "Unknown"
            message = row[1].strip()
            if not message:
                continue
            messages.append(ParsedMessage(sender_name=sender, content=message))
        return messages

    def _parse_json(self, content: str) -> list[ParsedMessage]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        items: list[dict] = []
        if isinstance(payload, list):
            items = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            candidate = payload.get("messages") or payload.get("data") or []
            if isinstance(candidate, list):
                items = [item for item in candidate if isinstance(item, dict)]
        messages: list[ParsedMessage] = []
        for item in items:
            sender = str(item.get("sender") or item.get("sender_name") or item.get("from") or "Unknown").strip()
            message = str(item.get("content") or item.get("message") or item.get("text") or "").strip()
            if not message:
                continue
            messages.append(ParsedMessage(sender_name=sender or "Unknown", content=message))
        return messages

    def _extract_timestamp(self, message: str) -> datetime | None:
        match = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*", message)
        if not match:
            return None
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")

    def _strip_leading_timestamp(self, message: str) -> str:
        return re.sub(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]\s*", "", message)

import hashlib
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import ImportTask, Message, Person, PersonMemory, User
from app.services.chat_parser import ChatParserService
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.relationship_event_service import RelationshipEventService
from app.vector.pgvector_store import VectorStore


def detect_text_encoding(raw_bytes: bytes) -> tuple[str, str]:
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
    raise ValueError("无法识别聊天文件编码，请转换为 UTF-8 或 GB18030 后重试")


def message_fingerprint(
    sender_name: str,
    content: str,
    sent_at: datetime | None,
) -> str:
    timestamp = sent_at.isoformat(timespec="minutes") if sent_at else ""
    normalized = "\x1f".join(
        [
            sender_name.strip().casefold(),
            " ".join(content.split()),
            timestamp,
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ImportTaskProcessor:
    def run(self, task_id: str) -> None:
        try:
            self._run(task_id)
        except Exception as exc:
            with SessionLocal() as db:
                task = db.get(ImportTask, task_id)
                if task:
                    message_ids = db.scalars(
                        select(Message.id).where(Message.import_task_id == task_id)
                    ).all()
                    if message_ids:
                        message_id_set = set(message_ids)
                        memories = db.scalars(
                            select(PersonMemory).where(
                                PersonMemory.person_id == task.person_id
                            )
                        ).all()
                        for memory in memories:
                            source_ids = set(
                                filter(None, (memory.source_message_ids or "").split(","))
                            )
                            if source_ids & message_id_set:
                                db.delete(memory)
                        db.execute(
                            delete(Message).where(Message.import_task_id == task_id)
                        )
                    person = db.get(Person, task.person_id) if task.person_id else None
                    db.flush()
                    has_messages = (
                        db.scalar(
                            select(Message.id)
                            .where(Message.person_id == task.person_id)
                            .limit(1)
                        )
                        is not None
                    )
                    has_memories = (
                        db.scalar(
                            select(PersonMemory.id)
                            .where(PersonMemory.person_id == task.person_id)
                            .limit(1)
                        )
                        is not None
                    )
                    if person and not has_messages and not has_memories:
                        task.person_id = None
                        db.delete(person)
                    task.imported_count = 0
                    task.status = "failed"
                    task.stage = "failed"
                    task.error = str(exc)[:2000]
                    db.commit()

    def _run(self, task_id: str) -> None:
        with SessionLocal() as db:
            task = db.get(ImportTask, task_id)
            if not task:
                return
            task.status = "running"
            task.stage = "parsing"
            task.progress = 10
            task.error = None
            task.attempts += 1
            path = Path(task.stored_path)
            filename = task.filename
            self_name = task.self_name
            original_encoding = task.encoding
            user = db.get(User, task.user_id)
            if not user:
                raise ValueError("导入任务所属用户不存在")
            user_email = user.email
            db.commit()

        extracted = DocumentTextExtractor().extract(filename, path.read_bytes())
        content = extracted.text
        encoding = original_encoding or extracted.encoding or extracted.extraction_method
        parser = ChatParserService()
        parsed = parser.parse(content, extracted.format if extracted.format in parser.supported_formats else parser.detect_format(filename))
        if not parsed:
            raise ValueError("未找到有效聊天消息")

        from app.api.routes.chat import _resolve_contact_name

        contact_name = _resolve_contact_name(
            [message.sender_name for message in parsed],
            user_email,
            self_name,
        )
        with SessionLocal() as db:
            task = db.get(ImportTask, task_id)
            task.encoding = encoding
            task.contact_name = contact_name
            task.parsed_count = len(parsed)
            task.stage = "persisting"
            task.progress = 30

            person = db.scalar(
                select(Person).where(
                    Person.user_id == task.user_id,
                    Person.name == contact_name,
                )
            )
            if not person:
                person = Person(user_id=task.user_id, name=contact_name)
                db.add(person)
                db.flush()
            task.person_id = person.id

            fingerprints = [
                message_fingerprint(item.sender_name, item.content, item.sent_at)
                for item in parsed
            ]
            existing = set(
                db.scalars(
                    select(Message.fingerprint).where(
                        Message.user_id == task.user_id,
                        Message.person_id == person.id,
                        Message.fingerprint.in_(fingerprints),
                    )
                ).all()
            )
            persisted: list[Message] = []
            for item, fingerprint in zip(parsed, fingerprints, strict=True):
                if fingerprint in existing:
                    continue
                message = Message(
                    user_id=task.user_id,
                    person_id=person.id,
                    sender_name=item.sender_name,
                    direction="inbound" if item.sender_name == contact_name else "outbound",
                    content=item.content,
                    sent_at=item.sent_at,
                    fingerprint=fingerprint,
                    import_task_id=task.id,
                )
                db.add(message)
                db.flush()
                persisted.append(message)
                existing.add(fingerprint)
            task.imported_count = len(persisted)
            task.duplicate_count = len(parsed) - len(persisted)
            new_message_ids = [item.id for item in persisted]
            new_contents = [item.content for item in persisted]
            new_sent_ats = [item.sent_at for item in persisted]
            db.commit()

        if new_message_ids:
            with SessionLocal() as db:
                task = db.get(ImportTask, task_id)
                task.stage = "memory"
                task.progress = 55
                db.commit()
            memory_payload = MemoryService().extract_memories(
                [
                    {"id": message_id, "content": content, "sent_at": sent_at}
                    for message_id, content, sent_at in zip(
                        new_message_ids, new_contents, new_sent_ats, strict=True
                    )
                ]
            )
            with SessionLocal() as db:
                task = db.get(ImportTask, task_id)
                task.stage = "vectorizing"
                task.progress = 80
                db.commit()
            settings = get_settings()
            embeddings = EmbeddingService().batch_embeddings(
                new_contents,
                model=settings.embedding_model,
            )
            with SessionLocal() as db:
                task = db.get(ImportTask, task_id)
                for memory in memory_payload:
                    db.add(
                        PersonMemory(
                            person_id=task.person_id,
                            event=memory["event"],
                            emotion=memory["emotion"],
                            importance=memory["importance"],
                            source_message_ids=memory.get("source_message_ids"),
                            timestamp=memory.get("timestamp"),
                        )
                    )
                VectorStore().upsert_message_vectors(
                    db,
                    task.person_id,
                    new_message_ids,
                    embeddings,
                )
                RelationshipEventService().extract_incremental(
                    db,
                    user_id=task.user_id,
                    person_id=task.person_id,
                    message_ids=new_message_ids,
                )
                db.commit()

        with SessionLocal() as db:
            task = db.get(ImportTask, task_id)
            task.status = "completed"
            task.stage = "completed"
            task.progress = 100
            db.commit()


def resume_incomplete_imports() -> None:
    with SessionLocal() as db:
        task_ids = db.scalars(
            select(ImportTask.id).where(
                ImportTask.status.in_(["queued", "running"])
            )
        ).all()
        if task_ids:
            db.query(ImportTask).filter(ImportTask.id.in_(task_ids)).update(
                {
                    ImportTask.status: "queued",
                    ImportTask.stage: "queued",
                    ImportTask.error: None,
                },
                synchronize_session=False,
            )
            db.commit()
    for task_id in task_ids:
        threading.Thread(
            target=ImportTaskProcessor().run,
            args=(task_id,),
            daemon=True,
            name=f"import-{task_id[:8]}",
        ).start()

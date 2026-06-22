import io
import json
import os
import struct
import zipfile
import zlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


MAGIC = b"ROSBACKUP"
CONTAINER_VERSION = 1
KDF_PBKDF2_SHA256 = 1
KDF_ITERATIONS = 600_000
SALT_SIZE = 16
NONCE_SIZE = 12
MAX_UPLOAD_SIZE = 200 * 1024 * 1024
MAX_PLAINTEXT_SIZE = 500 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
LEGACY_ENTRY = "relationship-os-backup.json"
HEADER = struct.Struct(">9sBBI16s12s")


class BackupError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedBackup:
    payload: object
    legacy_unencrypted: bool


def _derive_key(password: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
    ).derive(password.encode("utf-8"))


def create_encrypted_backup(payload: object, password: str) -> bytes:
    plaintext = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(plaintext) > MAX_PLAINTEXT_SIZE:
        raise BackupError("备份内容超过 500 MB")
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    header = HEADER.pack(
        MAGIC, CONTAINER_VERSION, KDF_PBKDF2_SHA256, KDF_ITERATIONS, salt, nonce
    )
    compressed = zlib.compress(plaintext, level=9)
    ciphertext = AESGCM(_derive_key(password, salt)).encrypt(nonce, compressed, header)
    return header + ciphertext


def _decompress_payload(compressed: bytes) -> bytes:
    try:
        decompressor = zlib.decompressobj()
        plaintext = decompressor.decompress(compressed, MAX_PLAINTEXT_SIZE + 1)
        if len(plaintext) > MAX_PLAINTEXT_SIZE or decompressor.unconsumed_tail:
            raise BackupError
        plaintext += decompressor.flush(MAX_PLAINTEXT_SIZE + 1 - len(plaintext))
        if (
            len(plaintext) > MAX_PLAINTEXT_SIZE
            or not decompressor.eof
            or decompressor.unused_data
        ):
            raise BackupError
        return plaintext
    except (BackupError, zlib.error) as exc:
        raise BackupError("无效的加密备份或密码错误") from exc


def _parse_encrypted(raw: bytes, password: str | None) -> object:
    # All container/authentication failures intentionally collapse to one error.
    try:
        if password is None or len(raw) < HEADER.size + 16:
            raise BackupError
        header = raw[: HEADER.size]
        magic, version, kdf_id, iterations, salt, nonce = HEADER.unpack(header)
        if (
            magic != MAGIC
            or version != CONTAINER_VERSION
            or kdf_id != KDF_PBKDF2_SHA256
            or iterations != KDF_ITERATIONS
        ):
            raise BackupError
        compressed = AESGCM(_derive_key(password, salt, iterations)).decrypt(
            nonce, raw[HEADER.size :], header
        )
        plaintext = _decompress_payload(compressed)
        return json.loads(plaintext.decode("utf-8"))
    except (BackupError, InvalidTag, UnicodeDecodeError, json.JSONDecodeError, struct.error) as exc:
        raise BackupError("无效的加密备份或密码错误") from exc


def _parse_legacy_zip(raw: bytes) -> object:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) != 1:
                raise BackupError("旧备份必须仅包含一个条目")
            info = infos[0]
            if info.filename != LEGACY_ENTRY or info.is_dir():
                raise BackupError("旧备份条目路径无效")
            if info.file_size > MAX_PLAINTEXT_SIZE:
                raise BackupError("备份内容超过 500 MB")
            if info.file_size and (
                info.compress_size == 0
                or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise BackupError("备份压缩比异常")
            data = archive.read(info)
            if len(data) != info.file_size:
                raise BackupError("备份内容不完整")
            return json.loads(data.decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("无效的旧版备份") from exc


def parse_backup(raw: bytes, password: str | None) -> ParsedBackup:
    if len(raw) > MAX_UPLOAD_SIZE:
        raise OverflowError("备份文件不能超过 200 MB")
    if raw.startswith(MAGIC):
        return ParsedBackup(_parse_encrypted(raw, password), False)
    return ParsedBackup(_parse_legacy_zip(raw), True)

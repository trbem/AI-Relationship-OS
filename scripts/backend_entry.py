"""PyInstaller entry point for the packaged Relationship OS backend."""

import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn


def _runtime_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1] / "backend"


def _configure_packaged_logs() -> None:
    if not getattr(sys, "frozen", False):
        return
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    log_directory = local_app_data / "RelationshipOS" / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_stream = (log_directory / "backend.log").open(
        "a", encoding="utf-8", buffering=1
    )
    sys.stdout = log_stream
    sys.stderr = log_stream


def _configure_packaged_version(runtime_directory: Path) -> None:
    if not getattr(sys, "frozen", False):
        return
    for candidate in (
        runtime_directory / "VERSION",
        runtime_directory.parent / "VERSION",
    ):
        if candidate.exists():
            version = candidate.read_text(encoding="ascii").strip()
            if version:
                os.environ.setdefault("APP_VERSION", version)
            break


def main() -> None:
    runtime_directory = _runtime_directory()
    os.chdir(runtime_directory)
    os.environ.setdefault("RELATIONSHIP_OS_PACKAGED", "1")
    _configure_packaged_version(runtime_directory)
    _configure_packaged_logs()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

import os
import shutil
import tempfile
from pathlib import Path


_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="relationship-os-tests-"))
os.environ["RELATIONSHIP_OS_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DATA_DIR / 'test.db').as_posix()}"
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_FALLBACK_ENABLED"] = "false"


def pytest_sessionfinish(session, exitstatus) -> None:
    from app.db import engine

    engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)

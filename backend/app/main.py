from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.db import init_db
from app.logging_config import configure_logging
from app.services.import_service import resume_incomplete_imports

settings = get_settings()
logger = logging.getLogger("relationship_os")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    resume_incomplete_imports()
    logger.info("Relationship OS backend started")
    yield
    logger.info("Relationship OS backend stopped")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = perf_counter()
    request_id = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started) * 1000,
        request_id,
    )
    return response


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "request_id": str(uuid4()),
    }

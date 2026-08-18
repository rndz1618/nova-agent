import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from .config import get_settings, Settings
from .routes import router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


def _default_rate_limit() -> str:
    try:
        n = get_settings().rate_limit_per_minute
        return f"{max(1, int(n))}/minute"
    except Exception:
        return "60/minute"


limiter = Limiter(key_func=get_remote_address, default_limits=[_default_rate_limit()])
_last_activity: float = time.time()


def touch_activity() -> None:
    global _last_activity
    _last_activity = time.time()


async def idle_watcher(settings: Settings) -> None:
    if settings.idle_timeout_minutes <= 0:
        return
    timeout = settings.idle_timeout_minutes * 60
    while True:
        await asyncio.sleep(30)
        idle_for = time.time() - _last_activity
        if idle_for >= timeout:
            logger.warning("idle_timeout_reached", idle_seconds=idle_for)
            raise SystemExit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task = asyncio.create_task(idle_watcher(settings))
    logger.info(
        "nova_agent_started",
        repo=str(settings.repo_path),
        host=settings.host,
        port=settings.port,
        idle_timeout=settings.idle_timeout_minutes,
    )
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("nova_agent_stopped")


app = FastAPI(
    title="Nova Agent",
    description="Secure remote maintenance agent for local Git repositories",
    version="1.2.2",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def activity_middleware(request: Request, call_next):
    touch_activity()
    return await call_next(request)


app.include_router(router)

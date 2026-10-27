import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, health, webhook
from app.config import Settings, get_settings
from app.db import make_engine, make_sessionmaker
from app.logging_config import configure_logging, request_id_var
from app.queue import ArqQueue
from app.services.rate_limit import SlidingWindowLimiter

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, queue=None, sessionmaker=None) -> FastAPI:
    """Build the app. Tests pass their own settings / queue / sessionmaker."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        if not settings.github_webhook_secret:
            raise RuntimeError("GITHUB_WEBHOOK_SECRET must be set - refusing to start unsigned")
        engine = None
        created_queue = False
        if app.state.sessionmaker is None:
            engine = make_engine(settings.database_url)
            app.state.sessionmaker = make_sessionmaker(engine)
        if app.state.queue is None:
            app.state.queue = await ArqQueue.connect(settings.redis_url)
            created_queue = True
        log.info("api started", extra={"environment": settings.environment})
        yield
        if created_queue:
            await app.state.queue.close()
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="PR Review Assistant", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://pr-review-assistant-frontend.getvoroa.com",
        ],
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.state.settings = settings
    app.state.queue = queue
    app.state.sessionmaker = sessionmaker
    app.state.limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    app.include_router(health.router)
    app.include_router(webhook.router)
    app.include_router(admin.router)
    return app


app = create_app()

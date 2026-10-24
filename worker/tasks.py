"""ARQ worker. Run with:  arq worker.tasks.WorkerSettings"""

import httpx
from arq.connections import RedisSettings

from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.logging_config import configure_logging
from app.services.github_auth import build_token_provider
from app.services.job_runner import handle_job
from app.services.llm_client import build_llm_client

settings = get_settings()


async def startup(ctx: dict) -> None:
    configure_logging(settings.log_level)
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    ctx["http"] = httpx.AsyncClient(timeout=30)
    ctx["tokens"] = build_token_provider(settings, ctx["http"])
    ctx["llm"] = build_llm_client(settings, ctx["http"])


async def shutdown(ctx: dict) -> None:
    await ctx["http"].aclose()
    await ctx["engine"].dispose()


async def process_review(ctx: dict, job_id: int) -> str:
    return await handle_job(
        job_id,
        sessionmaker=ctx["sessionmaker"],
        settings=settings,
        tokens=ctx["tokens"],
        http=ctx["http"],
        llm=ctx["llm"],
        job_try=ctx.get("job_try", 1),
    )


class WorkerSettings:
    functions = [process_review]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = settings.max_job_attempts
    job_timeout = 300
    keep_result = 3600
    max_jobs = 10

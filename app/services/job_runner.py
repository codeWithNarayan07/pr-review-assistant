"""Runs one queued job: status bookkeeping, retries with backoff, final failure."""

import logging

import httpx
from arq import Retry
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.errors import ReviewError
from app.logging_config import job_id_var
from app.models import JobStatus, ReviewJob, utcnow
from app.services.github_client import GitHubClient
from app.services.review_pipeline import run_review

log = logging.getLogger(__name__)


def backoff_seconds(attempt: int) -> int:
    return min(15 * 2**attempt, 900)  # 30s, 60s, 120s, ... capped at 15 min


async def _set(sessionmaker: async_sessionmaker, job_id: int, **values) -> None:
    async with sessionmaker() as session:
        await session.execute(update(ReviewJob).where(ReviewJob.id == job_id).values(**values))
        await session.commit()


async def handle_job(
    job_id: int,
    *,
    sessionmaker: async_sessionmaker,
    settings: Settings,
    tokens,
    http: httpx.AsyncClient,
    llm,
    job_try: int = 1,
) -> str:
    job_id_var.set(job_id)
    async with sessionmaker() as session:
        job = await session.get(ReviewJob, job_id)
        if job is None:
            log.warning("job not found")
            return "missing"
        if job.status in (JobStatus.done.value, JobStatus.skipped.value):
            return job.status  # duplicate queue message: nothing to do
        installation_id = job.installation_id

    await _set(
        sessionmaker,
        job_id,
        status=JobStatus.processing.value,
        attempts=job_try,
        started_at=utcnow(),
    )
    final_attempt = job_try >= settings.max_job_attempts
    try:
        async with sessionmaker() as session:
            job = await session.get(ReviewJob, job_id)
            token = await tokens.get_token(installation_id)
            gh = GitHubClient(http, settings.github_api_url, token)
            outcome = await run_review(job, session, gh, llm, settings, final_attempt=final_attempt)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
        retryable = exc.retryable if isinstance(exc, ReviewError) else True
        message = f"{type(exc).__name__}: {exc}"[:2000]
        if retryable and not final_attempt:
            log.warning("job failed, will retry", extra={"attempt": job_try, "error": message})
            await _set(sessionmaker, job_id, status=JobStatus.pending.value, error=message)
            raise Retry(defer=backoff_seconds(job_try)) from exc
        log.error("job failed permanently", extra={"attempt": job_try, "error": message})
        await _set(
            sessionmaker, job_id, status=JobStatus.failed.value, error=message, finished_at=utcnow()
        )
        return "failed"

    status = JobStatus.skipped if outcome.startswith("skipped") else JobStatus.done
    await _set(
        sessionmaker, job_id, status=status.value, result=outcome, error=None, finished_at=utcnow()
    )
    log.info("job finished", extra={"outcome": outcome})
    return outcome

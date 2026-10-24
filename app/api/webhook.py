import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_queue, get_session, get_settings_dep
from app.models import ReviewJob, WebhookDelivery
from app.schemas import PullRequestEvent
from app.services.security import verify_signature

log = logging.getLogger(__name__)
router = APIRouter()

HANDLED_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


@router.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    queue=Depends(get_queue),
    settings=Depends(get_settings_dep),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
):
    client_ip = request.client.host if request.client else "unknown"
    if not request.app.state.limiter.allow(client_ip):
        raise HTTPException(429, "Too many requests")

    body = await request.body()  # the signature covers the raw bytes, so read them untouched
    if not verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
        log.warning("rejected webhook with bad signature", extra={"client": client_ip})
        raise HTTPException(401, "Invalid signature")
    if not x_github_event or not x_github_delivery:
        raise HTTPException(400, "Missing GitHub headers")

    if x_github_event == "ping":
        return {"status": "pong"}
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": "event_type"}

    try:
        event = PullRequestEvent.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(400, "Unexpected pull_request payload") from exc

    if event.action not in HANDLED_ACTIONS:
        return {"status": "ignored", "reason": "action"}
    repo = event.repository.full_name
    allowed = settings.allowed_repo_set
    if allowed and repo.lower() not in allowed:
        return {"status": "ignored", "reason": "repo_not_allowed"}
    if event.pull_request.draft and settings.skip_draft_prs:
        return {"status": "ignored", "reason": "draft"}

    pr = event.pull_request
    key = f"{repo.lower()}#{pr.number}@{pr.head.sha}"

    # 1) never process the same delivery twice
    delivery = WebhookDelivery(
        delivery_id=x_github_delivery, event=x_github_event, action=event.action
    )
    session.add(delivery)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return {"status": "duplicate", "reason": "delivery"}

    # 2) one job per PR commit, even if GitHub sends different deliveries for it
    job = ReviewJob(
        idempotency_key=key,
        repo_full_name=repo,
        pr_number=pr.number,
        head_sha=pr.head.sha,
        installation_id=event.installation.id if event.installation else None,
        delivery_id=x_github_delivery,
    )
    try:
        async with session.begin_nested():
            session.add(job)
            await session.flush()
    except IntegrityError:
        await session.commit()
        return {"status": "duplicate", "reason": "commit_already_queued"}
    await session.commit()

    try:
        await queue.enqueue_review(job.id)
    except Exception:
        # Undo, so GitHub's "redeliver" button works once the queue is back.
        log.exception("enqueue failed")
        await session.delete(await session.get(ReviewJob, job.id))
        await session.delete(await session.get(WebhookDelivery, delivery.id))
        await session.commit()
        raise HTTPException(503, "Queue unavailable, please retry") from None

    log.info("queued review", extra={"repo": repo, "pr": pr.number, "job": job.id})
    return {"status": "queued", "job_id": job.id}

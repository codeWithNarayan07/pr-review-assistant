import json
import uuid

from sqlalchemy import func, select

from app.models import ReviewJob, WebhookDelivery
from app.services.security import sign
from tests.conftest import SECRET


def payload(action="opened", sha="sha1111111", number=1, repo="acme/shop", draft=False):
    return {
        "action": action,
        "pull_request": {"number": number, "draft": draft, "head": {"sha": sha}},
        "repository": {"full_name": repo},
        "installation": {"id": 42},
    }


async def post(client, body, *, event="pull_request", delivery=None, secret=SECRET, sig=None):
    raw = json.dumps(body).encode()
    return await client.post(
        "/webhook/github",
        content=raw,
        headers={
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery or str(uuid.uuid4()),
            "X-Hub-Signature-256": sig or sign(secret, raw),
            "Content-Type": "application/json",
        },
    )


async def count(sessionmaker, model):
    async with sessionmaker() as s:
        return await s.scalar(select(func.count()).select_from(model))


async def test_bad_signature_is_rejected(client, queue, sessionmaker):
    resp = await post(client, payload(), secret="wrong")
    assert resp.status_code == 401
    assert queue.jobs == [] and await count(sessionmaker, ReviewJob) == 0


async def test_missing_signature_is_rejected(client):
    raw = json.dumps(payload()).encode()
    resp = await client.post(
        "/webhook/github",
        content=raw,
        headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "d1"},
    )
    assert resp.status_code == 401


async def test_ping_returns_pong(client):
    resp = await post(client, {"zen": "hi"}, event="ping")
    assert resp.status_code == 202 and resp.json() == {"status": "pong"}


async def test_other_events_and_actions_are_ignored(client, queue):
    assert (await post(client, {"x": 1}, event="push")).json()["reason"] == "event_type"
    assert (await post(client, payload(action="closed"))).json()["reason"] == "action"
    assert (await post(client, payload(action="labeled"))).json()["reason"] == "action"
    assert queue.jobs == []


async def test_opened_pr_creates_job_and_enqueues(client, queue, sessionmaker):
    resp = await post(client, payload())
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"
    assert queue.jobs == [resp.json()["job_id"]]
    async with sessionmaker() as s:
        job = await s.get(ReviewJob, resp.json()["job_id"])
    assert (job.repo_full_name, job.pr_number, job.head_sha) == ("acme/shop", 1, "sha1111111")
    assert job.installation_id == 42 and job.status == "pending"


async def test_redelivery_of_same_delivery_id_is_ignored(client, queue, sessionmaker):
    await post(client, payload(), delivery="same-id")
    resp = await post(client, payload(), delivery="same-id")
    assert resp.json() == {"status": "duplicate", "reason": "delivery"}
    assert len(queue.jobs) == 1 and await count(sessionmaker, ReviewJob) == 1


async def test_same_commit_from_a_different_delivery_makes_one_job(client, queue, sessionmaker):
    await post(client, payload())
    resp = await post(client, payload(action="reopened"))
    assert resp.json()["reason"] == "commit_already_queued"
    assert len(queue.jobs) == 1 and await count(sessionmaker, ReviewJob) == 1


async def test_new_commit_creates_a_new_job(client, queue):
    await post(client, payload(sha="aaaaaaa"))
    await post(client, payload(action="synchronize", sha="bbbbbbb"))
    assert len(queue.jobs) == 2


async def test_allowed_repos_filter(client, queue, settings):
    settings.allowed_repos = "acme/shop"
    assert (await post(client, payload(repo="evil/repo"))).json()["reason"] == "repo_not_allowed"
    assert (await post(client, payload(repo="ACME/Shop"))).json()["status"] == "queued"
    assert len(queue.jobs) == 1


async def test_draft_prs_are_skipped(client, queue):
    assert (await post(client, payload(draft=True))).json()["reason"] == "draft"
    assert queue.jobs == []


async def test_malformed_payload_is_400(client):
    assert (await post(client, {"action": "opened"})).status_code == 400


async def test_queue_outage_returns_503_and_allows_redelivery(client, queue, sessionmaker):
    queue.fail = True
    resp = await post(client, payload(), delivery="d-1")
    assert resp.status_code == 503
    assert await count(sessionmaker, ReviewJob) == 0
    assert await count(sessionmaker, WebhookDelivery) == 0

    queue.fail = False  # queue is back; GitHub redelivers the same delivery id
    resp = await post(client, payload(), delivery="d-1")
    assert resp.json()["status"] == "queued"


async def test_rate_limit(client, settings):
    client._transport.app.state.limiter.limit = 2
    codes = [(await post(client, payload(), event="ping")).status_code for _ in range(3)]
    assert codes == [202, 202, 429]

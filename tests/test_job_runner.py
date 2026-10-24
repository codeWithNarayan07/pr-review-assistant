import pytest
from arq import Retry
from sqlalchemy import select

from app.models import BotComment, ReviewJob
from app.services.formatter import MARKER
from app.services.job_runner import backoff_seconds, handle_job
from tests.fakes import FakeLLM


async def make_job(sessionmaker, sha="sha1111111", pr=1):
    async with sessionmaker() as s:
        job = ReviewJob(
            idempotency_key=f"acme/shop#{pr}@{sha}",
            repo_full_name="acme/shop",
            pr_number=pr,
            head_sha=sha,
        )
        s.add(job)
        await s.commit()
        return job.id


async def run(job_id, sessionmaker, settings, github, tokens, llm, job_try=1):
    return await handle_job(
        job_id,
        sessionmaker=sessionmaker,
        settings=settings,
        tokens=tokens,
        http=github.client(),
        llm=llm,
        job_try=job_try,
    )


async def get_job(sessionmaker, job_id):
    async with sessionmaker() as s:
        return await s.get(ReviewJob, job_id)


async def test_happy_path_posts_one_comment(sessionmaker, settings, github, tokens, llm):
    job_id = await make_job(sessionmaker)
    assert await run(job_id, sessionmaker, settings, github, tokens, llm) == "commented"

    assert len(github.bodies) == 1
    body = github.bodies[0]
    assert body.startswith(MARKER)
    assert "Adds rate limiting" in body  # from the LLM
    assert "authentication" in body  # from the rules
    assert "- [ ]" in body
    job = await get_job(sessionmaker, job_id)
    assert (job.status, job.result, job.attempts) == ("done", "commented", 1)


async def test_noise_files_never_reach_the_llm(sessionmaker, settings, github, tokens, llm):
    job_id = await make_job(sessionmaker)
    await run(job_id, sessionmaker, settings, github, tokens, llm)
    sent = llm.calls[0]
    assert "app/auth/login.py" in sent.diff_text
    assert "package-lock.json" not in sent.diff_text


async def test_secrets_are_redacted_before_the_llm_and_flagged(
    sessionmaker, settings, github, tokens, llm
):
    github.files[0]["patch"] = "+AWS = 'AKIAIOSFODNN7EXAMPLE'\n"
    job_id = await make_job(sessionmaker)
    await run(job_id, sessionmaker, settings, github, tokens, llm)
    assert "AKIAIOSFODNN7EXAMPLE" not in llm.calls[0].diff_text
    assert "AKIAIOSFODNN7EXAMPLE" not in github.bodies[0]
    assert "secret" in github.bodies[0].lower()


async def test_same_job_delivered_twice_comments_once(sessionmaker, settings, github, tokens, llm):
    job_id = await make_job(sessionmaker)
    await run(job_id, sessionmaker, settings, github, tokens, llm)
    assert await run(job_id, sessionmaker, settings, github, tokens, llm) == "done"
    assert len(github.comments) == 1 and len(llm.calls) == 1


async def test_new_commit_updates_the_same_comment(sessionmaker, settings, github, tokens, llm):
    first = await make_job(sessionmaker, "sha1111111")
    await run(first, sessionmaker, settings, github, tokens, llm)

    github.pr["head"]["sha"] = "sha2222222"
    second = await make_job(sessionmaker, "sha2222222")
    assert await run(second, sessionmaker, settings, github, tokens, llm) == "updated"

    assert len(github.comments) == 1
    assert "sha2222" in github.bodies[0]
    async with sessionmaker() as s:
        rows = (await s.scalars(select(BotComment))).all()
    assert len(rows) == 1 and rows[0].last_head_sha == "sha2222222"


async def test_comment_deleted_by_a_human_is_recreated(sessionmaker, settings, github, tokens, llm):
    await run(await make_job(sessionmaker), sessionmaker, settings, github, tokens, llm)
    github.comments.clear()
    github.pr["head"]["sha"] = "sha2222222"
    out = await run(
        await make_job(sessionmaker, "sha2222222"), sessionmaker, settings, github, tokens, llm
    )
    assert out == "commented" and len(github.comments) == 1


async def test_existing_comment_found_by_marker_when_db_lost_track(
    sessionmaker, settings, github, tokens, llm
):
    github.comments[7] = {"id": 7, "body": f"{MARKER} old text"}
    out = await run(await make_job(sessionmaker), sessionmaker, settings, github, tokens, llm)
    assert out == "updated" and list(github.comments) == [7]
    assert "old text" not in github.comments[7]["body"]


async def test_superseded_closed_and_disabled_prs_are_skipped(
    sessionmaker, settings, github, tokens, llm
):
    github.pr["head"]["sha"] = "newer"
    job_id = await make_job(sessionmaker)
    assert await run(job_id, sessionmaker, settings, github, tokens, llm) == "skipped:superseded"

    github.pr.update(head={"sha": "sha3333333"}, state="closed")
    out = await run(
        await make_job(sessionmaker, "sha3333333"), sessionmaker, settings, github, tokens, llm
    )
    assert out == "skipped:closed"

    github.pr.update(head={"sha": "sha4444444"}, state="open")
    github.config_yaml = "enabled: false\n"
    out = await run(
        await make_job(sessionmaker, "sha4444444"), sessionmaker, settings, github, tokens, llm
    )
    assert out == "skipped:disabled"
    assert github.comments == {} and llm.calls == []
    assert (await get_job(sessionmaker, job_id)).status == "skipped"


async def test_repo_config_adds_rules_checklist_and_ignores(
    sessionmaker, settings, github, tokens, llm
):
    github.config_yaml = (
        "ignore_paths: ['app/auth/*']\n"
        "extra_checklist: ['Update the changelog']\n"
        "custom_risks:\n  - {pattern: 'app/*', message: 'Owned by platform team'}\n"
    )
    github.files.append(
        {
            "filename": "app/core.py",
            "status": "modified",
            "additions": 3,
            "deletions": 0,
            "patch": "+y",
        }
    )
    await run(await make_job(sessionmaker), sessionmaker, settings, github, tokens, llm)
    body = github.bodies[0]
    assert "Update the changelog" in body and "Owned by platform team" in body
    assert "app/auth/login.py" not in llm.calls[0].diff_text


async def test_invalid_repo_config_falls_back_to_defaults(
    sessionmaker, settings, github, tokens, llm
):
    github.config_yaml = "enabled: [this is not valid\n"
    out = await run(await make_job(sessionmaker), sessionmaker, settings, github, tokens, llm)
    assert out == "commented"


async def test_llm_failure_retries_then_succeeds(sessionmaker, settings, github, tokens):
    job_id = await make_job(sessionmaker)
    llm = FakeLLM(fail_times=1)
    with pytest.raises(Retry) as exc:
        await run(job_id, sessionmaker, settings, github, tokens, llm, job_try=1)
    assert exc.value.defer_score == backoff_seconds(1) * 1000
    job = await get_job(sessionmaker, job_id)
    assert job.status == "pending" and "LLMError" in job.error and github.comments == {}

    assert await run(job_id, sessionmaker, settings, github, tokens, llm, job_try=2) == "commented"
    assert (await get_job(sessionmaker, job_id)).attempts == 2


async def test_final_attempt_posts_rule_based_comment_when_llm_is_down(
    sessionmaker, settings, github, tokens
):
    job_id = await make_job(sessionmaker)
    llm = FakeLLM(fail_times=99)
    out = await run(
        job_id, sessionmaker, settings, github, tokens, llm, job_try=settings.max_job_attempts
    )
    assert out == "commented"
    assert "AI summary was unavailable" in github.bodies[0]
    assert "authentication" in github.bodies[0]


async def test_permanent_github_error_fails_without_retry(
    sessionmaker, settings, github, tokens, llm
):
    github.fail_status = 404
    job_id = await make_job(sessionmaker)
    assert await run(job_id, sessionmaker, settings, github, tokens, llm) == "failed"
    job = await get_job(sessionmaker, job_id)
    assert job.status == "failed" and "404" in job.error and job.finished_at


async def test_transient_github_error_retries_then_fails_at_the_limit(
    sessionmaker, settings, github, tokens, llm
):
    github.fail_status = 503
    job_id = await make_job(sessionmaker)
    with pytest.raises(Retry):
        await run(job_id, sessionmaker, settings, github, tokens, llm, job_try=1)
    out = await run(
        job_id, sessionmaker, settings, github, tokens, llm, job_try=settings.max_job_attempts
    )
    assert out == "failed"
    assert (await get_job(sessionmaker, job_id)).status == "failed"


async def test_without_llm_the_bot_still_posts_rule_based_findings(
    sessionmaker, settings, github, tokens
):
    from app.services.llm_client import NullLLMClient

    out = await run(
        await make_job(sessionmaker), sessionmaker, settings, github, tokens, NullLLMClient()
    )
    assert out == "commented"
    assert "This PR changes" in github.bodies[0] and "authentication" in github.bodies[0]


async def test_missing_job_is_a_noop(sessionmaker, settings, github, tokens, llm):
    assert await run(9999, sessionmaker, settings, github, tokens, llm) == "missing"


def test_backoff_grows_and_is_capped():
    assert backoff_seconds(1) < backoff_seconds(2) < backoff_seconds(3)
    assert backoff_seconds(50) == 900

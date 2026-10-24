import httpx
import pytest

from app.errors import GitHubError
from app.services.github_client import GitHubClient


def make(github):
    return GitHubClient(github.client(), "https://api.github.test", "tok")


async def test_pagination_collects_all_files(github):
    github.files = [
        {"filename": f"f{i}.py", "status": "added", "additions": 1, "deletions": 0, "patch": "+x"}
        for i in range(250)
    ]
    files, truncated = await make(github).list_pull_files("o/r", 1, max_files=1000)
    assert len(files) == 250 and not truncated


async def test_pagination_stops_at_limit_and_reports_truncation(github):
    github.files = [
        {"filename": f"f{i}.py", "status": "added", "additions": 1, "deletions": 0}
        for i in range(250)
    ]
    files, truncated = await make(github).list_pull_files("o/r", 1, max_files=200)
    assert len(files) == 200 and truncated


async def test_error_statuses_have_correct_retryability(github):
    for status, retryable in ((500, True), (502, True), (429, True), (404, False), (401, False)):
        github.fail_status = status
        with pytest.raises(GitHubError) as exc:
            await make(github).get_pull("o/r", 1)
        assert exc.value.retryable is retryable


async def test_network_errors_are_retryable():
    def boom(request):
        raise httpx.ConnectError("no route")

    client = GitHubClient(httpx.AsyncClient(transport=httpx.MockTransport(boom)), "http://x", "t")
    with pytest.raises(GitHubError) as exc:
        await client.get_pull("o/r", 1)
    assert exc.value.retryable


async def test_update_missing_comment_returns_false(github):
    assert await make(github).update_comment("o/r", 999, "body") is False


async def test_find_comment_by_marker(github):
    gh = make(github)
    await gh.create_comment("o/r", 1, "hello")
    cid = await gh.create_comment("o/r", 1, "<!-- m --> mine")
    assert await gh.find_comment_with_marker("o/r", 1, "<!-- m -->") == cid
    assert await gh.find_comment_with_marker("o/r", 1, "<!-- other -->") is None

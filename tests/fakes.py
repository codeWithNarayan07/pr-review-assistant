"""Test doubles: a fake GitHub API (via httpx.MockTransport), a fake LLM and a fake queue."""

import base64
import json
import re

import httpx

from app.errors import LLMError
from app.schemas import LLMReview, ReviewContext


class FakeGitHub:
    def __init__(self):
        self.pr = {
            "number": 1,
            "state": "open",
            "title": "Add login rate limiting",
            "body": "Limits login attempts.",
            "head": {"sha": "sha1111111"},
        }
        self.files = [
            {
                "filename": "app/auth/login.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
                "patch": "@@ -1,3 +1,5 @@\n+attempts = 0\n",
            },
            {
                "filename": "package-lock.json",
                "status": "modified",
                "additions": 500,
                "deletions": 400,
                "patch": "@@ lock @@",
            },
        ]
        self.comments: dict[int, dict] = {}
        self.next_id = 100
        self.config_yaml: str | None = None
        self.fail_status: int | None = None
        self.requests: list[tuple[str, str]] = []

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.requests.append((method, path))
        if self.fail_status:
            return httpx.Response(self.fail_status, json={"message": "boom"})

        if m := re.fullmatch(r"/repos/[^/]+/[^/]+/pulls/\d+", path):
            return httpx.Response(200, json=self.pr)
        if re.fullmatch(r"/repos/[^/]+/[^/]+/pulls/\d+/files", path):
            page = int(request.url.params.get("page", 1))
            per = int(request.url.params.get("per_page", 100))
            return httpx.Response(200, json=self.files[(page - 1) * per : page * per])
        if re.fullmatch(r"/repos/[^/]+/[^/]+/contents/.+", path):
            if self.config_yaml is None:
                return httpx.Response(404, json={"message": "Not Found"})
            content = base64.b64encode(self.config_yaml.encode()).decode()
            return httpx.Response(200, json={"encoding": "base64", "content": content})
        if re.fullmatch(r"/repos/[^/]+/[^/]+/issues/\d+/comments", path):
            if method == "GET":
                page = int(request.url.params.get("page", 1))
                return httpx.Response(200, json=list(self.comments.values()) if page == 1 else [])
            self.next_id += 1
            self.comments[self.next_id] = {"id": self.next_id, **json.loads(request.content)}
            return httpx.Response(201, json=self.comments[self.next_id])
        if m := re.fullmatch(r"/repos/[^/]+/[^/]+/issues/comments/(\d+)", path):
            cid = int(m.group(1))
            if cid not in self.comments:
                return httpx.Response(404, json={"message": "Not Found"})
            self.comments[cid].update(json.loads(request.content))
            return httpx.Response(200, json=self.comments[cid])
        return httpx.Response(500, json={"message": f"unhandled {method} {path}"})

    @property
    def bodies(self) -> list[str]:
        return [c["body"] for c in self.comments.values()]


class FakeLLM:
    def __init__(self, review: LLMReview | None = None, fail_times: int = 0):
        self.review_result = review or LLMReview(
            summary="Adds rate limiting to the login flow.",
            key_changes=["Counts failed attempts"],
            risks=["Counter is stored in memory only"],
            checklist=["Check lockout resets"],
        )
        self.fail_times = fail_times
        self.calls: list[ReviewContext] = []

    async def review(self, ctx: ReviewContext) -> LLMReview:
        self.calls.append(ctx)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise LLMError("temporary LLM failure")
        return self.review_result


class FakeTokens:
    async def get_token(self, installation_id):
        return "test-token"


class FakeQueue:
    def __init__(self, fail: bool = False):
        self.jobs: list[int] = []
        self.fail = fail

    async def enqueue_review(self, job_id: int) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.jobs.append(job_id)

    async def ping(self) -> bool:
        return not self.fail

    async def close(self) -> None:
        pass

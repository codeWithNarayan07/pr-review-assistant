"""Minimal GitHub REST client: only the calls this bot needs."""

import base64

import httpx

from app.errors import GitHubError
from app.schemas import FileChange


class GitHubClient:
    def __init__(self, http: httpx.AsyncClient, api_url: str, token: str):
        self.http = http
        self.base = api_url.rstrip("/")
        self.token = token

    async def _request(self, method: str, path: str, *, allow_404: bool = False, **kwargs):
        try:
            resp = await self.http.request(
                method,
                f"{self.base}{path}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub request failed: {exc}") from exc
        if resp.status_code == 404 and allow_404:
            return None
        if resp.status_code >= 400:
            raise GitHubError(f"GitHub {method} {path} -> {resp.status_code}", resp.status_code)
        return resp

    async def get_pull(self, repo: str, number: int) -> dict:
        resp = await self._request("GET", f"/repos/{repo}/pulls/{number}")
        return resp.json()

    async def list_pull_files(
        self, repo: str, number: int, max_files: int
    ) -> tuple[list[FileChange], bool]:
        """Return (files, truncated). Walks the paginated endpoint up to `max_files`."""
        files: list[FileChange] = []
        page = 1
        while len(files) < max_files:
            resp = await self._request(
                "GET",
                f"/repos/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            batch = resp.json()
            files.extend(
                FileChange(
                    path=item["filename"],
                    status=item.get("status", "modified"),
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    patch=item.get("patch"),
                )
                for item in batch
            )
            if len(batch) < 100:
                return files, False
            page += 1
        return files[:max_files], True

    async def get_file_content(self, repo: str, path: str, ref: str) -> str | None:
        resp = await self._request(
            "GET", f"/repos/{repo}/contents/{path}", params={"ref": ref}, allow_404=True
        )
        if resp is None:
            return None
        data = resp.json()
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return None

    async def find_comment_with_marker(self, repo: str, number: int, marker: str) -> int | None:
        """Look for our existing comment (used if the database lost track of it)."""
        for page in range(1, 11):
            resp = await self._request(
                "GET",
                f"/repos/{repo}/issues/{number}/comments",
                params={"per_page": 100, "page": page},
            )
            batch = resp.json()
            for comment in batch:
                if marker in (comment.get("body") or ""):
                    return comment["id"]
            if len(batch) < 100:
                return None
        return None

    async def create_comment(self, repo: str, number: int, body: str) -> int:
        resp = await self._request(
            "POST", f"/repos/{repo}/issues/{number}/comments", json={"body": body}
        )
        return resp.json()["id"]

    async def update_comment(self, repo: str, comment_id: int, body: str) -> bool:
        """Return False if the comment no longer exists (deleted by a human)."""
        resp = await self._request(
            "PATCH",
            f"/repos/{repo}/issues/comments/{comment_id}",
            json={"body": body},
            allow_404=True,
        )
        return resp is not None

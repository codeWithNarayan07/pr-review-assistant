"""A tiny fake of the GitHub REST API, for trying the bot offline.

Run:  uvicorn scripts.fake_github:app --port 9000
Then point the bot at it with  GITHUB_API_URL=http://localhost:9000
See what the bot posted at  http://localhost:9000/_debug/comments
"""

import itertools

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Fake GitHub")

DEMO_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
state = {"sha": DEMO_SHA, "comments": {}, "ids": itertools.count(1001)}

FILES = [
    {
        "filename": "app/auth/login.py",
        "status": "modified",
        "additions": 12,
        "deletions": 3,
        "patch": (
            "@@ -10,6 +10,15 @@ def login(user, password):\n"
            "-    return check(user, password)\n"
            "+    token = issue_token(user)\n"
            "+    AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
            "+    return token\n"
        ),
    },
    {
        "filename": "migrations/versions/0007_add_last_login.py",
        "status": "added",
        "additions": 20,
        "deletions": 0,
        "patch": (
            "@@ -0,0 +1,20 @@\n+def upgrade():\n"
            "+    op.add_column('users', sa.Column('last_login', sa.DateTime()))\n"
        ),
    },
    {
        "filename": "requirements.txt",
        "status": "modified",
        "additions": 1,
        "deletions": 0,
        "patch": "@@ -3,0 +4 @@\n+pyjwt==2.9.0\n",
    },
    {
        "filename": "package-lock.json",
        "status": "modified",
        "additions": 900,
        "deletions": 40,
        "patch": "@@ huge lock file change @@",
    },
]


@app.get("/repos/{owner}/{repo}/pulls/{number}")
def get_pull(owner: str, repo: str, number: int):
    return {
        "number": number,
        "state": "open",
        "title": "Add last-login tracking",
        "body": "Stores the last login time for each user.",
        "head": {"sha": state["sha"]},
    }


@app.get("/repos/{owner}/{repo}/pulls/{number}/files")
def list_files(owner: str, repo: str, number: int, page: int = 1, per_page: int = 100):
    return FILES if page == 1 else []


@app.get("/repos/{owner}/{repo}/contents/{path:path}")
def get_contents(owner: str, repo: str, path: str):
    raise HTTPException(404, "Not Found")  # no .pr-assistant.yml in the demo repo


@app.get("/repos/{owner}/{repo}/issues/{number}/comments")
def list_comments(owner: str, repo: str, number: int, page: int = 1):
    return list(state["comments"].values()) if page == 1 else []


@app.post("/repos/{owner}/{repo}/issues/{number}/comments", status_code=201)
async def create_comment(owner: str, repo: str, number: int, request: Request):
    comment_id = next(state["ids"])
    state["comments"][comment_id] = {"id": comment_id, **(await request.json())}
    return state["comments"][comment_id]


@app.patch("/repos/{owner}/{repo}/issues/comments/{comment_id}")
async def update_comment(owner: str, repo: str, comment_id: int, request: Request):
    if comment_id not in state["comments"]:
        raise HTTPException(404, "Not Found")
    state["comments"][comment_id].update(await request.json())
    return state["comments"][comment_id]


@app.get("/_debug/comments", response_class=PlainTextResponse)
def debug_comments():
    if not state["comments"]:
        return "(the bot has not commented yet)"
    return "\n\n==========\n\n".join(c["body"] for c in state["comments"].values())


@app.post("/_debug/head_sha")
def set_head_sha(sha: str):
    """Pretend the PR got a new commit (use with: send_test_webhook.py --action synchronize)."""
    state["sha"] = sha
    return {"sha": sha}

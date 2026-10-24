# PR Review Assistant

A GitHub bot that reads every new pull request and posts **one comment** that it keeps up to date:
a short summary, risks to watch out for, and a checklist for the human reviewer.

```
GitHub ──webhook──▶ FastAPI ──▶ PostgreSQL (jobs, dedupe)
                       │
                       └──▶ Redis queue ──▶ Worker ──▶ GitHub API (fetch diff)
                                               │
                                               ├──▶ rules (auth, migrations, no tests, size...)
                                               ├──▶ LLM (optional; secrets redacted first)
                                               └──▶ GitHub API (create / update the one comment)
```

It works **with or without an LLM**. With `LLM_PROVIDER=none` you still get the rule-based
findings; add an Anthropic API key to get the AI summary as well.

## What the bot checks

- Verifies the GitHub webhook signature (HMAC SHA-256) and rejects anything unsigned.
- Never processes the same delivery twice, and creates one job per PR commit.
- Flags: auth code, payments, DB migrations, CI/infra, dependency changes, committed secrets,
  source changes without tests, very large PRs.
- Skips noise (lock files, images, minified and generated files) and respects size limits.
- Redacts credentials from the diff before anything is sent to the LLM.
- Treats the PR text as untrusted input (prompt-injection safe), validates the LLM's JSON, strips
  `@mentions` and HTML from what it posts.
- Retries failures with backoff. If the LLM is still down on the last attempt it posts the
  rule-based findings instead of nothing.
- On a new commit it **edits** its comment instead of adding another.

---

## 1. Install and try it on your laptop (offline demo, ~5 minutes)

No GitHub account, no API keys. You only need **Docker Desktop** (includes Docker Compose) and
**Python 3** (only to send the test webhook; standard library only).

```bash
# 1. open a terminal in the project folder
cd pr-review-assistant

# 2. use the demo settings (fake GitHub, no LLM)
cp .env.demo .env              # Windows PowerShell:  Copy-Item .env.demo .env

# 3. start everything (first build takes a few minutes)
docker compose --profile demo up --build
```

Wait until you see the `api` and `worker` containers running, then open a **second terminal**:

```bash
# 4. send a signed "pull request opened" webhook, like GitHub would
python scripts/send_test_webhook.py          # Windows: py scripts\send_test_webhook.py
# -> 202 {"status":"queued","job_id":1}

# 5. see the comment the bot posted (fake GitHub keeps it in memory)
#    open in your browser:  http://localhost:9000/_debug/comments
```

Other things to try:

| Try this | Expected result |
|---|---|
| Run step 4 again | `duplicate` (same commit is never reviewed twice) |
| `python scripts/send_test_webhook.py --secret wrong` | `401 Invalid signature` |
| `curl -X POST "localhost:9000/_debug/head_sha?sha=abc1234"` then `python scripts/send_test_webhook.py --action synchronize --sha abc1234` | the **same** comment is updated for the new commit |
| Open `http://localhost:8000/docs` | the API docs |
| `curl http://localhost:8000/health/ready` | `{"status":"ok","database":"ok","redis":"ok"}` |
| `curl -H "Authorization: Bearer demo-admin" http://localhost:8000/admin/stats` | job counts |

Stop with `Ctrl+C`, then `docker compose --profile demo down` (add `-v` to delete the database).

---

## 2. Use it on a real GitHub repository

### a) Get the app reachable from the internet
GitHub has to reach your laptop. Use [ngrok](https://ngrok.com) (or smee.io):

```bash
ngrok http 8000        # copy the https URL it prints, e.g. https://abcd1234.ngrok-free.app
```

### b) Create a token
GitHub → Settings → Developer settings → **Fine-grained personal access tokens** → new token.
Select your test repository, and give it **Pull requests: Read and write** and
**Contents: Read** (and **Metadata: Read**, which is automatic).

### c) Configure
```bash
cp .env.example .env
```
Edit `.env`:

```
GITHUB_WEBHOOK_SECRET=<a long random string you make up>
GITHUB_TOKEN=<the token from step b>
ALLOWED_REPOS=your-username/your-test-repo      # strongly recommended
LLM_PROVIDER=none                               # or "anthropic", see section 3
```

### d) Start (without the fake GitHub this time)
```bash
docker compose up --build
```

### e) Add the webhook
Repository → Settings → Webhooks → **Add webhook**:

- Payload URL: `https://<your-ngrok-url>/webhook/github`
- Content type: `application/json`
- Secret: the same `GITHUB_WEBHOOK_SECRET`
- Events: *Let me select* → tick **Pull requests** only

GitHub sends a `ping`; under *Recent Deliveries* it should show a green tick.
Now open a pull request on that repo; the bot comments within a few seconds.
(If a delivery failed, you can click **Redeliver**.)

> **GitHub App instead of a token:** create a GitHub App with the same permissions, subscribe it
> to *Pull request* events, install it on your repo, and set `GITHUB_APP_ID` and
> `GITHUB_APP_PRIVATE_KEY` (the PEM text, or a path to the `.pem` file) instead of
> `GITHUB_TOKEN`. The bot then gets short-lived installation tokens automatically.

---

## 3. Turn on AI summaries (optional)

In `.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=<your key>
LLM_MODEL=claude-haiku-5-5
```

Restart: `docker compose up -d --force-recreate api worker`.

Cost control: each PR sends at most `MAX_DIFF_CHARS` (default 60,000) characters, and the reply
is limited to `LLM_MAX_TOKENS`.

---

## 4. Per-repo settings (optional)

Add `.pr-assistant.yml` to the root of the repository being reviewed:

```yaml
enabled: true                     # false = bot stays silent on this repo
ignore_paths: ["docs/*", "*.generated.ts"]
extra_checklist:
  - "Update the changelog"
custom_risks:
  - pattern: "src/payments/*"
    message: "Owned by the payments team - tag them"
```

---

## 5. Developing without Docker for the app

Docker is still handy for Postgres and Redis:

```bash
docker compose up -d db redis

python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                   # then edit it
alembic upgrade head                   # create the tables

uvicorn app.main:app --reload          # terminal 1: the API
arq worker.tasks.WorkerSettings        # terminal 2: the worker
```

Run the checks:

```bash
pytest          # 69 tests, no Postgres/Redis/GitHub/LLM needed
ruff check .
ruff format --check .
```

The tests use SQLite and fake GitHub / LLM / queue objects (`tests/fakes.py`), so they run
anywhere in a few seconds.

---

## Configuration reference

| Variable | Default | Meaning |
|---|---|---|
| `GITHUB_WEBHOOK_SECRET` | *(required)* | Shared secret for verifying webhooks. The API refuses to start without it. |
| `GITHUB_TOKEN` | | Personal access token (simplest). |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` | | GitHub App credentials (used when no token is set). |
| `GITHUB_API_URL` | `https://api.github.com` | Change only for GitHub Enterprise or the fake server. |
| `ALLOWED_REPOS` | *(all)* | Comma-separated `owner/repo` list. |
| `SKIP_DRAFT_PRS` | `true` | Ignore draft PRs (they are reviewed when marked ready). |
| `LLM_PROVIDER` | `none` | `none` or `anthropic`. |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | | Needed when the provider is `anthropic`. |
| `DATABASE_URL` | local Postgres | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | `redis://localhost:6379/0` | Queue backend. |
| `MAX_JOB_ATTEMPTS` | `4` | Tries per job (backoff 30s, 60s, 120s...). |
| `MAX_DIFF_CHARS` / `MAX_CHARS_PER_FILE` | `60000` / `6000` | Size budget sent to the LLM. |
| `LARGE_PR_LINES` / `LARGE_PR_FILES` | `600` / `25` | When to flag a PR as large. |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-IP limit on the webhook endpoint. |
| `ADMIN_TOKEN` | *(disabled)* | Enables `/admin/stats` and `/admin/jobs`. |
| `LOG_LEVEL` | `INFO` | Logs are JSON, one line each, with request/job ids. |

## Project layout

```
app/
  main.py               app factory, request-id middleware, lifespan
  config.py             settings (env vars)
  models.py             webhook_deliveries, review_jobs, bot_comments
  api/                  webhook.py, health.py, admin.py
  services/
    security.py         webhook signature check
    github_auth.py      PAT / GitHub App tokens
    github_client.py    the few GitHub calls we need
    risk_rules.py       deterministic checks
    diff_utils.py       noise filtering + size budget
    secret_redaction.py credential removal
    llm_client.py       prompt, Anthropic call, JSON validation
    formatter.py        the Markdown comment
    review_pipeline.py  fetch -> analyse -> LLM -> post/update
    job_runner.py       statuses, retries, backoff
  queue.py              Redis (ARQ) queue
worker/tasks.py         ARQ worker entry point
migrations/             Alembic
scripts/                fake_github.py, send_test_webhook.py
tests/                  69 tests
.github/workflows/      ci.yml (lint + tests + docker build), release-image.yml
```

## Deploying

`.github/workflows/release-image.yml` publishes `ghcr.io/<you>/<repo>:latest` on every push to
`main`. On any host (Render, Railway, Fly.io, a VPS) run three things from that image, with a
managed Postgres and Redis:

1. `alembic upgrade head` (once per release)
2. `uvicorn app.main:app --host 0.0.0.0 --port 8000` (the web service)
3. `arq worker.tasks.WorkerSettings` (the worker)

Then change the webhook URL on GitHub to your public URL and set the same environment variables.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Invalid signature` | The webhook secret on GitHub differs from `GITHUB_WEBHOOK_SECRET`. |
| Webhook shows 202 but no comment | Check `docker compose logs worker`. Usually a token without *Pull requests: write*, or the repo is not in `ALLOWED_REPOS`. |
| Delivery says `ignored: draft` | Draft PRs are skipped; mark it ready, or set `SKIP_DRAFT_PRS=false`. |
| `ignored: action` | Only opened / synchronize / reopened / ready_for_review are handled. |
| `GITHUB_WEBHOOK_SECRET must be set` | Create `.env` (copy `.env.demo` or `.env.example`). |
| `port is already allocated` | Something else uses 8000, 5432, 6379 or 9000; stop it or edit the port in `docker-compose.yml`. |
| Job stuck as `failed` | See its `error` in `GET /admin/jobs` (needs `ADMIN_TOKEN`). |
| ngrok URL changed after restart | Update the webhook Payload URL on GitHub. |

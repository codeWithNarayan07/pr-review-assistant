# PR Review Assistant

A GitHub bot that reviews pull requests and maintains **one up-to-date review comment** containing a summary, potential risks, and a checklist for the human reviewer.

It is built with FastAPI, PostgreSQL, Redis, ARQ, and a React/Vite dashboard. Rule-based checks work without an LLM; an optional Anthropic integration can add an AI-generated summary.

## How it works

```text
GitHub ──webhook──▶ FastAPI ──▶ PostgreSQL (jobs and deduplication)
                       │
                       └──▶ Redis queue ──▶ ARQ worker ──▶ GitHub API (fetch diff)
                                                   │
                                                   ├──▶ Rule-based risk checks
                                                   ├──▶ Optional LLM analysis
                                                   └──▶ Create/update one PR comment

React/Vite dashboard ──▶ FastAPI admin endpoints
```

## Features

- Verifies GitHub webhook signatures using HMAC SHA-256.
- Deduplicates webhook deliveries and review jobs.
- Flags sensitive or high-risk changes, including authentication, payments, migrations, CI/infra, dependencies, secrets, missing tests, and unusually large pull requests.
- Filters noisy files such as lock files, images, minified files, and generated files.
- Redacts credentials before sending diffs to an LLM.
- Treats pull-request text as untrusted input and validates LLM output.
- Retries failed jobs with backoff and falls back to rule-based findings if the LLM fails.
- Updates the existing bot comment when a new commit arrives instead of posting a duplicate.
- Provides admin endpoints for job statistics and job inspection.
- Includes a React/Vite dashboard for viewing review-job activity.
- Supports a fake GitHub service for local demos without a real GitHub account or API token.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **Queue and worker:** Redis, ARQ
- **Frontend:** React, Vite
- **Testing and linting:** pytest, Ruff
- **Optional AI:** Anthropic API

## Prerequisites

For the Docker workflow, install Docker Desktop with Docker Compose. Python 3 is needed to run the test-webhook script. Node.js and npm are needed to run the frontend locally outside Docker.

## Quick start: local Docker demo

The demo uses the fake GitHub service and disables LLM calls. No GitHub credentials or AI API key are required.

From the repository root:

```powershell
Copy-Item .env.demo .env
docker compose --profile demo up --build
```

Wait for the API and worker containers to start. In a second terminal, from the repository root, send a test webhook:

```powershell
py scripts\send_test_webhook.py
```

Useful local URLs:

- API health: http://localhost:8000/health
- API documentation: http://localhost:8000/docs
- Fake GitHub comments: http://localhost:9000/_debug/comments

Try sending the same test webhook again; the duplicate should be ignored. You can also test signature validation:

```powershell
py scripts\send_test_webhook.py --secret wrong
```

That request should be rejected with `401 Invalid signature`.

Stop the demo with `Ctrl+C`, then run:

```powershell
docker compose --profile demo down
```

Add `-v` only if you intentionally want to delete the database volume and its stored data.

## Run the dashboard locally

The dashboard is in `frontend/`. Start the backend services from the repository root:

```powershell
docker compose up -d --build
docker compose ps
```

Confirm that the API, database, Redis, and worker are running. Then open a **separate terminal**:

```powershell
cd frontend
npm install
npm run dev
```

Open the local Vite URL printed in the terminal, usually http://localhost:5173.

The dashboard calls the local API at `http://localhost:8000`. When prompted for the admin token, use the `ADMIN_TOKEN` configured for your local environment. To read the value from the running API container without putting it in source control:

```powershell
# Run this from the repository root. Keep the output private.
docker compose exec api python -c "import os; print(os.environ['ADMIN_TOKEN'])"
```

Paste the token into the dashboard's token field. Do not commit the token or share it publicly. If the dashboard cannot reach the API, check that the containers are healthy, the API is available at port 8000, and the browser origin is allowed by the API's CORS configuration.

To create a production frontend bundle:

```powershell
cd frontend
npm run build
```

The generated files are written to `frontend/dist/`.

## Run tests and code checks

From the repository root:

```powershell
python -m pytest -v
ruff check .
ruff format --check .
```

The test suite uses test doubles and SQLite where applicable, so the unit tests do not require a live GitHub repository or LLM credentials. The project was locally verified with **69 passing tests**, Ruff checks passing, and a successful Vite production build.

## Connect a real GitHub repository

This is an optional integration step. It is not needed for the local demo.

1. Make the API reachable by GitHub using a secure public HTTPS endpoint or webhook relay.
2. Create a fine-grained personal access token scoped to the test repository. Grant only the permissions the bot needs, including pull-request read/write and contents read.
3. Copy `.env.example` to `.env` and configure the webhook secret, GitHub credentials, and an `ALLOWED_REPOS` entry for the repository you want to permit.
4. Start the regular Compose services:

   ```powershell
   docker compose up --build
   ```

5. In the GitHub repository, open **Settings → Webhooks → Add webhook**:
   - Payload URL: `https://<your-public-host>/webhook/github`
   - Content type: `application/json`
   - Secret: the same value as `GITHUB_WEBHOOK_SECRET`
   - Event: **Pull requests**

6. Verify the webhook delivery, then open a test pull request and inspect the bot's comment and worker logs.

Treat webhook secrets, GitHub tokens, admin tokens, and AI keys as credentials. Never commit `.env` or paste secrets into issues or screenshots. A GitHub App can be used instead of a personal access token if the application credentials and permissions are configured.

## Optional AI summaries

The bot supports rule-based reviews without an LLM. To enable Anthropic, configure the following in `.env`:

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=<your-key>
LLM_MODEL=claude-haiku-5-5
```

Use a valid model identifier supported by your configured Anthropic account. Restart the API and worker after changing environment variables. Review the provider's pricing and limits before enabling AI calls. The application limits the amount of diff text sent for analysis.

## Optional per-repository settings

A reviewed repository can include a `.pr-assistant.yml` file at its root:

```yaml
enabled: true
ignore_paths:
  - "docs/*"
  - "*.generated.ts"
extra_checklist:
  - "Update the changelog"
custom_risks:
  - pattern: "src/payments/*"
    message: "Owned by the payments team - tag them"
```

## Configuration reference

Configure these values in `.env`. Defaults can vary with the selected Compose profile and environment; use `.env.example` and `.env.demo` as the authoritative starting points for this checkout.

| Variable | Purpose |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Shared secret used to verify webhook signatures. |
| `GITHUB_TOKEN` | GitHub personal access token, if using token-based authentication. |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` | Optional GitHub App credentials. |
| `GITHUB_API_URL` | GitHub API base URL; useful for compatible test servers. |
| `ALLOWED_REPOS` | Optional comma-separated allowlist of `owner/repo` names. |
| `SKIP_DRAFT_PRS` | Whether draft pull requests are skipped. |
| `LLM_PROVIDER` | `none` for rule-only reviews, or `anthropic` for AI summaries. |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | Credentials and model identifier for Anthropic. |
| `DATABASE_URL` | SQLAlchemy database connection URL. |
| `REDIS_URL` | Redis connection URL used by the job queue. |
| `MAX_JOB_ATTEMPTS` | Maximum number of job attempts. |
| `MAX_DIFF_CHARS`, `MAX_CHARS_PER_FILE` | Limits on diff content considered for review. |
| `LARGE_PR_LINES`, `LARGE_PR_FILES` | Thresholds used to flag large pull requests. |
| `RATE_LIMIT_PER_MINUTE` | Webhook endpoint rate limit. |
| `ADMIN_TOKEN` | Protects admin endpoints such as `/admin/stats` and `/admin/jobs`. |
| `LOG_LEVEL` | Application logging level. |

## Project layout

```text
app/
  main.py                 FastAPI app, middleware, and lifespan
  config.py               Environment-based settings
  models.py               Database models
  api/                    Webhook, health, and admin endpoints
  services/
    security.py           Webhook signature verification
    github_auth.py        GitHub token and app authentication
    github_client.py      GitHub API calls
    risk_rules.py         Rule-based checks
    diff_utils.py         Diff filtering and size limits
    secret_redaction.py   Credential redaction
    llm_client.py         Optional LLM integration and validation
    formatter.py          Review-comment formatting
    review_pipeline.py    Review and comment workflow
    job_runner.py         Job status, retries, and backoff
  queue.py                Redis/ARQ queue integration
worker/
  tasks.py                ARQ worker entry point
frontend/                 React/Vite dashboard
migrations/               Alembic database migrations
scripts/                  Fake GitHub service and test webhook sender
tests/                    Automated tests
.github/workflows/        CI and image-release workflows
```

## Troubleshooting

| Symptom | What to check |
|---|---|
| `401 Invalid signature` | The GitHub webhook secret must match `GITHUB_WEBHOOK_SECRET`. |
| Webhook returns `202` but no comment appears | Check `docker compose logs worker`, repository permissions, and `ALLOWED_REPOS`. |
| A draft PR is ignored | Check `SKIP_DRAFT_PRS` and mark the PR ready if appropriate. |
| `GITHUB_WEBHOOK_SECRET must be set` | Create `.env` from `.env.demo` for the demo or `.env.example` for a real integration. |
| A port is already allocated | Check ports 8000, 5173, 5432, 6379, and 9000, then stop the conflicting process or update the relevant configuration. |
| Dashboard cannot load data | Confirm the API is healthy at `http://localhost:8000`, enter the correct local `ADMIN_TOKEN`, and check CORS settings. |
| A job is marked failed | Inspect the worker logs and the authenticated `GET /admin/jobs` endpoint. |
| The public webhook URL changed | Update the webhook's payload URL in GitHub. |

## License

Add a `LICENSE` file if you intend to publish this project under an open-source license.

Test PR for PR Review Assistant bot.

<!-- webhook re-test: 2026-10-30 -->

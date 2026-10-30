# PR Review Assistant

An automated GitHub Pull Request review bot that helps developers identify potential code risks and receive structured feedback directly on their pull requests.

PR Review Assistant integrates with GitHub through a GitHub App, processes webhook events asynchronously, and publishes review comments without blocking webhook delivery.

## Features

- **GitHub App integration** — Connects to GitHub repositories using App authentication.
- **Webhook signature verification** — Validates incoming GitHub webhook requests.
- **Asynchronous processing** — Uses Redis and ARQ to process review jobs in the background.
- **Duplicate job prevention** — Prevents duplicate processing of webhook deliveries.
- **Automated code-risk checks** — Identifies potential risks and generates structured review feedback.
- **Review checklists** — Provides developers with actionable review points.
- **Comment updates** — Updates existing review comments when new commits are pushed to a pull request.
- **Dashboard** — Provides a frontend interface for viewing review activity and job information.

## Tech Stack

| Component           | Technology             |
| ------------------- | ---------------------- |
| Backend API         | Python, FastAPI        |
| Frontend            | React 19, Vite         |
| Database            | PostgreSQL             |
| ORM                 | SQLAlchemy             |
| Database migrations | Alembic                |
| Background jobs     | ARQ                    |
| Message broker      | Redis                  |
| GitHub integration  | GitHub Apps, Webhooks  |
| Containers          | Docker, Docker Compose |
| Testing             | Pytest                 |
| Code quality        | Ruff, Oxlint           |

## Architecture

flowchart TD
A[GitHub Pull Request] --> B[GitHub Webhook]
B --> C[FastAPI API]
C --> D[Signature Verification]
D --> E[Duplicate Job Prevention]
E --> F[Redis Job Queue]
F --> G[ARQ Worker]
G --> H[Automated Code Risk Checks]
G --> I[PostgreSQL]
G --> J[GitHub API]
J --> K[Review Comment]
L[React Dashboard] --> M[Admin API]
M --> C

## Project Structure

```text
pr-review-assistant/
├── .github/
│   └── workflows/
├── app/
│   ├── api/
│   ├── services/
│   ├── config.py
│   └── main.py
├── frontend/
│   ├── public/
│   ├── src/
│   └── package.json
├── migrations/
├── scripts/
├── secrets/                 # Local GitHub App private key (not committed)
├── tests/
├── worker/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Git
- Docker Desktop with Docker Compose
- Node.js and npm (for local frontend development)

### 1. Clone the repository

```bash
git clone https://github.com/codeWithNarayan07/pr-review-assistant.git
cd pr-review-assistant
```

### 2. Configure environment variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Configure the required values in `.env`:

```env
ENVIRONMENT=development
LOG_LEVEL=INFO

GITHUB_WEBHOOK_SECRET=your-long-random-webhook-secret

GITHUB_APP_ID=your-github-app-id
GITHUB_APP_PRIVATE_KEY=/run/secrets/github-app-private-key.pem

LLM_PROVIDER=none
ADMIN_TOKEN=your-admin-token
```

### GitHub App Setup

1. Create and configure a GitHub App.
2. Grant the required repository permissions:
   - Issues: Read and write
   - Pull requests: Read and write
   - Contents: Read-only
   - Metadata: Read-only
3. Configure the required pull request webhook events.
4. Generate and download the App's private key.

Create the local secrets directory:

```powershell
New-Item -ItemType Directory -Force .\secrets
```

Place the downloaded private key at:

```text
secrets/github-app-private-key.pem
```

Configure the following values in `.env`:

```env
GITHUB_APP_ID=your-github-app-id
GITHUB_APP_PRIVATE_KEY=/run/secrets/github-app-private-key.pem
GITHUB_WEBHOOK_SECRET=your-long-random-webhook-secret
```

Configure the GitHub App webhook URL to use your publicly reachable endpoint:

```text
https://your-domain.com/webhook/github
```

Use the same webhook secret in GitHub and `.env`.

**Security:** Never commit `.env`, private keys, access tokens, or webhook secrets.

### 3. Start the application

```bash
docker compose up -d --build
```

Docker Compose starts PostgreSQL, Redis, runs database migrations, and starts the API and background worker.

### 4. Check application status

```bash
docker compose ps
```

Check API health:

```text
http://localhost:8000/health
```

### 5. Access the frontend

For local frontend development:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite in your terminal.

### 6. Optional: Start demo mode

To start the fake GitHub service:

```bash
docker compose --profile demo up -d --build
```

The fake GitHub service is available at:

```text
http://localhost:9000
```

### Useful Docker commands

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f db
docker compose down
```

To stop the application without deleting persistent database data, use `docker compose down`. Avoid `-v` unless you intentionally want to remove the database volume.

## Testing

### Backend tests

```bash
pytest
```

### Backend linting

```bash
ruff check .
```

### Backend formatting check

```bash
ruff format --check .
```

### Frontend build

```bash
cd frontend
npm run build
```

### Frontend lint

```bash
npm run lint
```

## GitHub Integration

The project uses a GitHub App to receive pull request webhook events.

The workflow:

1. A developer opens or updates a pull request.
2. GitHub sends a webhook event to the FastAPI application.
3. The application verifies the webhook signature.
4. A review job is queued for background processing.
5. The ARQ worker performs automated code-risk checks.
6. The bot publishes a review comment on the pull request.
7. When new commits arrive, the existing review comment can be updated.

## Project Validation

The following checks have passed during development:

- 69 backend tests passed.
- Ruff lint checks passed.
- Ruff formatting checks passed.
- Frontend production build completed successfully.
- Frontend lint completed with one warning and zero errors.
- Live GitHub App webhook integration tested successfully.
- Review comments successfully created and updated after new commits.

## Future Improvements

- AI-powered code review assistance.
- Expanded review analysis and reporting.
- Additional dashboard capabilities.

## Author

**Narayan Ammannavar**

GitHub: [@codeWithNarayan07](https://github.com/codeWithNarayan07)

LinkedIn: [narayan-ammannavar](https://www.linkedin.com/in/narayan-ammannavar/)

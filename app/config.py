"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- general ---
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pr_assistant"
    redis_url: str = "redis://localhost:6379/0"

    # --- GitHub ---
    github_webhook_secret: str = ""
    github_api_url: str = "https://api.github.com"
    # Option 1 (easiest): a personal access token
    github_token: str = ""
    # Option 2 (recommended for real use): a GitHub App
    github_app_id: str = ""
    github_app_private_key: str = ""  # PEM text, or a path to a .pem file
    # Comma-separated "owner/repo" values. Empty = every repo that sends events.
    allowed_repos: str = ""
    skip_draft_prs: bool = True

    # --- LLM ---
    llm_provider: str = "none"  # "none" (rule-based only) or "anthropic"
    anthropic_api_key: str = ""
    anthropic_api_url: str = "https://api.anthropic.com"
    llm_model: str = "claude-haiku-5-5"
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    # --- limits ---
    max_diff_chars: int = 60_000
    max_chars_per_file: int = 6_000
    max_files_fetched: int = 300
    large_pr_lines: int = 600
    large_pr_files: int = 25
    max_job_attempts: int = 4
    rate_limit_per_minute: int = 120

    # --- admin API (disabled when empty) ---
    admin_token: str = ""

    @property
    def allowed_repo_set(self) -> set[str]:
        return {r.strip().lower() for r in self.allowed_repos.split(",") if r.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

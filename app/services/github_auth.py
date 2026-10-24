"""Turn the configured credentials (PAT or GitHub App) into an API token."""

import os
import time

import httpx
import jwt

from app.config import Settings
from app.errors import ConfigError, GitHubError


class StaticTokenProvider:
    def __init__(self, token: str):
        self._token = token

    async def get_token(self, installation_id: int | None) -> str:
        return self._token


class AppTokenProvider:
    """GitHub App flow: sign a short-lived JWT, exchange it for an installation token."""

    def __init__(self, app_id: str, private_key: str, api_url: str, http: httpx.AsyncClient):
        self.app_id = app_id
        self.private_key = _load_key(private_key)
        self.api_url = api_url.rstrip("/")
        self.http = http
        self._cache: dict[int, tuple[str, float]] = {}

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": self.app_id}
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_token(self, installation_id: int | None) -> str:
        if installation_id is None:
            raise ConfigError("Webhook had no installation id; cannot use GitHub App auth")
        cached = self._cache.get(installation_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        resp = await self.http.post(
            f"{self.api_url}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._app_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        if resp.status_code >= 400:
            raise GitHubError(
                f"Could not get installation token: {resp.status_code}", resp.status_code
            )
        # tokens last 1 hour; refresh a minute early
        self._cache[installation_id] = (resp.json()["token"], time.time() + 55 * 60)
        return self._cache[installation_id][0]


def _load_key(value: str) -> str:
    value = value.strip()
    if "BEGIN" in value:
        return value.replace("\\n", "\n")
    if os.path.exists(value):
        with open(value) as fh:
            return fh.read()
    raise ConfigError("GITHUB_APP_PRIVATE_KEY is neither PEM text nor an existing file path")


def build_token_provider(settings: Settings, http: httpx.AsyncClient):
    if settings.github_token:
        return StaticTokenProvider(settings.github_token)
    if settings.github_app_id and settings.github_app_private_key:
        return AppTokenProvider(
            settings.github_app_id, settings.github_app_private_key, settings.github_api_url, http
        )
    raise ConfigError("Set GITHUB_TOKEN, or GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY")

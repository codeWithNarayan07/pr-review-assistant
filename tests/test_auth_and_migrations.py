import subprocess
import sys

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.errors import ConfigError
from app.services.github_auth import (
    AppTokenProvider,
    StaticTokenProvider,
    build_token_provider,
)


def make_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private, public


async def test_github_app_token_exchange_and_caching():
    private, public = make_pem()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(201, json={"token": "inst-token", "expires_at": "2099-01-01"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AppTokenProvider("12345", private, "https://api.github.test", http)

    assert await provider.get_token(77) == "inst-token"
    assert await provider.get_token(77) == "inst-token"  # cached
    assert len(calls) == 1
    assert calls[0].url.path == "/app/installations/77/access_tokens"

    claims = jwt.decode(
        calls[0].headers["authorization"].removeprefix("Bearer "), public, algorithms=["RS256"]
    )
    assert claims["iss"] == "12345" and claims["exp"] > claims["iat"]


async def test_app_auth_needs_an_installation_id():
    private, _ = make_pem()
    provider = AppTokenProvider("1", private, "https://x", httpx.AsyncClient())
    with pytest.raises(ConfigError):
        await provider.get_token(None)


def test_token_provider_selection():
    http = httpx.AsyncClient()
    assert isinstance(
        build_token_provider(Settings(_env_file=None, github_token="t"), http), StaticTokenProvider
    )
    with pytest.raises(ConfigError):
        build_token_provider(
            Settings(_env_file=None, github_token="", github_app_id="", github_app_private_key=""),
            http,
        )


def test_migrations_apply_and_roll_back(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'm.db'}"

    def alembic(*args):
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"url={url}", *args],
            capture_output=True,
            text=True,
        )

    up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    down = alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr

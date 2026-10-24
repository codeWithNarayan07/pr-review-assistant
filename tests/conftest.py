import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, make_sessionmaker
from app.main import create_app
from tests.fakes import FakeGitHub, FakeLLM, FakeQueue, FakeTokens

SECRET = "test-secret"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        github_webhook_secret=SECRET,
        github_token="x",
        database_url="sqlite+aiosqlite://",
        max_job_attempts=3,
        rate_limit_per_minute=1000,
        admin_token="admin-secret",
    )


@pytest_asyncio.fixture
async def sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield make_sessionmaker(engine)
    await engine.dispose()


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest_asyncio.fixture
async def client(settings, sessionmaker, queue):
    app = create_app(settings, queue=queue, sessionmaker=sessionmaker)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def tokens() -> FakeTokens:
    return FakeTokens()

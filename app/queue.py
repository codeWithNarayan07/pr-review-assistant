from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings


class JobQueue(Protocol):
    async def enqueue_review(self, job_id: int) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class ArqQueue:
    def __init__(self, pool: ArqRedis):
        self.pool = pool

    @classmethod
    async def connect(cls, redis_url: str) -> "ArqQueue":
        return cls(await create_pool(RedisSettings.from_dsn(redis_url)))

    async def enqueue_review(self, job_id: int) -> None:
        # _job_id makes enqueueing the same job twice a no-op
        await self.pool.enqueue_job("process_review", job_id, _job_id=f"review-{job_id}")

    async def ping(self) -> bool:
        return bool(await self.pool.ping())

    async def close(self) -> None:
        await self.pool.aclose()

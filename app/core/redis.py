from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import settings


def create_redis_client() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def init_redis(app: FastAPI) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    redis = create_redis_client()
    await redis.ping()
    app.state.redis = redis


async def close_redis(app: FastAPI) -> None:
    redis: Redis | None = getattr(app.state, "redis", None)
    if redis is not None:
        await redis.aclose()

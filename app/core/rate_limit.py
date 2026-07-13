from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.api.deps import CurrentUser
from app.core.config import settings


def _get_client_ip(request: Request) -> str:
    if request.client is None or request.client.host is None:
        return "unknown"
    return request.client.host


def _get_redis(request: Request) -> Redis:
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service is unavailable",
        )
    return redis


async def _enforce_limit(
        *,
        redis: Redis,
        key: str,
        limit: int,
        window_seconds: int,
) -> None:
    current_count = await redis.incr(key)
    ttl = await redis.ttl(key)

    if current_count == 1 or ttl == -1:
        await redis.expire(key, window_seconds)
        ttl = window_seconds

    if current_count > limit:
        retry_after = max(int(ttl), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def ip_rate_limit(*, scope: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        redis = _get_redis(request)
        client_ip = _get_client_ip(request)
        key = f"rate_limit:{scope}:ip:{client_ip}"

        await _enforce_limit(
            redis=redis,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency


def user_rate_limit(*, scope: str, limit: int, window_seconds: int):
    async def dependency(request: Request, current_user: CurrentUser) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        redis = _get_redis(request)
        key = f"rate_limit:{scope}:user:{current_user.id}"

        await _enforce_limit(
            redis=redis,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency

"""Redis caching service with connection pooling and error handling."""

import json
from typing import Optional, Any, Union
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from src.config import settings
from src.exceptions.custom_exceptions import CacheError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RedisService:
    """Redis service for caching PR analysis results."""

    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._default_ttl = settings.REDIS_TTL

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client with connection pooling."""
        if self._client is None:
            try:
                self._pool = ConnectionPool.from_url(
                    settings.REDIS_URL,
                    max_connections=settings.REDIS_MAX_CONNECTIONS,
                    decode_responses=True,
                )
                self._client = redis.Redis(connection_pool=self._pool)
                self._connected = True
                logger.info("Redis connection pool created successfully")
            except Exception as e:
                self._connected = False
                logger.error(f"Failed to create Redis connection pool: {str(e)}")
                raise CacheError(f"Redis connection failed: {str(e)}")
        return self._client

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = await self._get_client()
            result = await client.ping()
            self._connected = True
            return result
        except Exception as e:
            self._connected = False
            logger.warning(f"Redis ping failed: {str(e)}")
            return False

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True,
    ) -> bool:
        """
        Set a value in Redis with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (defaults to REDIS_TTL)
            serialize: Whether to JSON serialize the value

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_client()

            if serialize:
                value = json.dumps(value, default=str)

            ttl = ttl or self._default_ttl

            result = await client.setex(key, ttl, value)
            logger.debug(f"Cached key: {key} with TTL: {ttl}s")
            return result

        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {str(e)}")
            return False

    async def get(
        self,
        key: str,
        deserialize: bool = True,
        default: Any = None,
    ) -> Optional[Any]:
        """
        Get a value from Redis.

        Args:
            key: Cache key
            deserialize: Whether to JSON deserialize the value
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is None:
                logger.debug(f"Cache miss: {key}")
                return default

            if deserialize:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    # If not JSON, return raw value
                    return value

            logger.debug(f"Cache hit: {key}")
            return value

        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {str(e)}")
            return default

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        try:
            client = await self._get_client()
            return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Failed to check cache key {key}: {str(e)}")
            return False

    async def set_with_retry(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        max_retries: int = 3,
    ) -> bool:
        """Set value with retry logic."""
        for attempt in range(max_retries):
            try:
                return await self.set(key, value, ttl)
            except Exception as e:
                logger.warning(f"Redis set attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    return False
        return False

    async def get_with_retry(
        self,
        key: str,
        default: Any = None,
        max_retries: int = 3,
    ) -> Optional[Any]:
        """Get value with retry logic."""
        for attempt in range(max_retries):
            try:
                return await self.get(key, default=default)
            except Exception as e:
                logger.warning(f"Redis get attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    return default
        return default

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        try:
            client = await self._get_client()
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += await client.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Cleared {deleted} keys matching pattern: {pattern}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to clear pattern {pattern}: {str(e)}")
            return 0

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.disconnect()
            self._client = None
            self._pool = None
            self._connected = False
            logger.info("Redis connection pool closed")


# Singleton instance
redis_service = RedisService()
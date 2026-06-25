import os
import json
import logging
import redis

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.client.ping()
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
            self.client = None

    def get(self, key: str):
        if not self.client:
            return None
        try:
            val = self.client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.error(f"Error reading from Redis key '{key}': {e}")
            return None

    def set(self, key: str, value, ex_seconds: int = None):
        if not self.client:
            return False
        try:
            serialized = json.dumps(value)
            self.client.set(key, serialized, ex=ex_seconds)
            return True
        except Exception as e:
            logger.error(f"Error writing to Redis key '{key}': {e}")
            return False

    def delete(self, key: str):
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting Redis key '{key}': {e}")
            return False

    def clear_pattern(self, pattern: str):
        if not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Error clearing Redis keys matching '{pattern}': {e}")
            return False

# Global instance
cache = CacheService()

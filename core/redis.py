import redis.asyncio as redis
from core.config import settings


class RedisClient:
    """Клиент для работы с Redis."""

    def __init__(self):
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def connect(self):
        """Подключение к Redis."""
        await self.client.ping()

    async def close(self):
        """Закрытие соединения с Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    # Методы для работы с задачами обработки
    async def set_task_status(self, task_id: int, status: str, ttl: int = 3600):
        """Установить статус задачи."""
        key = f"task:{task_id}:status"
        await self.client.set(key, status, ex=ttl)

    async def get_task_status(self, task_id: int) -> str | None:
        """Получить статус задачи."""
        key = f"task:{task_id}:status"
        return await self.client.get(key)

    async def delete_task_status(self, task_id: int):
        """Удалить статус задачи."""
        key = f"task:{task_id}:status"
        await self.client.delete(key)

    # Методы для работы с пользователями
    async def set_user_subscription_check(
        self,
        user_id: int,
        is_subscribed: bool,
        ttl: int = 300
    ):
        """Кэширование результата проверки подписки."""
        key = f"user:{user_id}:subscription"
        await self.client.set(key, "1" if is_subscribed else "0", ex=ttl)

    async def get_user_subscription_check(self, user_id: int) -> bool | None:
        """Получить кэшированный результат проверки подписки."""
        key = f"user:{user_id}:subscription"
        result = await self.client.get(key)
        if result is None:
            return None
        return result == "1"

    # Методы для блокировок (rate limiting)
    async def acquire_lock(self, key: str, ttl: int = 60) -> bool:
        """Получить блокировку."""
        return await self.client.set(key, "1", nx=True, ex=ttl)

    async def release_lock(self, key: str):
        """Освободить блокировку."""
        await self.client.delete(key)

    # Методы для статистики
    async def increment_counter(self, key: str) -> int:
        """Увеличить счетчик."""
        return await self.client.incr(key)

    async def get_counter(self, key: str) -> int:
        """Получить значение счетчика."""
        value = await self.client.get(key)
        return int(value) if value else 0


# Глобальный экземпляр
redis_client = RedisClient()

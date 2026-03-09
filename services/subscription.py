import logging
import re
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from core.config import settings
from core.database import Channel, async_session_maker
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def get_active_channels() -> list[Channel]:
    """Получить список активных каналов."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        return list(result.scalars().all())


async def check_subscription(user_id: int) -> bool:
    """
    Проверка подписки пользователя на все каналы.

    Args:
        user_id: ID пользователя в Telegram.

    Returns:
        True если пользователь подписан на все каналы, False иначе.
    """
    # Получаем активные каналы из БД
    channels = await get_active_channels()
    
    # Если каналов нет - подписка не требуется
    if not channels:
        return True

    # Пробуем получить кэш из Redis (если доступен)
    try:
        from core.redis import redis_client
        cached_result = await redis_client.get_user_subscription_check(user_id)
        if cached_result is not None:
            logger.debug(f"Подписка пользователя {user_id} получена из кэша: {cached_result}")
            return cached_result
    except Exception as e:
        logger.debug(f"Redis недоступен, пропускаем кэш: {e}")

    bot = Bot(token=settings.BOT_TOKEN)
    all_subscribed = True

    try:
        for channel in channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_id,
                    user_id=user_id,
                )

                # Проверяем статус участника
                is_subscribed = member.status in ("member", "administrator", "creator")
                
                if not is_subscribed:
                    all_subscribed = False
                    logger.debug(f"Пользователь {user_id} не подписан на канал {channel.username}")
                    break

            except TelegramBadRequest as e:
                logger.error(f"Ошибка проверки канала {channel.username}: {e}")
                # Если бот не админ канала - считаем что подписки нет
                all_subscribed = False
                break

        # Кэшируем результат проверки подписки (TTL=60 секунд)
        # Это снижает нагрузку на Telegram API при частых запросах
        try:
            from core.redis import redis_client
            await redis_client.set_user_subscription_check(user_id, all_subscribed, ttl=60)
            logger.debug(f"Кэш подписки пользователя {user_id} обновлён: {all_subscribed}")
        except Exception as e:
            logger.debug(f"Не удалось закэшировать в Redis: {e}")

        logger.debug(f"Пользователь {user_id} подписан на все каналы: {all_subscribed}")
        return all_subscribed

    except Exception as e:
        logger.exception(f"Неожиданная ошибка проверки подписки: {e}")
        return False

    finally:
        await bot.session.close()


async def clear_subscription_cache(user_id: int):
    """
    Очистка кэша подписки пользователя.
    """
    try:
        from core.redis import redis_client
        await redis_client.client.delete(f"user:{user_id}:subscription")
        logger.debug(f"Кэш подписки пользователя {user_id} очищен")
    except Exception as e:
        logger.debug(f"Не удалось очистить кэш Redis: {e}")


def parse_channel_username(text: str) -> str | None:
    """
    Парсинг username канала из текста.
    
    Поддерживаемые форматы:
    - t.me/username
    - https://t.me/username
    - @username
    - username
    """
    text = text.strip()
    
    # Удаляем префиксы
    if text.startswith("https://t.me/"):
        text = text[13:]
    elif text.startswith("t.me/"):
        text = text[5:]
    elif text.startswith("@"):
        text = text[1:]
    
    # Проверяем что остался только username
    if re.match(r'^[a-zA-Z0-9_]{5,32}$', text):
        return text
    
    return None

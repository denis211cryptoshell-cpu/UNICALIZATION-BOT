from typing import Callable, Any
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from core.config import settings

logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки пользователей."""

    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        # Получаем пользователя
        if isinstance(event, Message):
            user_id = event.from_user.id
            message = event
            callback = None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            message = None
            callback = event
        else:
            logger.warning(f"Unknown event type: {type(event)}")
            return await handler(event, data)

        # Пропускаем администраторов
        if user_id in settings.admin_ids:
            return await handler(event, data)

        # Проверяем наличие активных каналов
        from services.subscription import get_active_channels
        channels = await get_active_channels()

        if not channels:
            return await handler(event, data)

        # Пропускаем только /start
        if isinstance(event, Message):
            if event.text and event.text == "/start":
                return await handler(event, data)

        # Пропускаем кнопку проверки подписки
        if isinstance(event, CallbackQuery):
            if event.data == "check_subscription":
                return await handler(event, data)

        # Проверка подписки
        from services.subscription import check_subscription
        is_subscribed = await check_subscription(user_id)

        if not is_subscribed:
            # Формируем сообщение о необходимости подписки
            channels_text = "\n".join([f"• @{ch.username}" for ch in channels])
            subscribe_text = (
                "❌ <b>Доступ запрещён!</b>\n\n"
                "Для использования бота необходимо подписаться на наши каналы:\n\n"
                f"{channels_text}\n\n"
                "После подписки нажмите кнопку ниже."
            )

            from bot.keyboards.inline import get_subscribe_keyboard
            keyboard = get_subscribe_keyboard()

            if message:
                await message.answer(
                    subscribe_text,
                    reply_markup=keyboard,
                )
            elif callback:
                await callback.message.edit_text(
                    subscribe_text,
                    reply_markup=keyboard,
                )
                await callback.answer()

            return None

        return await handler(event, data)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой подписки."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я подписался",
                    callback_data="check_subscription",
                )
            ],
        ]
    )
    return keyboard


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая клавиатура."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Уникализировать видео",
                    callback_data="start_processing",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Моя статистика",
                    callback_data="my_stats",
                )
            ],
        ]
    )
    return keyboard

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
    """Стартовая клавиатура (главное меню)."""
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
                ),
                InlineKeyboardButton(
                    text="❓ Помощь",
                    callback_data="my_help",
                ),
            ],
        ]
    )
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой «Назад» (в главное меню)."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="« Назад в главное меню",
                    callback_data="back_to_start",
                )
            ],
        ]
    )
    return keyboard


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для статистики (Обновить + Назад)."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="my_stats",
                ),
                InlineKeyboardButton(
                    text="« Назад",
                    callback_data="back_to_start",
                ),
            ],
        ]
    )
    return keyboard


def get_upload_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для режима загрузки видео (Отмена)."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить загрузку",
                    callback_data="cancel_upload",
                )
            ],
        ]
    )
    return keyboard


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели с кнопкой главное меню."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin_users",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin_stats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка",
                    callback_data="admin_broadcast",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📺 Каналы подписки",
                    callback_data="admin_channels",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="back_to_start",
                )
            ],
        ]
    )
    return keyboard


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопками «В админку» и «Главное меню»."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔧 В админ-панель",
                    callback_data="admin",
                ),
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="back_to_start",
                ),
            ],
        ]
    )
    return keyboard

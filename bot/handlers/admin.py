import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.config import settings
from core.database import User, ProcessingTask, Channel, async_session_maker, SubscriptionStatus
from sqlalchemy import select, func
from services.subscription import parse_channel_username

logger = logging.getLogger(__name__)

router = Router()


class Broadcast(StatesGroup):
    """Состояния для рассылки сообщений."""
    waiting_for_message = State()


class AddChannel(StatesGroup):
    """Состояния для добавления канала."""
    waiting_for_channel_link = State()


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь администратором."""
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель."""
    if not is_admin(message.from_user.id):
        return

    text = (
        "🔧 <b>Панель администратора</b>\n\n"
        "Выберите действие:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        ]
    )

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    """Просмотр списка пользователей."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        total = len(users)
        active = sum(1 for u in users if u.subscription_status == SubscriptionStatus.ACTIVE)
        trial = sum(1 for u in users if u.subscription_status == SubscriptionStatus.TRIAL)

    text = (
        "👥 <b>Пользователи</b>\n\n"
        f"Всего: {total}\n"
        f"Активные: {active}\n"
        f"Триал: {trial}\n\n"
        "Последние 10 пользователей:\n"
    )

    # Показываем последних 10 пользователей
    for user in sorted(users, key=lambda u: u.created_at, reverse=True)[:10]:
        status_emoji = {"none": "❌", "trial": "🆓", "active": "✅", "expired": "⏰"}.get(
            user.subscription_status.value, "❓"
        )
        text += (
            f"\n{status_emoji} <code>{user.telegram_id}</code> - "
            f"{user.first_name or 'Unknown'}"
        )
        if user.subscription_expires_at:
            text += f" (до {user.subscription_expires_at.strftime('%d.%m')})"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="admin_users",
                )
            ],
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Просмотр статистики."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    async with async_session_maker() as session:
        # Общая статистика
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(
                User.subscription_status == SubscriptionStatus.ACTIVE
            )
        )

        # Статистика задач
        total_tasks = await session.scalar(select(func.count(ProcessingTask.id)))
        completed_tasks = await session.scalar(
            select(func.count(ProcessingTask.id)).where(
                ProcessingTask.status == "completed"
            )
        )
        failed_tasks = await session.scalar(
            select(func.count(ProcessingTask.id)).where(
                ProcessingTask.status == "failed"
            )
        )

        # Статистика за сегодня
        today = datetime.utcnow().date()
        today_tasks = await session.scalar(
            select(func.count(ProcessingTask.id)).where(
                func.date(ProcessingTask.created_at) == today
            )
        )

    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователи:\n"
        f"  • Всего: {total_users}\n"
        f"  • Активные: {active_users}\n\n"
        f"📹 Задачи:\n"
        f"  • Всего: {total_tasks}\n"
        f"  • Успешно: {completed_tasks}\n"
        f"  • С ошибками: {failed_tasks}\n"
        f"  • Сегодня: {today_tasks}\n\n"
        f"🤖 Статус: {'🟢 Работает' if total_users > 0 else '🔴 Ожидает пользователей'}"
    )

    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начало рассылки."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    await state.set_state(Broadcast.waiting_for_message)

    text = (
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение, которое будет отправлено всем пользователям.\n\n"
        "Поддерживается HTML-разметка.\n"
        "Или нажмите /cancel для отмены."
    )

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(Broadcast.waiting_for_message, F.text)
async def handle_broadcast_message(message: Message, state: FSMContext):
    """Отправка рассылки."""
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    broadcast_text = message.text

    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

    sent_count = 0
    failed_count = 0

    bot = Bot(token=settings.BOT_TOKEN)

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=broadcast_text,
                parse_mode="HTML",
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
            failed_count += 1

    await bot.session.close()

    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: {sent_count}\n"
        f"Не доставлено: {failed_count}"
    )


# ==================== Управление каналами ====================

@router.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery):
    """Просмотр списка каналов."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    async with async_session_maker() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        text = (
            "📺 <b>Каналы подписки</b>\n\n"
            "Список каналов пуст.\n\n"
            "Добавьте первый канал для обязательной подписки."
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Добавить канал",
                        callback_data="admin_channel_add",
                    )
                ],
            ]
        )
    else:
        text = "📺 <b>Каналы подписки</b>\n\n"
        keyboard_buttons = []
        
        for i, channel in enumerate(channels, 1):
            status = "✅" if channel.is_active else "❌"
            text += f"{status} <code>{channel.username}</code> - {channel.title or 'Без названия'}\n"
            text += f"   ID: <code>{channel.channel_id}</code>\n\n"
            
            # Кнопки управления для каждого канала
            toggle_text = "🚫 Выкл" if channel.is_active else "✅ Вкл"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_channel_toggle_{channel.id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"admin_channel_delete_{channel.id}",
                ),
            ])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Добавить канал",
                        callback_data="admin_channel_add",
                    )
                ],
                *keyboard_buttons,
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить",
                        callback_data="admin_channels",
                    )
                ],
            ]
        )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_channel_add")
async def cb_admin_channel_add(callback: CallbackQuery, state: FSMContext):
    """Добавление канала."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    await state.set_state(AddChannel.waiting_for_channel_link)

    text = (
        "📺 <b>Добавление канала</b>\n\n"
        "Отправьте ссылку на канал или username:\n"
        "- t.me/username\n"
        "- @username\n"
        "- username\n\n"
        "⚠️ <b>Важно:</b> Бот должен быть администратором в канале!\n\n"
        "Или нажмите /cancel для отмены."
    )

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(AddChannel.waiting_for_channel_link, F.text)
async def handle_channel_link(message: Message, state: FSMContext):
    """Обработка ссылки на канал."""
    if not is_admin(message.from_user.id):
        return

    username = parse_channel_username(message.text)

    if not username:
        await message.answer(
            "❌ Неверный формат канала.\n\n"
            "Отправьте ссылку в формате:\n"
            "- t.me/username\n"
            "- @username\n"
            "- username\n\n"
            "Или нажмите /cancel для отмены."
        )
        return

    await state.update_data(channel_username=username)

    bot = Bot(token=settings.BOT_TOKEN)

    try:
        # Получаем информацию о канале
        chat = await bot.get_chat(f"@{username}")

        if chat.type not in ("channel", "supergroup"):
            await message.answer("❌ Это не канал. Отправьте ссылку на канал.")
            return

        # Проверяем что бот админ в канале
        member = await bot.get_chat_member(chat.id, bot.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                "❌ Бот не является администратором этого канала.\n\n"
                "Добавьте бота в канал с правами администратора."
            )
            return

        # Сохраняем канал в БД
        async with async_session_maker() as session:
            # Проверяем существует ли уже такой канал
            existing = await session.execute(
                select(Channel).where(
                    (Channel.channel_id == chat.id) | (Channel.username == username)
                )
            )
            if existing.scalar_one_or_none():
                await message.answer("❌ Этот канал уже добавлен.")
                await state.clear()
                return

            channel = Channel(
                channel_id=chat.id,
                username=username,
                title=chat.title,
                is_active=True,
            )
            session.add(channel)
            await session.commit()

        await state.clear()

        await message.answer(
            f"✅ <b>Канал добавлен!</b>\n\n"
            f"Название: {chat.title}\n"
            f"Username: @{username}\n"
            f"ID: <code>{chat.id}</code>\n\n"
            "Теперь пользователи должны будут подписаться на этот канал."
        )

    except Exception as e:
        logger.error(f"Ошибка добавления канала: {e}")
        await message.answer(f"❌ Ошибка: {e}")

    finally:
        await bot.session.close()


@router.callback_query(F.data.startswith("admin_channel_toggle_"))
async def cb_admin_channel_toggle(callback: CallbackQuery):
    """Включение/выключение канала."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    channel_id = int(callback.data.split("_")[-1])

    async with async_session_maker() as session:
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if not channel:
            await callback.answer("❌ Канал не найден.")
            return

        channel.is_active = not channel.is_active
        await session.commit()

        status = "активирован" if channel.is_active else "деактивирован"
        await callback.answer(f"✅ Канал {status}")

        # Обновляем список каналов
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

        text = "📺 <b>Каналы подписки</b>\n\n"
        keyboard_buttons = []
        
        for i, ch in enumerate(channels, 1):
            status = "✅" if ch.is_active else "❌"
            text += f"{status} <code>{ch.username}</code> - {ch.title or 'Без названия'}\n"
            text += f"   ID: <code>{ch.channel_id}</code>\n\n"
            
            toggle_text = "🚫 Выкл" if ch.is_active else "✅ Вкл"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_channel_toggle_{ch.id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"admin_channel_delete_{ch.id}",
                ),
            ])

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Добавить канал",
                        callback_data="admin_channel_add",
                    )
                ],
                *keyboard_buttons,
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить",
                        callback_data="admin_channels",
                    )
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin_channel_delete_"))
async def cb_admin_channel_delete(callback: CallbackQuery):
    """Удаление канала."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    channel_id = int(callback.data.split("_")[-1])

    async with async_session_maker() as session:
        result = await session.execute(
            select(Channel).where(Channel.id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if not channel:
            await callback.answer("❌ Канал не найден.")
            return

        await session.delete(channel)
        await session.commit()

        await callback.answer(f"✅ Канал @{channel.username} удален")

        # Обновляем список каналов
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

        if not channels:
            text = (
                "📺 <b>Каналы подписки</b>\n\n"
                "Список каналов пуст.\n\n"
                "Добавьте первый канал для обязательной подписки."
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➕ Добавить канал",
                            callback_data="admin_channel_add",
                        )
                    ],
                ]
            )
        else:
            text = "📺 <b>Каналы подписки</b>\n\n"
            keyboard_buttons = []
            
            for i, ch in enumerate(channels, 1):
                status = "✅" if ch.is_active else "❌"
                text += f"{status} <code>{ch.username}</code> - {ch.title or 'Без названия'}\n"
                text += f"   ID: <code>{ch.channel_id}</code>\n\n"
                
                toggle_text = "🚫 Выкл" if ch.is_active else "✅ Вкл"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=toggle_text,
                        callback_data=f"admin_channel_toggle_{ch.id}",
                    ),
                    InlineKeyboardButton(
                        text="🗑 Удалить",
                        callback_data=f"admin_channel_delete_{ch.id}",
                    ),
                ])

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➕ Добавить канал",
                            callback_data="admin_channel_add",
                        )
                    ],
                    *keyboard_buttons,
                    [
                        InlineKeyboardButton(
                            text="🔄 Обновить",
                            callback_data="admin_channels",
                        )
                    ],
                ]
            )

        await callback.message.edit_text(text, reply_markup=keyboard)

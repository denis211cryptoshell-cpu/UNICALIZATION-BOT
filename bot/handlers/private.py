import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.config import settings
from core.database import User, SubscriptionStatus, ProcessingTask, async_session_maker
from sqlalchemy import select
from datetime import datetime, timedelta
from services.subscription import check_subscription, clear_subscription_cache
from bot.keyboards.inline import get_start_keyboard, get_subscribe_keyboard

logger = logging.getLogger(__name__)

router = Router()


class VideoUpload(StatesGroup):
    """Состояния для загрузки видео."""
    waiting_for_video = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()

    # Получаем или создаём пользователя
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            session.add(user)
            await session.commit()
            logger.info(f"Новый пользователь: {user.telegram_id}")

    text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я бот для уникализации видео.\n"
        "Отправь мне видео, и я сделаю его уникальным.\n\n"
        "📹 <b>Как это работает:</b>\n"
        "1. Отправь видео\n"
        "2. Дождись обработки\n"
        "3. Получи уникализированное видео\n\n"
        "Нажми кнопку ниже, чтобы начать."
    )

    await message.answer(
        text,
        reply_markup=get_start_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "📹 <b>Уникализация видео:</b>\n"
        "Отправьте видеофайл, и бот обработает его.\n\n"
        "📊 <b>Статистика:</b>\n"
        "Узнайте количество обработанных видео.\n\n"
        "⚙️ <b>Команды:</b>\n"
        "/start - Запустить бота\n"
        "/help - Показать эту справку\n"
        "/stats - Моя статистика\n"
        "/cancel - Отменить текущее действие"
    )
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработчик команды /stats."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Пользователь не найден.")
            return

        # Получаем количество задач
        result = await session.execute(
            select(ProcessingTask).where(ProcessingTask.user_id == message.from_user.id)
        )
        tasks = result.scalars().all()
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")

    # Статус подписки
    status_text = "Не активна"
    if user.subscription_status == SubscriptionStatus.ACTIVE:
        if user.subscription_expires_at:
            expires = user.subscription_expires_at.strftime("%d.%m.%Y %H:%M")
            status_text = f"Активна до {expires}"
        else:
            status_text = "Активна"

    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"📹 Видео обработано: {user.videos_processed}\n"
        f"✅ Успешно: {completed}\n"
        f"❌ С ошибками: {failed}\n\n"
        f"💎 Подписка: {status_text}"
    )

    await message.answer(text)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel."""
    await state.clear()
    await message.answer("❌ Действие отменено.")


@router.callback_query(F.data == "start_processing")
async def cb_start_processing(callback: CallbackQuery, state: FSMContext):
    """Начало процесса загрузки видео."""
    await state.clear()
    await state.set_state(VideoUpload.waiting_for_video)

    text = (
        "📹 <b>Отправьте видео для уникализации</b>\n\n"
        f"Максимальный размер: {settings.MAX_VIDEO_SIZE_MB} МБ\n"
        "Поддерживаемые форматы: MP4, AVI, MOV, MKV\n\n"
        "Или нажмите /cancel для отмены."
    )

    await callback.message.edit_text(text)
    await callback.answer()


@router.message(VideoUpload.waiting_for_video, F.video)
async def handle_video(message: Message, state: FSMContext):
    """Обработка полученного видео."""
    video = message.video

    # Проверка размера файла
    file_size_mb = video.file_size / (1024 * 1024)
    if file_size_mb > settings.MAX_VIDEO_SIZE_MB:
        await message.answer(
            f"❌ Файл слишком большой.\n"
            f"Максимальный размер: {settings.MAX_VIDEO_SIZE_MB} МБ\n"
            f"Ваш файл: {file_size_mb:.2f} МБ"
        )
        return

    await state.clear()

    # Создаём задачу в БД
    async with async_session_maker() as session:
        processing_task = ProcessingTask(
            user_id=message.from_user.id,
            input_file_id=video.file_id,
            input_file_name=video.file_name or "video.mp4",
            status="pending",
            request_message_id=message.message_id,
        )
        session.add(processing_task)
        await session.commit()
        task_id = processing_task.id

    # Отправляем сообщение о начале обработки
    status_message = await message.answer(
        "⏳ <b>Видео принято в обработку...</b>\n\n"
        f"📁 Файл: {video.file_name or 'video.mp4'}\n"
        f"📊 Размер: {file_size_mb:.2f} МБ\n\n"
        "Ожидайте завершения обработки."
    )

    # Обновляем ID сообщения статуса
    async with async_session_maker() as session:
        await session.execute(
            ProcessingTask.__table__.update()
            .where(ProcessingTask.id == task_id)
            .values(status_message_id=status_message.message_id)
        )
        await session.commit()

    # Запускаем Celery задачу
    try:
        from worker.tasks import process_video
        process_video.delay(task_id, message.from_user.id, video.file_id, video.file_name or "video.mp4")
        logger.info(f"Задача Celery запущена. Task ID: {task_id}")
    except Exception as e:
        logger.error(f"Ошибка запуска Celery: {e}")
        await message.answer(f"❌ Ошибка запуска обработки: {e}")
        return

    await message.answer(
        "✅ <b>Задача запущена!</b>\n\n"
        "Ожидайте завершения обработки.\n"
        "Мы уведомим вас, когда видео будет готово."
    )


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery):
    """Проверка подписки по кнопке."""
    from services.subscription import get_active_channels
    
    # Очищаем кэш и проверяем заново
    await clear_subscription_cache(callback.from_user.id)
    is_subscribed = await check_subscription(callback.from_user.id)

    if is_subscribed:
        # Обновляем статус в БД
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()

            if user:
                user.subscription_status = SubscriptionStatus.ACTIVE
                if not user.subscription_expires_at:
                    user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
                await session.commit()

        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\n"
            "Теперь вы можете использовать все функции бота."
        )
        await callback.message.answer(
            "🎬 <b>Готовы начать?</b>\n\n"
            "Нажмите кнопку ниже, чтобы загрузить видео.",
            reply_markup=get_start_keyboard(),
        )
    else:
        # Получаем активные каналы и показываем ссылки
        channels = await get_active_channels()
        
        if channels:
            channels_text = "\n".join([
                f"• [{ch.username}](https://t.me/{ch.username})"
                for ch in channels
            ])
            await callback.answer(
                f"❌ Вы не подписаны на каналы:\n\n{channels_text}\n\n"
                f"Подпишитесь и нажмите 'Я подписался' ещё раз.",
                show_alert=True,
            )
        else:
            await callback.answer("❌ Подписка не найдена. Попробуйте ещё раз.", show_alert=True)


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(callback: CallbackQuery):
    """Показ статистики пользователя."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return

        result = await session.execute(
            select(ProcessingTask).where(ProcessingTask.user_id == callback.from_user.id)
        )
        tasks = result.scalars().all()
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")

    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"📹 Всего видео: {user.videos_processed}\n"
        f"✅ Обработано: {completed}\n"
        f"📥 В очереди: {total - completed}"
    )

    await callback.message.answer(text)
    await callback.answer()

import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from celery import Task
from worker.celery import celery_app
from core.database import ProcessingTask, User, async_session_maker, SubscriptionStatus
from core.config import settings
from services.video_uniquer import video_uniquer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

logger = logging.getLogger(__name__)


class BotTask(Task):
    """Базовый класс для задач с доступом к боту."""

    _bot = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=settings.BOT_TOKEN)
        return self._bot


@celery_app.task(
    base=BotTask,
    bind=True,
    name="worker.tasks.process_video",
    queue="video_processing",
)
def process_video(self, task_id: int, user_id: int, input_file_id: str, input_file_name: str):
    """
    Задача обработки видео.
    """
    bot = self.bot
    
    # Запускаем ВСЮ асинхронную работу в одном event loop
    async def run_task():
        input_path = None
        output_path = None
        
        async with async_session_maker() as session:
            try:
                # Обновляем статус задачи
                await session.execute(
                    ProcessingTask.__table__.update()
                    .where(ProcessingTask.id == task_id)
                    .values(
                        status="processing",
                        started_at=datetime.utcnow(),
                    )
                )
                await session.commit()

                logger.info(f"Начало обработки задачи {task_id} для пользователя {user_id}")

                # Скачиваем файл от Telegram
                input_path = settings.input_path / f"{task_id}_{input_file_name}"

                # Скачиваем файл через Bot API
                file = await bot.get_file(input_file_id)
                await bot.download_file(file.file_path, input_path)
                logger.info(f"Файл скачан: {input_path}")

                # Уникализация видео
                output_path = await video_uniquer.process(input_path)

                if output_path is None:
                    raise Exception("Не удалось обработать видео")

                logger.info(f"Видео обработано: {output_path}")

                # Обновляем задачу в БД
                await session.execute(
                    ProcessingTask.__table__.update()
                    .where(ProcessingTask.id == task_id)
                    .values(
                        status="completed",
                        completed_at=datetime.utcnow(),
                        output_file_name=output_path.name,
                    )
                )

                # Обновляем статистику пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    user.videos_processed += 1
                    if user.subscription_status == SubscriptionStatus.NONE:
                        user.subscription_status = SubscriptionStatus.TRIAL
                        user.subscription_expires_at = datetime.utcnow() + timedelta(days=7)

                await session.commit()

                # Отправляем результат пользователю
                with open(output_path, "rb") as f:
                    await bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption="✅ <b>Видео уникализировано!</b>\n\n"
                                "Файл готов к использованию.",
                    )
                logger.info(f"Задача {task_id} завершена успешно. Видео отправлено пользователю {user_id}")

                return {"status": "completed", "output_file": str(output_path)}

            except Exception as e:
                logger.exception(f"Ошибка обработки задачи {task_id}: {e}")

                # Обновляем статус задачи на failed
                await session.execute(
                    ProcessingTask.__table__.update()
                    .where(ProcessingTask.id == task_id)
                    .values(
                        status="failed",
                        completed_at=datetime.utcnow(),
                        error_message=str(e),
                    )
                )
                await session.commit()

                return {"status": "failed", "error": str(e)}

            finally:
                # Очистка файлов
                if input_path and input_path.exists():
                    try:
                        input_path.unlink()
                    except Exception:
                        pass

    # Запускаем в одном event loop
    return asyncio.run(run_task())


@celery_app.task(name="worker.tasks.check_subscriptions")
def check_subscriptions():
    """
    Периодическая задача проверки истёкших подписок.
    """
    from services.subscription import clear_subscription_cache

    logger.info("Запуск проверки подписок")

    async def run_check():
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(
                    User.subscription_status == SubscriptionStatus.ACTIVE,
                    User.subscription_expires_at != None,
                )
            )
            users = result.scalars().all()

            expired_count = 0
            for user in users:
                if user.subscription_expires_at < datetime.utcnow():
                    user.subscription_status = SubscriptionStatus.EXPIRED
                    expired_count += 1
                    clear_subscription_cache(user.telegram_id)
                    logger.info(f"Подписка пользователя {user.telegram_id} истекла")

            await session.commit()

        logger.info(f"Проверка подписок завершена. Истекло: {expired_count}")
        return {"expired": expired_count}

    return asyncio.run(run_check())

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from core.config import settings
from core.database import init_db, close_db
from core.redis import redis_client
from bot.middlewares.subscription import SubscriptionMiddleware

# Импорт хендлеров
from bot.handlers import private, admin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Выполняется при запуске бота."""
    logger.info("Бот запускается...")
    
    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")
    
    # Подключение к Redis (опционально)
    try:
        await redis_client.connect()
        logger.info("Redis подключен")
    except Exception as e:
        logger.warning(f"Redis не доступен (работаем без кэширования): {e}")
    
    # Создание папок для хранения файлов
    settings.input_path.mkdir(parents=True, exist_ok=True)
    settings.output_path.mkdir(parents=True, exist_ok=True)
    logger.info("Папки для файлов созданы")
    
    # Уведомление админа
    if settings.admin_ids:
        try:
            await bot.send_message(
                next(iter(settings.admin_ids)),
                "🟢 Бот успешно запущен!",
            )
        except Exception:
            pass


async def on_shutdown(bot: Bot):
    """Выполняется при остановке бота."""
    logger.info("Бот останавливается...")
    
    # Закрытие соединений
    try:
        await redis_client.close()
    except Exception:
        pass
    await close_db()
    
    logger.info("Все соединения закрыты")


def create_dispatcher() -> Dispatcher:
    """Создание и настройка диспетчера."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрация middleware
    subscription_middleware = SubscriptionMiddleware()
    
    # Регистрация роутеров с middleware
    private.router.message.middleware(subscription_middleware)
    private.router.callback_query.middleware(subscription_middleware)
    admin.router.message.middleware(subscription_middleware)
    admin.router.callback_query.middleware(subscription_middleware)
    
    dp.include_router(private.router)
    dp.include_router(admin.router)

    # Регистация хендлеров запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp


async def main():
    """Точка входа."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    dp = create_dispatcher()
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

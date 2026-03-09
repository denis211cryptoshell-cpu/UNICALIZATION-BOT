from datetime import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, Enum, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import settings
import enum


class Base(DeclarativeBase):
    """Базовый класс для моделей."""
    pass


class SubscriptionStatus(enum.Enum):
    """Статусы подписки."""
    NONE = "none"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"


class User(Base):
    """Модель пользователя."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Подписка
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus),
        default=SubscriptionStatus.NONE
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Статистика
    videos_processed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Даты
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, status={self.subscription_status})>"


class ProcessingTask(Base):
    """Модель задачи обработки видео."""
    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False
    )

    # Информация о задаче
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Файлы
    input_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    input_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    output_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Сообщения
    request_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Ошибки
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Даты
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ProcessingTask(id={self.id}, status={self.status})>"


class Channel(Base):
    """Модель канала для обязательной подписки."""
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Даты
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Channel(username={self.username}, active={self.is_active})>"


# Определение типа БД
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Настройки пула соединений для PostgreSQL
POOL_SIZE = 20 if not IS_SQLITE else None  # Количество соединений в пуле
MAX_OVERFLOW = 40 if not IS_SQLITE else None  # Дополнительные соединения при пиковой нагрузке
POOL_TIMEOUT = 30 if not IS_SQLITE else None  # Таймаут ожидания соединения
POOL_RECYCLE = 1800 if not IS_SQLITE else None  # Пересоздавать соединения каждые 30 минут

# Создание движка и сессии
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=not IS_SQLITE,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Получить сессию базы данных."""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Инициализация базы данных (создание таблиц)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Закрытие соединения с базой данных."""
    await engine.dispose()

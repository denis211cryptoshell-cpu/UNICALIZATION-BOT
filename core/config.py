import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Конфигурация проекта."""

    # Telegram Bot
    BOT_TOKEN: str = Field(..., description="Токен Telegram бота")
    BOT_ADMIN_IDS: str = Field(
        default="",
        description="Список ID администраторов через запятую"
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/uniquer_bot",
        description="URL подключения к PostgreSQL"
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL подключения к Redis"
    )

    # Celery
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="URL брокера для Celery"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="URL бэкенда результатов для Celery"
    )

    # Subscription Check
    SUBSCRIPTION_CHANNEL_ID: str = Field(
        default="",
        description="ID канала для проверки подписки"
    )
    SUBSCRIPTION_CHANNEL_USERNAME: str = Field(
        default="",
        description="Юзернейм канала для проверки подписки"
    )

    # Paths
    STORAGE_INPUT_PATH: str = Field(
        default="./storage/input",
        description="Путь к папке входящих файлов"
    )
    STORAGE_OUTPUT_PATH: str = Field(
        default="./storage/output",
        description="Путь к папке исходящих файлов"
    )

    # Video Processing
    FFMPEG_PATH: str = Field(
        default="ffmpeg",
        description="Путь к исполняемому файлу FFmpeg"
    )
    MAX_VIDEO_SIZE_MB: int = Field(
        default=50,
        description="Максимальный размер видео в МБ"
    )
    PROCESSING_TIMEOUT_SECONDS: int = Field(
        default=300,
        description="Таймаут обработки видео в секундах"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def admin_ids(self) -> set[int]:
        """Получить список ID администраторов."""
        if not self.BOT_ADMIN_IDS:
            return set()
        return {int(id.strip()) for id in self.BOT_ADMIN_IDS.split(",") if id.strip()}

    @property
    def input_path(self) -> Path:
        """Получить абсолютный путь к папке входящих файлов."""
        return Path(self.STORAGE_INPUT_PATH).resolve()

    @property
    def output_path(self) -> Path:
        """Получить абсолютный путь к папке исходящих файлов."""
        return Path(self.STORAGE_OUTPUT_PATH).resolve()


settings = Settings()

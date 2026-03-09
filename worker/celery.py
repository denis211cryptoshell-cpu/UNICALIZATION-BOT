from celery import Celery
from core.config import settings


# Создание приложения Celery
celery_app = Celery(
    "video_uniquer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["worker.tasks"],
)

# Конфигурация Celery для продакшена
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Таймауты
    task_ack_late=True,
    task_time_limit=settings.PROCESSING_TIMEOUT_SECONDS,
    task_soft_time_limit=settings.PROCESSING_TIMEOUT_SECONDS - 30,

    # Повторные попытки
    task_acks_late=True,
    task_reject_on_worker_or_memloss=True,
    task_default_retry_delay=60,
    task_max_retries=3,

    # Очереди
    task_routes={
        "worker.tasks.process_video": {"queue": "video_processing"},
        "worker.tasks.check_subscriptions": {"queue": "default"},
    },

    # Rate limiting - оптимизация для высокой нагрузки
    worker_prefetch_multiplier=1,  # Не брать больше 1 задачи за раз
    worker_max_tasks_per_child=100,  # Перезапускать воркер каждые 100 задач
    
    # Размеры очередей
    broker_transport_options={"visibility_timeout": 3600},
    
    # Количество одновременных задач на воркер
    worker_concurrency=4,
)

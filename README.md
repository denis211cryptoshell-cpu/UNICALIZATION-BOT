# 🤖 Бот для уникализации видео — Полная документация

## 📋 Содержание

1. [Архитектура проекта](#архитектура-проекта)
2. [Структура файлов](#структура-файлов)
3. [Как это работает](#как-это-работает)
4. [Подробное описание компонентов](#подробное-описание-компонентов)
5. [База данных](#база-данных)
6. [Middleware подписки](#middleware-подписки)
7. [Админ-панель](#админ-панель)
8. [Установка и запуск](#установка-и-запуск)
9. [Конфигурация](#конфигурация)

---

## 🏗 Архитектура проекта

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram Bot                              │
│                     (aiogram 3.x framework)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Middleware Layer                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SubscriptionMiddleware — проверка подписки на каналы    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│   Private Handlers      │      │    Admin Handlers       │
│  - /start, /help        │      │   - /admin              │
│  - Обработка видео      │      │   - Управление каналами │
│  - Проверка подписки    │      │   - Рассылка            │
│  - Статистика           │      │   - Статистика          │
└─────────────────────────┘      └─────────────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌────────────────────┐  ┌─────────────────────────────────┐   │
│  │ subscription.py    │  │      video_uniquer.py           │   │
│  │ - check_subscription│ │      - FFmpeg обработка         │   │
│  │ - get_active_channels│ │      - Уникализация видео       │   │
│  └────────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
│  ┌────────────────────┐  ┌─────────────────────────────────┐   │
│  │   PostgreSQL/SQLite│  │           Redis                 │   │
│  │   - Users          │  │   - Кэш подписок (опционально)  │   │
│  │   - Channels       │  │   - Сессии                      │   │
│  │   - ProcessingTasks│  │                                 │   │
│  └────────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Структура файлов

```
бот уникализатор/
├── .env                      # Конфигурация (токены, URL БД)
├── .env.example              # Пример конфигурации
├── requirements.txt          # Python зависимости
├── README.md                 # Эта документация
├── DEPLOY.md                 # Инструкция по деплою на VPS
│
├── bot/                      # Telegram бот (aiogram)
│   ├── __init__.py
│   ├── main.py               # ТОЧКА ВХОДА — запуск бота
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── private.py        # Обработчики для пользователей
│   │   └── admin.py          # Админ-панель
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py         # Inline-клавиатуры
│   └── middlewares/
│       ├── __init__.py
│       └── subscription.py   # ПРОВЕРКА ПОДПИСКИ (ВАЖНО!)
│
├── core/                     # Ядро проекта
│   ├── __init__.py
│   ├── config.py             # Конфигурация (pydantic)
│   ├── database.py           # SQLAlchemy модели + сессии
│   └── redis.py              # Redis клиент
│
├── services/                 # Бизнес-логика
│   ├── __init__.py
│   ├── subscription.py       # Логика проверки подписки
│   └── video_uniquer.py      # FFmpeg уникализация
│
├── worker/                   # Celery worker (фоновые задачи)
│   ├── __init__.py
│   ├── celery.py             # Настройка Celery
│   └── tasks.py              # Задачи обработки видео
│
├── admin_panel/              # Веб-админка (будущая)
│   └── __init__.py
│
└── storage/                  # Файловое хранилище
    ├── input/                # Входные видео
    └── output/               # Обработанные видео
```

---

## ⚙️ Как это работает

### 1. Запуск бота

**Файл:** `bot/main.py`

```python
# ТОЧКА ВХОДА
if __name__ == "__main__":
    asyncio.run(main())
```

**Что происходит:**
1. Создаётся `Bot` и `Dispatcher`
2. Регистрируются middleware (проверка подписки)
3. Подключаются роутеры (handlers)
4. Инициализируется БД и Redis
5. Запускается polling (ожидание сообщений от Telegram)

### 2. Обработка сообщения

```
Пользователь отправляет сообщение
         │
         ▼
┌────────────────────────┐
│  SubscriptionMiddleware│ ← ПРОВЕРКА ПОДПИСКИ
│  (срабатывает ПЕРВЫМ)  │
└────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Подписан   НЕ подписан
    │         │
    ▼         ▼
Хендлер   Блокировка +
          сообщение о
          подписке
```

### 3. Middleware подписки (КРИТИЧЕСКИ ВАЖНО)

**Файл:** `bot/middlewares/subscription.py`

```python
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        # 1. Получаем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        # 2. Пропускаем администраторов
        if user_id in settings.admin_ids:
            return await handler(event, data)
        
        # 3. Получаем активные каналы из БД
        channels = await get_active_channels()
        
        # 4. Если каналов нет — пропускаем всех
        if not channels:
            return await handler(event, data)
        
        # 5. Пропускаем /start
        if isinstance(event, Message):
            if event.text == "/start":
                return await handler(event, data)
        
        # 6. Пропускаем кнопку "Я подписался"
        if isinstance(event, CallbackQuery):
            if event.data == "check_subscription":
                return await handler(event, data)
        
        # 7. ПРОВЕРКА ПОДПИСКИ
        is_subscribed = await check_subscription(user_id)
        
        # 8. БЛОКИРОВКА если не подписан
        if not is_subscribed:
            channels_text = "\n".join([f"• @{ch.username}" for ch in channels])
            subscribe_text = (
                "❌ <b>Доступ запрещён!</b>\n\n"
                "Для использования бота необходимо подписаться:\n\n"
                f"{channels_text}\n\n"
                "После подписки нажмите кнопку ниже."
            )
            keyboard = get_subscribe_keyboard()
            
            if message:
                await message.answer(subscribe_text, reply_markup=keyboard)
            elif callback:
                await callback.message.edit_text(subscribe_text, reply_markup=keyboard)
                await callback.answer()
            
            return None  # ← БЛОКИРОВКА
        
        # 9. Пропускаем если подписан
        return await handler(event, data)
```

### 4. Проверка подписки в Telegram

**Файл:** `services/subscription.py`

```python
async def check_subscription(user_id: int) -> bool:
    # 1. Получаем активные каналы из БД
    channels = await get_active_channels()
    
    if not channels:
        return True  # Нет каналов — подписка не нужна
    
    # 2. Пробуем получить из кэша Redis
    cached_result = await redis_client.get_user_subscription_check(user_id)
    if cached_result is not None:
        return cached_result  # Возвращаем кэш
    
    # 3. Запрашиваем у Telegram
    bot = Bot(token=settings.BOT_TOKEN)
    all_subscribed = True
    
    for channel in channels:
        member = await bot.get_chat_member(
            chat_id=channel.channel_id,
            user_id=user_id,
        )
        
        # Статусы: member, administrator, creator
        is_subscribed = member.status in ("member", "administrator", "creator")
        
        if not is_subscribed:
            all_subscribed = False
            break
    
    # 4. Кэшируем результат (TTL=30 сек или отключено)
    # await redis_client.set_user_subscription_check(user_id, all_subscribed, ttl=30)
    
    return all_subscribed
```

### 5. Добавление канала через админку

**Файл:** `bot/handlers/admin.py`

```python
@router.callback_query(F.data == "admin_channel_add")
async def cb_admin_channel_add(callback: CallbackQuery, state: FSMContext):
    # 1. Переводим в состояние ожидания
    await state.set_state(AddChannel.waiting_for_channel_link)
    
    text = (
        "📺 <b>Добавление канала</b>\n\n"
        "Отправьте ссылку на канал:\n"
        "- t.me/username\n"
        "- @username\n\n"
        "⚠️ Бот должен быть АДМИНИСТРАТОРОМ в канале!"
    )
    await callback.message.edit_text(text)


@router.message(AddChannel.waiting_for_channel_link, F.text)
async def handle_channel_link(message: Message, state: FSMContext):
    # 2. Парсим username
    username = parse_channel_username(message.text)
    
    # 3. Получаем информацию о канале
    bot = Bot(token=settings.BOT_TOKEN)
    chat = await bot.get_chat(f"@{username}")
    
    # 4. Проверяем что бот админ
    member = await bot.get_chat_member(chat.id, bot.id)
    if member.status not in ("administrator", "creator"):
        await message.answer("❌ Бот не администратор в канале!")
        return
    
    # 5. Сохраняем в БД
    async with async_session_maker() as session:
        channel = Channel(
            channel_id=chat.id,
            username=username,
            title=chat.title,
            is_active=True,
        )
        session.add(channel)
        await session.commit()
    
    await message.answer(f"✅ Канал @{username} добавлен!")
```

---

## 📊 База данных

### Модели (SQLAlchemy)

**Файл:** `core/database.py`

```python
# Пользователи
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str | None]
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    
    # Подписка
    subscription_status: Mapped[SubscriptionStatus]  # none, trial, active, expired
    subscription_expires_at: Mapped[datetime | None]
    is_trial_used: Mapped[bool] = False
    
    # Статистика
    videos_processed: Mapped[int] = 0
    
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# Каналы для обязательной подписки
class Channel(Base):
    __tablename__ = "channels"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str | None]
    is_active: Mapped[bool] = True
    
    created_at: Mapped[datetime]


# Задачи обработки видео
class ProcessingTask(Base):
    __tablename__ = "processing_tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    celery_task_id: Mapped[str | None] = mapped_column(index=True)
    status: Mapped[str]  # pending, processing, completed, failed
    
    input_file_id: Mapped[str]
    input_file_name: Mapped[str]
    output_file_id: Mapped[str | None]
    output_file_name: Mapped[str | None]
    
    request_message_id: Mapped[int | None]
    status_message_id: Mapped[int | None]
    
    error_message: Mapped[str | None]
    
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
```

### Сессии

```python
# Создание движка
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=not IS_SQLITE,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Использование
async with async_session_maker() as session:
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
```

---

## 🔐 Middleware подписки — Детали

### Жизненный цикл запроса

```
1. Пользователь нажимает кнопку в боте
         │
         ▼
2. Telegram отправляет Update боту
         │
         ▼
3. Dispatcher получает Update
         │
         ▼
4. SubscriptionMiddleware.__call__()  ← ПРОВЕРКА ЗДЕСЬ
         │
    ┌────┴────┐
    │         │
    ▼         ▼
5a. Блокировка   5b. Пропуск
    │              │
    ▼              ▼
6. Показ сообщения  6. Вызов хендлера
   о подписке         (private.py/admin.py)
```

### Что пропускается без проверки

| Событие | Условие | Почему |
|---------|---------|--------|
| Сообщение от админа | `user_id in settings.admin_ids` | Админы всегда имеют доступ |
| Команда `/start` | `event.text == "/start"` | Пользователь должен иметь возможность начать диалог |
| Кнопка "Я подписался" | `event.data == "check_subscription"` | Иначе пользователь не сможет подтвердить подписку |
| Нет активных каналов | `not channels` | Нечего проверять |

### Строгость проверки

**По умолчанию кэш ОТКЛЮЧЕН** — проверка происходит при КАЖДОМ действии.

Если пользователь отпишется от канала — следующее сообщение будет заблокировано.

---

## 🛠 Админ-панель

### Команды

| Команда | Описание |
|---------|----------|
| `/admin` | Открыть панель администратора |
| `/start` | Личное использование (не проверяется) |

### Функции админ-панели

```
🔧 Панель администратора

├── 👥 Пользователи
│   └── Список всех пользователей со статусами
│
├── 📊 Статистика
│   ├── Всего пользователей
│   ├── Активных подписок
│   ├── Всего задач обработки
│   └── За сегодня
│
├── 📢 Рассылка
│   └── Отправка сообщения всем пользователям
│
└── 📺 Каналы подписки
    ├── Добавить канал (t.me/username)
    ├── Включить/Выключить канал
    └── Удалить канал
```

### Добавление канала

1. `/admin` → **"📺 Каналы подписки"**
2. **"➕ Добавить канал"**
3. Отправить ссылку: `t.me/username` или `@username`
4. **Важно:** Бот должен быть АДМИНИСТРАТОРОМ в канале!

---

## ⚙️ Установка и запуск

### 1. Требования

- Python 3.11+
- PostgreSQL 14+ (или SQLite для тестов)
- Redis 6+ (опционально, для кэша)
- FFmpeg

### 2. Установка зависимостей

```bash
# Создание виртуального окружения
python -m venv venv
venv\Scripts\activate  # Windows
# или
source venv/bin/activate  # Linux/Mac

# Установка пакетов
pip install -r requirements.txt
```

### 3. Настройка .env

```bash
# Копирование примера
cp .env.example .env

# Редактирование
nano .env  # или блокнот
```

### 4. Переменные окружения

```ini
# Telegram Bot
BOT_TOKEN=123456:ABC-DEF1234...  # от @BotFather
BOT_ADMIN_IDS=7901094710  # Ваш Telegram ID

# Database
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db
# или для PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/uniquer_bot

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0

# Celery (для фоновой обработки)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Пути
STORAGE_INPUT_PATH=./storage/input
STORAGE_OUTPUT_PATH=./storage/output

# FFmpeg
FFMPEG_PATH=C:\path\to\ffmpeg.exe  # Windows
# FFMPEG_PATH=/usr/bin/ffmpeg  # Linux
```

### 5. Запуск бота

```bash
# Основной бот
python -m bot.main

# Celery worker (фоновая обработка видео)
celery -A worker.celery worker --loglevel=info --queue=video_processing

# Celery beat (периодические задачи)
celery -A worker.celery beat --loglevel=info
```

---

## 📝 Конфигурация

### core/config.py

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    BOT_ADMIN_IDS: str  # "7901094710,123456789"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./bot_database.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Paths
    STORAGE_INPUT_PATH: str = "./storage/input"
    STORAGE_OUTPUT_PATH: str = "./storage/output"
    
    # FFmpeg
    FFMPEG_PATH: str = "ffmpeg"
    MAX_VIDEO_SIZE_MB: int = 50
    PROCESSING_TIMEOUT_SECONDS: int = 300
    
    class Config:
        env_file = ".env"
    
    @property
    def admin_ids(self) -> set[int]:
        """Парсинг ID администраторов."""
        if not self.BOT_ADMIN_IDS:
            return set()
        return {int(id.strip()) for id in self.BOT_ADMIN_IDS.split(",")}
    
    @property
    def input_path(self) -> Path:
        return Path(self.STORAGE_INPUT_PATH).resolve()
    
    @property
    def output_path(self) -> Path:
        return Path(self.STORAGE_OUTPUT_PATH).resolve()


settings = Settings()
```

---

## 🎬 Обработка видео (Celery)

### worker/tasks.py

```python
@celery_app.task(bind=True, name="worker.tasks.process_video")
def process_video(self, task_id: int, user_id: int, input_file_id: str):
    # 1. Скачиваем видео от Telegram
    input_path = settings.input_path / f"{task_id}.mp4"
    bot = Bot(token=settings.BOT_TOKEN)
    await bot.download_file(input_file_id, input_path)
    
    # 2. Уникализация через FFmpeg
    from services.video_uniquer import video_uniquer
    output_path = await video_uniquer.process(input_path)
    
    # 3. Обновляем задачу в БД
    async with async_session_maker() as session:
        task = await session.get(ProcessingTask, task_id)
        task.status = "completed"
        task.output_file_name = output_path.name
        await session.commit()
    
    # 4. Отправляем результат пользователю
    await bot.send_video(
        chat_id=user_id,
        video=output_path,
        caption="✅ Видео готово!"
    )
```

---

## 🔧 Отладка

### Включить подробные логи

**bot/main.py:**
```python
logging.basicConfig(
    level=logging.DEBUG,  # ← Было INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

### Проверка подписки вручную

```bash
python -c "
import asyncio
from services.subscription import check_subscription

async def test():
    result = await check_subscription(1260886378)
    print(f'Подписан: {result}')

asyncio.run(test())
"
```

### Очистка кэша Redis

```bash
python -c "
import asyncio
from core.redis import redis_client

async def clear():
    await redis_client.connect()
    await redis_client.client.delete('user:1260886378:subscription')
    print('Кэш очищен')
    await redis_client.close()

asyncio.run(clear())
"
```

---

## 📚 Зависимости

**requirements.txt:**
```txt
# Telegram Bot
aiogram==3.5.0
aiofiles==23.2.1

# Database
sqlalchemy==2.0.25
asyncpg==0.29.0
aiosqlite==0.19.0
alembic==1.13.1

# Redis & Celery
redis==5.0.1
celery==5.3.6
flower==2.0.1

# Video Processing
ffmpeg-python==0.2.0

# Configuration
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Utils
aiohttp==3.9.1
pillow==10.2.0
```

---

## 🚀 Деплой на VPS

Смотрите подробную инструкцию в **[DEPLOY.md](DEPLOY.md)**

Кратко:
1. Установить Python, PostgreSQL, Redis, FFmpeg
2. Склонировать проект
3. Настроить `.env`
4. Создать systemd сервисы для бота и Celery
5. Настроить nginx + SSL (опционально)

---

## 📞 Контакты

- **Telegram:** @your_username
- **GitHub:** your_repo

---

**Версия документации:** 1.0  
**Последнее обновление:** 2026-03-07

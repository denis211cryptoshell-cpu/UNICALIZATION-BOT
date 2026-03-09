# Инструкция по деплою на VPS

## Требования

- VPS с Ubuntu 20.04+ или Debian 11+
- Минимум 2 GB RAM, 2 CPU cores
- 20 GB свободного места

## 1. Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Установка FFmpeg
sudo apt install -y ffmpeg

# Установка PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Установка Redis
sudo apt install -y redis-server
```

## 2. Настройка базы данных

```bash
# Вход в PostgreSQL
sudo -u postgres psql

# Создание базы данных и пользователя
CREATE DATABASE uniquer_bot;
CREATE USER uniquer_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE uniquer_bot TO uniquer_user;
\q
```

## 3. Клонирование проекта

```bash
# Создание директории
sudo mkdir -p /opt/uniquer-bot
sudo chown $USER:$USER /opt/uniquer-bot

# Клонирование или копирование файлов
cd /opt/uniquer-bot
# Скопируйте файлы проекта в эту директорию
```

## 4. Настройка окружения

```bash
# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Создание .env файла
cp .env.example .env
nano .env
```

### Пример .env для продакшена

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
BOT_ADMIN_IDS=123456789

# Database
DATABASE_URL=postgresql+asyncpg://uniquer_user:your_secure_password@localhost:5432/uniquer_bot

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Subscription
SUBSCRIPTION_CHANNEL_ID=-1001234567890
SUBSCRIPTION_CHANNEL_USERNAME=your_channel

# Paths
STORAGE_INPUT_PATH=/opt/uniquer-bot/storage/input
STORAGE_OUTPUT_PATH=/opt/uniquer-bot/storage/output

# Video Processing
FFMPEG_PATH=/usr/bin/ffmpeg
MAX_VIDEO_SIZE_MB=50
PROCESSING_TIMEOUT_SECONDS=300
```

## 5. Создание systemd сервисов

### Бот (bot.service)

```bash
sudo nano /etc/systemd/system/uniquer-bot.service
```

```ini
[Unit]
Description=Video Uniquer Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/uniquer-bot
Environment="PATH=/opt/uniquer-bot/venv/bin"
ExecStart=/opt/uniquer-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Worker (celery.service)

```bash
sudo nano /etc/systemd/system/uniquer-celery.service
```

```ini
[Unit]
Description=Video Uniquer Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/uniquer-bot
Environment="PATH=/opt/uniquer-bot/venv/bin"
ExecStart=/opt/uniquer-bot/venv/bin/celery -A worker.celery worker --loglevel=info --queue=video_processing --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Beat (для периодических задач)

```bash
sudo nano /etc/systemd/system/uniquer-celery-beat.service
```

```ini
[Unit]
Description=Video Uniquer Celery Beat
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/uniquer-bot
Environment="PATH=/opt/uniquer-bot/venv/bin"
ExecStart=/opt/uniquer-bot/venv/bin/celery -A worker.celery beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 6. Запуск сервисов

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable uniquer-bot
sudo systemctl enable uniquer-celery
sudo systemctl enable uniquer-celery-beat

# Запуск
sudo systemctl start uniquer-bot
sudo systemctl start uniquer-celery
sudo systemctl start uniquer-celery-beat

# Проверка статуса
sudo systemctl status uniquer-bot
sudo systemctl status uniquer-celery
```

## 7. Настройка логирования

```bash
# Просмотр логов бота
sudo journalctl -u uniquer-bot -f

# Просмотр логов Celery
sudo journalctl -u uniquer-celery -f

# Логирование в файл (опционально)
# Добавьте в systemd сервисы:
# StandardOutput=append:/var/log/uniquer-bot/bot.log
# StandardError=append:/var/log/uniquer-bot/bot.err
```

## 8. Мониторинг

### Flower (веб-интерфейс для Celery)

```bash
# Установка Flower уже выполнена через requirements.txt

# Создание сервиса
sudo nano /etc/systemd/system/uniquer-flower.service
```

```ini
[Unit]
Description=Video Uniquer Flower
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/uniquer-bot
Environment="PATH=/opt/uniquer-bot/venv/bin"
ExecStart=/opt/uniquer-bot/venv/bin/celery -A worker.celery flower --port=5555
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Запуск
sudo systemctl enable uniquer-flower
sudo systemctl start uniquer-flower

# Доступ через nginx с базовой авторизацией
```

## 9. Обновление проекта

```bash
cd /opt/uniquer-bot

# Остановка сервисов
sudo systemctl stop uniquer-bot
sudo systemctl stop uniquer-celery
sudo systemctl stop uniquer-celery-beat

# Обновление кода
git pull origin main  # или копирование новых файлов

# Установка новых зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Миграции БД (если есть alembic)
alembic upgrade head

# Запуск сервисов
sudo systemctl start uniquer-bot
sudo systemctl start uniquer-celery
sudo systemctl start uniquer-celery-beat
```

## 10. Безопасность

```bash
# Настройка фаервола
sudo apt install -y ufw
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Настройка Fail2Ban
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Команды для управления

```bash
# Перезапуск всех сервисов
sudo systemctl restart uniquer-bot uniquer-celery uniquer-celery-beat

# Просмотр логов
sudo journalctl -u uniquer-bot -f --no-pager

# Остановка бота
sudo systemctl stop uniquer-bot

# Проверка статуса
sudo systemctl status uniquer-bot
```

## Troubleshooting

### Бот не запускается

```bash
# Проверка логов
sudo journalctl -u uniquer-bot -n 50

# Проверка .env файла
cat /opt/uniquer-bot/.env

# Проверка подключения к БД
psql -h localhost -U uniquer_user -d uniquer_bot
```

### Celery не обрабатывает задачи

```bash
# Проверка очереди Redis
redis-cli
> KEYS *
> LLEN celery

# Проверка логов Celery
sudo journalctl -u uniquer-celery -n 50
```

### Проблемы с FFmpeg

```bash
# Проверка установки
ffmpeg -version

# Проверка пути в .env
# Убедитесь что FFMPEG_PATH=/usr/bin/ffmpeg
```

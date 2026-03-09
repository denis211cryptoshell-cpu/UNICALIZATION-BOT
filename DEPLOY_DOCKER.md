# 🐳 Деплой через Docker — ОЧЕНЬ ПРОСТО

## 📋 Что это даёт

| Было (без Docker) | Стало (с Docker) |
|-------------------|------------------|
| Ставить Python, PostgreSQL, Redis, FFmpeg вручную | **Всё уже в контейнерах** |
| Настраивать systemd сервисы | **Одна команда** |
| Следить за зависимостями | **Изолировано** |
| "На моём ПК работает, на сервере нет" | **Работает везде одинаково** |

---

## 🚀 Инструкция (5 минут)

### Шаг 1: Подключись к VPS по SSH

```bash
# Windows (PowerShell или cmd)
ssh root@87.249.38.179

# Или через PuTTY
# Host: 87.249.38.179
# Port: 22
# User: root
```

---

### Шаг 2: Установи Docker на VPS

```bash
# Одна команда установит Docker и Docker Compose
curl -fsSL https://get.docker.com | sh

# Проверка
docker --version
docker compose version
```

---

### Шаг 3: Загрузи файлы бота на VPS

**Способ 1: Через Git (рекомендую)**
```bash
# На VPS
cd /root
git clone <твой репозиторий> unificator
cd unificator
```

**Способ 2: Через FileZilla (FTP)**
1. Открой FileZilla
2. Подключись по FTP (твои данные выше)
3. Передай все файлы в папку на сервере

**Способ 3: Через scp**
```bash
# С своего ПК (Windows PowerShell)
scp -r d:\Боты\унификатор\* root@87.249.38.179:/root/unificator
```

---

### Шаг 4: Настрой .env.docker

```bash
# На VPS
cd /root/unificator
nano .env.docker
```

**Измени только 2 строки:**
```ini
BOT_TOKEN=123456:ABC-DEF1234...  # Твой токен от @BotFather
BOT_ADMIN_IDS=7901094710  # Твой Telegram ID
```

**Остальное НЕ трогай!** PostgreSQL и Redis уже настроены для Docker.

---

### Шаг 5: Запусти бота

```bash
# Одна команда поднимет ВСЁ:
docker compose up -d

# Посмотреть что запустилось
docker compose ps
```

**Должно быть 5 контейнеров:**
- `uniquer_postgres` — база данных
- `uniquer_redis` — кэш
- `uniquer_bot` — твой бот
- `uniquer_celery_worker` — обработка видео
- `uniquer_celery_beat` — периодические задачи

---

### Шаг 6: Проверь логи

```bash
# Логи бота
docker compose logs -f bot

# Логи всех сервисов
docker compose logs -f

# Выход из логов: Ctrl+C
```

---

## 🔧 Управление

```bash
# Остановить всё
docker compose down

# Перезапустить бота
docker compose restart bot

# Перезапустить всё
docker compose restart

# Посмотреть логи
docker compose logs -f bot

# Обновить код (если Git)
git pull
docker compose up -d --build

# Посмотреть что работает
docker compose ps
```

---

## 📊 Мониторинг

```bash
# Использование ресурсов
docker stats

# Войти в контейнер с ботом
docker exec -it uniquer_bot sh

# Войти в PostgreSQL
docker exec -it uniquer_postgres psql -U postgres

# Посмотреть Redis
docker exec -it uniquer_redis redis-cli
```

---

## 🛡 Если что-то пошло не так

### Бот не запускается
```bash
# Посмотреть логи
docker compose logs bot

# Пересобрать
docker compose up -d --build
```

### Ошибка базы данных
```bash
# Перезапустить PostgreSQL
docker compose restart postgres

# Подождать 10 секунд, перезапустить бота
docker compose restart bot
```

### Контейнер постоянно перезапускается
```bash
# Посмотреть почему
docker inspect uniquer_bot | grep -A 10 "State"

# Логи
docker compose logs bot
```

---

## 📁 Бэкап данных

```bash
# Бэкап базы данных
docker exec uniquer_postgres pg_dump -U postgres uniquer_bot > backup.sql

# Восстановление
docker exec -i uniquer_postgres psql -U postgres uniquer_bot < backup.sql

# Бэкап Redis
docker exec uniquer_redis redis-cli SAVE
```

---

## ✅ Чек-лист

- [ ] Docker установлен (`docker --version`)
- [ ] Файлы загружены на VPS
- [ ] `.env.docker` настроен (токен и админ ID)
- [ ] Запущено (`docker compose up -d`)
- [ ] Все контейнеры работают (`docker compose ps`)
- [ ] Логи в норме (`docker compose logs -f bot`)
- [ ] Бот отвечает в Telegram

---

## 🎉 Готово!

Бот работает в Docker. Всё что нужно для обновлений:

```bash
git pull && docker compose up -d --build
```

**Время на деплой:** 5-10 минут  
**Сложность:** ⭐ (одна команда `docker compose up -d`)

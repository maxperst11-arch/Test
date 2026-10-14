# Волшебный сапог

Злой Telegram-бот, который принимает задачи и пинает тебя напоминаниями: чем ближе дедлайн, тем чаще. Ночью молчит, в 08:00 присылает план на день.

- Логика бота: [docs/SPEC.md](docs/SPEC.md)
- Идеи на потом: [docs/IDEAS.md](docs/IDEAS.md)

## Настройка

Скопируй `.env.example` в `.env` и заполни:

| Переменная | Что это |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `ALLOWED_USERS` | Кому можно пользоваться ботом: ID или @username через запятую. Пусто — всем |
| `DEFAULT_TIMEZONE` | Часовой пояс новых пользователей, по умолчанию `Europe/Moscow` |
| `DATABASE_PATH` | Где лежит база, по умолчанию `data/magic_boot.db` |

## Запуск локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m magic_boot
```

## Запуск на сервере

```bash
docker compose up -d --build
```

База хранится в папке `data/` рядом с `docker-compose.yml` и переживает перезапуски.

## Тесты

```bash
pytest
```

## Устройство

| Файл | Что внутри |
|---|---|
| `magic_boot/texts.py` | Все фразы бота |
| `magic_boot/reminders.py` | Расчёт срочности, интервалов и тихих часов |
| `magic_boot/dates.py` | Разбор дат вроде «завтра 18:00» и «через 3 дня» |
| `magic_boot/scheduler.py` | Фоновый цикл: напоминания, утренняя и вечерняя сводки |
| `magic_boot/db.py` | База SQLite |
| `magic_boot/handlers/` | Обработчики сообщений и кнопок |

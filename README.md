# Волшебный сапог

Злой Telegram-бот, который принимает задачи и пинает тебя напоминаниями: чем ближе дедлайн, тем чаще. Ночью молчит, в 08:00 присылает план на день.

- Логика бота: [docs/SPEC.md](docs/SPEC.md)
- Идеи на потом: [docs/IDEAS.md](docs/IDEAS.md)

## Запуск локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # вписать TELEGRAM_BOT_TOKEN
python -m magic_boot
```

## Запуск на сервере

```bash
cp .env.example .env   # вписать TELEGRAM_BOT_TOKEN
docker compose up -d --build
```

## Тесты

```bash
pytest
```

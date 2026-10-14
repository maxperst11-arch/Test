import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from magic_boot.config import Settings
from magic_boot.db import Database
from magic_boot.handlers import build_router
from magic_boot.middlewares import UserMiddleware
from magic_boot.scheduler import Scheduler

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="new", description="Новая задача"),
    BotCommand(command="tasks", description="Мои задачи"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="cancel", description="Отменить ввод"),
]


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    middleware = UserMiddleware()
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    dp.include_router(build_router())
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    db = Database(settings.database_path)
    await db.connect()
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    await bot.set_my_commands(COMMANDS)
    scheduler = asyncio.create_task(Scheduler(bot, db).run())
    try:
        await build_dispatcher().start_polling(bot, settings=settings, db=db)
    finally:
        scheduler.cancel()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

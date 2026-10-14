import asyncio
import logging

from aiogram import Bot, Dispatcher

from magic_boot.config import Settings
from magic_boot.handlers import build_router
from magic_boot.middlewares import AccessMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    access = AccessMiddleware(settings)
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    dp.include_router(build_router())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

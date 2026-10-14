from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject
from aiogram.types import User as TgUser

from magic_boot import clock, texts
from magic_boot.config import Settings
from magic_boot.db import Database


class UserMiddleware(BaseMiddleware):
    """Проверяет доступ, заводит пользователя при первом обращении и передаёт его в обработчики.

    Настройки и база приходят из данных диспетчера: start_polling(bot, settings=..., db=...).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return None
        settings: Settings = data["settings"]
        db: Database = data["db"]
        if not settings.is_allowed(tg_user.id, tg_user.username):
            if isinstance(event, CallbackQuery):
                await event.answer(texts.pick(texts.NOT_ALLOWED), show_alert=True)
            else:
                await event.answer(texts.pick(texts.NOT_ALLOWED))
            return None

        user = await db.get_user(tg_user.id)
        data["is_new_user"] = user is None
        if user is None:
            user = await db.create_user(tg_user.id, settings.default_timezone, clock.now())
        data["user"] = user
        return await handler(event, data)

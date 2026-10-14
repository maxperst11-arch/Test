from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from magic_boot import texts
from magic_boot.config import Settings


class AccessMiddleware(BaseMiddleware):
    """Пропускает только пользователей из ALLOWED_USER_IDS (если список задан)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or self.settings.is_allowed(user.id):
            return await handler(event, data)
        answer = getattr(event, "answer", None)
        if answer is not None:
            await answer(texts.pick(texts.NOT_ALLOWED))
        return None

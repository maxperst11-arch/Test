"""Дневник позора."""

from datetime import timedelta

from aiogram.types import Message

from magic_boot import clock, texts
from magic_boot.db import Database, User


async def show_shame(message: Message, db: Database, user: User) -> None:
    now = clock.now()
    stats = await db.stats(user.id, now, now - timedelta(days=7))
    if stats.overdue:
        streak = 0
        verdict = texts.SHAME_VERDICT_BAD
    else:
        streak = (now - (user.last_overdue_at or user.created_at)).days
        good = stats.done_week >= 3 and stats.done_late * 2 <= stats.done_total
        verdict = texts.SHAME_VERDICT_GOOD if good else texts.SHAME_VERDICT_OK
    await message.answer(
        texts.SHAME.format(
            done_total=stats.done_total,
            done_week=stats.done_week,
            done_late=stats.done_late,
            active=stats.active,
            overdue=stats.overdue,
            postponed=stats.postponed,
            streak=streak,
            verdict=texts.pick(verdict),
        )
    )

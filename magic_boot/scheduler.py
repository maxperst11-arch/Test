"""Фоновый цикл: напоминания, утренняя и вечерняя сводки."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from magic_boot import clock, keyboards, texts
from magic_boot.db import Database, Task, User
from magic_boot.reminders import (
    OVERDUE_BUCKET,
    in_quiet_hours,
    next_reminder,
    parse_hhmm,
    push_out_of_quiet,
    urgency_bucket,
)
from magic_boot.render import sort_by_urgency, task_line
from magic_boot.timefmt import duration

log = logging.getLogger(__name__)

TICK_SECONDS = 30
# Если бот лежал и проснулся сильно позже времени сводки, старую сводку не шлём.
DIGEST_WINDOW = timedelta(hours=3)
EVENING_TIME = time(21, 0)
# Напоминания, которые придут вскоре после утренней сводки, сдвигаем: сводка их уже показала.
DIGEST_COVERS = timedelta(minutes=45)
UPCOMING_LIMIT = 5

# Текст напоминания по корзине срочности (см. reminders.STEPS).
BUCKET_TEXTS = [
    texts.REMIND_URGENT,  # < 2 ч
    texts.REMIND_SOON,    # < 6 ч
    texts.REMIND_SOON,    # < 24 ч
    texts.REMIND_MID,     # < 3 дней
    texts.REMIND_FAR,     # < 7 дней
    texts.REMIND_FAR,     # больше недели
]


def reminder_text(task: Task, now: datetime) -> str:
    title = escape(task.title)
    left = task.deadline - now
    bucket = urgency_bucket(left)
    if bucket != OVERDUE_BUCKET:
        return texts.pick(BUCKET_TEXTS[bucket], title=title, left=duration(left))
    if task.overdue_reminders == 0 and -left < timedelta(minutes=5):
        return texts.pick(texts.REMIND_DEADLINE, title=title)
    level = min(task.overdue_reminders, len(texts.REMIND_OVERDUE) - 1)
    return texts.pick(texts.REMIND_OVERDUE[level], title=title, late=duration(left))


def morning_digest(user: User, tasks: list[Task], now: datetime) -> str:
    if not tasks:
        return texts.pick(texts.MORNING_EMPTY)
    today = now.astimezone(user.tz).date()
    tasks = sort_by_urgency(tasks, now)
    overdue = [t for t in tasks if t.deadline <= now]
    due_today = [t for t in tasks if t.deadline > now and t.deadline.astimezone(user.tz).date() == today]
    upcoming = [t for t in tasks if t.deadline.astimezone(user.tz).date() > today]
    upcoming = sorted(upcoming, key=lambda t: t.deadline)[:UPCOMING_LIMIT]

    parts = [texts.pick(texts.MORNING_GREETING)]
    for header, group in (
        (texts.MORNING_OVERDUE, overdue),
        (texts.MORNING_TODAY, due_today),
        (texts.MORNING_UPCOMING, upcoming),
    ):
        if group:
            parts.append(header + "\n" + "\n".join(task_line(t, user, now) for t in group))
    parts.append(texts.pick(texts.MORNING_OUTRO))
    return "\n\n".join(parts)


def evening_report(tasks_done: list[Task], overdue_count: int) -> str:
    if not tasks_done:
        text = texts.pick(texts.EVENING_NOTHING)
    else:
        lines = [texts.EVENING_HEADER.format(count=len(tasks_done))]
        lines += [f"✅ {escape(t.title)}" for t in tasks_done]
        text = "\n".join(lines)
    if overdue_count:
        text += "\n\n" + texts.EVENING_OVERDUE.format(count=overdue_count)
    return text


def is_due(local: datetime, at: time, last_sent: str | None) -> bool:
    """Пора ли слать ежедневное сообщение, запланированное на время at."""
    if last_sent == local.date().isoformat():
        return False
    scheduled = local.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return scheduled <= local < scheduled + DIGEST_WINDOW


class Scheduler:
    def __init__(self, bot: Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    async def run(self) -> None:
        while True:
            try:
                await self.tick(clock.now())
            except Exception:
                log.exception("Сбой в цикле напоминаний")
            await asyncio.sleep(TICK_SECONDS)

    async def tick(self, now: datetime) -> None:
        for user in await self.db.list_users():
            await self.daily_messages(user, now)
        users: dict[int, User] = {}
        for task in await self.db.due_tasks(now):
            if task.user_id not in users:
                users[task.user_id] = await self.db.get_user(task.user_id)
            await self.remind(users[task.user_id], task, now)

    async def send(self, user: User, text: str, **kwargs) -> bool:
        try:
            await self.bot.send_message(user.id, text, **kwargs)
            return True
        except TelegramForbiddenError:
            log.info("Пользователь %s заблокировал бота", user.id)
        except Exception:
            log.exception("Не удалось отправить сообщение пользователю %s", user.id)
        return False

    async def daily_messages(self, user: User, now: datetime) -> None:
        local = now.astimezone(user.tz)
        today = local.date().isoformat()

        if is_due(local, parse_hhmm(user.digest_time), user.last_digest_date):
            tasks = await self.db.active_tasks(user.id)
            await self.send(user, morning_digest(user, tasks, now))
            await self.db.update_user(user.id, last_digest_date=today)
            await self.postpone_covered(user, tasks, now)

        start, end = user.quiet
        if (
            user.evening_digest
            and is_due(local, EVENING_TIME, user.last_evening_date)
            and not in_quiet_hours(local, start, end)
        ):
            midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
            done = await self.db.done_since(user.id, midnight)
            overdue = sum(t.deadline <= now for t in await self.db.active_tasks(user.id))
            await self.send(user, evening_report(done, overdue))
            await self.db.update_user(user.id, last_evening_date=today)

    async def postpone_covered(self, user: User, tasks: list[Task], now: datetime) -> None:
        start, end = user.quiet
        for task in tasks:
            if task.next_remind_at and task.next_remind_at <= now + DIGEST_COVERS:
                next_at = next_reminder(now, task.deadline, task.importance, user.anger, user.tz, start, end)
                await self.db.update_task(task.id, next_remind_at=next_at)

    async def remind(self, user: User, task: Task, now: datetime) -> None:
        start, end = user.quiet
        if in_quiet_hours(now.astimezone(user.tz), start, end):
            await self.db.update_task(task.id, next_remind_at=push_out_of_quiet(now, user.tz, start, end))
            return

        await self.send(user, reminder_text(task, now), reply_markup=keyboards.reminder(task.id))
        fields = {
            "next_remind_at": next_reminder(now, task.deadline, task.importance, user.anger, user.tz, start, end)
        }
        if task.deadline <= now:
            fields["overdue_reminders"] = task.overdue_reminders + 1
            if task.overdue_reminders == 0:
                await self.db.update_user(user.id, last_overdue_at=now)
        await self.db.update_task(task.id, **fields)

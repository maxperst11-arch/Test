from datetime import UTC, datetime, timedelta

from magic_boot import texts
from magic_boot.reminders import MEDIUM
from magic_boot.scheduler import Scheduler


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


async def test_morning_digest_once_a_day(db):
    # 08:00 по Москве = 05:00 UTC
    morning = utc(2026, 10, 14, 5, 0)
    await db.create_user(1, "Europe/Moscow", morning - timedelta(days=1))
    await db.add_task(1, "Сдать отчёт", None, MEDIUM, utc(2026, 10, 14, 15, 0), morning + timedelta(hours=5), morning)
    await db.add_task(1, "Старый долг", None, MEDIUM, utc(2026, 10, 13, 15, 0), morning + timedelta(hours=5), morning)
    bot = FakeBot()
    scheduler = Scheduler(bot, db)

    await scheduler.tick(morning - timedelta(minutes=1))
    assert bot.sent == []

    await scheduler.tick(morning)
    await scheduler.tick(morning + timedelta(minutes=10))
    assert len(bot.sent) == 1
    digest = bot.sent[0][1]
    assert "Сдать отчёт" in digest and "Старый долг" in digest
    assert texts.MORNING_OVERDUE in digest and texts.MORNING_TODAY in digest


async def test_no_reminders_at_night(db):
    night = utc(2026, 10, 14, 23, 0)  # 02:00 по Москве
    await db.create_user(1, "Europe/Moscow", night)
    task = await db.add_task(1, "Ночная", None, MEDIUM, night + timedelta(hours=3), night, night)
    bot = FakeBot()

    await Scheduler(bot, db).tick(night)

    assert bot.sent == []
    moved = await db.get_task(1, task.id)
    assert moved.next_remind_at == utc(2026, 10, 15, 5, 0)  # 08:00 по Москве


async def test_overdue_reminders_escalate(db):
    now = utc(2026, 10, 14, 10, 0)
    await db.create_user(1, "Europe/Moscow", now)
    task = await db.add_task(1, "Просрочка", None, MEDIUM, now - timedelta(hours=1), now, now)
    bot = FakeBot()
    scheduler = Scheduler(bot, db)

    await scheduler.tick(now)
    first = await db.get_task(1, task.id)
    assert first.overdue_reminders == 1
    assert first.next_remind_at == now + timedelta(hours=1)
    assert (await db.get_user(1)).last_overdue_at == now

    await scheduler.tick(first.next_remind_at)
    assert (await db.get_task(1, task.id)).overdue_reminders == 2
    assert len(bot.sent) == 2


async def test_reminder_not_sent_before_time(db):
    now = utc(2026, 10, 14, 10, 0)
    await db.create_user(1, "Europe/Moscow", now)
    await db.add_task(1, "Потом", None, MEDIUM, now + timedelta(days=1), now + timedelta(hours=2), now)
    bot = FakeBot()
    await Scheduler(bot, db).tick(now)
    assert bot.sent == []

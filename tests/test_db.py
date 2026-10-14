from datetime import timedelta

from magic_boot.db import DONE


async def test_new_user_gets_default_topics(db, fake_clock):
    await db.create_user(1, "Europe/Moscow", fake_clock())
    topics = await db.list_topics(1)
    names = {t.name for t in topics}
    assert {"Личное", "Финансы", "Работа", "Отчётность"} <= names
    finance = next(t for t in topics if t.name == "Финансы")
    personal = next(t for t in topics if t.name == "Личное")
    assert finance.parent_id == personal.id


async def test_delete_section_moves_tasks(db, fake_clock):
    now = fake_clock()
    await db.create_user(1, "Europe/Moscow", now)
    topics = {t.name: t for t in await db.list_topics(1)}
    task = await db.add_task(1, "Заплатить налог", topics["Финансы"].id, 2, now + timedelta(days=1), now, now)
    assert await db.count_topic_tasks(1, topics["Личное"].id) == 1

    await db.delete_topic(1, topics["Личное"].id, move_to=topics["Работа"].id)

    names = {t.name for t in await db.list_topics(1)}
    assert "Личное" not in names and "Финансы" not in names
    assert (await db.get_task(1, task.id)).topic_id == topics["Работа"].id


async def test_users_do_not_see_each_other(db, fake_clock):
    now = fake_clock()
    await db.create_user(1, "Europe/Moscow", now)
    await db.create_user(2, "Europe/Moscow", now)
    task = await db.add_task(1, "Секрет", None, 1, now + timedelta(days=1), now, now)
    assert await db.get_task(2, task.id) is None
    assert await db.active_tasks(2) == []


async def test_stats(db, fake_clock):
    now = fake_clock()
    await db.create_user(1, "Europe/Moscow", now)
    late = await db.add_task(1, "Поздно", None, 1, now - timedelta(hours=2), now, now)
    await db.update_task(late.id, status=DONE, done_at=now, postpone_count=2)
    await db.add_task(1, "Горит", None, 1, now - timedelta(hours=1), now, now)
    await db.add_task(1, "Потом", None, 1, now + timedelta(days=2), now, now)

    stats = await db.stats(1, now, now - timedelta(days=7))
    assert (stats.done_total, stats.done_week, stats.done_late) == (1, 1, 1)
    assert (stats.active, stats.overdue, stats.postponed) == (2, 1, 2)

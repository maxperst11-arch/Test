"""Текстовое представление задач, тем и сводок."""

from datetime import datetime
from html import escape

from magic_boot import texts
from magic_boot.db import Task, Topic, User
from magic_boot.reminders import urgency_bucket
from magic_boot.timefmt import date_time, time_left


def topic_names(topics: list[Topic]) -> dict[int, str]:
    """id темы → «Раздел › Тема»."""
    by_id = {topic.id: topic for topic in topics}
    names = {}
    for topic in topics:
        parent = by_id.get(topic.parent_id) if topic.parent_id else None
        names[topic.id] = f"{parent.name} › {topic.name}" if parent else topic.name
    return names


def ordered_topics(topics: list[Topic]) -> list[Topic]:
    """Разделы, и сразу под каждым — его темы."""
    result = []
    for section in (t for t in topics if t.parent_id is None):
        result.append(section)
        result.extend(t for t in topics if t.parent_id == section.id)
    return result


def sort_by_urgency(tasks: list[Task], now: datetime) -> list[Task]:
    return sorted(
        tasks, key=lambda t: (urgency_bucket(t.deadline - now), -t.importance, t.deadline)
    )


def task_line(task: Task, user: User, now: datetime) -> str:
    deadline = task.deadline.astimezone(user.tz)
    left = time_left(task.deadline, now)
    marker = "🔥 " if task.deadline <= now else ""
    return (
        f"{texts.IMPORTANCE_ICONS[task.importance]} {marker}<b>{escape(task.title)}</b>\n"
        f"    ⏰ {date_time(deadline)} · {left}"
    )


def task_card(
    title: str,
    topic: str | None,
    importance: int,
    deadline: datetime,
    user: User,
    now: datetime,
    postpone_count: int = 0,
) -> str:
    lines = [
        f"📝 <b>{escape(title)}</b>",
        f"🗂 {escape(topic or texts.NO_TOPIC)}",
        f"❗ {texts.IMPORTANCE_LABELS[importance]}",
        f"⏰ {date_time(deadline.astimezone(user.tz))} — {time_left(deadline, now)}",
    ]
    if postpone_count:
        lines.append(f"📅 Переносов: {postpone_count}")
    return "\n".join(lines)


def short_title(title: str, limit: int = 32) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"

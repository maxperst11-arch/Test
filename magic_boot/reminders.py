"""Расчёт срочности и времени следующего напоминания. Без Telegram и базы."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

HIGH, MEDIUM, LOW = 2, 1, 0
IMPORTANCE_FACTOR = {HIGH: 0.75, MEDIUM: 1.0, LOW: 1.5}

STRICT, VERY_STRICT, MERCILESS = 0, 1, 2
ANGER_FACTOR = {STRICT: 1.25, VERY_STRICT: 1.0, MERCILESS: 0.75}

# Дальше этого срока бот напоминает только в утренней сводке.
DIGEST_ONLY = timedelta(days=7)
OVERDUE_INTERVAL = timedelta(hours=1)

# (осталось меньше, чем ..., напоминать каждые ...)
STEPS = [
    (timedelta(hours=2), timedelta(minutes=30)),
    (timedelta(hours=6), timedelta(hours=1)),
    (timedelta(hours=24), timedelta(hours=2)),
    (timedelta(days=3), timedelta(hours=4)),
    (DIGEST_ONLY, timedelta(hours=12)),
]

OVERDUE_BUCKET = -1
DIGEST_BUCKET = len(STEPS)


def urgency_bucket(left: timedelta) -> int:
    """0 — горит сильнее всего; OVERDUE_BUCKET — просрочено; DIGEST_BUCKET — не скоро."""
    if left <= timedelta(0):
        return OVERDUE_BUCKET
    for index, (limit, _) in enumerate(STEPS):
        if left < limit:
            return index
    return DIGEST_BUCKET


def base_interval(left: timedelta) -> timedelta | None:
    bucket = urgency_bucket(left)
    if bucket == OVERDUE_BUCKET:
        return OVERDUE_INTERVAL
    if bucket == DIGEST_BUCKET:
        return None
    return STEPS[bucket][1]


def reminder_interval(left: timedelta, importance: int, anger: int) -> timedelta | None:
    base = base_interval(left)
    if base is None:
        return None
    return base * IMPORTANCE_FACTOR[importance] * ANGER_FACTOR[anger]


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_quiet_hours(local: datetime, start: time, end: time) -> bool:
    current = local.time().replace(second=0, microsecond=0)
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def push_out_of_quiet(moment: datetime, tz: ZoneInfo, start: time, end: time) -> datetime:
    """Если момент попадает в тихие часы, переносит его на их конец."""
    local = moment.astimezone(tz)
    if not in_quiet_hours(local, start, end):
        return moment
    wake = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if wake <= local:
        wake += timedelta(days=1)
    return wake.astimezone(UTC)


def next_reminder(
    now: datetime,
    deadline: datetime,
    importance: int,
    anger: int,
    tz: ZoneInfo,
    quiet_start: time,
    quiet_end: time,
) -> datetime:
    left = deadline - now
    interval = reminder_interval(left, importance, anger)
    if interval is None:
        # Пока до дедлайна больше недели, ждём, когда до него останется неделя.
        moment = deadline - DIGEST_ONLY
    else:
        moment = now + interval
        # Момент дедлайна не пропускаем: «время вышло» должно прийти вовремя.
        if now < deadline < moment:
            moment = deadline
    return push_out_of_quiet(moment, tz, quiet_start, quiet_end)

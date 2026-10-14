"""Человеческое форматирование времени на русском."""

from datetime import datetime, timedelta

WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def duration(delta: timedelta) -> str:
    """«2 дня 3 ч», «5 ч 10 мин», «15 мин»."""
    minutes = max(int(abs(delta).total_seconds()) // 60, 1)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        text = f"{days} {plural(days, 'день', 'дня', 'дней')}"
        return f"{text} {hours} ч" if hours else text
    if hours:
        return f"{hours} ч {minutes} мин" if minutes else f"{hours} ч"
    return f"{minutes} мин"


def date_time(local: datetime) -> str:
    return f"{local:%d.%m} ({WEEKDAYS_SHORT[local.weekday()]}) {local:%H:%M}"


def time_left(deadline: datetime, now: datetime) -> str:
    left = deadline - now
    if left <= timedelta(0):
        return f"просрочено на {duration(left)}"
    return f"осталось {duration(left)}"

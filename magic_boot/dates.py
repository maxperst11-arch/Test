"""Разбор дедлайна, написанного текстом: «завтра», «25.10 18:00», «через 3 дня», «в пятницу»."""

import re
from datetime import datetime, time, timedelta

DEFAULT_TIME = time(20, 0)

WEEKDAYS = {
    "пн": 0, "понедельник": 0,
    "вт": 1, "вторник": 1,
    "ср": 2, "среда": 2, "среду": 2,
    "чт": 3, "четверг": 3,
    "пт": 4, "пятница": 4, "пятницу": 4,
    "сб": 5, "суббота": 5, "субботу": 5,
    "вс": 6, "воскресенье": 6,
}

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

RELATIVE = re.compile(
    r"через (?:(\d+) )?(минут[уы]?|мин|час(?:а|ов)?|день|дн(?:я|ей)|недел(?:ю|и|ь)|месяц(?:а|ев)?)"
)
CLOCK = re.compile(r"(?:^|\s)(?:в\s)?(\d{1,2}):(\d{2})$")
HOUR_ONLY = re.compile(r"(?:^|\s)в (\d{1,2})(?: час\w*)?$")
NUMERIC_DATE = re.compile(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2}|\d{4}))?")
TEXT_DATE = re.compile(r"(\d{1,2}) ([а-я]+)(?: (\d{4}))?")


def parse_deadline(text: str, now: datetime) -> datetime | None:
    """now — текущее время в часовом поясе пользователя. Возвращает время там же."""
    s = re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()
    if not s:
        return None

    relative = RELATIVE.fullmatch(s)
    if relative:
        return _relative(int(relative.group(1) or 1), relative.group(2), now)

    clock: time | None = None
    match = CLOCK.search(s) or HOUR_ONLY.search(s)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.re is CLOCK else 0
        if hour > 23 or minute > 59:
            return None
        clock = time(hour, minute)
        s = s[: match.start()].strip()

    day = _date_part(s, now, has_clock=clock is not None)
    if day is None:
        return None
    result = datetime.combine(day, clock or DEFAULT_TIME, tzinfo=now.tzinfo)
    # «18:00» без даты, когда 18:00 уже прошло, — это завтра.
    if not s and result <= now:
        result += timedelta(days=1)
    return result


def _relative(n: int, unit: str, now: datetime) -> datetime:
    if unit.startswith("мин"):
        return now + timedelta(minutes=n)
    if unit.startswith("час"):
        return now + timedelta(hours=n)
    if unit.startswith("недел"):
        days = 7 * n
    elif unit.startswith("месяц"):
        days = 30 * n
    else:
        days = n
    day = (now + timedelta(days=days)).date()
    return datetime.combine(day, DEFAULT_TIME, tzinfo=now.tzinfo)


def _date_part(s: str, now: datetime, has_clock: bool):
    today = now.date()
    if not s:
        return today if has_clock else None
    if s == "сегодня":
        return today
    if s == "завтра":
        return today + timedelta(days=1)
    if s == "послезавтра":
        return today + timedelta(days=2)

    weekday = WEEKDAYS.get(re.sub(r"^(?:в|во) ", "", s))
    if weekday is not None:
        ahead = (weekday - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)

    numeric = NUMERIC_DATE.fullmatch(s)
    if numeric:
        return _calendar_date(int(numeric.group(1)), int(numeric.group(2)), numeric.group(3), today)

    textual = TEXT_DATE.fullmatch(s)
    if textual and textual.group(2) in MONTHS:
        return _calendar_date(int(textual.group(1)), MONTHS[textual.group(2)], textual.group(3), today)
    return None


def _calendar_date(day: int, month: int, year: str | None, today):
    try:
        if year:
            full_year = int(year) + 2000 if len(year) == 2 else int(year)
            return today.replace(year=full_year, month=month, day=day)
        candidate = today.replace(month=month, day=day)
        if candidate < today:
            candidate = candidate.replace(year=today.year + 1)
        return candidate
    except ValueError:
        return None

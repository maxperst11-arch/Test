from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from magic_boot.dates import parse_deadline

MSK = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 10, 14, 15, 30, tzinfo=MSK)  # среда


def at(*args) -> datetime:
    return datetime(*args, tzinfo=MSK)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("завтра", at(2026, 10, 15, 20, 0)),
        ("Завтра 18:00", at(2026, 10, 15, 18, 0)),
        ("завтра в 9", at(2026, 10, 15, 9, 0)),
        ("сегодня в 18:30", at(2026, 10, 14, 18, 30)),
        ("послезавтра", at(2026, 10, 16, 20, 0)),
        ("25.10", at(2026, 10, 25, 20, 0)),
        ("25.10 18:00", at(2026, 10, 25, 18, 0)),
        ("1.11.2026 10:15", at(2026, 11, 1, 10, 15)),
        ("01/02", at(2027, 2, 1, 20, 0)),
        ("25 октября в 15", at(2026, 10, 25, 15, 0)),
        ("в пятницу", at(2026, 10, 16, 20, 0)),
        ("в среду 10:00", at(2026, 10, 21, 10, 0)),
        ("пн", at(2026, 10, 19, 20, 0)),
        ("через 3 дня", at(2026, 10, 17, 20, 0)),
        ("через неделю", at(2026, 10, 21, 20, 0)),
        ("через 2 часа", at(2026, 10, 14, 17, 30)),
        ("через час", at(2026, 10, 14, 16, 30)),
        ("через 15 минут", at(2026, 10, 14, 15, 45)),
        ("18:00", at(2026, 10, 14, 18, 0)),
        ("10:00", at(2026, 10, 15, 10, 0)),
    ],
)
def test_parse(text, expected):
    assert parse_deadline(text, NOW) == expected


@pytest.mark.parametrize("text", ["", "когда-нибудь", "31.02", "25:00", "завтра в 25"])
def test_garbage(text):
    assert parse_deadline(text, NOW) is None

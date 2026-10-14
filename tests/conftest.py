from datetime import UTC, datetime

import pytest

from magic_boot import clock
from magic_boot.db import Database


class FakeClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture
def fake_clock(monkeypatch):
    fake = FakeClock(datetime(2026, 10, 14, 9, 0, tzinfo=UTC))  # 12:00 по Москве
    monkeypatch.setattr(clock, "now", fake)
    return fake


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()

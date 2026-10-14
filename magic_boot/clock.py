from datetime import UTC, datetime


def now() -> datetime:
    """Текущее время в UTC. Отдельной функцией, чтобы в тестах его можно было подменить."""
    return datetime.now(UTC)

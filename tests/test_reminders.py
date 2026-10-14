from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from magic_boot.reminders import (
    HIGH,
    LOW,
    MEDIUM,
    MERCILESS,
    VERY_STRICT,
    in_quiet_hours,
    next_reminder,
    reminder_interval,
)

MSK = ZoneInfo("Europe/Moscow")
QUIET = (time(23, 0), time(8, 0))


def msk(*args) -> datetime:
    return datetime(*args, tzinfo=MSK)


def test_interval_grows_more_frequent_near_deadline():
    intervals = [
        reminder_interval(timedelta(days=5), MEDIUM, VERY_STRICT),
        reminder_interval(timedelta(days=2), MEDIUM, VERY_STRICT),
        reminder_interval(timedelta(hours=12), MEDIUM, VERY_STRICT),
        reminder_interval(timedelta(hours=4), MEDIUM, VERY_STRICT),
        reminder_interval(timedelta(hours=1), MEDIUM, VERY_STRICT),
    ]
    assert intervals == sorted(intervals, reverse=True)
    assert intervals[-1] == timedelta(minutes=30)


def test_far_deadline_means_digest_only():
    assert reminder_interval(timedelta(days=10), MEDIUM, VERY_STRICT) is None


def test_importance_and_anger_scale_interval():
    left = timedelta(hours=12)
    assert reminder_interval(left, HIGH, VERY_STRICT) < reminder_interval(left, MEDIUM, VERY_STRICT)
    assert reminder_interval(left, LOW, VERY_STRICT) > reminder_interval(left, MEDIUM, VERY_STRICT)
    assert reminder_interval(left, MEDIUM, MERCILESS) < reminder_interval(left, MEDIUM, VERY_STRICT)


def test_quiet_hours_across_midnight():
    assert in_quiet_hours(msk(2026, 10, 14, 23, 30), *QUIET)
    assert in_quiet_hours(msk(2026, 10, 15, 3, 0), *QUIET)
    assert not in_quiet_hours(msk(2026, 10, 15, 8, 0), *QUIET)
    assert not in_quiet_hours(msk(2026, 10, 15, 22, 59), *QUIET)


def test_night_reminder_moves_to_morning():
    now = msk(2026, 10, 14, 22, 30)
    deadline = msk(2026, 10, 16, 12, 0)  # ~1.5 дня → каждые 4 часа → 02:30 ночью
    result = next_reminder(now, deadline, MEDIUM, VERY_STRICT, MSK, *QUIET)
    assert result == msk(2026, 10, 15, 8, 0)


def test_deadline_moment_is_not_skipped():
    now = msk(2026, 10, 14, 12, 0)
    deadline = msk(2026, 10, 14, 12, 10)
    result = next_reminder(now, deadline, LOW, VERY_STRICT, MSK, *QUIET)
    assert result == deadline


def test_far_deadline_wakes_up_a_week_before():
    now = msk(2026, 10, 1, 12, 0)
    deadline = msk(2026, 10, 20, 12, 0)
    result = next_reminder(now, deadline, MEDIUM, VERY_STRICT, MSK, *QUIET)
    assert result == deadline - timedelta(days=7)


def test_result_is_aware_and_comparable_with_utc():
    now = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    result = next_reminder(now, now + timedelta(hours=3), MEDIUM, VERY_STRICT, MSK, *QUIET)
    assert result == now + timedelta(hours=1)

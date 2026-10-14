"""Хранилище на SQLite. Все даты хранятся в UTC строками ISO."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiosqlite

from magic_boot.reminders import parse_hhmm

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL,
    quiet_start TEXT NOT NULL DEFAULT '23:00',
    quiet_end TEXT NOT NULL DEFAULT '08:00',
    digest_time TEXT NOT NULL DEFAULT '08:00',
    anger INTEGER NOT NULL DEFAULT 1,
    evening_digest INTEGER NOT NULL DEFAULT 0,
    last_digest_date TEXT,
    last_evening_date TEXT,
    last_overdue_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    parent_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    importance INTEGER NOT NULL,
    deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    done_at TEXT,
    next_remind_at TEXT,
    overdue_reminders INTEGER NOT NULL DEFAULT 0,
    snooze_streak INTEGER NOT NULL DEFAULT 0,
    postpone_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, next_remind_at);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id, status);
"""

DEFAULT_TOPICS = {
    "Личное": ["Финансы", "Режим сна", "Полезные привычки"],
    "Работа": ["Отчётность", "Регулярные обязанности"],
    "Учёба": [],
    "Здоровье": [],
}

ACTIVE, DONE = "active", "done"


def to_db(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def from_db(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass
class User:
    id: int
    timezone: str
    quiet_start: str
    quiet_end: str
    digest_time: str
    anger: int
    evening_digest: bool
    last_digest_date: str | None
    last_evening_date: str | None
    last_overdue_at: datetime | None
    created_at: datetime

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def quiet(self):
        return parse_hhmm(self.quiet_start), parse_hhmm(self.quiet_end)

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "User":
        return cls(
            id=row["id"],
            timezone=row["timezone"],
            quiet_start=row["quiet_start"],
            quiet_end=row["quiet_end"],
            digest_time=row["digest_time"],
            anger=row["anger"],
            evening_digest=bool(row["evening_digest"]),
            last_digest_date=row["last_digest_date"],
            last_evening_date=row["last_evening_date"],
            last_overdue_at=from_db(row["last_overdue_at"]),
            created_at=from_db(row["created_at"]),
        )


@dataclass
class Topic:
    id: int
    user_id: int
    parent_id: int | None
    name: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Topic":
        return cls(row["id"], row["user_id"], row["parent_id"], row["name"])


@dataclass
class Task:
    id: int
    user_id: int
    topic_id: int | None
    title: str
    importance: int
    deadline: datetime
    status: str
    created_at: datetime
    done_at: datetime | None
    next_remind_at: datetime | None
    overdue_reminders: int
    snooze_streak: int
    postpone_count: int

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Task":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            topic_id=row["topic_id"],
            title=row["title"],
            importance=row["importance"],
            deadline=from_db(row["deadline"]),
            status=row["status"],
            created_at=from_db(row["created_at"]),
            done_at=from_db(row["done_at"]),
            next_remind_at=from_db(row["next_remind_at"]),
            overdue_reminders=row["overdue_reminders"],
            snooze_streak=row["snooze_streak"],
            postpone_count=row["postpone_count"],
        )


@dataclass
class Stats:
    done_total: int
    done_week: int
    done_late: int
    active: int
    overdue: int
    postponed: int


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()

    async def _fetchone(self, sql: str, *params):
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def _fetchall(self, sql: str, *params):
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def _update(self, table: str, row_id: int, fields: dict) -> None:
        values = {k: to_db(v) if isinstance(v, datetime) else v for k, v in fields.items()}
        assignments = ", ".join(f"{key} = ?" for key in values)
        await self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?", (*values.values(), row_id)
        )
        await self.conn.commit()

    # --- пользователи ---

    async def get_user(self, user_id: int) -> User | None:
        row = await self._fetchone("SELECT * FROM users WHERE id = ?", user_id)
        return User.from_row(row) if row else None

    async def create_user(self, user_id: int, timezone: str, now: datetime) -> User:
        await self.conn.execute(
            "INSERT INTO users (id, timezone, created_at) VALUES (?, ?, ?)",
            (user_id, timezone, to_db(now)),
        )
        for section, children in DEFAULT_TOPICS.items():
            cursor = await self.conn.execute(
                "INSERT INTO topics (user_id, name) VALUES (?, ?)", (user_id, section)
            )
            for child in children:
                await self.conn.execute(
                    "INSERT INTO topics (user_id, parent_id, name) VALUES (?, ?, ?)",
                    (user_id, cursor.lastrowid, child),
                )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def update_user(self, user_id: int, **fields) -> None:
        await self._update("users", user_id, fields)

    async def list_users(self) -> list[User]:
        return [User.from_row(row) for row in await self._fetchall("SELECT * FROM users")]

    # --- темы ---

    async def list_topics(self, user_id: int) -> list[Topic]:
        rows = await self._fetchall(
            "SELECT * FROM topics WHERE user_id = ? ORDER BY id", user_id
        )
        return [Topic.from_row(row) for row in rows]

    async def get_topic(self, user_id: int, topic_id: int) -> Topic | None:
        row = await self._fetchone(
            "SELECT * FROM topics WHERE id = ? AND user_id = ?", topic_id, user_id
        )
        return Topic.from_row(row) if row else None

    async def add_topic(self, user_id: int, name: str, parent_id: int | None = None) -> Topic:
        cursor = await self.conn.execute(
            "INSERT INTO topics (user_id, parent_id, name) VALUES (?, ?, ?)",
            (user_id, parent_id, name),
        )
        await self.conn.commit()
        return await self.get_topic(user_id, cursor.lastrowid)

    async def rename_topic(self, topic_id: int, name: str) -> None:
        await self._update("topics", topic_id, {"name": name})

    async def count_topic_tasks(self, user_id: int, topic_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = ? AND topic_id IN "
            "(SELECT id FROM topics WHERE id = ? OR parent_id = ?)",
            user_id, ACTIVE, topic_id, topic_id,
        )
        return row[0]

    async def delete_topic(self, user_id: int, topic_id: int, move_to: int | None) -> None:
        """Удаляет тему вместе с подтемами, задачи переносит в move_to (None — без темы)."""
        await self.conn.execute(
            "UPDATE tasks SET topic_id = ? WHERE user_id = ? AND topic_id IN "
            "(SELECT id FROM topics WHERE id = ? OR parent_id = ?)",
            (move_to, user_id, topic_id, topic_id),
        )
        await self.conn.execute(
            "DELETE FROM topics WHERE user_id = ? AND (id = ? OR parent_id = ?)",
            (user_id, topic_id, topic_id),
        )
        await self.conn.commit()

    # --- задачи ---

    async def add_task(
        self,
        user_id: int,
        title: str,
        topic_id: int | None,
        importance: int,
        deadline: datetime,
        next_remind_at: datetime,
        now: datetime,
    ) -> Task:
        cursor = await self.conn.execute(
            "INSERT INTO tasks (user_id, topic_id, title, importance, deadline, "
            "created_at, next_remind_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, topic_id, title, importance, to_db(deadline), to_db(now), to_db(next_remind_at)),
        )
        await self.conn.commit()
        return await self.get_task(user_id, cursor.lastrowid)

    async def get_task(self, user_id: int, task_id: int) -> Task | None:
        row = await self._fetchone(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", task_id, user_id
        )
        return Task.from_row(row) if row else None

    async def update_task(self, task_id: int, **fields) -> None:
        await self._update("tasks", task_id, fields)

    async def delete_task(self, user_id: int, task_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        )
        await self.conn.commit()

    async def active_tasks(self, user_id: int) -> list[Task]:
        rows = await self._fetchall(
            "SELECT * FROM tasks WHERE user_id = ? AND status = ? ORDER BY deadline",
            user_id, ACTIVE,
        )
        return [Task.from_row(row) for row in rows]

    async def due_tasks(self, now: datetime) -> list[Task]:
        rows = await self._fetchall(
            "SELECT * FROM tasks WHERE status = ? AND next_remind_at <= ? ORDER BY next_remind_at",
            ACTIVE, to_db(now),
        )
        return [Task.from_row(row) for row in rows]

    async def done_since(self, user_id: int, since: datetime) -> list[Task]:
        rows = await self._fetchall(
            "SELECT * FROM tasks WHERE user_id = ? AND status = ? AND done_at >= ? ORDER BY done_at",
            user_id, DONE, to_db(since),
        )
        return [Task.from_row(row) for row in rows]

    async def stats(self, user_id: int, now: datetime, week_ago: datetime) -> Stats:
        sql = """
            SELECT
                SUM(status = :done),
                SUM(status = :done AND done_at >= :week_ago),
                SUM(status = :done AND done_at > deadline),
                SUM(status = :active),
                SUM(status = :active AND deadline <= :now),
                SUM(postpone_count)
            FROM tasks WHERE user_id = :user_id
        """
        params = {"done": DONE, "active": ACTIVE, "week_ago": to_db(week_ago),
                  "now": to_db(now), "user_id": user_id}
        async with self.conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
        return Stats(*(value or 0 for value in row))

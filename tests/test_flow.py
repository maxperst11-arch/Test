"""Сквозные сценарии: настоящий диспетчер aiogram, вместо серверов Telegram — подделка."""

from datetime import UTC, datetime
from itertools import count

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User

from magic_boot import texts
from magic_boot.__main__ import build_dispatcher
from magic_boot.config import Settings

USER_ID = 1001
CHAT = Chat(id=USER_ID, type="private")
ME = User(id=USER_ID, is_bot=False, first_name="Тест", username="tester")
BOT_USER = User(id=1, is_bot=True, first_name="Сапог")

# Роутеры aiogram подключаются к диспетчеру один раз, поэтому диспетчер общий на все тесты.
DP = build_dispatcher()


def inline(method) -> InlineKeyboardMarkup | None:
    markup = method.reply_markup
    return markup if isinstance(markup, InlineKeyboardMarkup) else None


class FakeSession(BaseSession):
    """Запоминает запросы бота и отвечает как Telegram."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self.ids = count(1)

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(
                message_id=next(self.ids),
                date=datetime.now(UTC),
                chat=CHAT,
                from_user=BOT_USER,
                text=method.text,
                reply_markup=inline(method),
            )
        return True

    async def stream_content(self, *args, **kwargs):
        raise NotImplementedError

    async def close(self) -> None:
        pass


class Chatter:
    def __init__(self, bot, session, settings, db) -> None:
        self.bot, self.session = bot, session
        self.context = {"settings": settings, "db": db}
        self.update_ids = count(1)

    @property
    def last(self) -> SendMessage | EditMessageText:
        """Последнее сообщение бота (отправленное или отредактированное)."""
        for method in reversed(self.session.requests):
            if isinstance(method, (SendMessage, EditMessageText)):
                return method
        raise AssertionError("бот ничего не отправил")

    @property
    def last_with_buttons(self) -> SendMessage | EditMessageText:
        for method in reversed(self.session.requests):
            if isinstance(method, (SendMessage, EditMessageText)) and inline(method):
                return method
        raise AssertionError("у бота нет сообщений с кнопками")

    async def say(self, text: str) -> None:
        message = Message(message_id=next(self.update_ids), date=datetime.now(UTC), chat=CHAT, from_user=ME, text=text)
        await DP.feed_update(self.bot, Update(update_id=next(self.update_ids), message=message), **self.context)

    async def press(self, label: str) -> None:
        """Нажимает инлайн-кнопку в последнем сообщении бота по началу её текста."""
        source = self.last_with_buttons
        buttons = [b for row in source.reply_markup.inline_keyboard for b in row]
        button = next((b for b in buttons if b.text.strip().startswith(label)), None)
        assert button is not None, f"нет кнопки {label!r} среди {[b.text for b in buttons]}"
        callback = CallbackQuery(
            id=str(next(self.update_ids)), from_user=ME, chat_instance="x",
            data=button.callback_data,
            message=Message(
                message_id=999, date=datetime.now(UTC), chat=CHAT, from_user=BOT_USER,
                text=source.text, reply_markup=source.reply_markup,
            ),
        )
        await DP.feed_update(self.bot, Update(update_id=next(self.update_ids), callback_query=callback), **self.context)


@pytest.fixture
async def chat(db, fake_clock):
    settings = Settings(_env_file=None, telegram_bot_token="1:x", allowed_users="tester")
    session = FakeSession()
    bot = Bot("123456:TEST", session=session, default=DefaultBotProperties(parse_mode="HTML"))
    return Chatter(bot, session, settings, db)


async def test_start_shows_greeting_and_menu(chat):
    await chat.say("/start")
    assert "Волшебный сапог" in chat.last.text
    keyboard = [b.text for row in chat.last.reply_markup.keyboard for b in row]
    assert texts.MENU_NEW_TASK in keyboard


async def test_create_task_end_to_end(chat, db):
    await chat.say("/start")
    await chat.say(texts.MENU_NEW_TASK)
    await chat.say("Подготовить квартальный отчёт")
    await chat.press("· Отчётность")
    await chat.press("🔴")
    await chat.say("завтра 18:00")
    assert "Подготовить квартальный отчёт" in chat.last.text
    await chat.press("✅ Сохранить")

    [task] = await db.active_tasks(USER_ID)
    assert task.title == "Подготовить квартальный отчёт"
    assert task.importance == 2
    assert task.deadline == datetime(2026, 10, 15, 15, 0, tzinfo=UTC)  # 18:00 МСК
    assert task.next_remind_at is not None

    await chat.say(texts.MENU_TASKS)
    assert "Подготовить квартальный отчёт" in chat.last.text
    await chat.press("1.")
    await chat.press("✅ Сделал")
    assert await db.active_tasks(USER_ID) == []


async def test_free_text_becomes_task_with_new_topic(chat, db):
    await chat.say("/start")
    await chat.say("Купить абонемент в зал")
    await chat.press("✅ Да")
    await chat.press("➕ Новая тема")
    await chat.say("Спорт")
    await chat.press("⚪")
    await chat.press("Через неделю")
    await chat.press("✅ Сохранить")

    [task] = await db.active_tasks(USER_ID)
    topic = await db.get_topic(USER_ID, task.topic_id)
    assert topic.name == "Спорт"


async def test_bad_and_past_deadlines_are_rejected(chat, db):
    await chat.say("/start")
    await chat.say(texts.MENU_NEW_TASK)
    await chat.say("Задача")
    await chat.press(texts.NO_TOPIC)
    await chat.press("🟡")
    await chat.say("когда-нибудь")
    assert chat.last.text in texts.BAD_DEADLINE
    await chat.say("01.01.2020")
    assert chat.last.text in texts.PAST_DEADLINE
    assert await db.active_tasks(USER_ID) == []


async def test_menu_button_interrupts_dialog(chat):
    await chat.say("/start")
    await chat.say(texts.MENU_NEW_TASK)
    await chat.say(texts.MENU_SETTINGS)
    assert "Настройки" in chat.last.text


async def test_move_deadline_counts_postpones(chat, db, fake_clock):
    await chat.say("/start")
    await chat.say(texts.MENU_NEW_TASK)
    await chat.say("Оплатить интернет")
    await chat.press(texts.NO_TOPIC)
    await chat.press("🟡")
    await chat.press("Завтра")
    await chat.press("✅ Сохранить")
    await chat.say(texts.MENU_TASKS)
    await chat.press("1.")
    await chat.press("📅 Перенести")
    await chat.say("через 3 дня")

    [task] = await db.active_tasks(USER_ID)
    assert task.postpone_count == 1
    assert "дневник позора" in chat.last.text.lower() or "перенос" in chat.last.text.lower()


async def test_topics_add_and_delete_with_move(chat, db):
    await chat.say("/start")
    await chat.say(texts.MENU_TOPICS)
    await chat.press("📁 Учёба")
    await chat.press("➕ Тема внутри")
    await chat.say("Английский")
    names = {t.name for t in await db.list_topics(USER_ID)}
    assert "Английский" in names

    await chat.press("📁 Учёба")
    await chat.press("🗑 Удалить")
    await chat.press("🗑 Да")
    names = {t.name for t in await db.list_topics(USER_ID)}
    assert "Учёба" not in names and "Английский" not in names


async def test_settings_change(chat, db):
    await chat.say("/start")
    await chat.say(texts.MENU_SETTINGS)
    await chat.press("🌙 Тихие часы")
    await chat.say("22:30-07:00")
    user = await db.get_user(USER_ID)
    assert (user.quiet_start, user.quiet_end) == ("22:30", "07:00")
    await chat.press("😠")
    assert (await db.get_user(USER_ID)).anger == 2


async def test_stranger_is_rejected(db, fake_clock):
    settings = Settings(_env_file=None, telegram_bot_token="1:x", allowed_users="someone_else")
    session = FakeSession()
    bot = Bot("123456:TEST", session=session)
    stranger = Chatter(bot, session, settings, db)
    await stranger.say("/start")
    assert stranger.last.text in texts.NOT_ALLOWED
    assert await db.get_user(USER_ID) is None

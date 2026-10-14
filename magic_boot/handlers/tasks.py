"""Добавление задач, списки, карточка задачи и действия с ней."""

from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from magic_boot import clock, keyboards, texts
from magic_boot.callbacks import ListCb, NewTaskCb, TaskCb
from magic_boot.dates import DEFAULT_TIME, parse_deadline
from magic_boot.db import DONE, Database, User
from magic_boot.handlers.common import edit_or_send
from magic_boot.reminders import next_reminder, parse_hhmm, push_out_of_quiet
from magic_boot.render import sort_by_urgency, task_card, task_line, topic_names
from magic_boot.states import EditDeadline, NewTask
from magic_boot.timefmt import date_time

router = Router()

MAX_TITLE = 200
MAX_LIST = 30


def schedule(user: User, deadline: datetime, importance: int, now: datetime) -> datetime:
    start, end = user.quiet
    return next_reminder(now, deadline, importance, user.anger, user.tz, start, end)


# --- новая задача ---


async def start_new_task(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NewTask.title)
    await message.answer(texts.pick(texts.ASK_TITLE))


async def ask_topic(message: Message, state: FSMContext, db: Database, user: User, edit: bool) -> None:
    await state.set_state(NewTask.topic)
    markup = keyboards.choose_topic(await db.list_topics(user.id))
    if edit:
        await edit_or_send(message, texts.ASK_TOPIC, markup)
    else:
        await message.answer(texts.ASK_TOPIC, reply_markup=markup)


async def ask_importance(message: Message, state: FSMContext, edit: bool) -> None:
    await state.set_state(NewTask.importance)
    if edit:
        await edit_or_send(message, texts.ASK_IMPORTANCE, keyboards.choose_importance())
    else:
        await message.answer(texts.ASK_IMPORTANCE, reply_markup=keyboards.choose_importance())


@router.message(NewTask.title, F.text)
async def got_title(message: Message, state: FSMContext, db: Database, user: User) -> None:
    title = message.text.strip()
    if not title:
        await message.answer(texts.EMPTY_TITLE)
        return
    await state.update_data(title=title[:MAX_TITLE])
    await ask_topic(message, state, db, user, edit=False)


@router.callback_query(NewTaskCb.filter(F.action == "quick"))
async def quick_task(callback: CallbackQuery, state: FSMContext, db: Database, user: User) -> None:
    title = (await state.get_data()).get("quick_title")
    if not title:
        await callback.answer(texts.UNKNOWN_CALLBACK, show_alert=True)
        return
    await state.set_data({"title": title[:MAX_TITLE]})
    await ask_topic(callback.message, state, db, user, edit=True)
    await callback.answer()


@router.callback_query(NewTask.topic, NewTaskCb.filter(F.action == "topic"))
async def got_topic(callback: CallbackQuery, callback_data: NewTaskCb, state: FSMContext, db: Database, user: User) -> None:
    topic_id = int(callback_data.value) or None
    if topic_id and await db.get_topic(user.id, topic_id) is None:
        await callback.answer(texts.UNKNOWN_CALLBACK, show_alert=True)
        return
    await state.update_data(topic_id=topic_id)
    await ask_importance(callback.message, state, edit=True)
    await callback.answer()


@router.callback_query(NewTask.topic, NewTaskCb.filter(F.action == "new_topic"))
async def new_topic(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewTask.new_topic_name)
    await edit_or_send(callback.message, texts.ASK_NEW_TOPIC_NAME)
    await callback.answer()


@router.message(NewTask.new_topic_name, F.text)
async def got_new_topic(message: Message, state: FSMContext, db: Database, user: User) -> None:
    name = message.text.strip()
    if not name or len(name) > 40:
        await message.answer(texts.TOPIC_NAME_TOO_LONG)
        return
    topic = await db.add_topic(user.id, name)
    await state.update_data(topic_id=topic.id)
    await message.answer(texts.TOPIC_CREATED.format(name=escape(name)))
    await ask_importance(message, state, edit=False)


@router.callback_query(NewTask.importance, NewTaskCb.filter(F.action == "importance"))
async def got_importance(callback: CallbackQuery, callback_data: NewTaskCb, state: FSMContext) -> None:
    await state.update_data(importance=int(callback_data.value))
    await state.set_state(NewTask.deadline)
    await edit_or_send(callback.message, texts.ASK_DEADLINE, keyboards.choose_deadline())
    await callback.answer()


def quick_deadline(key: str, user: User, now: datetime) -> datetime:
    local = now.astimezone(user.tz)
    days = {"today": 0, "tomorrow": 1, "3days": 3, "week": 7}[key]
    deadline = datetime.combine(local.date() + timedelta(days=days), DEFAULT_TIME, tzinfo=user.tz)
    if deadline <= local:
        # «Сегодня», но 20:00 уже прошло — значит, до конца дня.
        deadline = local.replace(hour=23, minute=59, second=0, microsecond=0)
    return deadline


@router.callback_query(NewTask.deadline, NewTaskCb.filter(F.action == "deadline"))
@router.callback_query(EditDeadline.waiting, NewTaskCb.filter(F.action == "deadline"))
async def got_quick_deadline(callback: CallbackQuery, callback_data: NewTaskCb, state: FSMContext, db: Database, user: User) -> None:
    deadline = quick_deadline(callback_data.value, user, clock.now())
    await callback.answer()
    await apply_deadline(callback.message, state, db, user, deadline, edit=True)


@router.message(NewTask.deadline, F.text)
@router.message(EditDeadline.waiting, F.text)
async def got_text_deadline(message: Message, state: FSMContext, db: Database, user: User) -> None:
    now = clock.now()
    deadline = parse_deadline(message.text, now.astimezone(user.tz))
    if deadline is None:
        await message.answer(texts.pick(texts.BAD_DEADLINE))
        return
    await apply_deadline(message, state, db, user, deadline, edit=False)


async def apply_deadline(message: Message, state: FSMContext, db: Database, user: User, deadline: datetime, edit: bool) -> None:
    now = clock.now()
    if deadline <= now:
        await message.answer(texts.pick(texts.PAST_DEADLINE))
        return
    if await state.get_state() == EditDeadline.waiting.state:
        await move_deadline(message, state, db, user, deadline, now)
        return

    await state.update_data(deadline=deadline.isoformat())
    await state.set_state(NewTask.confirm)
    data = await state.get_data()
    names = topic_names(await db.list_topics(user.id))
    card = task_card(data["title"], names.get(data.get("topic_id")), data["importance"], deadline, user, now)
    text = texts.CONFIRM_TASK.format(card=card)
    if edit:
        await edit_or_send(message, text, keyboards.confirm_task())
    else:
        await message.answer(text, reply_markup=keyboards.confirm_task())


@router.callback_query(NewTask.confirm, NewTaskCb.filter(F.action == "save"))
async def save_task(callback: CallbackQuery, state: FSMContext, db: Database, user: User) -> None:
    data = await state.get_data()
    await state.clear()
    now = clock.now()
    deadline = datetime.fromisoformat(data["deadline"])
    remind_at = schedule(user, deadline, data["importance"], now)
    await db.add_task(user.id, data["title"], data.get("topic_id"), data["importance"], deadline, remind_at, now)
    first = date_time(remind_at.astimezone(user.tz))
    await edit_or_send(callback.message, texts.pick(texts.TASK_SAVED, first=first))
    await callback.answer()


@router.callback_query(NewTaskCb.filter(F.action == "cancel"))
async def cancel_new_task(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_or_send(callback.message, texts.pick(texts.CANCELLED))
    await callback.answer()


# --- списки ---


async def task_list_view(db: Database, user: User, topic_id: int = 0):
    now = clock.now()
    tasks = await db.active_tasks(user.id)
    if topic_id == -1:
        tasks = [t for t in tasks if t.topic_id is None]
    elif topic_id:
        topics = await db.list_topics(user.id)
        allowed = {topic_id} | {t.id for t in topics if t.parent_id == topic_id}
        tasks = [t for t in tasks if t.topic_id in allowed]
    if not tasks:
        return texts.pick(texts.NO_TASKS), keyboards.task_list([], filtered=bool(topic_id))

    tasks = sort_by_urgency(tasks, now)
    names = topic_names(await db.list_topics(user.id))
    lines = [texts.TASKS_HEADER, ""]
    for index, task in enumerate(tasks[:MAX_LIST], start=1):
        topic = names.get(task.topic_id, texts.NO_TOPIC)
        lines.append(f"{index}. {task_line(task, user, now)}\n    🗂 {escape(topic)}")
    if len(tasks) > MAX_LIST:
        lines.append(f"\n…и ещё {len(tasks) - MAX_LIST}. Слишком много, начни уже что-то закрывать.")
    return "\n".join(lines), keyboards.task_list(tasks, filtered=bool(topic_id))


async def show_tasks(message: Message, db: Database, user: User) -> None:
    text, markup = await task_list_view(db, user)
    await message.answer(text, reply_markup=markup)


async def show_burning(message: Message, db: Database, user: User) -> None:
    now = clock.now()
    today = now.astimezone(user.tz).date()
    tasks = [
        t for t in await db.active_tasks(user.id)
        if t.deadline <= now or t.deadline.astimezone(user.tz).date() == today
    ]
    if not tasks:
        await message.answer(texts.pick(texts.NOTHING_BURNING))
        return
    tasks = sort_by_urgency(tasks, now)
    lines = [texts.BURNING_HEADER, ""]
    lines += [f"{i}. {task_line(t, user, now)}" for i, t in enumerate(tasks, start=1)]
    await message.answer("\n".join(lines), reply_markup=keyboards.task_list(tasks, filtered=False))


@router.callback_query(ListCb.filter(F.action == "show"))
async def list_callback(callback: CallbackQuery, callback_data: ListCb, db: Database, user: User) -> None:
    text, markup = await task_list_view(db, user, callback_data.topic_id)
    await edit_or_send(callback.message, text, markup)
    await callback.answer()


@router.callback_query(ListCb.filter(F.action == "filter"))
async def filter_callback(callback: CallbackQuery, db: Database, user: User) -> None:
    markup = keyboards.topic_filter(await db.list_topics(user.id))
    await edit_or_send(callback.message, texts.FILTER_HEADER, markup)
    await callback.answer()


# --- карточка и действия ---


async def load_task(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User):
    task = await db.get_task(user.id, callback_data.task_id)
    if task is None or task.status == DONE:
        await callback.answer(texts.TASK_NOT_FOUND, show_alert=True)
        return None
    return task


@router.callback_query(TaskCb.filter(F.action == "open"))
async def open_task(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    names = topic_names(await db.list_topics(user.id))
    card = task_card(task.title, names.get(task.topic_id), task.importance, task.deadline, user, clock.now(), task.postpone_count)
    await edit_or_send(callback.message, card, keyboards.task_card(task.id))
    await callback.answer()


@router.callback_query(TaskCb.filter(F.action == "done"))
async def done_task(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    now = clock.now()
    await db.update_task(task.id, status=DONE, done_at=now, next_remind_at=None, snooze_streak=0)
    phrases = texts.TASK_DONE_LATE if now > task.deadline else texts.TASK_DONE
    await edit_or_send(callback.message, f"✅ <s>{escape(task.title)}</s>\n\n{texts.pick(phrases)}")
    await callback.answer()


@router.callback_query(TaskCb.filter(F.action == "snooze"))
async def snooze_task(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    now = clock.now()
    if callback_data.value == "tomorrow":
        local = now.astimezone(user.tz)
        wake = parse_hhmm(user.digest_time)
        until = datetime.combine(local.date() + timedelta(days=1), wake, tzinfo=user.tz) + timedelta(hours=1)
    else:
        until = now + timedelta(hours=int(callback_data.value.rstrip("h")))
    start, end = user.quiet
    until = push_out_of_quiet(until, user.tz, start, end)
    streak = task.snooze_streak + 1
    await db.update_task(task.id, next_remind_at=until, snooze_streak=streak)
    phrases = texts.SNOOZED_AGAIN if streak >= 3 else texts.SNOOZED
    reply = texts.pick(phrases, until=date_time(until.astimezone(user.tz)), count=streak)
    await edit_or_send(callback.message, f"{callback.message.html_text}\n\n⏰ {reply}")
    await callback.answer()


@router.callback_query(TaskCb.filter(F.action == "move"))
async def ask_move(callback: CallbackQuery, callback_data: TaskCb, state: FSMContext, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    await state.clear()
    await state.set_state(EditDeadline.waiting)
    await state.update_data(task_id=task.id)
    await callback.message.answer(
        f"«{escape(task.title)}». {texts.ASK_NEW_DEADLINE}", reply_markup=keyboards.choose_deadline()
    )
    await callback.answer()


async def move_deadline(message: Message, state: FSMContext, db: Database, user: User, deadline: datetime, now: datetime) -> None:
    task_id = (await state.get_data()).get("task_id")
    await state.clear()
    task = await db.get_task(user.id, task_id) if task_id else None
    if task is None or task.status == DONE:
        await message.answer(texts.TASK_NOT_FOUND)
        return
    count = task.postpone_count + 1
    await db.update_task(
        task.id,
        deadline=deadline,
        postpone_count=count,
        overdue_reminders=0,
        snooze_streak=0,
        next_remind_at=schedule(user, deadline, task.importance, now),
    )
    await message.answer(
        texts.pick(texts.DEADLINE_MOVED, deadline=date_time(deadline.astimezone(user.tz)), count=count)
    )


@router.callback_query(TaskCb.filter(F.action == "delete"))
async def ask_delete(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    text = texts.CONFIRM_DELETE.format(title=escape(task.title))
    await edit_or_send(callback.message, text, keyboards.confirm_delete(task.id))
    await callback.answer()


@router.callback_query(TaskCb.filter(F.action == "delete_yes"))
async def delete_task(callback: CallbackQuery, callback_data: TaskCb, db: Database, user: User) -> None:
    task = await load_task(callback, callback_data, db, user)
    if task is None:
        return
    await db.delete_task(user.id, task.id)
    await edit_or_send(callback.message, f"🗑 <s>{escape(task.title)}</s>\n\n{texts.pick(texts.TASK_DELETED)}")
    await callback.answer()

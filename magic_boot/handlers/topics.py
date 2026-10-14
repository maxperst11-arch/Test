"""Разделы и темы: просмотр, добавление, переименование, удаление."""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from magic_boot import keyboards, texts
from magic_boot.callbacks import TopicCb
from magic_boot.db import Database, User
from magic_boot.handlers.common import edit_or_send
from magic_boot.states import TopicInput
from magic_boot.timefmt import plural

router = Router()

MAX_NAME = 40


async def show_topics(message: Message, db: Database, user: User, edit: bool = False) -> None:
    markup = keyboards.topics_menu(await db.list_topics(user.id))
    if edit:
        await edit_or_send(message, texts.TOPICS_HEADER, markup)
    else:
        await message.answer(texts.TOPICS_HEADER, reply_markup=markup)


async def load_topic(callback: CallbackQuery, callback_data: TopicCb, db: Database, user: User):
    topic = await db.get_topic(user.id, callback_data.topic_id)
    if topic is None:
        await callback.answer(texts.UNKNOWN_CALLBACK, show_alert=True)
    return topic


@router.callback_query(TopicCb.filter(F.action == "list"))
async def list_topics(callback: CallbackQuery, state: FSMContext, db: Database, user: User) -> None:
    await state.clear()
    await show_topics(callback.message, db, user, edit=True)
    await callback.answer()


@router.callback_query(TopicCb.filter(F.action == "open"))
async def open_topic(callback: CallbackQuery, callback_data: TopicCb, db: Database, user: User) -> None:
    topic = await load_topic(callback, callback_data, db, user)
    if topic is None:
        return
    count = await db.count_topic_tasks(user.id, topic.id)
    icon = "·" if topic.parent_id else "📁"
    text = f"{icon} <b>{escape(topic.name)}</b>\nЗадач в работе: {count}"
    await edit_or_send(callback.message, text, keyboards.topic_card(topic))
    await callback.answer()


@router.callback_query(TopicCb.filter(F.action == "add_section"))
async def add_section(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopicInput.name)
    await state.set_data({"parent_id": None})
    await callback.message.answer(texts.ASK_SECTION_NAME)
    await callback.answer()


@router.callback_query(TopicCb.filter(F.action == "add_sub"))
async def add_subtopic(callback: CallbackQuery, callback_data: TopicCb, state: FSMContext, db: Database, user: User) -> None:
    parent = await load_topic(callback, callback_data, db, user)
    if parent is None:
        return
    await state.set_state(TopicInput.name)
    await state.set_data({"parent_id": parent.id})
    await callback.message.answer(texts.ASK_SUBTOPIC_NAME.format(parent=escape(parent.name)))
    await callback.answer()


@router.message(TopicInput.name, F.text)
async def got_topic_name(message: Message, state: FSMContext, db: Database, user: User) -> None:
    name = message.text.strip()
    if not name or len(name) > MAX_NAME:
        await message.answer(texts.TOPIC_NAME_TOO_LONG)
        return
    parent_id = (await state.get_data()).get("parent_id")
    await state.clear()
    if parent_id and await db.get_topic(user.id, parent_id) is None:
        parent_id = None
    await db.add_topic(user.id, name, parent_id)
    await message.answer(texts.TOPIC_CREATED.format(name=escape(name)))
    await show_topics(message, db, user)


@router.callback_query(TopicCb.filter(F.action == "rename"))
async def ask_rename(callback: CallbackQuery, callback_data: TopicCb, state: FSMContext, db: Database, user: User) -> None:
    topic = await load_topic(callback, callback_data, db, user)
    if topic is None:
        return
    await state.set_state(TopicInput.rename)
    await state.set_data({"topic_id": topic.id})
    await callback.message.answer(texts.ASK_RENAME.format(name=escape(topic.name)))
    await callback.answer()


@router.message(TopicInput.rename, F.text)
async def got_rename(message: Message, state: FSMContext, db: Database, user: User) -> None:
    name = message.text.strip()
    if not name or len(name) > MAX_NAME:
        await message.answer(texts.TOPIC_NAME_TOO_LONG)
        return
    topic_id = (await state.get_data()).get("topic_id")
    await state.clear()
    if topic_id and await db.get_topic(user.id, topic_id):
        await db.rename_topic(topic_id, name)
        await message.answer(texts.TOPIC_RENAMED.format(name=escape(name)))
    await show_topics(message, db, user)


@router.callback_query(TopicCb.filter(F.action == "delete"))
async def ask_delete(callback: CallbackQuery, callback_data: TopicCb, db: Database, user: User) -> None:
    topic = await load_topic(callback, callback_data, db, user)
    if topic is None:
        return
    count = await db.count_topic_tasks(user.id, topic.id)
    if count:
        text = texts.TOPIC_DELETE_MOVE.format(
            name=escape(topic.name), count=count, tasks_word=plural(count, "задача", "задачи", "задач")
        )
        markup = keyboards.topic_move_targets(topic, await db.list_topics(user.id))
    else:
        text = texts.TOPIC_CONFIRM_DELETE.format(name=escape(topic.name))
        markup = keyboards.topic_confirm_delete(topic)
    await edit_or_send(callback.message, text, markup)
    await callback.answer()


@router.callback_query(TopicCb.filter(F.action == "move_to"))
async def delete_topic(callback: CallbackQuery, callback_data: TopicCb, db: Database, user: User) -> None:
    topic = await load_topic(callback, callback_data, db, user)
    if topic is None:
        return
    target = callback_data.value or None
    if target is not None:
        target_topic = await db.get_topic(user.id, target)
        if target_topic is None or target_topic.parent_id == topic.id:
            target = None
    await db.delete_topic(user.id, topic.id, target)
    await callback.answer(texts.TOPIC_DELETED.format(name=topic.name))
    await show_topics(callback.message, db, user, edit=True)

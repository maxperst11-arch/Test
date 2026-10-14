"""/start, /help, /cancel и кнопки главного меню. Работают из любого состояния."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from magic_boot import texts
from magic_boot.db import Database, User
from magic_boot.handlers import settings, stats, tasks, topics
from magic_boot.keyboards import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, is_new_user: bool) -> None:
    await state.clear()
    phrases = texts.GREETING if is_new_user else texts.GREETING_BACK
    await message.answer(texts.pick(phrases), reply_markup=main_menu())


@router.message(Command("help"))
@router.message(F.text == texts.MENU_HELP)
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.HELP, reply_markup=main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.pick(texts.CANCELLED), reply_markup=main_menu())


@router.message(Command("new"))
@router.message(F.text == texts.MENU_NEW_TASK)
async def menu_new_task(message: Message, state: FSMContext) -> None:
    await tasks.start_new_task(message, state)


@router.message(Command("tasks"))
@router.message(F.text == texts.MENU_TASKS)
async def menu_tasks(message: Message, state: FSMContext, db: Database, user: User) -> None:
    await state.clear()
    await tasks.show_tasks(message, db, user)


@router.message(F.text == texts.MENU_BURNING)
async def menu_burning(message: Message, state: FSMContext, db: Database, user: User) -> None:
    await state.clear()
    await tasks.show_burning(message, db, user)


@router.message(F.text == texts.MENU_TOPICS)
async def menu_topics(message: Message, state: FSMContext, db: Database, user: User) -> None:
    await state.clear()
    await topics.show_topics(message, db, user)


@router.message(F.text == texts.MENU_SHAME)
async def menu_shame(message: Message, state: FSMContext, db: Database, user: User) -> None:
    await state.clear()
    await stats.show_shame(message, db, user)


@router.message(F.text == texts.MENU_SETTINGS)
async def menu_settings(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await settings.show_settings(message, user)

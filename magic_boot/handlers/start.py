from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from magic_boot import texts
from magic_boot.keyboards import main_menu

router = Router()

MENU_BUTTONS = {
    texts.MENU_TASKS,
    texts.MENU_BURNING,
    texts.MENU_NEW_TASK,
    texts.MENU_TOPICS,
    texts.MENU_SHAME,
    texts.MENU_SETTINGS,
    texts.MENU_HELP,
}


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(texts.pick(texts.GREETING), reply_markup=main_menu())


# Заглушка, пока разделы меню не реализованы.
@router.message(F.text.in_(MENU_BUTTONS))
async def menu_stub(message: Message) -> None:
    await message.answer(texts.pick(texts.STUB))

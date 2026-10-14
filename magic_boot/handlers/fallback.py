"""То, что не поймали остальные обработчики."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from magic_boot import keyboards, texts

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def offer_task(message: Message, state: FSMContext) -> None:
    """Любой текст вне диалогов — кандидат в задачи."""
    await state.clear()
    await state.set_data({"quick_title": message.text.strip()})
    await message.answer(texts.QUICK_TASK_OFFER, reply_markup=keyboards.quick_task_offer())


@router.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer(texts.UNKNOWN_CALLBACK, show_alert=True)

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def edit_or_send(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Редактирует сообщение бота, а если нельзя — отправляет новое."""
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            await message.answer(text, reply_markup=markup)

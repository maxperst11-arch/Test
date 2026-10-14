from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from magic_boot import texts


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [texts.MENU_TASKS, texts.MENU_BURNING],
        [texts.MENU_NEW_TASK, texts.MENU_TOPICS],
        [texts.MENU_SHAME, texts.MENU_SETTINGS],
        [texts.MENU_HELP],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
    )

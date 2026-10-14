"""Настройки: тихие часы, время сводки, часовой пояс, уровень злости, вечерний отчёт."""

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from magic_boot import keyboards, texts
from magic_boot.callbacks import SettingsCb
from magic_boot.db import Database, User
from magic_boot.handlers.common import edit_or_send
from magic_boot.states import SettingsInput

router = Router()

HHMM = re.compile(r"([01]?\d|2[0-3])[:.]([0-5]\d)")


def normalize_time(text: str) -> str | None:
    match = HHMM.fullmatch(text.strip())
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def settings_text(user: User) -> str:
    return texts.SETTINGS.format(
        quiet_start=user.quiet_start,
        quiet_end=user.quiet_end,
        digest_time=user.digest_time,
        timezone=user.timezone,
        anger=texts.ANGER_LABELS[user.anger],
        evening="вкл" if user.evening_digest else "выкл",
    )


async def show_settings(message: Message, user: User, edit: bool = False) -> None:
    markup = keyboards.settings(user.evening_digest)
    if edit:
        await edit_or_send(message, settings_text(user), markup)
    else:
        await message.answer(settings_text(user), reply_markup=markup)


async def update_and_show(message: Message, db: Database, user: User, edit: bool, **fields) -> None:
    await db.update_user(user.id, **fields)
    await show_settings(message, await db.get_user(user.id), edit=edit)


@router.callback_query(SettingsCb.filter(F.action == "quiet"))
async def ask_quiet(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsInput.quiet)
    await callback.message.answer(texts.ASK_QUIET)
    await callback.answer()


@router.message(SettingsInput.quiet, F.text)
async def got_quiet(message: Message, state: FSMContext, db: Database, user: User) -> None:
    parts = re.split(r"\s*[-–—]\s*|\s+до\s+|\s+", message.text.strip().lower().removeprefix("с "))
    times = [normalize_time(part) for part in parts if part]
    if len(times) != 2 or None in times:
        await message.answer(texts.ASK_QUIET)
        return
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)
    await update_and_show(message, db, user, edit=False, quiet_start=times[0], quiet_end=times[1])


@router.callback_query(SettingsCb.filter(F.action == "digest"))
async def ask_digest(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsInput.digest_time)
    await callback.message.answer(texts.ASK_DIGEST_TIME)
    await callback.answer()


@router.message(SettingsInput.digest_time, F.text)
async def got_digest(message: Message, state: FSMContext, db: Database, user: User) -> None:
    value = normalize_time(message.text)
    if value is None:
        await message.answer(texts.BAD_TIME)
        return
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)
    await update_and_show(message, db, user, edit=False, digest_time=value)


@router.callback_query(SettingsCb.filter(F.action == "tz"))
async def ask_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsInput.timezone)
    await callback.message.answer(texts.ASK_TIMEZONE, reply_markup=keyboards.timezones())
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "tz_set"))
async def set_timezone(callback: CallbackQuery, callback_data: SettingsCb, state: FSMContext, db: Database, user: User) -> None:
    if callback_data.value not in keyboards.TIMEZONES:
        await callback.answer(texts.UNKNOWN_CALLBACK, show_alert=True)
        return
    await state.clear()
    await update_and_show(callback.message, db, user, edit=True, timezone=callback_data.value)
    await callback.answer(texts.SETTINGS_SAVED)


@router.message(SettingsInput.timezone, F.text)
async def got_timezone(message: Message, state: FSMContext, db: Database, user: User) -> None:
    name = message.text.strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        await message.answer(texts.BAD_TIMEZONE)
        return
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)
    await update_and_show(message, db, user, edit=False, timezone=name)


@router.callback_query(SettingsCb.filter(F.action == "anger"))
async def cycle_anger(callback: CallbackQuery, db: Database, user: User) -> None:
    anger = (user.anger + 1) % len(texts.ANGER_LABELS)
    await update_and_show(callback.message, db, user, edit=True, anger=anger)
    await callback.answer(f"Уровень злости: {texts.ANGER_LABELS[anger]}")


@router.callback_query(SettingsCb.filter(F.action == "evening"))
async def toggle_evening(callback: CallbackQuery, db: Database, user: User) -> None:
    await update_and_show(callback.message, db, user, edit=True, evening_digest=int(not user.evening_digest))
    await callback.answer(texts.SETTINGS_SAVED)

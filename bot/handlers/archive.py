from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.constants import MENU_ARCHIVE
from bot.google.sheets import SheetsService
from bot.keyboards.common import main_menu
from bot.services.access import require_warehouse_message
from bot.services.formatting import archive_card
from bot.services.photos import extract_photo_url
from bot.states.medicine import ArchiveSearch

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == MENU_ARCHIVE)
async def archive_start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_message(message, bot, sheets, settings)
    if not access:
        return

    await state.clear()
    await state.set_state(ArchiveSearch.query)
    await message.answer("Введите часть названия или ID для поиска в архиве.")


@router.message(ArchiveSearch.query, F.text)
async def archive_query(
    message: Message,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_message(message, bot, sheets, settings)
    if not access:
        await state.clear()
        return

    query = message.text.strip()
    if not query:
        await message.answer("Введите хотя бы один символ для поиска.")
        return

    try:
        medicines = await asyncio.to_thread(sheets.search_archive, query)
    except Exception:
        logger.exception("Failed to search archive")
        await message.answer("Не удалось выполнить поиск в архиве.", reply_markup=main_menu())
        return

    await state.clear()
    if not medicines:
        await message.answer("В архиве ничего не найдено.", reply_markup=main_menu())
        return

    await message.answer(f"Найдено в архиве: {len(medicines)}", reply_markup=main_menu())
    for medicine in medicines:
        text = archive_card(medicine)
        photo_url = extract_photo_url(medicine.get("Фото", ""))
        if photo_url:
            text = f"{text}\nФото: {photo_url}"
        await message.answer(text)

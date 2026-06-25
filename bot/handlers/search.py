from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import CONTENT_TYPES, DEFAULT_CATEGORIES, MENU_SEARCH, STORAGE_LOCATIONS
from bot.google.sheets import SheetsService
from bot.keyboards.common import categories_keyboard, content_keyboard, main_menu, search_mode_keyboard, storage_keyboard
from bot.services.access import require_warehouse_callback, require_warehouse_message
from bot.services.formatting import medicine_card
from bot.services.photos import extract_photo_url
from bot.states.medicine import SearchMedicine

router = Router()
logger = logging.getLogger(__name__)


async def send_medicine_card(message: Message, medicine: dict) -> None:
    text = medicine_card(medicine)
    photo_url = extract_photo_url(medicine.get("Фото", ""))
    if photo_url:
        try:
            await message.answer_photo(photo=photo_url, caption=text)
            return
        except TelegramBadRequest:
            pass
        text = f"{text}\nФото: {photo_url}"
    await message.answer(text)


async def _send_results(message: Message, medicines: list[dict]) -> None:
    if not medicines:
        await message.answer("Ничего не найдено.", reply_markup=main_menu())
        return

    await message.answer(f"Найдено позиций: {len(medicines)}", reply_markup=main_menu())
    for medicine in medicines:
        await send_medicine_card(message, medicine)


async def _search_by_option(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
    *,
    field: str,
    options: Sequence[str],
) -> None:
    access = await require_warehouse_callback(callback, bot, sheets, settings)
    if not access:
        return

    try:
        value = options[int(callback.data.split(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer("Значение не найдено.", show_alert=True)
        return

    try:
        medicines = await asyncio.to_thread(sheets.search_medicines_by_field, field, value)
    except Exception:
        logger.exception("Failed to search medicines by %s", field)
        await callback.answer("Ошибка Google Sheets.", show_alert=True)
        return

    await callback.answer()
    await state.clear()
    if callback.message:
        await _send_results(callback.message, medicines)


@router.message(F.text == MENU_SEARCH)
async def search_start(
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
    await state.set_state(SearchMedicine.mode)
    await message.answer("Выберите способ поиска.", reply_markup=search_mode_keyboard())


@router.callback_query(SearchMedicine.mode, F.data == "search_mode:name")
async def search_mode_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchMedicine.query)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Введите часть названия лекарства.")


@router.callback_query(SearchMedicine.mode, F.data == "search_mode:category")
async def search_mode_category(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите категорию.", reply_markup=categories_keyboard("search_category"))


@router.callback_query(SearchMedicine.mode, F.data == "search_mode:content")
async def search_mode_content(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите содержимое.", reply_markup=content_keyboard("search_content"))


@router.callback_query(SearchMedicine.mode, F.data == "search_mode:storage")
async def search_mode_storage(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите место хранения.", reply_markup=storage_keyboard("search_storage"))


@router.message(SearchMedicine.query, F.text)
async def search_query(
    message: Message,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_message(message, bot, sheets, settings)
    if not access:
        return
    query = message.text.strip()
    if not query:
        await message.answer("Введите хотя бы один символ для поиска.")
        return

    try:
        medicines = await asyncio.to_thread(sheets.search_medicines, query)
    except Exception:
        logger.exception("Failed to search medicines")
        await message.answer("Не удалось выполнить поиск в Google Sheets.")
        return

    await state.clear()
    await _send_results(message, medicines)


@router.callback_query(F.data.startswith("search_category:"))
async def search_by_category(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    await _search_by_option(
        callback,
        state,
        bot,
        sheets,
        settings,
        field="Категория",
        options=DEFAULT_CATEGORIES,
    )


@router.callback_query(F.data.startswith("search_content:"))
async def search_by_content(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    await _search_by_option(
        callback,
        state,
        bot,
        sheets,
        settings,
        field="Содержимое",
        options=CONTENT_TYPES,
    )


@router.callback_query(F.data.startswith("search_storage:"))
async def search_by_storage(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    await _search_by_option(
        callback,
        state,
        bot,
        sheets,
        settings,
        field="Место хранения",
        options=STORAGE_LOCATIONS,
    )

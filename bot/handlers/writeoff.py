from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import MENU_WRITE_OFF, WRITE_OFF_REASON_USED
from bot.google.sheets import SheetsService
from bot.keyboards.common import main_menu, writeoff_confirm_keyboard, writeoff_select_keyboard
from bot.services.access import require_warehouse_callback, require_warehouse_message
from bot.services.formatting import medicine_card
from bot.services.photos import extract_photo_url
from bot.states.medicine import WriteOffMedicine

router = Router()
logger = logging.getLogger(__name__)


async def _send_card(message: Message, medicine: dict) -> None:
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


async def _show_confirm(message: Message, medicine: dict) -> None:
    await _send_card(message, medicine)
    await message.answer(
        "Списать это лекарство?",
        reply_markup=writeoff_confirm_keyboard(int(medicine["_row_number"])),
    )


@router.message(F.text == MENU_WRITE_OFF)
async def writeoff_start(
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
    await state.set_state(WriteOffMedicine.query)
    await message.answer("Введите название или часть названия лекарства.")


@router.message(WriteOffMedicine.query, F.text)
async def writeoff_query(
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
        logger.exception("Failed to search medicines for writeoff")
        await message.answer("Не удалось выполнить поиск в Google Sheets.", reply_markup=main_menu())
        return

    if not medicines:
        await state.clear()
        await message.answer("Ничего не найдено.", reply_markup=main_menu())
        return

    await state.set_state(WriteOffMedicine.confirm)
    if len(medicines) == 1:
        await _show_confirm(message, medicines[0])
        return

    await message.answer(
        "Найдено несколько лекарств. Выберите нужное.",
        reply_markup=writeoff_select_keyboard(medicines),
    )


@router.callback_query(WriteOffMedicine.confirm, F.data.startswith("writeoff_select:"))
async def writeoff_select(
    callback: CallbackQuery,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_callback(callback, bot, sheets, settings)
    if not access:
        return

    try:
        row_number = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Строка не найдена.", show_alert=True)
        return

    medicine = await asyncio.to_thread(sheets.get_medicine_by_row_number, row_number)
    if not medicine:
        await callback.answer("Лекарство уже не найдено.", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await _show_confirm(callback.message, medicine)


@router.callback_query(WriteOffMedicine.confirm, F.data.startswith("writeoff_confirm:"))
async def writeoff_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_callback(callback, bot, sheets, settings)
    if not access:
        return

    try:
        row_number = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Строка не найдена.", show_alert=True)
        return

    try:
        await asyncio.to_thread(
            sheets.archive_by_row_number,
            row_number,
            written_off_by=access.label,
            written_off_by_id=callback.from_user.id,
            reason=WRITE_OFF_REASON_USED,
            action="Списано",
        )
    except Exception:
        logger.exception("Failed to write off medicine")
        await callback.answer("Ошибка Google Sheets.", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer("Лекарство перенесено в архив.", reply_markup=main_menu())


@router.callback_query(F.data == "writeoff_cancel")
async def writeoff_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.answer("Списание отменено.", reply_markup=main_menu())

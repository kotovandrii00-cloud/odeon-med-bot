from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import MENU_SEARCH, STATUS_ACTIVE, STATUS_NO_STOCK
from bot.google.sheets import SheetsService
from bot.keyboards.common import confirm_keyboard, main_menu, medicine_actions
from bot.services.access import require_active_callback, require_active_message
from bot.services.formatting import medicine_card
from bot.services.parsing import format_decimal, parse_positive_decimal, table_decimal
from bot.states.medicine import SearchMedicine, UseMedicine

router = Router()
logger = logging.getLogger(__name__)


async def _send_medicine_card(message: Message, medicine: dict, *, can_delete: bool) -> None:
    text = medicine_card(medicine)
    markup = medicine_actions(medicine.get("ID", ""), can_delete=can_delete)
    photo_url = medicine.get("Фото", "")
    if photo_url:
        try:
            await message.answer_photo(photo=photo_url, caption=text, reply_markup=markup)
            return
        except TelegramBadRequest:
            pass
    if photo_url:
        text = f"{text}\nФото: {photo_url}"
    await message.answer(text, reply_markup=markup)


@router.message(F.text == MENU_SEARCH)
async def search_start(
    message: Message,
    state: FSMContext,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_message(message, sheets, settings)
    if not access:
        return
    await state.clear()
    await state.set_state(SearchMedicine.query)
    await message.answer("Введите часть названия или ID лекарства.")


@router.message(SearchMedicine.query, F.text)
async def search_query(
    message: Message,
    state: FSMContext,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_message(message, sheets, settings)
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
    if not medicines:
        await message.answer("Ничего не найдено.", reply_markup=main_menu())
        return

    await message.answer(f"Найдено позиций: {len(medicines)}", reply_markup=main_menu())
    for medicine in medicines:
        await _send_medicine_card(message, medicine, can_delete=access.is_admin)


@router.callback_query(F.data.startswith("use:"))
async def use_start(
    callback: CallbackQuery,
    state: FSMContext,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_callback(callback, sheets, settings)
    if not access:
        return
    medicine_id = callback.data.split(":", 1)[1]
    medicine = await asyncio.to_thread(sheets.get_medicine_by_id, medicine_id)
    if not medicine:
        await callback.answer("Лекарство уже не найдено.", show_alert=True)
        return

    await state.set_state(UseMedicine.quantity)
    await state.update_data(medicine_id=medicine_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Сколько использовали?\nТекущий остаток: {medicine.get('Остаток', '')} {medicine.get('Единица', '')}"
        )


@router.message(UseMedicine.quantity, F.text)
async def use_quantity(
    message: Message,
    state: FSMContext,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_message(message, sheets, settings)
    if not access:
        return

    try:
        used = parse_positive_decimal(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    medicine_id = data.get("medicine_id")
    medicine = await asyncio.to_thread(sheets.get_medicine_by_id, medicine_id)
    if not medicine:
        await state.clear()
        await message.answer("Лекарство уже не найдено.", reply_markup=main_menu())
        return

    current = table_decimal(medicine.get("Остаток", "0"))
    new_remainder = current - used
    used_text = format_decimal(used)
    if new_remainder > 0:
        remainder_text = format_decimal(new_remainder)
        try:
            await asyncio.to_thread(
                sheets.update_remainder,
                medicine_id,
                remainder_text,
                STATUS_ACTIVE,
                access.label,
                used_text,
                "Использовано",
            )
        except Exception:
            logger.exception("Failed to update remainder")
            await message.answer("Не удалось обновить остаток в Google Sheets.")
            return
        await state.clear()
        await message.answer(f"Остаток обновлён: {remainder_text}", reply_markup=main_menu())
        return

    await state.set_state(UseMedicine.confirm_archive)
    await state.update_data(used_quantity=used_text)
    await message.answer(
        "Остаток закончился. Перенести в архив?",
        reply_markup=confirm_keyboard("stock_archive", medicine_id),
    )


@router.callback_query(UseMedicine.confirm_archive, F.data.startswith("stock_archive:"))
async def use_confirm_archive(
    callback: CallbackQuery,
    state: FSMContext,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_callback(callback, sheets, settings)
    if not access:
        return
    _, answer, medicine_id = callback.data.split(":", 2)
    data = await state.get_data()
    used_quantity = data.get("used_quantity", "")

    try:
        if answer == "yes":
            await asyncio.to_thread(
                sheets.archive_by_id,
                medicine_id,
                reason="Использовано полностью",
                user_label=access.label,
                action="Использовано и перенесено в архив",
                quantity=used_quantity,
                remainder_override="0",
                status_override=STATUS_NO_STOCK,
            )
            text = "Лекарство перенесено в архив."
        else:
            await asyncio.to_thread(
                sheets.update_remainder,
                medicine_id,
                "0",
                STATUS_NO_STOCK,
                access.label,
                used_quantity,
                "Остаток закончился",
            )
            text = "Лекарство оставлено в активном списке со статусом «Нет остатка»."
    except Exception:
        logger.exception("Failed to finalize stock use")
        await callback.answer("Ошибка Google Sheets.", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer(text, reply_markup=main_menu())


@router.callback_query(F.data.startswith("delete:"))
async def delete_start(
    callback: CallbackQuery,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_callback(callback, sheets, settings)
    if not access:
        return
    if not access.is_admin:
        await callback.answer("Удалять/списывать может только администратор.", show_alert=True)
        return

    medicine_id = callback.data.split(":", 1)[1]
    medicine = await asyncio.to_thread(sheets.get_medicine_by_id, medicine_id)
    if not medicine:
        await callback.answer("Лекарство уже не найдено.", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Вы точно хотите удалить/списать это лекарство?",
            reply_markup=confirm_keyboard("delete_confirm", medicine_id),
        )


@router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_confirm(
    callback: CallbackQuery,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_callback(callback, sheets, settings)
    if not access:
        return
    if not access.is_admin:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    _, answer, medicine_id = callback.data.split(":", 2)
    if answer != "yes":
        await callback.answer("Отменено")
        if callback.message:
            await callback.message.answer("Списание отменено.", reply_markup=main_menu())
        return

    try:
        await asyncio.to_thread(
            sheets.archive_by_id,
            medicine_id,
            reason="Списано вручную",
            user_label=access.label,
            action="Списано вручную",
        )
    except Exception:
        logger.exception("Failed to archive medicine manually")
        await callback.answer("Ошибка Google Sheets.", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await callback.message.answer("Лекарство перенесено в архив.", reply_markup=main_menu())


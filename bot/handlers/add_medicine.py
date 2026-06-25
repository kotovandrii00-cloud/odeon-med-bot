from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import MENU_ADD, SKIP_TEXT, UNITS
from bot.google.drive import DriveService
from bot.google.sheets import SheetsService
from bot.keyboards.common import cancel_keyboard, categories_keyboard, main_menu, skip_keyboard, units_keyboard
from bot.services.access import require_warehouse_callback, require_warehouse_message
from bot.services.parsing import (
    format_decimal,
    parse_non_negative_decimal,
    parse_positive_decimal,
    parse_ru_date,
)
from bot.states.medicine import AddMedicine

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == MENU_ADD)
async def add_start(
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
    await state.set_state(AddMedicine.photo)
    await message.answer("Загрузите фото упаковки.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.photo, F.photo)
async def add_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    drive: DriveService,
    settings: Settings,
) -> None:
    buffer = BytesIO()
    await bot.download(message.photo[-1].file_id, destination=buffer)
    content = buffer.getvalue()
    timestamp = datetime.now(settings.tzinfo)
    filename = f"medicine_{timestamp:%Y-%m-%d_%H-%M-%S}_{message.from_user.id}.jpg"

    try:
        uploaded = await asyncio.to_thread(drive.upload_photo, content, filename, "image/jpeg", timestamp)
    except Exception:
        logger.exception("Failed to upload photo to Google Drive")
        await message.answer(
            "Не удалось сохранить фото в Google Drive. Проверьте папку, OAuth-переменные Google Drive и доступы."
        )
        return

    await state.update_data(photo_id=uploaded.file_id, photo_url=uploaded.url, photo_cell=uploaded.sheet_value)
    await state.set_state(AddMedicine.name)
    await message.answer("Введите название лекарства.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.photo)
async def add_photo_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото упаковки.")


@router.message(AddMedicine.name, F.text)
async def add_name(
    message: Message,
    state: FSMContext,
    sheets: SheetsService,
) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return

    try:
        categories = await asyncio.to_thread(sheets.get_categories)
    except Exception:
        logger.exception("Failed to load categories")
        await message.answer("Не удалось загрузить категории из Google Sheets.")
        return

    await state.update_data(name=name)
    await state.set_state(AddMedicine.category)
    await message.answer("Выберите категорию.", reply_markup=categories_keyboard(categories))


@router.callback_query(AddMedicine.category, F.data.startswith("category:"))
async def add_category(
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
        category_index = int(callback.data.split(":", 1)[1])
        categories = await asyncio.to_thread(sheets.get_categories)
        category = categories[category_index]
    except Exception:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    await state.update_data(category=category)
    await state.set_state(AddMedicine.manufacturer)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Введите производителя или нажмите «Пропустить».", reply_markup=skip_keyboard())


@router.message(AddMedicine.manufacturer, F.text)
async def add_manufacturer(message: Message, state: FSMContext) -> None:
    manufacturer = "" if message.text == SKIP_TEXT else message.text.strip()
    await state.update_data(manufacturer=manufacturer)
    await state.set_state(AddMedicine.series)
    await message.answer("Введите серию/партию или нажмите «Пропустить».", reply_markup=skip_keyboard())


@router.message(AddMedicine.series, F.text)
async def add_series(message: Message, state: FSMContext) -> None:
    series = "" if message.text == SKIP_TEXT else message.text.strip()
    await state.update_data(series=series)
    await state.set_state(AddMedicine.expiration_date)
    await message.answer("Введите срок годности в формате ДД.ММ.ГГГГ.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.expiration_date, F.text)
async def add_expiration_date(message: Message, state: FSMContext) -> None:
    try:
        expiration = parse_ru_date(message.text)
    except ValueError:
        await message.answer("Дата должна быть в формате ДД.ММ.ГГГГ, например 31.12.2026.")
        return

    await state.update_data(expiration_date=expiration.strftime("%d.%m.%Y"))
    await state.set_state(AddMedicine.initial_quantity)
    await message.answer("Введите начальное количество.")


@router.message(AddMedicine.initial_quantity, F.text)
async def add_initial_quantity(message: Message, state: FSMContext) -> None:
    try:
        quantity = parse_positive_decimal(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(initial_quantity=format_decimal(quantity))
    await state.set_state(AddMedicine.unit)
    await message.answer("Выберите единицу измерения.", reply_markup=units_keyboard())


@router.callback_query(AddMedicine.unit, F.data.startswith("unit:"))
async def add_unit(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        unit_index = int(callback.data.split(":", 1)[1])
        unit = UNITS[unit_index]
    except Exception:
        await callback.answer("Единица не найдена.", show_alert=True)
        return

    await state.update_data(unit=unit)
    await state.set_state(AddMedicine.min_quantity)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Введите минимальный остаток.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.min_quantity, F.text)
async def add_min_quantity(message: Message, state: FSMContext) -> None:
    try:
        minimum = parse_non_negative_decimal(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(min_quantity=format_decimal(minimum))
    await state.set_state(AddMedicine.storage)
    await message.answer("Введите место хранения.")


@router.message(AddMedicine.storage, F.text)
async def add_storage(
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

    storage = message.text.strip()
    if not storage:
        await message.answer("Место хранения не может быть пустым.")
        return

    data = await state.get_data()
    data["storage"] = storage

    try:
        medicine_id = await asyncio.to_thread(sheets.add_medicine, data, access.label)
    except Exception:
        logger.exception("Failed to add medicine")
        await message.answer("Не удалось сохранить лекарство в Google Sheets. Проверьте доступ к таблице.")
        return

    await state.clear()
    await message.answer(f"Лекарство сохранено. ID: {medicine_id}", reply_markup=main_menu())

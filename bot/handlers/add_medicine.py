from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import CONTENT_TYPES, DEFAULT_CATEGORIES, MENU_ADD, STORAGE_LOCATIONS
from bot.google.drive import DriveService
from bot.google.sheets import SheetsService
from bot.keyboards.common import cancel_keyboard, categories_keyboard, content_keyboard, main_menu, storage_keyboard
from bot.services.access import require_warehouse_callback, require_warehouse_message
from bot.services.parsing import format_decimal, parse_positive_decimal, parse_ru_date
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
    await message.answer("Загрузите фото лекарства.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.photo, F.photo)
async def add_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
) -> None:
    buffer = BytesIO()
    await bot.download(message.photo[-1].file_id, destination=buffer)
    content = buffer.getvalue()
    if not content:
        await message.answer("Фото пустое, попробуйте отправить ещё раз.")
        return

    timestamp = datetime.now(settings.tzinfo)
    filename = f"medicine_{timestamp:%Y-%m-%d_%H-%M-%S}_{message.from_user.id}.jpg"
    await state.update_data(photo_content=content, photo_filename=filename, photo_timestamp=timestamp)
    await state.set_state(AddMedicine.name)
    await message.answer("Введите название лекарства.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.photo)
async def add_photo_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото лекарства.")


@router.message(AddMedicine.name, F.text)
async def add_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return

    await state.update_data(name=name)
    await state.set_state(AddMedicine.category)
    await message.answer("Выберите категорию.", reply_markup=categories_keyboard())


@router.callback_query(AddMedicine.category, F.data.startswith("add_category:"))
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
        category = DEFAULT_CATEGORIES[int(callback.data.split(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    await state.update_data(category=category)
    await state.set_state(AddMedicine.content)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Выберите содержимое.", reply_markup=content_keyboard())


@router.message(AddMedicine.category)
async def add_category_invalid(message: Message) -> None:
    await message.answer("Выберите категорию кнопкой.")


@router.callback_query(AddMedicine.content, F.data.startswith("add_content:"))
async def add_content(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        content = CONTENT_TYPES[int(callback.data.split(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer("Содержимое не найдено.", show_alert=True)
        return

    await state.update_data(content=content)
    await state.set_state(AddMedicine.expiration_date)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Введите срок годности в формате ДД.ММ.ГГГГ.", reply_markup=cancel_keyboard())


@router.message(AddMedicine.content)
async def add_content_invalid(message: Message) -> None:
    await message.answer("Выберите содержимое кнопкой.")


@router.message(AddMedicine.expiration_date, F.text)
async def add_expiration_date(message: Message, state: FSMContext) -> None:
    try:
        expiration = parse_ru_date(message.text)
    except ValueError:
        await message.answer("Дата должна быть в формате ДД.ММ.ГГГГ, например 31.12.2026.")
        return

    await state.update_data(expiration_date=expiration.strftime("%d.%m.%Y"))
    await state.set_state(AddMedicine.quantity)
    await message.answer("Введите количество.")


@router.message(AddMedicine.quantity, F.text)
async def add_quantity(message: Message, state: FSMContext) -> None:
    try:
        quantity = parse_positive_decimal(message.text)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(quantity=format_decimal(quantity))
    await state.set_state(AddMedicine.storage)
    await message.answer("Выберите место хранения.", reply_markup=storage_keyboard())


@router.callback_query(AddMedicine.storage, F.data.startswith("add_storage:"))
async def add_storage(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    drive: DriveService,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_warehouse_callback(callback, bot, sheets, settings)
    if not access:
        await state.clear()
        return

    try:
        storage = STORAGE_LOCATIONS[int(callback.data.split(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer("Место хранения не найдено.", show_alert=True)
        return

    data = await state.get_data()
    data["storage"] = storage
    await callback.answer()

    try:
        uploaded = await asyncio.to_thread(
            drive.upload_photo,
            data["photo_content"],
            data["photo_filename"],
            "image/jpeg",
            data["photo_timestamp"],
        )
        data["photo_id"] = uploaded.file_id
        data["photo_url"] = uploaded.url
        data["photo_cell"] = uploaded.sheet_value
        medicine_id = await asyncio.to_thread(
            sheets.add_medicine,
            data,
            access.label,
            callback.from_user.id,
        )
    except Exception:
        logger.exception("Failed to add medicine")
        if callback.message:
            await callback.message.answer(
                "Не удалось сохранить лекарство или фото. Проверьте Google Drive, таблицу и переменные Railway."
            )
        return

    await state.clear()
    if callback.message:
        await callback.message.answer(f"Лекарство сохранено. ID: {medicine_id}", reply_markup=main_menu())


@router.message(AddMedicine.storage)
async def add_storage_invalid(message: Message) -> None:
    await message.answer("Выберите место хранения кнопкой.")

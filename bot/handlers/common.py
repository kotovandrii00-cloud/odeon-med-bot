from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.constants import CANCEL_TEXT, MENU_PROFILE
from bot.google.sheets import SheetsService
from bot.keyboards.common import main_menu
from bot.services.access import require_active_message

router = Router()


@router.message(CommandStart())
async def start(message: Message, sheets: SheetsService, settings: Settings) -> None:
    access = await require_active_message(message, sheets, settings)
    if not access:
        return
    await message.answer(
        "Бот учёта лекарств готов. Выберите действие в меню.",
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_TEXT)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.callback_query(F.data == "flow:cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.answer("Действие отменено.", reply_markup=main_menu())


@router.callback_query(F.data == "card:cancel")
async def cancel_card(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")


@router.message(F.text == MENU_PROFILE)
async def profile(message: Message, sheets: SheetsService, settings: Settings) -> None:
    access = await require_active_message(message, sheets, settings)
    if not access:
        return
    user = access.user
    await message.answer(
        "\n".join(
            [
                "Ваш профиль:",
                f"Telegram ID: {user.get('Telegram ID', '')}",
                f"Имя: {user.get('Имя', '')}",
                f"Роль: {user.get('Роль', '')}",
                f"Активен: {user.get('Активен', '')}",
            ]
        ),
        reply_markup=main_menu(),
    )


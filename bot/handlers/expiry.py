from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from bot.config import Settings
from bot.constants import MENU_EXPIRY
from bot.google.sheets import SheetsService
from bot.keyboards.common import main_menu
from bot.services.access import require_active_message
from bot.services.formatting import expiry_report

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == MENU_EXPIRY)
async def check_expiry(
    message: Message,
    sheets: SheetsService,
    settings: Settings,
) -> None:
    access = await require_active_message(message, sheets, settings)
    if not access:
        return

    try:
        result = await asyncio.to_thread(
            sheets.check_expirations,
            user_label=access.label,
            archive_expired=True,
        )
    except Exception:
        logger.exception("Failed to check expiration dates")
        await message.answer("Не удалось проверить сроки в Google Sheets.", reply_markup=main_menu())
        return

    await message.answer(expiry_report(result), reply_markup=main_menu())


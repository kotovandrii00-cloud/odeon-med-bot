from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message, User

from bot.config import Settings
from bot.constants import ROLE_ADMIN
from bot.google.sheets import SheetsService
from bot.services.formatting import user_label


@dataclass(frozen=True)
class Access:
    user: dict[str, Any]
    label: str

    @property
    def is_active(self) -> bool:
        return str(self.user.get("Активен", "")).casefold() in {"да", "yes", "true", "1"}

    @property
    def is_admin(self) -> bool:
        return self.user.get("Роль") == ROLE_ADMIN


def _display_name(user: User | None) -> str:
    if not user:
        return "Unknown"
    if user.full_name:
        return user.full_name
    return user.username or str(user.id)


async def get_access(user: User | None, sheets: SheetsService, settings: Settings) -> Access | None:
    if user is None:
        return None
    name = _display_name(user)
    sheet_user = await asyncio.to_thread(sheets.get_or_create_user, user.id, name)
    return Access(user=sheet_user, label=user_label(user.id, name))


async def require_active_message(message: Message, sheets: SheetsService, settings: Settings) -> Access | None:
    access = await get_access(message.from_user, sheets, settings)
    if access is None:
        await message.answer("Не удалось определить пользователя Telegram.")
        return None
    if not access.is_active:
        await message.answer("Ваш профиль отключён. Обратитесь к администратору.")
        return None
    return access


def _chat_member_status_value(status: Any) -> str:
    return getattr(status, "value", str(status))


async def is_warehouse_member(bot: Bot, user_id: int, settings: Settings) -> bool:
    try:
        member = await bot.get_chat_member(settings.telegram_group_id, user_id)
    except TelegramAPIError:
        return False

    status = _chat_member_status_value(member.status)
    if status in {"creator", "administrator", "member"}:
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


async def require_warehouse_message(
    message: Message,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> Access | None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        await message.answer("Не удалось определить пользователя Telegram.")
        return None

    if not await is_warehouse_member(bot, user_id, settings):
        await message.answer(
            f"Доступ к складу есть только у участников Telegram-группы {settings.telegram_group_id}."
        )
        return None

    return await require_active_message(message, sheets, settings)


async def require_active_callback(
    callback: CallbackQuery,
    sheets: SheetsService,
    settings: Settings,
) -> Access | None:
    access = await get_access(callback.from_user, sheets, settings)
    if access is None:
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return None
    if not access.is_active:
        await callback.answer("Ваш профиль отключён.", show_alert=True)
        return None
    return access


async def require_warehouse_callback(
    callback: CallbackQuery,
    bot: Bot,
    sheets: SheetsService,
    settings: Settings,
) -> Access | None:
    if not await is_warehouse_member(bot, callback.from_user.id, settings):
        await callback.answer(
            f"Доступ только для участников группы {settings.telegram_group_id}.",
            show_alert=True,
        )
        return None

    return await require_active_callback(callback, sheets, settings)

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.constants import (
    CANCEL_TEXT,
    MENU_ADD,
    MENU_ARCHIVE,
    MENU_EXPIRY,
    MENU_PROFILE,
    MENU_SEARCH,
    SKIP_TEXT,
    UNITS,
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_ADD), KeyboardButton(text=MENU_SEARCH)],
            [KeyboardButton(text=MENU_EXPIRY), KeyboardButton(text=MENU_ARCHIVE)],
            [KeyboardButton(text=MENU_PROFILE)],
        ],
        resize_keyboard=True,
    )


def skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SKIP_TEXT)], [KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
    )


def categories_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, category in enumerate(categories):
        rows.append([InlineKeyboardButton(text=category, callback_data=f"category:{index}")])
    rows.append([InlineKeyboardButton(text=CANCEL_TEXT, callback_data="flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def units_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=unit, callback_data=f"unit:{index}")]
        for index, unit in enumerate(UNITS)
    ]
    rows.append([InlineKeyboardButton(text=CANCEL_TEXT, callback_data="flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def medicine_actions(medicine_id: str, *, can_delete: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="➖ Использовали", callback_data=f"use:{medicine_id}")]]
    if can_delete:
        rows.append([InlineKeyboardButton(text="🗑 Удалить / Списать", callback_data=f"delete:{medicine_id}")])
    rows.append([InlineKeyboardButton(text=CANCEL_TEXT, callback_data="card:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(prefix: str, medicine_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"{prefix}:yes:{medicine_id}"),
                InlineKeyboardButton(text="Нет", callback_data=f"{prefix}:no:{medicine_id}"),
            ]
        ]
    )


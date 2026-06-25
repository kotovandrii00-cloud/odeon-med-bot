from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.constants import (
    CANCEL_TEXT,
    CONTENT_TYPES,
    DEFAULT_CATEGORIES,
    MENU_ADD,
    MENU_ARCHIVE,
    MENU_EXPIRY,
    MENU_PROFILE,
    MENU_SEARCH,
    MENU_WRITE_OFF,
    STORAGE_LOCATIONS,
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_ADD), KeyboardButton(text=MENU_SEARCH)],
            [KeyboardButton(text=MENU_WRITE_OFF), KeyboardButton(text=MENU_EXPIRY)],
            [KeyboardButton(text=MENU_ARCHIVE), KeyboardButton(text=MENU_PROFILE)],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
    )


def options_keyboard(options: Sequence[str], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, option in enumerate(options):
        rows.append([InlineKeyboardButton(text=option, callback_data=f"{prefix}:{index}")])
    rows.append([InlineKeyboardButton(text=CANCEL_TEXT, callback_data="flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_keyboard(prefix: str = "add_category") -> InlineKeyboardMarkup:
    return options_keyboard(DEFAULT_CATEGORIES, prefix)


def content_keyboard(prefix: str = "add_content") -> InlineKeyboardMarkup:
    return options_keyboard(CONTENT_TYPES, prefix)


def storage_keyboard(prefix: str = "add_storage") -> InlineKeyboardMarkup:
    return options_keyboard(STORAGE_LOCATIONS, prefix)


def search_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="По названию", callback_data="search_mode:name")],
            [InlineKeyboardButton(text="По категории", callback_data="search_mode:category")],
            [InlineKeyboardButton(text="По содержимому", callback_data="search_mode:content")],
            [InlineKeyboardButton(text="По месту хранения", callback_data="search_mode:storage")],
            [InlineKeyboardButton(text=CANCEL_TEXT, callback_data="flow:cancel")],
        ]
    )


def writeoff_select_keyboard(medicines: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for medicine in medicines:
        row_number = medicine.get("_row_number")
        text = (
            f"{medicine.get('Название', '')} | "
            f"{medicine.get('Срок годности', '')} | "
            f"{medicine.get('Место хранения', '')}"
        )
        rows.append([InlineKeyboardButton(text=text[:64], callback_data=f"writeoff_select:{row_number}")])
    rows.append([InlineKeyboardButton(text=CANCEL_TEXT, callback_data="writeoff_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def writeoff_confirm_keyboard(row_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, списать", callback_data=f"writeoff_confirm:{row_number}")],
            [InlineKeyboardButton(text=CANCEL_TEXT, callback_data="writeoff_cancel")],
        ]
    )

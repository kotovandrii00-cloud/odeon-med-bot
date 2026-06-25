import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, date, time
from typing import Any, Dict, List, Optional

import gspread
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from zoneinfo import ZoneInfo

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")
NOTIFY_DAYS = int(os.getenv("NOTIFY_DAYS", "90"))
DAILY_CHECK_HOUR = int(os.getenv("DAILY_CHECK_HOUR", "9"))
DAILY_CHECK_MINUTE = int(os.getenv("DAILY_CHECK_MINUTE", "0"))

MEDS_SHEET = "Лекарства"
CATEGORIES_SHEET = "Категории"
ARCHIVE_SHEET = "Архив"

HEADERS = [
    "ID",
    "Фото file_id",
    "Название",
    "Категория",
    "Срок годности",
    "Количество",
    "Место",
    "Группа",
    "Статус",
    "Добавил",
    "Дата добавления",
]

ARCHIVE_HEADERS = HEADERS + ["Дата списания", "Кто списал"]
DEFAULT_CATEGORIES = ['Аллергия', 'Жкт', 'Мази,кремы', 'Мази, кремы', 'Кашель', 'Успокоительные', 'Сердце', 'Давление', 'Нос', 'Уши', 'Глаза', 'Простуда', 'Антибиотик', 'Обезболивающие', 'Обезболивающие, жаропонижающие', 'Обезболивающие, жаропонижающие, противосполительное', 'Горло', 'Пластыри', 'Противовирусное', 'Почки', 'Антисептики', 'Сорбенты, пробиотики', 'От парозитов', 'Холодильник', 'Над холодильнтком']
DEFAULT_GROUPS = ["Одеон", "Мадам", "Холодильник", "Другое"]

class AddMedicine(StatesGroup):
    photo = State()
    name = State()
    category = State()
    expiry = State()
    quantity = State()
    place = State()
    group = State()

class SearchMedicine(StatesGroup):
    query = State()

class ArchiveMedicine(StatesGroup):
    confirm = State()

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


def get_gspread_client():
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is empty")
    info = json.loads(GOOGLE_CREDENTIALS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def open_sheet():
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is empty")
    return get_gspread_client().open_by_key(GOOGLE_SHEET_ID)


def get_or_create_worksheet(sh, title: str, headers: List[str]):
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(12, len(headers)))
        ws.append_row(headers)
        return ws

    first_row = ws.row_values(1)
    if first_row != headers:
        if not first_row:
            ws.append_row(headers)
        else:
            ws.update("A1", [headers])
    return ws


def setup_google_sheet():
    sh = open_sheet()
    meds = get_or_create_worksheet(sh, MEDS_SHEET, HEADERS)
    get_or_create_worksheet(sh, ARCHIVE_SHEET, ARCHIVE_HEADERS)
    try:
        cats_ws = sh.worksheet(CATEGORIES_SHEET)
    except gspread.WorksheetNotFound:
        cats_ws = sh.add_worksheet(title=CATEGORIES_SHEET, rows=200, cols=1)
        cats_ws.append_row(["Категория"])
        for c in DEFAULT_CATEGORIES:
            cats_ws.append_row([c])
    return meds


def get_categories() -> List[str]:
    sh = open_sheet()
    try:
        ws = sh.worksheet(CATEGORIES_SHEET)
        values = ws.col_values(1)[1:]
        values = [v.strip() for v in values if v.strip()]
        return values or DEFAULT_CATEGORIES
    except Exception:
        return DEFAULT_CATEGORIES


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить лекарство")],
            [KeyboardButton(text="🔍 Поиск лекарства"), KeyboardButton(text="⚠️ Проверить сроки")],
            [KeyboardButton(text="📦 Архив / списание"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def inline_from_list(prefix: str, items: List[str], columns: int = 2) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(items), columns):
        rows.append([
            InlineKeyboardButton(text=item[:40], callback_data=f"{prefix}:{item[:50]}")
            for item in items[i : i + columns]
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_date(value: str) -> Optional[date]:
    value = value.strip().replace("/", ".").replace("-", ".")
    formats = ["%d.%m.%Y", "%d.%m.%y", "%Y.%m.%d"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def days_until(expiry_str: str) -> Optional[int]:
    d = parse_date(expiry_str)
    if not d:
        return None
    return (d - datetime.now(ZoneInfo(TIMEZONE)).date()).days


def status_for(expiry_str: str) -> str:
    days = days_until(expiry_str)
    if days is None:
        return "Неизвестно"
    if days < 0:
        return "❌ Просрочено"
    if days <= NOTIFY_DAYS:
        return "⚠️ Скоро истекает"
    return "✅ Годно"


def get_all_meds() -> List[Dict[str, Any]]:
    ws = setup_google_sheet()
    return ws.get_all_records()


def find_med_row_by_id(medicine_id: str):
    ws = setup_google_sheet()
    values = ws.get_all_values()
    for idx, row in enumerate(values[1:], start=2):
        if row and row[0] == medicine_id:
            return ws, idx, row
    return ws, None, None


def format_med_card(med: Dict[str, Any]) -> str:
    expiry = str(med.get("Срок годности", ""))
    days = days_until(expiry)
    left = "неизвестно" if days is None else f"{days} дней"
    return (
        f"<b>{med.get('Название', '')}</b>\n"
        f"Категория: {med.get('Категория', '')}\n"
        f"Срок годности: {expiry}\n"
        f"Осталось: {left}\n"
        f"Количество: {med.get('Количество', '')}\n"
        f"Место: {med.get('Место', '')}\n"
        f"Группа: {med.get('Группа', '')}\n"
        f"Статус: {status_for(expiry)}"
    )

async def send_med(message_or_chat, med: Dict[str, Any], with_archive_button: bool = False):
    text = format_med_card(med)
    photo_id = str(med.get("Фото file_id", "")).strip()
    med_id = str(med.get("ID", "")).strip()
    markup = None
    if with_archive_button and med_id:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗑 Списать в архив", callback_data=f"archive:{med_id}")
        ]])
    if isinstance(message_or_chat, Message):
        if photo_id:
            await message_or_chat.answer_photo(photo=photo_id, caption=text, reply_markup=markup)
        else:
            await message_or_chat.answer(text, reply_markup=markup)
    else:
        if photo_id:
            await bot.send_photo(chat_id=message_or_chat, photo=photo_id, caption=text, reply_markup=markup)
        else:
            await bot.send_message(chat_id=message_or_chat, text=text, reply_markup=markup)

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    setup_google_sheet()
    await message.answer(
        "Привет. Я бот учёта лекарств.\n\nВыбери действие в меню.",
        reply_markup=main_keyboard(),
    )

@dp.message(F.text == "ℹ️ Помощь")
async def help_msg(message: Message):
    await message.answer(
        "Команды:\n"
        "➕ Добавить лекарство — внести препарат в базу\n"
        "🔍 Поиск лекарства — найти по названию\n"
        "⚠️ Проверить сроки — показать препараты, у которых срок ≤ 90 дней или уже истёк\n"
        "📦 Архив / списание — показать просроченные для списания"
    )

@dp.message(F.text == "➕ Добавить лекарство")
async def add_start(message: Message, state: FSMContext):
    await state.set_state(AddMedicine.photo)
    await message.answer("Загрузи фото упаковки лекарства. Если фото нет — напиши: нет", reply_markup=ReplyKeyboardRemove())

@dp.message(AddMedicine.photo, F.photo)
async def add_photo(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AddMedicine.name)
    await message.answer("Введи название лекарства:")

@dp.message(AddMedicine.photo)
async def add_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id="")
    await state.set_state(AddMedicine.name)
    await message.answer("Введи название лекарства:")

@dp.message(AddMedicine.name)
async def add_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое. Введи ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(AddMedicine.category)
    await message.answer("Выбери категорию:", reply_markup=inline_from_list("cat", get_categories()))

@dp.callback_query(AddMedicine.category, F.data.startswith("cat:"))
async def add_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(AddMedicine.expiry)
    await callback.message.edit_text(f"Категория: {category}\n\nВведи срок годности в формате ДД.ММ.ГГГГ:")
    await callback.answer()

@dp.message(AddMedicine.expiry)
async def add_expiry(message: Message, state: FSMContext):
    expiry_date = parse_date(message.text or "")
    if not expiry_date:
        await message.answer("Не понял дату. Введи так: 12.09.2026")
        return
    await state.update_data(expiry=expiry_date.strftime("%d.%m.%Y"))
    await state.set_state(AddMedicine.quantity)
    await message.answer("Введи количество, например: 2 упаковки или 10 ампул:")

@dp.message(AddMedicine.quantity)
async def add_quantity(message: Message, state: FSMContext):
    await state.update_data(quantity=(message.text or "").strip())
    await state.set_state(AddMedicine.place)
    await message.answer("Введи место хранения, например: шкаф, холодильник, аптечка:")

@dp.message(AddMedicine.place)
async def add_place(message: Message, state: FSMContext):
    await state.update_data(place=(message.text or "").strip())
    await state.set_state(AddMedicine.group)
    await message.answer("Выбери группу:", reply_markup=inline_from_list("grp", DEFAULT_GROUPS, columns=2))

@dp.callback_query(AddMedicine.group, F.data.startswith("grp:"))
async def add_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split(":", 1)[1]
    data = await state.get_data()
    med_id = str(uuid.uuid4())[:8]
    expiry = data["expiry"]
    row = [
        med_id,
        data.get("photo_file_id", ""),
        data.get("name", ""),
        data.get("category", ""),
        expiry,
        data.get("quantity", ""),
        data.get("place", ""),
        group,
        status_for(expiry),
        callback.from_user.full_name or callback.from_user.username or str(callback.from_user.id),
        datetime.now(ZoneInfo(TIMEZONE)).strftime("%d.%m.%Y %H:%M"),
    ]
    ws = setup_google_sheet()
    ws.append_row(row)
    await state.clear()
    await callback.message.edit_text("✅ Лекарство добавлено в базу.")
    await bot.send_message(callback.message.chat.id, "Выбери следующее действие:", reply_markup=main_keyboard())
    await callback.answer()

@dp.message(F.text == "🔍 Поиск лекарства")
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchMedicine.query)
    await message.answer("Введи название или часть названия лекарства:", reply_markup=ReplyKeyboardRemove())

@dp.message(SearchMedicine.query)
async def search_query(message: Message, state: FSMContext):
    q = (message.text or "").strip().lower()
    meds = get_all_meds()
    matches = [m for m in meds if q in str(m.get("Название", "")).lower() and "Списано" not in str(m.get("Статус", ""))]
    if not matches:
        await message.answer("Ничего не найдено.", reply_markup=main_keyboard())
        await state.clear()
        return
    await message.answer(f"Найдено: {len(matches)}")
    for med in matches[:10]:
        await send_med(message, med, with_archive_button=False)
    if len(matches) > 10:
        await message.answer("Показал первые 10 совпадений. Уточни поиск, если нужно.")
    await state.clear()
    await message.answer("Готово.", reply_markup=main_keyboard())

@dp.message(F.text == "⚠️ Проверить сроки")
async def check_expiry_now(message: Message):
    await update_statuses_and_notify(chat_id=message.chat.id, manual=True)

@dp.message(F.text == "📦 Архив / списание")
async def archive_menu(message: Message):
    meds = get_all_meds()
    expired = [m for m in meds if days_until(str(m.get("Срок годности", ""))) is not None and days_until(str(m.get("Срок годности", ""))) < 0]
    if not expired:
        await message.answer("Просроченных лекарств нет.", reply_markup=main_keyboard())
        return
    await message.answer(f"Просроченные лекарства: {len(expired)}")
    for med in expired[:20]:
        await send_med(message, med, with_archive_button=True)

@dp.callback_query(F.data.startswith("archive:"))
async def archive_item(callback: CallbackQuery):
    med_id = callback.data.split(":", 1)[1]
    ws, row_idx, row = find_med_row_by_id(med_id)
    if not row_idx or not row:
        await callback.answer("Не найдено", show_alert=True)
        return
    sh = open_sheet()
    archive_ws = get_or_create_worksheet(sh, ARCHIVE_SHEET, ARCHIVE_HEADERS)
    while len(row) < len(HEADERS):
        row.append("")
    row[8] = "🗑 Списано"
    row += [
        datetime.now(ZoneInfo(TIMEZONE)).strftime("%d.%m.%Y %H:%M"),
        callback.from_user.full_name or callback.from_user.username or str(callback.from_user.id),
    ]
    archive_ws.append_row(row)
    ws.delete_rows(row_idx)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🗑 Лекарство перенесено в архив.", reply_markup=main_keyboard())
    await callback.answer()

async def update_statuses_and_notify(chat_id: Optional[int] = None, manual: bool = False):
    ws = setup_google_sheet()
    records = ws.get_all_records()
    notify_target = chat_id or (int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None)
    soon_or_expired = []

    for i, med in enumerate(records, start=2):
        expiry = str(med.get("Срок годности", ""))
        new_status = status_for(expiry)
        old_status = str(med.get("Статус", ""))
        if new_status != old_status:
            ws.update_cell(i, 9, new_status)
            med["Статус"] = new_status
        d = days_until(expiry)
        if d is not None and d <= NOTIFY_DAYS:
            soon_or_expired.append(med)

    if manual:
        if not soon_or_expired:
            await bot.send_message(notify_target, "✅ Нет лекарств со сроком 90 дней или меньше.", reply_markup=main_keyboard())
            return
        await bot.send_message(notify_target, f"⚠️ Найдено лекарств со сроком ≤ {NOTIFY_DAYS} дней: {len(soon_or_expired)}")
        for med in soon_or_expired[:20]:
            await send_med(notify_target, med, with_archive_button=days_until(str(med.get("Срок годности", ""))) < 0)
        return

    # Daily notification: send only if there is something important.
    if notify_target and soon_or_expired:
        await bot.send_message(notify_target, f"⚠️ Ежедневная проверка: лекарств со сроком ≤ {NOTIFY_DAYS} дней: {len(soon_or_expired)}")
        for med in soon_or_expired[:20]:
            await send_med(notify_target, med, with_archive_button=days_until(str(med.get("Срок годности", ""))) < 0)

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    setup_google_sheet()
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(TIMEZONE))
    scheduler.add_job(update_statuses_and_notify, "cron", hour=DAILY_CHECK_HOUR, minute=DAILY_CHECK_MINUTE)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

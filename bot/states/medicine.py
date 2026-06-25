from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddMedicine(StatesGroup):
    photo = State()
    name = State()
    category = State()
    content = State()
    expiration_date = State()
    quantity = State()
    storage = State()


class SearchMedicine(StatesGroup):
    mode = State()
    query = State()


class WriteOffMedicine(StatesGroup):
    query = State()
    confirm = State()


class ArchiveSearch(StatesGroup):
    query = State()

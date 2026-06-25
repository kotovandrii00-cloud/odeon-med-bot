from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddMedicine(StatesGroup):
    photo = State()
    name = State()
    category = State()
    manufacturer = State()
    series = State()
    expiration_date = State()
    initial_quantity = State()
    unit = State()
    min_quantity = State()
    storage = State()


class SearchMedicine(StatesGroup):
    query = State()


class UseMedicine(StatesGroup):
    quantity = State()
    confirm_archive = State()


class ArchiveSearch(StatesGroup):
    query = State()


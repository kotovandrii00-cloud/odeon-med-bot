from __future__ import annotations

from aiogram import Router

from bot.handlers import add_medicine, archive, common, expiry, search, writeoff


def get_routers() -> list[Router]:
    return [
        common.router,
        add_medicine.router,
        search.router,
        writeoff.router,
        expiry.router,
        archive.router,
    ]

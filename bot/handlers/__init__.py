from __future__ import annotations

from aiogram import Router

from bot.handlers import add_medicine, archive, common, expiry, search


def get_routers() -> list[Router]:
    return [
        common.router,
        add_medicine.router,
        search.router,
        expiry.router,
        archive.router,
    ]


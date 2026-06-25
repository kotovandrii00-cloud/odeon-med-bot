from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from bot.config import Settings
from bot.google.drive import DriveService
from bot.google.sheets import SheetsService
from bot.handlers import get_routers
from bot.scheduler.jobs import setup_scheduler


async def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = Settings.from_env(require_bot_token=True, require_drive_folder=True)
        sheets = SheetsService(settings)
        drive = DriveService(settings)
        await asyncio.to_thread(sheets.ensure_structure)
    except Exception as exc:
        logging.exception("Startup failed")
        raise SystemExit(f"Бот не запущен: {exc}") from exc

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(settings=settings, sheets=sheets, drive=drive)
    for router in get_routers():
        dispatcher.include_router(router)

    scheduler = setup_scheduler(bot, sheets, settings)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())


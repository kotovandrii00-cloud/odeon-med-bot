from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Settings
from bot.google.sheets import SheetsService
from bot.services.formatting import expiry_report

logger = logging.getLogger(__name__)


async def _send_group_notification(bot: Bot, settings: Settings, text: str) -> None:
    try:
        await bot.send_message(settings.telegram_group_id, text)
    except Exception:
        logger.exception("Failed to send scheduled notification to group %s", settings.telegram_group_id)


async def daily_expiry_check(bot: Bot, sheets: SheetsService, settings: Settings) -> None:
    try:
        result = await asyncio.to_thread(
            sheets.check_expirations,
            user_label="system",
            archive_expired=True,
        )
    except Exception:
        logger.exception("Scheduled expiration check failed")
        await _send_group_notification(
            bot,
            settings,
            "Ежедневная проверка сроков не выполнена: ошибка Google Sheets.",
        )
        return

    if not result.expired and not result.expiring and not result.invalid_dates:
        return

    text = expiry_report(result, scheduled=True)
    await _send_group_notification(bot, settings, text)


def setup_scheduler(bot: Bot, sheets: SheetsService, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tzinfo)
    scheduler.add_job(
        daily_expiry_check,
        trigger=CronTrigger(hour=8, minute=0, timezone=settings.tzinfo),
        id="daily_expiry_check",
        replace_existing=True,
        kwargs={"bot": bot, "sheets": sheets, "settings": settings},
    )
    scheduler.start()
    return scheduler

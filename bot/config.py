from __future__ import annotations

import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _split_chat_ids(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    parts = re.split(r"[\s,;]+", value.strip())
    ids: list[int] = []
    for part in parts:
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise RuntimeError(f"ADMIN_CHAT_ID содержит неверное значение: {part}") from exc
    return tuple(ids)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    google_sheet_id: str
    google_credentials_json: str
    google_drive_folder_id: str
    admin_chat_ids: tuple[int, ...]
    timezone: str = "Europe/Paris"
    expiry_warning_days: int = 90

    @classmethod
    def from_env(
        cls,
        *,
        require_bot_token: bool = True,
        require_drive_folder: bool = True,
        require_admin_chat: bool = True,
    ) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        admin_chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
        timezone = os.getenv("TIMEZONE", "Europe/Paris").strip() or "Europe/Paris"

        missing: list[str] = []
        if require_bot_token and not bot_token:
            missing.append("BOT_TOKEN")
        if not sheet_id:
            missing.append("GOOGLE_SHEET_ID")
        if not credentials_json:
            missing.append("GOOGLE_CREDENTIALS_JSON")
        if require_drive_folder and not drive_folder_id:
            missing.append("GOOGLE_DRIVE_FOLDER_ID")
        if require_admin_chat and not admin_chat_id:
            missing.append("ADMIN_CHAT_ID")

        if missing:
            raise RuntimeError("Не заданы переменные окружения: " + ", ".join(missing))

        try:
            ZoneInfo(timezone)
        except Exception as exc:  # pragma: no cover - depends on OS tzdata.
            raise RuntimeError(f"Неверный TIMEZONE: {timezone}") from exc

        return cls(
            bot_token=bot_token,
            google_sheet_id=sheet_id,
            google_credentials_json=credentials_json,
            google_drive_folder_id=drive_folder_id,
            admin_chat_ids=_split_chat_ids(admin_chat_id),
            timezone=timezone,
        )

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

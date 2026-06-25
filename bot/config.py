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
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    admin_chat_ids: tuple[int, ...]
    telegram_group_id: int = -5460034736
    timezone: str = "Europe/Paris"
    expiry_warning_days: int = 90

    @classmethod
    def from_env(
        cls,
        *,
        require_bot_token: bool = True,
        require_drive_folder: bool = True,
        require_admin_chat: bool = False,
    ) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        google_refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()
        admin_chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
        telegram_group_id = os.getenv("TELEGRAM_GROUP_ID", "-5460034736").strip()
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

        try:
            parsed_group_id = int(telegram_group_id)
        except ValueError as exc:
            raise RuntimeError(f"TELEGRAM_GROUP_ID содержит неверное значение: {telegram_group_id}") from exc

        return cls(
            bot_token=bot_token,
            google_sheet_id=sheet_id,
            google_credentials_json=credentials_json,
            google_drive_folder_id=drive_folder_id,
            google_client_id=google_client_id,
            google_client_secret=google_client_secret,
            google_refresh_token=google_refresh_token,
            admin_chat_ids=_split_chat_ids(admin_chat_id),
            telegram_group_id=parsed_group_id,
            timezone=timezone,
        )

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def has_drive_oauth(self) -> bool:
        return all([self.google_client_id, self.google_client_secret, self.google_refresh_token])

    @property
    def has_partial_drive_oauth(self) -> bool:
        return any([self.google_client_id, self.google_client_secret, self.google_refresh_token]) and not self.has_drive_oauth

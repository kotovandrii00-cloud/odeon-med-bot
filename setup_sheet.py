from __future__ import annotations

from dotenv import load_dotenv

from bot.config import Settings
from bot.google.sheets import SheetsService


def main() -> None:
    load_dotenv()
    settings = Settings.from_env(
        require_bot_token=False,
        require_drive_folder=False,
        require_admin_chat=False,
    )
    sheets = SheetsService(settings)
    sheets.ensure_structure()
    print("Google Таблица готова: листы, заголовки и категории созданы.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import gspread
from gspread.exceptions import WorksheetNotFound

from bot.config import Settings
from bot.constants import (
    ARCHIVE_HEADERS,
    CATEGORY_HEADERS,
    DATE_FORMAT,
    DEFAULT_CATEGORIES,
    HISTORY_HEADERS,
    MEDICINE_HEADERS,
    ROLE_USER,
    SHEET_ARCHIVE,
    SHEET_CATEGORIES,
    SHEET_HISTORY,
    SHEET_MEDICINES,
    SHEET_USERS,
    STATUS_ACTIVE,
    USER_HEADERS,
)
from bot.google.auth import load_service_account_credentials
from bot.services.parsing import format_decimal, parse_date_or_none, table_decimal


@dataclass(frozen=True)
class ExpiryCheckResult:
    expired: list[dict[str, Any]]
    expiring: list[dict[str, Any]]
    invalid_dates: list[dict[str, Any]]


class SheetsService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        credentials = load_service_account_credentials(settings.google_credentials_json)
        self._client = gspread.authorize(credentials)
        self._spreadsheet = self._client.open_by_key(settings.google_sheet_id)

    def ensure_structure(self) -> None:
        self._ensure_sheet(SHEET_MEDICINES, MEDICINE_HEADERS, rows=500, cols=20)
        self._ensure_sheet(SHEET_CATEGORIES, CATEGORY_HEADERS, rows=50, cols=3)
        self._ensure_sheet(SHEET_HISTORY, HISTORY_HEADERS, rows=1000, cols=12)
        self._ensure_sheet(SHEET_ARCHIVE, ARCHIVE_HEADERS, rows=500, cols=22)
        self._ensure_sheet(SHEET_USERS, USER_HEADERS, rows=100, cols=8)
        self._ensure_default_categories()

    def _ensure_sheet(self, title: str, headers: list[str], *, rows: int, cols: int):
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

        current = worksheet.row_values(1)
        if current != headers:
            worksheet.update(range_name="A1", values=[headers])
        return worksheet

    def _worksheet(self, title: str):
        return self._spreadsheet.worksheet(title)

    def _now(self) -> datetime:
        return datetime.now(self._settings.tzinfo)

    def _today_text(self) -> str:
        return self._now().strftime(DATE_FORMAT)

    def _ensure_default_categories(self) -> None:
        worksheet = self._worksheet(SHEET_CATEGORIES)
        values = worksheet.get_all_values()[1:]
        existing = {row[0].strip() for row in values if row and row[0].strip()}
        missing = [[category] for category in DEFAULT_CATEGORIES if category not in existing]
        if missing:
            worksheet.append_rows(missing, value_input_option="USER_ENTERED")

    @staticmethod
    def _row_to_dict(headers: list[str], row: list[str], row_number: int | None = None) -> dict[str, Any]:
        item = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        if row_number is not None:
            item["_row_number"] = row_number
        return item

    @staticmethod
    def _row_from_dict(headers: list[str], data: dict[str, Any]) -> list[str]:
        return [str(data.get(header, "")) for header in headers]

    @staticmethod
    def _column_letter(index: int) -> str:
        result = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def get_categories(self) -> list[str]:
        worksheet = self._worksheet(SHEET_CATEGORIES)
        rows = worksheet.get_all_values()[1:]
        categories = [row[0].strip() for row in rows if row and row[0].strip()]
        if not categories:
            self._ensure_default_categories()
            categories = DEFAULT_CATEGORIES.copy()
        return categories

    def get_all_medicines(self) -> list[dict[str, Any]]:
        worksheet = self._worksheet(SHEET_MEDICINES)
        rows = worksheet.get_all_values()[1:]
        medicines: list[dict[str, Any]] = []
        for row_number, row in enumerate(rows, start=2):
            if any(cell.strip() for cell in row):
                medicines.append(self._row_to_dict(MEDICINE_HEADERS, row, row_number))
        return medicines

    def get_medicine_by_id(self, medicine_id: str) -> dict[str, Any] | None:
        for medicine in self.get_all_medicines():
            if medicine.get("ID") == medicine_id:
                return medicine
        return None

    def search_medicines(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        return [
            medicine
            for medicine in self.get_all_medicines()
            if needle in medicine.get("Название", "").casefold()
            or needle in medicine.get("ID", "").casefold()
        ]

    def search_archive(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        worksheet = self._worksheet(SHEET_ARCHIVE)
        rows = worksheet.get_all_values()[1:]
        archive: list[dict[str, Any]] = []
        for row_number, row in enumerate(rows, start=2):
            if not any(cell.strip() for cell in row):
                continue
            item = self._row_to_dict(ARCHIVE_HEADERS, row, row_number)
            if needle in item.get("Название", "").casefold() or needle in item.get("ID", "").casefold():
                archive.append(item)
        return archive

    def next_medicine_id(self) -> str:
        max_number = 0
        for medicine in self.get_all_medicines():
            match = re.fullmatch(r"MED-(\d{6})", medicine.get("ID", ""))
            if match:
                max_number = max(max_number, int(match.group(1)))
        return f"MED-{max_number + 1:06d}"

    def add_medicine(self, data: dict[str, Any], user_label: str) -> str:
        medicine_id = self.next_medicine_id()
        today = self._today_text()
        row = [
            medicine_id,
            data.get("photo_cell") or data.get("photo_url", ""),
            data["name"],
            data["category"],
            data.get("manufacturer", ""),
            data.get("series", ""),
            data["expiration_date"],
            data["initial_quantity"],
            data["initial_quantity"],
            data["unit"],
            data["min_quantity"],
            data["storage"],
            STATUS_ACTIVE,
            user_label,
            today,
            today,
        ]
        self._worksheet(SHEET_MEDICINES).append_row(row, value_input_option="USER_ENTERED")
        self.append_history(
            user_label=user_label,
            action="Добавлено",
            medicine_id=medicine_id,
            name=data["name"],
            quantity=data["initial_quantity"],
            remainder=data["initial_quantity"],
            comment="",
        )
        return medicine_id

    def update_remainder(
        self,
        medicine_id: str,
        remainder: str,
        status: str,
        user_label: str,
        quantity: str,
        comment: str,
    ) -> dict[str, Any]:
        medicine = self.get_medicine_by_id(medicine_id)
        if not medicine:
            raise ValueError(f"Лекарство {medicine_id} не найдено")

        row_number = int(medicine["_row_number"])
        worksheet = self._worksheet(SHEET_MEDICINES)
        row = self._row_from_dict(MEDICINE_HEADERS, medicine)
        row[MEDICINE_HEADERS.index("Остаток")] = remainder
        row[MEDICINE_HEADERS.index("Статус")] = status
        row[MEDICINE_HEADERS.index("Последнее изменение")] = self._today_text()
        last_column = self._column_letter(len(MEDICINE_HEADERS))
        worksheet.update(range_name=f"A{row_number}:{last_column}{row_number}", values=[row])
        self.append_history(
            user_label=user_label,
            action="Использовано",
            medicine_id=medicine_id,
            name=medicine.get("Название", ""),
            quantity=quantity,
            remainder=remainder,
            comment=comment,
        )
        medicine["Остаток"] = remainder
        medicine["Статус"] = status
        medicine["Последнее изменение"] = self._today_text()
        return medicine

    def archive_by_id(
        self,
        medicine_id: str,
        *,
        reason: str,
        user_label: str,
        action: str,
        quantity: str = "",
        remainder_override: str | None = None,
        status_override: str | None = None,
    ) -> dict[str, Any]:
        medicine = self.get_medicine_by_id(medicine_id)
        if not medicine:
            raise ValueError(f"Лекарство {medicine_id} не найдено")
        self.archive_medicine(
            medicine,
            reason=reason,
            user_label=user_label,
            action=action,
            quantity=quantity,
            remainder_override=remainder_override,
            status_override=status_override,
        )
        return medicine

    def archive_medicine(
        self,
        medicine: dict[str, Any],
        *,
        reason: str,
        user_label: str,
        action: str,
        quantity: str = "",
        remainder_override: str | None = None,
        status_override: str | None = None,
    ) -> None:
        archived = dict(medicine)
        if remainder_override is not None:
            archived["Остаток"] = remainder_override
        if status_override is not None:
            archived["Статус"] = status_override
        archived["Последнее изменение"] = self._today_text()

        archive_row = self._row_from_dict(MEDICINE_HEADERS, archived)
        archive_row.extend([self._today_text(), reason])
        self._worksheet(SHEET_ARCHIVE).append_row(archive_row, value_input_option="USER_ENTERED")
        self._worksheet(SHEET_MEDICINES).delete_rows(int(medicine["_row_number"]))
        self.append_history(
            user_label=user_label,
            action=action,
            medicine_id=medicine.get("ID", ""),
            name=medicine.get("Название", ""),
            quantity=quantity,
            remainder=str(archived.get("Остаток", "")),
            comment=reason,
        )

    def append_history(
        self,
        *,
        user_label: str,
        action: str,
        medicine_id: str,
        name: str,
        quantity: str,
        remainder: str,
        comment: str,
    ) -> None:
        row = [
            self._today_text(),
            user_label,
            action,
            medicine_id,
            name,
            quantity,
            remainder,
            comment,
        ]
        self._worksheet(SHEET_HISTORY).append_row(row, value_input_option="USER_ENTERED")

    def check_expirations(self, *, user_label: str, archive_expired: bool = True) -> ExpiryCheckResult:
        today = self._now().date()
        expired: list[dict[str, Any]] = []
        expiring: list[dict[str, Any]] = []
        invalid_dates: list[dict[str, Any]] = []

        for medicine in self.get_all_medicines():
            expiration = parse_date_or_none(medicine.get("Срок годности", ""))
            if expiration is None:
                invalid_dates.append(medicine)
                continue
            days_left = (expiration - today).days
            medicine["days_left"] = days_left
            if days_left < 0:
                expired.append(medicine)
            elif days_left <= self._settings.expiry_warning_days:
                expiring.append(medicine)

        if archive_expired:
            for medicine in sorted(expired, key=lambda item: int(item["_row_number"]), reverse=True):
                self.archive_medicine(
                    medicine,
                    reason="Истёк срок годности",
                    user_label=user_label,
                    action="Просрочено и перенесено в архив",
                )

        return ExpiryCheckResult(expired=expired, expiring=expiring, invalid_dates=invalid_dates)

    def get_or_create_user(self, telegram_id: int, name: str) -> dict[str, Any]:
        worksheet = self._worksheet(SHEET_USERS)
        rows = worksheet.get_all_values()[1:]
        for row_number, row in enumerate(rows, start=2):
            if row and row[0].strip() == str(telegram_id):
                user = self._row_to_dict(USER_HEADERS, row, row_number)
                if user.get("Имя") != name:
                    worksheet.update_cell(row_number, USER_HEADERS.index("Имя") + 1, name)
                    user["Имя"] = name
                return user

        user = {
            "Telegram ID": str(telegram_id),
            "Имя": name,
            "Роль": ROLE_USER,
            "Активен": "Да",
        }
        worksheet.append_row(self._row_from_dict(USER_HEADERS, user), value_input_option="USER_ENTERED")
        return user

    def low_stock_medicines(self) -> list[dict[str, Any]]:
        low_stock: list[dict[str, Any]] = []
        for medicine in self.get_all_medicines():
            remainder = table_decimal(medicine.get("Остаток", "0"))
            minimum = table_decimal(medicine.get("Минимальный остаток", "0"))
            if remainder <= minimum:
                medicine["Остаток"] = format_decimal(remainder)
                medicine["Минимальный остаток"] = format_decimal(minimum)
                low_stock.append(medicine)
        return low_stock
